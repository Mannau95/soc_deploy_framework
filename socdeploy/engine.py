"""Moteur d'orchestration SOC Deploy Framework."""

import sys
import time
import socket
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
import yaml
from jinja2 import Environment, FileSystemLoader
from loguru import logger

from socdeploy.models import (
    UserConfig, PluginManifest, ToolConfig, ServiceState, HealthcheckConfig
)
from socdeploy.catalog import PluginCatalog
from socdeploy.system import system
from socdeploy.state import StateManager
from socdeploy.runners.docker import DockerComposeRunner
from socdeploy.runners.native import NativeRunner
from socdeploy.reporter import DeploymentReporter


class SOCDeployEngine:
    """Moteur principal de déploiement."""

    def __init__(
        self,
        config_path: Path,
        plugins_dir: Path = Path("plugins"),
        deploy_base_dir: Path = Path("deployments")
    ):
        self.config_path = config_path
        self.plugins_dir = plugins_dir
        self.deploy_base_dir = deploy_base_dir
        self.catalog = PluginCatalog(plugins_dir)
        self.user_config: Optional[UserConfig] = None
        self.deploy_dir: Optional[Path] = None
        self.state_mgr: Optional[StateManager] = None
        self.docker_runner: Optional[DockerComposeRunner] = None
        self.native_runner = NativeRunner()
        self.reporter = DeploymentReporter()

    def load_config(self) -> UserConfig:
        """Charge et valide le fichier de configuration utilisateur."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Fichier de configuration introuvable : {self.config_path}")

        logger.info(f"Chargement de la configuration : {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        self.user_config = UserConfig(**raw)
        self.deploy_dir = self.deploy_base_dir / self.user_config.stack_name
        self.state_mgr = StateManager(self.deploy_dir)
        return self.user_config

    def validate_prerequisites(self) -> None:
        """Vérifie que le système respecte les exigences de tous les outils choisis."""
        if not self.user_config:
            raise RuntimeError("La configuration n'est pas chargée.")

        logger.info("Vérification des prérequis système...")

        # 1. Vérification Docker
        needs_docker = any(
            t.method == "docker" or (
                self.catalog.get_plugin(t.plugin) and
                self.catalog.get_plugin(t.plugin).modes.get(t.mode) and
                self.catalog.get_plugin(t.plugin).modes[t.mode].requirements.docker
            )
            for t in self.user_config.tools
        )
        if needs_docker:
            if not system.is_docker_available():
                raise RuntimeError("Docker est requis pour l'un des outils choisis mais n'est pas opérationnel.")
            self.docker_runner = DockerComposeRunner()

        # 2. Vérification root
        needs_root = any(
            self.catalog.get_plugin(t.plugin) and
            self.catalog.get_plugin(t.plugin).modes.get(t.mode) and
            self.catalog.get_plugin(t.plugin).modes[t.mode].requirements.root
            for t in self.user_config.tools
        )
        if needs_root and not system.is_root and system.os_family != "windows":
            logger.warning("Certains outils nécessitent les droits root (ex: iptables, scripts système).")

        # 3. Vérification des ports
        all_ports: List[int] = []
        for t in self.user_config.tools:
            manifest = self.catalog.get_plugin(t.plugin)
            if manifest and t.mode in manifest.modes:
                all_ports.extend(manifest.modes[t.mode].requirements.ports)

        busy_ports = system.check_ports(all_ports)
        if busy_ports:
            raise RuntimeError(f"Les ports suivants sont déjà occupés sur l'hôte : {busy_ports}")

        logger.info("Tous les prérequis sont validés avec succès.")

    def _load_hooks(self, plugin_name: str):
        """Charge dynamiquement le module hooks.py ou prepare.py d'un plugin."""
        hooks_file = self.plugins_dir / plugin_name / "hooks.py"
        if not hooks_file.exists():
            hooks_file = self.plugins_dir / plugin_name / "prepare.py"
            if not hooks_file.exists():
                return None

        spec = importlib.util.spec_from_file_location(f"plugins.{plugin_name}.hooks", hooks_file)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        return None

    def render_templates(self, plugin_name: str, mode: str, output_dir: Path, variables: Dict[str, Any]) -> None:
        """Rendu des fichiers templates Jinja2 (docker-compose, configs)."""
        manifest = self.catalog.get_plugin(plugin_name)
        if not manifest or mode not in manifest.modes:
            return

        mode_config = manifest.modes[mode]
        templates: List[str] = []

        # Récupérer la liste des templates
        if "docker" in mode_config.methods:
            templates = mode_config.methods["docker"].templates
        elif mode_config.templates:
            templates = mode_config.templates

        if not templates:
            return

        templates_dir = self.plugins_dir / plugin_name / "templates"
        if not templates_dir.exists():
            return

        env = Environment(loader=FileSystemLoader(str(templates_dir)))
        env.filters["auto_interface"] = lambda iface: iface if iface else system.get_default_interface()

        ctx = {
            **variables,
            "mode": mode,
            "stack_name": self.user_config.stack_name,
            "interface": variables.get("interface", system.get_default_interface())
        }

        for tmpl_name in templates:
            tmpl = env.get_template(tmpl_name)
            out_name = tmpl_name[:-3] if tmpl_name.endswith(".j2") else tmpl_name
            out_path = output_dir / out_name
            content = tmpl.render(**ctx)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Fichier généré : {out_path}")

    def perform_healthcheck(self, hc: HealthcheckConfig, cwd: Path) -> bool:
        """Exécute la vérification de santé d'un service."""
        logger.info(f"Vérification de santé (type: {hc.type}, retries: {hc.retries})...")

        if hc.type == "http" and hc.url:
            for i in range(hc.retries):
                try:
                    resp = requests.get(hc.url, timeout=hc.timeout, verify=False)
                    if resp.status_code == (hc.expected_status or 200):
                        logger.info(f"Healthcheck HTTP réussi sur {hc.url}")
                        return True
                except Exception:
                    pass
                logger.debug(f"Tentative {i+1}/{hc.retries} en attente de {hc.url}...")
                time.sleep(hc.interval)
            return False

        elif hc.type == "command" and hc.command:
            import subprocess
            for i in range(hc.retries):
                try:
                    res = subprocess.run(
                        hc.command, shell=True, cwd=str(cwd),
                        capture_output=True, text=True, timeout=hc.timeout
                    )
                    if res.returncode == 0:
                        logger.info("Healthcheck commande réussi.")
                        return True
                except Exception:
                    pass
                logger.debug(f"Tentative {i+1}/{hc.retries} en attente de '{hc.command}'...")
                time.sleep(hc.interval)
            return False

        elif hc.type == "tcp" and hc.port:
            for i in range(hc.retries):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2.0)
                    if s.connect_ex(("127.0.0.1", hc.port)) == 0:
                        logger.info(f"Healthcheck TCP réussi sur le port {hc.port}")
                        return True
                time.sleep(hc.interval)
            return False

        return True

    def deploy_tool(self, tool: ToolConfig) -> ServiceState:
        """Déploie un outil individuel."""
        manifest = self.catalog.get_plugin(tool.plugin)
        if not manifest:
            raise ValueError(f"Plugin inconnu : '{tool.plugin}'")

        if tool.mode not in manifest.modes:
            raise ValueError(f"Mode inconnu '{tool.mode}' pour le plugin '{tool.plugin}'")

        mode_config = manifest.modes[tool.mode]
        tool_dir = self.deploy_dir / tool.plugin
        tool_dir.mkdir(parents=True, exist_ok=True)

        hooks = self._load_hooks(tool.plugin)
        hook_ctx = {
            "deploy_dir": tool_dir,
            "variables": tool.variables,
            "mode": tool.mode,
            "method": tool.method,
            "system": system.to_dict(),
        }

        try:
            # 1. Pre-install hook
            if hooks and hasattr(hooks, "pre_install"):
                logger.info(f"[{tool.plugin}] Exécution du hook pre_install...")
                hooks.pre_install(hook_ctx)

            # 2. Exécution selon la méthode
            if tool.method == "docker":
                self.render_templates(tool.plugin, tool.mode, tool_dir, tool.variables)
                if not self.docker_runner:
                    self.docker_runner = DockerComposeRunner()
                self.docker_runner.up(tool_dir)

            elif tool.method == "native":
                if hooks and hasattr(hooks, "install_native"):
                    logger.info(f"[{tool.plugin}] Exécution de install_native...")
                    hooks.install_native(hook_ctx)
                elif hooks and hasattr(hooks, "install"):
                    hooks.install(hook_ctx)

            # 3. Healthcheck
            hc = mode_config.healthcheck
            if hc:
                if not self.perform_healthcheck(hc, tool_dir):
                    raise RuntimeError(f"Échec de la vérification de santé pour {tool.plugin}")

            # 4. Post-install hook
            if hooks and hasattr(hooks, "post_install"):
                logger.info(f"[{tool.plugin}] Exécution du hook post_install...")
                hooks.post_install(hook_ctx)

            # 5. Récupération des identifiants et URLs
            credentials = {}
            if hooks and hasattr(hooks, "credentials"):
                credentials = hooks.credentials(hook_ctx)

            urls: List[str] = []
            if hc and hc.url:
                urls.append(hc.url)
            elif mode_config.requirements.ports:
                urls.append(f"http://localhost:{mode_config.requirements.ports[0]}")

            logs: List[str] = []
            if hasattr(hooks, "logs"):
                logs = hooks.logs(hook_ctx)
            elif (tool_dir / "logs").exists():
                logs = [str(tool_dir / "logs")]

            service_state = ServiceState(
                plugin=tool.plugin,
                mode=tool.mode,
                method=tool.method,
                version=manifest.version,
                description=manifest.description,
                status="installed",
                urls=urls,
                credentials=credentials,
                logs=logs,
                variables=tool.variables
            )

            self.state_mgr.record_installed(service_state)
            return service_state

        except Exception as e:
            logger.error(f"Erreur lors du déploiement de {tool.plugin} : {e}")
            # Rollback ciblé sur cet outil
            if hooks and hasattr(hooks, "uninstall"):
                try:
                    logger.info(f"[{tool.plugin}] Exécution du nettoyage / rollback...")
                    hooks.uninstall(hook_ctx)
                except Exception as clean_err:
                    logger.warning(f"Erreur lors du nettoyage de {tool.plugin} : {clean_err}")

            if tool.method == "docker" and self.docker_runner:
                try:
                    self.docker_runner.down(tool_dir)
                except Exception:
                    pass
            raise

    def deploy(self) -> Path:
        """Exécute le déploiement complet de la configuration."""
        self.load_config()
        self.validate_prerequisites()

        deployed_services: List[ServiceState] = []

        for tool in self.user_config.tools:
            # Vérifier si déjà installé
            if self.state_mgr.is_installed(tool.plugin):
                logger.info(f"L'outil '{tool.plugin}' est déjà installé. Ignoré.")
                deployed_services.append(self.state_mgr.get_service(tool.plugin))
                continue

            logger.info(f"Déploiement de {tool.plugin} (mode: {tool.mode}, méthode: {tool.method})...")
            state = self.deploy_tool(tool)
            deployed_services.append(state)

        # 4. Traitement des interconnexions (chaîne SOC complète)
        integration_results: Dict[str, Any] = {}
        has_wazuh = any(t.plugin == "wazuh" for t in self.user_config.tools)
        has_suricata = any(t.plugin == "suricata" for t in self.user_config.tools)
        has_zeek = any(t.plugin == "zeek" for t in self.user_config.tools)
        has_thehive = any(t.plugin == "thehive" for t in self.user_config.tools)
        has_misp = any(t.plugin == "misp" for t in self.user_config.tools)

        # Suricata -> Wazuh
        if "wazuh_suricata" in self.user_config.integrations or (has_wazuh and has_suricata):
            wazuh_tool = next(t for t in self.user_config.tools if t.plugin == "wazuh")
            logger.info("Configuration de l'interconnexion Suricata -> Wazuh...")
            try:
                from socdeploy.integrations.wazuh_suricata import setup_wazuh_suricata_integration
                res = setup_wazuh_suricata_integration(
                    deploy_dir=self.deploy_dir,
                    wazuh_method=wazuh_tool.method,
                    suricata_dir=self.deploy_dir / "suricata"
                )
                integration_results["wazuh_suricata"] = res
            except Exception as e:
                logger.warning(f"Échec de l'interconnexion Suricata -> Wazuh : {e}")

        # Zeek -> Wazuh
        if "wazuh_zeek" in self.user_config.integrations or (has_wazuh and has_zeek):
            wazuh_tool = next(t for t in self.user_config.tools if t.plugin == "wazuh")
            logger.info("Configuration de l'interconnexion Zeek -> Wazuh...")
            try:
                from socdeploy.integrations.wazuh_zeek import setup_wazuh_zeek_integration
                res = setup_wazuh_zeek_integration(
                    deploy_dir=self.deploy_dir,
                    wazuh_method=wazuh_tool.method,
                    zeek_dir=self.deploy_dir / "zeek"
                )
                integration_results["wazuh_zeek"] = res
            except Exception as e:
                logger.warning(f"Échec de l'interconnexion Zeek -> Wazuh : {e}")

        # Wazuh -> TheHive
        if "wazuh_thehive" in self.user_config.integrations or (has_wazuh and has_thehive):
            wazuh_tool = next(t for t in self.user_config.tools if t.plugin == "wazuh")
            thehive_tool = next(t for t in self.user_config.tools if t.plugin == "thehive")
            thehive_port = thehive_tool.variables.get("http_port", 9000)
            logger.info("Configuration de l'interconnexion Wazuh -> TheHive...")
            try:
                from socdeploy.integrations.wazuh_thehive import setup_wazuh_thehive_integration
                res = setup_wazuh_thehive_integration(
                    deploy_dir=self.deploy_dir,
                    wazuh_method=wazuh_tool.method,
                    thehive_port=thehive_port
                )
                integration_results["wazuh_thehive"] = res
            except Exception as e:
                logger.warning(f"Échec de l'interconnexion Wazuh -> TheHive : {e}")

        # TheHive <-> MISP
        if "thehive_misp" in self.user_config.integrations or (has_thehive and has_misp):
            misp_tool = next(t for t in self.user_config.tools if t.plugin == "misp")
            misp_port = misp_tool.variables.get("https_port", 8443)
            logger.info("Configuration de l'interconnexion TheHive <-> MISP...")
            try:
                from socdeploy.integrations.thehive_misp import setup_thehive_misp_integration
                res = setup_thehive_misp_integration(
                    deploy_dir=self.deploy_dir,
                    misp_url=f"https://localhost:{misp_port}"
                )
                integration_results["thehive_misp"] = res
            except Exception as e:
                logger.warning(f"Échec de l'interconnexion TheHive <-> MISP : {e}")

        # 5. Sauvegarde sécurisée des mots de passe dans secrets.env (chmod 600)
        from socdeploy.utils import save_secrets_env
        all_creds = {s.plugin: s.credentials for s in deployed_services if s.credentials}
        save_secrets_env(self.deploy_dir, all_creds)

        # Génération du rapport
        report_path = self.deploy_dir / "report.md"
        self.reporter.generate_markdown(self.user_config, deployed_services, report_path, integrations=integration_results)
        self.reporter.print_summary(self.user_config, deployed_services, report_path)
        return report_path

    def destroy(self, plugin_name: Optional[str] = None) -> None:
        """Désinstalle un outil ou l'ensemble de la stack."""
        self.load_config()
        state = self.state_mgr.load()

        tools_to_remove = [plugin_name] if plugin_name else list(state.keys())

        for p_name in tools_to_remove:
            if p_name not in state:
                logger.warning(f"L'outil '{p_name}' n'est pas répertorié dans la stack.")
                continue

            svc = state[p_name]
            tool_dir = self.deploy_dir / p_name
            hooks = self._load_hooks(p_name)

            hook_ctx = {
                "deploy_dir": tool_dir,
                "variables": svc.variables,
                "mode": svc.mode,
                "method": svc.method,
                "system": system.to_dict(),
            }

            if hooks and hasattr(hooks, "uninstall"):
                logger.info(f"[{p_name}] Nettoyage spécifique...")
                try:
                    hooks.uninstall(hook_ctx)
                except Exception as e:
                    logger.warning(f"Erreur lors du hook uninstall de {p_name} : {e}")

            if svc.method == "docker":
                if not self.docker_runner:
                    self.docker_runner = DockerComposeRunner()
                self.docker_runner.down(tool_dir, remove_volumes=True)

            self.state_mgr.remove_service(p_name)
            logger.info(f"Outil '{p_name}' désinstallé avec succès.")
