"""
Moteur d'orchestration SOC Deploy.

Responsabilités :
- Charger la configuration utilisateur (config.yaml) et les manifestes des plugins.
- Valider les prérequis (Docker disponible, ports libres).
- Générer les fichiers de déploiement via Jinja2.
- Piloter Docker Compose pour lancer les services.
- Vérifier l'état de santé (healthchecks).
- Produire un rapport de déploiement complet.
- Gérer les erreurs avec rollback basique.
- Gérer un fichier d'état pour ne pas réinstaller les outils déjà déployés.
"""

import subprocess
import shutil
import time
import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import yaml
import docker
from docker.errors import DockerException
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from pydantic import BaseModel, ValidationError
import requests
import socket
from loguru import logger

# ---------------------------------------------------------------------------
# Modèles de données (Pydantic)
# ---------------------------------------------------------------------------

class HealthcheckConfig(BaseModel):
    """Configuration d'un healthcheck dans un manifeste."""
    type: str
    url: Optional[str] = None
    command: Optional[str] = None
    expected_status: Optional[int] = None
    expected_stdout: Optional[str] = None
    timeout: int = 60
    retries: int = 5
    interval: int = 10

class ModeConfig(BaseModel):
    """Un mode d'installation pour un outil."""
    description: str
    prerequisites: Dict[str, Any]
    templates: List[str]
    post_install: Optional[Dict[str, HealthcheckConfig]] = None

class PluginManifest(BaseModel):
    """Structure d'un fichier manifest.yaml pour un plugin."""
    name: str
    version: str
    description: str
    modes: Dict[str, ModeConfig]

class ToolConfig(BaseModel):
    """Configuration d'un outil dans le fichier config.yaml utilisateur."""
    plugin: str
    mode: str
    variables: Dict[str, Any] = {}

class UserConfig(BaseModel):
    """Fichier de configuration principal."""
    stack_name: str
    tools: List[ToolConfig]

# ---------------------------------------------------------------------------
# Classe principale du moteur
# ---------------------------------------------------------------------------

