"""Hooks de cycle de vie pour Suricata (IDS et IPS)."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader


def _run_cmd(cmd, check=False):
    """Exécute une commande avec sudo si nécessaire sous Linux."""
    if os.name != "nt" and os.geteuid() != 0 and shutil.which("sudo"):
        cmd = ["sudo"] + cmd
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def get_default_interface() -> str:
    """Détecte l'interface réseau active par défaut."""
    try:
        res = subprocess.run(
            "ip route show default | awk '{print $5}'",
            shell=True, capture_output=True, text=True
        )
        iface = res.stdout.strip()
        if iface:
            return iface
    except Exception:
        pass
    return "eth0"


def pre_install(ctx: Dict[str, Any]) -> None:
    """Préparation des configurations, logs et règles avant le démarrage."""
    deploy_dir = Path(ctx["deploy_dir"])
    variables = ctx.get("variables", {})
    mode = ctx.get("mode", "ids")
    plugin_dir = Path(__file__).resolve().parent

    # 1. Dossiers
    config_dir = deploy_dir / "config"
    rules_dir = deploy_dir / "rules"
    log_dir = deploy_dir / "logs"

    config_dir.mkdir(parents=True, exist_ok=True)
    rules_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try:
            os.chmod(log_dir, 0o777)
        except Exception:
            pass

    # 2. Copier suricata.yaml
    shutil.copy(plugin_dir / "config" / "suricata.yaml", config_dir / "suricata.yaml")

    # 3. Générer pass.rules
    env = Environment(loader=FileSystemLoader(str(plugin_dir / "config")))
    pass_tmpl = env.get_template("pass.rules.j2")
    rendered_pass = pass_tmpl.render(
        pass_ssh=variables.get("pass_ssh", True),
        pass_dns=variables.get("pass_dns", True),
    )
    with open(rules_dir / "pass.rules", "w", encoding="utf-8") as f:
        f.write(rendered_pass)

    # 4. S'assurer qu'un fichier suricata.rules existe pour ne pas planter Suricata
    suricata_rules_file = rules_dir / "suricata.rules"
    if not suricata_rules_file.exists():
        suricata_rules_file.write_text(
            '# Règles Suricata minimales par défaut\n'
            'alert icmp any any -> any any (msg:"SURICATA ICMP Ping détecté"; itype:8; sid:2000001; rev:1;)\n',
            encoding="utf-8"
        )

    # 5. Télécharger les règles fraîches (suricata-update) si demandé
    if variables.get("auto_rules", True) and ctx.get("method") == "docker":
        print("Mise à jour des règles de détection via suricata-update...")
        try:
            _run_cmd([
                "docker", "run", "--rm",
                "-v", f"{rules_dir}:/var/lib/suricata/rules",
                "jasonish/suricata:latest",
                "suricata-update", "-o", "/var/lib/suricata/rules"
            ])
            # Si le fichier s'appelle suricata.rules dans /var/lib/suricata/rules
            downloaded = rules_dir / "suricata.rules"
            if not downloaded.exists():
                for alt in rules_dir.glob("*.rules"):
                    if alt.name != "pass.rules":
                        shutil.copy(alt, downloaded)
                        break
        except Exception as e:
            print(f"Avertissement : suricata-update a échoué ({e}), conservation des règles de base.")


def post_install(ctx: Dict[str, Any]) -> None:
    """Actions après le démarrage sain de Suricata."""
    deploy_dir = Path(ctx["deploy_dir"])
    variables = ctx.get("variables", {})
    mode = ctx.get("mode", "ids")

    if mode == "ips" and os.name != "nt":
        iface = variables.get("interface") or get_default_interface()
        print(f"Configuration sécurisée de l'IPS sur l'interface {iface} (NFQUEUE avec bypass)...")

        # Vérifier si la règle existe déjà pour éviter les doublons
        check_input = _run_cmd(["iptables", "-C", "INPUT", "-i", iface, "-j", "NFQUEUE", "--queue-num", "0", "--queue-bypass"])
        if check_input.returncode != 0:
            _run_cmd(["iptables", "-I", "INPUT", "-i", iface, "-j", "NFQUEUE", "--queue-num", "0", "--queue-bypass"])

        check_output = _run_cmd(["iptables", "-C", "OUTPUT", "-o", iface, "-j", "NFQUEUE", "--queue-num", "0", "--queue-bypass"])
        if check_output.returncode != 0:
            _run_cmd(["iptables", "-I", "OUTPUT", "-o", iface, "-j", "NFQUEUE", "--queue-num", "0", "--queue-bypass"])

        # Script de nettoyage garanti
        cleanup_script = deploy_dir / "iptables_cleanup.sh"
        cleanup_script.write_text(
            f"#!/bin/bash\n"
            f"sudo iptables -D INPUT -i {iface} -j NFQUEUE --queue-num 0 --queue-bypass 2>/dev/null || true\n"
            f"sudo iptables -D OUTPUT -o {iface} -j NFQUEUE --queue-num 0 --queue-bypass 2>/dev/null || true\n",
            encoding="utf-8"
        )
        try:
            os.chmod(cleanup_script, 0o755)
        except Exception:
            pass
        print("Règles iptables NFQUEUE actives et script de nettoyage généré.")


def uninstall(ctx: Dict[str, Any]) -> None:
    """Nettoyage complet (règles iptables, etc.)."""
    deploy_dir = Path(ctx["deploy_dir"])
    cleanup_script = deploy_dir / "iptables_cleanup.sh"
    if cleanup_script.exists() and os.name != "nt":
        print("Suppression des règles iptables...")
        subprocess.run(["bash", str(cleanup_script)], check=False)


def credentials(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Retourne les métadonnées et fichiers de logs pour le rapport."""
    deploy_dir = Path(ctx["deploy_dir"])
    return {
        "eve_log": str(deploy_dir / "logs" / "eve.json"),
        "fast_log": str(deploy_dir / "logs" / "fast.log"),
        "mode": ctx.get("mode", "ids"),
    }
