"""Hooks de cycle de vie pour Wazuh."""

import os
import sys
import json
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Dict, Any


def _run_cmd(cmd, cwd=None, check=False, env=None):
    if os.name != "nt" and os.geteuid() != 0 and shutil.which("sudo"):
        cmd = ["sudo"] + cmd
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check, env=env)


def pre_install(ctx: Dict[str, Any]) -> None:
    """Préparation avant installation."""
    deploy_dir = Path(ctx["deploy_dir"])
    deploy_dir.mkdir(parents=True, exist_ok=True)


def install_native(ctx: Dict[str, Any]) -> None:
    """Exécution du script officiel Wazuh all-in-one."""
    deploy_dir = Path(ctx["deploy_dir"])
    variables = ctx.get("variables", {})
    plugin_dir = Path(__file__).resolve().parent
    install_script = plugin_dir / "wazuh-install.sh"

    # Copie dans le dossier de déploiement
    target_script = deploy_dir / "wazuh-install.sh"
    shutil.copy(install_script, target_script)
    if os.name != "nt":
        target_script.chmod(0o755)

    print("Lancement de l'installation rapide Wazuh (veuillez patienter quelques minutes)...")
    cmd = ["bash", "./wazuh-install.sh", "--all-in-one", "--overwrite"]

    env = {**os.environ}
    admin_pw = variables.get("admin_password")
    if admin_pw:
        env["WAZUH_PASSWORD"] = admin_pw
        env["KIBANA_PASSWORD"] = admin_pw
        env["WAZUH_ADMIN_PASSWORD"] = admin_pw

    res = _run_cmd(cmd, cwd=str(deploy_dir), env=env)
    if res.stdout:
        print(res.stdout[-1000:])  # Afficher la fin
    if res.returncode != 0:
        print(f"Erreur wazuh-install.sh : {res.stderr}")
        raise RuntimeError("Échec de l'installation officielle de Wazuh.")


def post_install(ctx: Dict[str, Any]) -> None:
    """Extraction et sauvegarde des identifiants générés."""
    deploy_dir = Path(ctx["deploy_dir"])
    creds_file = deploy_dir / "credentials.json"
    credentials_data = {
        "url": "https://localhost",
        "username": "admin",
        "password": ctx.get("variables", {}).get("admin_password", "Admin123!")
    }

    # Chercher l'archive générée par wazuh-install.sh
    tar_path = deploy_dir / "wazuh-install-files.tar"
    if tar_path.exists():
        try:
            with tarfile.open(tar_path, "r:*") as tar:
                for member in tar.getmembers():
                    if "wazuh-passwords.txt" in member.name:
                        f = tar.extractfile(member)
                        if f:
                            content = f.read().decode("utf-8", errors="ignore")
                            # Parser les mots de passe
                            for line in content.splitlines():
                                if line.startswith("admin:"):
                                    credentials_data["password"] = line.split(":", 1)[1].strip()
                                elif "User:" in line and "admin" in line:
                                    pass
                            credentials_data["full_passwords"] = content
                            break
        except Exception as e:
            print(f"Avertissement : lecture des identifiants Wazuh échouée ({e})")

    with open(creds_file, "w", encoding="utf-8") as f:
        json.dump(credentials_data, f, indent=2)


def uninstall(ctx: Dict[str, Any]) -> None:
    """Désinstallation de Wazuh."""
    method = ctx.get("method", "native")
    if method == "native" and os.name != "nt":
        print("Arrêt des services Wazuh...")
        _run_cmd(["systemctl", "stop", "wazuh-dashboard", "wazuh-manager", "wazuh-indexer"])
        _run_cmd(["systemctl", "disable", "wazuh-dashboard", "wazuh-manager", "wazuh-indexer"])


def credentials(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Retourne les identifiants pour le rapport."""
    deploy_dir = Path(ctx["deploy_dir"])
    creds_file = deploy_dir / "credentials.json"
    if creds_file.exists():
        try:
            with open(creds_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "url": "https://localhost",
        "username": "admin",
        "password": ctx.get("variables", {}).get("admin_password", "(voir wazuh-install-files.tar)")
    }