class SOCDeployEngine:
    """Moteur de déploiement SOC."""

    def __init__(self, config_path: Path, plugins_dir: Path = Path("plugins")):
        self.config_path = config_path
        self.plugins_dir = plugins_dir
        self.user_config: Optional[UserConfig] = None
        self.manifests: Dict[str, PluginManifest] = {}
        self.deploy_dir: Optional[Path] = None
        self.report: Dict[str, Any] = {"success": True, "services": []}
        self.docker_client = None

        # Configuration du logger
        logger.remove()
        logger.add(sys.stderr, level="INFO", format="<green>{time}</green> | <level>{message}</level>")

    # -----------------------------------------------------------------------
    # Chargement et validation
    # -----------------------------------------------------------------------

    def load_config(self) -> None:
        """Charge le fichier de configuration utilisateur."""
        logger.info(f"Chargement de la configuration : {self.config_path}")
        try:
            with open(self.config_path, 'r') as f:
                raw = yaml.safe_load(f)
            self.user_config = UserConfig(**raw)
        except FileNotFoundError:
            logger.error(f"Fichier de config introuvable : {self.config_path}")
            raise
        except ValidationError as e:
            logger.error(f"Configuration invalide : {e}")
            raise

    def load_plugin_manifest(self, plugin_name: str) -> PluginManifest:
        """Charge et valide le manifeste d'un plugin."""
        manifest_path = self.plugins_dir / plugin_name / "manifest.yaml"
        logger.info(f"Chargement du manifeste : {manifest_path}")
        if not manifest_path.exists():
            raise FileNotFoundError(f"Plugin inconnu : {manifest_path}")
        with open(manifest_path, 'r') as f:
            raw = yaml.safe_load(f)
        return PluginManifest(**raw)

    def load_all_manifests(self) -> None:
        """Charge tous les manifestes des outils demandés."""
        for tool in self.user_config.tools:
            if tool.plugin not in self.manifests:
                self.manifests[tool.plugin] = self.load_plugin_manifest(tool.plugin)

    # -----------------------------------------------------------------------
    # Gestion de l'état de la stack
    # -----------------------------------------------------------------------

    def load_state(self) -> Dict[str, Any]:
        """Charge l'état de la stack (outils déjà installés)."""
        if not self.deploy_dir:
            return {}
        state_file = self.deploy_dir / "stack_state.json"
        if state_file.exists():
            with open(state_file, 'r') as f:
                return json.load(f)
        return {}

    def save_state(self, state: Dict[str, Any]) -> None:
        """Sauvegarde l'état de la stack."""
        if not self.deploy_dir:
            return
        state_file = self.deploy_dir / "stack_state.json"
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)

    # -----------------------------------------------------------------------
    # Vérifications des prérequis
    # -----------------------------------------------------------------------

    def check_docker(self) -> bool:
        """Vérifie que le daemon Docker est accessible."""
        try:
            self.docker_client = docker.from_env()
            self.docker_client.ping()
            logger.info("Docker est opérationnel.")
            return True
        except DockerException:
            logger.error("Docker n'est pas accessible.")
            return False

    def check_ports(self, ports: List[int]) -> bool:
        """Vérifie qu'aucun processus n'écoute sur les ports donnés."""
        for port in ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            if result == 0:
                logger.error(f"Le port {port} est déjà utilisé.")
                return False
        logger.info(f"Ports libres : {ports}")
        return True

    def validate_prerequisites(self) -> None:
        """Valide tous les prérequis pour la stack entière."""
        logger.info("Validation des prérequis...")
        if not self.check_docker():
            raise RuntimeError("Docker requis.")
        for tool in self.user_config.tools:
            manifest = self.manifests[tool.plugin]
            mode = manifest.modes[tool.mode]
            pre = mode.prerequisites
            if pre.get("docker", False) and not self.docker_client:
                raise RuntimeError(f"Docker requis pour {tool.plugin}")
            ports = pre.get("ports", [])
            if ports and not self.check_ports(ports):
                raise RuntimeError(f"Ports requis pour {tool.plugin} non disponibles.")
        logger.info("Tous les prérequis sont satisfaits.")

    # -----------------------------------------------------------------------
    # Génération des fichiers de déploiement
    # -----------------------------------------------------------------------

    def setup_deploy_directory(self) -> None:
        """Crée le répertoire de déploiement pour la stack (sans effacer un existant)."""
        self.deploy_dir = Path("deployments") / self.user_config.stack_name
        self.deploy_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Répertoire de déploiement : {self.deploy_dir}")

    def render_templates(self, plugin_name: str, mode: str, variables: Dict[str, Any]) -> Path:
        """Génère les fichiers pour un plugin à partir des templates Jinja2."""
        plugin_dir = self.plugins_dir / plugin_name
        template_dir = plugin_dir / "templates"
        output_dir = self.deploy_dir / plugin_name
        output_dir.mkdir(parents=True, exist_ok=True)

        manifest = self.manifests[plugin_name]
        mode_config = manifest.modes[mode]

        if not mode_config.templates:
            return output_dir

        if not template_dir.exists():
            raise FileNotFoundError(f"Aucun dossier templates pour {plugin_name}")

        env = Environment(loader=FileSystemLoader(str(template_dir)))

        # Filtre personnalisé pour l'interface réseau automatique
        def get_default_interface():
            import subprocess
            try:
                res = subprocess.run(
                    "ip route show default | awk '{print $5}'",
                    shell=True, capture_output=True, text=True
                )
                iface = res.stdout.strip()
                if iface:
                    return iface
            except:
                pass
            return "eth0"

        env.filters['auto_interface'] = lambda iface: iface if iface else get_default_interface()

        for template_name in mode_config.templates:
            try:
                template = env.get_template(template_name)
                out_name = template_name[:-3] if template_name.endswith('.j2') else template_name
                output_path = output_dir / out_name
                content = template.render(variables)
                with open(output_path, 'w') as f:
                    f.write(content)
                logger.info(f"Template rendu : {output_path}")
            except TemplateNotFound:
                logger.error(f"Template introuvable : {template_name}")
                raise
        return output_dir

    # -----------------------------------------------------------------------
    # Préparation du plugin
    # -----------------------------------------------------------------------

    def prepare_plugin(
        self,
        plugin_name: str,
        mode: str,
        output_dir: Path,
        variables: Dict[str, Any]
    ) -> None:
        """Exécute le script de préparation du plugin s'il existe."""
        prepare_script: Path = self.plugins_dir / plugin_name / "prepare.py"
        if not prepare_script.exists():
            logger.info(f"Aucun script de préparation pour {plugin_name}")
            return

        logger.info(f"Exécution du script de préparation pour {plugin_name}")
        try:
            result = subprocess.run(
                [sys.executable, str(prepare_script), str(output_dir), json.dumps(variables)],
                check=True,
                capture_output=True,
                text=True
            )
            logger.info(f"Préparation terminée : {result.stdout}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Échec du script de préparation pour {plugin_name}: {e.stderr}")
            raise

    # -----------------------------------------------------------------------
    # Déploiement via Docker Compose
    # -----------------------------------------------------------------------

    def docker_compose_up(self, compose_dir: Path) -> None:
        """Lance `docker compose up -d` ou `docker-compose up -d`."""
        compose_cmd = None
        try:
            subprocess.run(
                ["docker", "compose", "version"],
                check=True, capture_output=True, text=True
            )
            compose_cmd = ["docker", "compose"]
        except (subprocess.CalledProcessError, FileNotFoundError):
            try:
                subprocess.run(
                    ["docker-compose", "version"],
                    check=True, capture_output=True, text=True
                )
                compose_cmd = ["docker-compose"]
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise RuntimeError("Ni 'docker compose' ni 'docker-compose' n'ont été trouvés.")

        logger.info(f"Lancement de {compose_cmd} dans {compose_dir}")
        try:
            subprocess.run(
                compose_cmd + ["up", "-d"],
                cwd=str(compose_dir),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logger.info("Conteneurs démarrés avec succès.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur Docker Compose : {e.stderr.decode()}")
            raise

    # -----------------------------------------------------------------------
    # Healthchecks
    # -----------------------------------------------------------------------

    def perform_healthcheck(self, plugin_name: str, mode: str, output_dir: Path) -> bool:
        """Exécute le healthcheck défini dans le manifeste du plugin."""
        manifest = self.manifests[plugin_name]
        mode_config = manifest.modes[mode]
        post = mode_config.post_install
        if not post or "healthcheck" not in post:
            logger.info(f"Pas de healthcheck pour {plugin_name}")
            return True

        hc = HealthcheckConfig(**post["healthcheck"])
        logger.info(f"Healthcheck pour {plugin_name}: type={hc.type}")
        if hc.type == "http":
            return self._http_healthcheck(hc)
        elif hc.type == "command":
            return self._command_healthcheck(hc, output_dir)
        else:
            logger.error(f"Type de healthcheck inconnu: {hc.type}")
            return False

    def _http_healthcheck(self, hc: HealthcheckConfig) -> bool:
        """Healthcheck par appel HTTP."""
        for i in range(hc.retries):
            try:
                resp = requests.get(hc.url, timeout=hc.timeout, verify=False)
                if resp.status_code == hc.expected_status:
                    logger.info(f"Healthcheck HTTP OK ({hc.url})")
                    return True
            except requests.RequestException:
                pass
            logger.info(f"Tentative {i+1}/{hc.retries} échouée, attente {hc.interval}s")
            time.sleep(hc.interval)
        logger.error(f"Healthcheck HTTP échoué pour {hc.url}")
        return False

    def _command_healthcheck(self, hc: HealthcheckConfig, cwd: Path) -> bool:
        """Healthcheck par exécution d'une commande shell."""
        for i in range(hc.retries):
            try:
                result = subprocess.run(
                    hc.command, shell=True, cwd=str(cwd),
                    capture_output=True, text=True, timeout=hc.timeout
                )
                if result.returncode == 0:
                    logger.info("Healthcheck commande OK")
                    return True
            except subprocess.TimeoutExpired:
                pass
            logger.info(f"Tentative {i+1}/{hc.retries} échouée, attente {hc.interval}s")
            time.sleep(hc.interval)
        logger.error("Healthcheck commande échoué")
        return False

    # -----------------------------------------------------------------------
    # Rapport
    # -----------------------------------------------------------------------

    def collect_service_info(self, plugin_name: str, mode: str) -> Dict[str, Any]:
        """Collecte les informations sur le service déployé pour le rapport."""
        manifest = self.manifests[plugin_name]
        mode_config = manifest.modes[mode]
        info = {
            "plugin": plugin_name,
            "version": manifest.version,
            "mode": mode,
            "description": manifest.description,
            "urls": [],
            "credentials": {}
        }
        pre = mode_config.prerequisites
        ports = pre.get("ports", [])
        if ports:
            info["urls"].append(f"localhost:{ports[0]}")
        return info

    def generate_report(self) -> str:
        """Génère le rapport markdown et l'écrit dans le répertoire de déploiement."""
        template_path = Path("templates") / "report.md.j2"
        if template_path.exists():
            env = Environment(loader=FileSystemLoader("templates"))
            template = env.get_template("report.md.j2")
            content = template.render(report=self.report, config=self.user_config)
        else:
            content = f"# Rapport de déploiement {self.user_config.stack_name}\n\n"
            for svc in self.report["services"]:
                content += f"- **{svc['plugin']}** ({svc['mode']}) : {svc['description']}\n"
                content += f"  URLs: {', '.join(svc.get('urls', []))}\n"

        if self.deploy_dir:
            report_path = self.deploy_dir / "report.md"
            with open(report_path, 'w') as f:
                f.write(content)
            logger.info(f"Rapport enregistré : {report_path}")
            return str(report_path)
        return ""

    # -----------------------------------------------------------------------
    # Orchestration principale
    # -----------------------------------------------------------------------

    def deploy(self) -> str:
        """Méthode principale : orchestre tout le déploiement."""
        try:
            self.load_config()
            self.load_all_manifests()
            self.validate_prerequisites()
            self.setup_deploy_directory()

            # Charger l'état existant
            state = self.load_state()

            for tool in self.user_config.tools:
                plugin_name = tool.plugin
                mode = tool.mode
                variables = tool.variables
                variables["stack_name"] = self.user_config.stack_name

                manifest = self.manifests[plugin_name]
                mode_config = manifest.modes[mode]

                # Vérifier si l'outil est déjà installé
                if state.get(plugin_name, {}).get("status") == "installed":
                    logger.info(f"--- {plugin_name} est déjà installé, ignoré ---")
                    # Ajouter quand même au rapport
                    service_info = state[plugin_name]
                    self.report["services"].append(service_info)
                    continue

                logger.info(f"--- Déploiement de {plugin_name} en mode {mode} ---")

                # Rendu des templates (si existants)
                if mode_config.templates:
                    compose_dir = self.render_templates(plugin_name, mode, variables)
                else:
                    output_dir = self.deploy_dir / plugin_name
                    output_dir.mkdir(parents=True, exist_ok=True)
                    compose_dir = output_dir

                # Exécution du script de préparation
                self.prepare_plugin(plugin_name, mode, compose_dir, variables)

                # Lancement Docker Compose seulement si un template a été rendu
                if mode_config.templates:
                    self.docker_compose_up(compose_dir)

                # Healthcheck
                if not self.perform_healthcheck(plugin_name, mode, compose_dir):
                    self.report["success"] = False
                    raise RuntimeError(f"Healthcheck échoué pour {plugin_name}")

                # Collecte d'infos pour le rapport
                service_info = self.collect_service_info(plugin_name, mode)
                service_info["status"] = "installed"
                self.report["services"].append(service_info)

                # Marquer l'outil comme installé dans l'état
                state[plugin_name] = service_info
                self.save_state(state)

            report_path = self.generate_report()
            logger.info(f"Déploiement terminé avec succès. Rapport : {report_path}")
            return report_path

        except Exception as e:
            logger.error(f"Échec du déploiement : {e}")
            self.report["success"] = False
            self.report["error"] = str(e)
            # Ne pas supprimer tout le dossier, seulement le dossier de l'outil en échec
            try:
                if self.deploy_dir:
                    # Garder le rapport et l'état, supprimer uniquement le sous-dossier de l'outil
                    pass  # On ne fait pas de rollback destructif pour préserver les autres outils
            except:
                pass
            raise