#!/usr/bin/env python3
"""Préparation Wazuh via le script d'installation rapide officiel."""

import sys, json, subprocess, shutil, os
from pathlib import Path

def main():
    deploy_dir = Path(sys.argv[1])
    variables = json.loads(sys.argv[2])
    admin_password = variables.get("admin_password", "Admin123!")

    # --- Créer le dossier de déploiement (évite l'erreur "FileNotFoundError") ---
    deploy_dir.mkdir(parents=True, exist_ok=True)

    # --- Nettoyage préventif de tout ancien agent Wazuh ---
    print("Nettoyage des anciennes installations Wazuh...")
    subprocess.run(["sudo", "rm", "-f", "/var/lib/dpkg/info/wazuh-agent.prerm"], check=False)
    subprocess.run(["sudo", "dpkg", "--purge", "--force-all", "wazuh-agent"], check=False)
    subprocess.run(["sudo", "rm", "-rf", "/var/lib/wazuh-agent", "/etc/wazuh-agent", "/var/log/wazuh-agent"], check=False)
    # --------------------------------------------------------

    plugin_dir = Path(__file__).resolve().parent
    install_script = plugin_dir / "wazuh-install.sh"

    # Copier le script d'installation dans le dossier de déploiement
    shutil.copy(install_script, deploy_dir / "wazuh-install.sh")
    (deploy_dir / "wazuh-install.sh").chmod(0o755)

    print("Lancement de l'installation rapide Wazuh...")
    result = subprocess.run(
        ["sudo", "bash", str(deploy_dir / "wazuh-install.sh"), "--all-in-one", "--overwrite"],
        cwd=str(deploy_dir),
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "WAZUH_PASSWORD": admin_password,
            "KIBANA_PASSWORD": admin_password,
            "WAZUH_ADMIN_PASSWORD": admin_password,
        }
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if result.returncode != 0:
        print("Erreur lors de l'installation.")
        sys.exit(1)

    # Restaurer la propriété du dossier de déploiement pour l'utilisateur courant
    import pwd
    uid = os.getuid()
    user = pwd.getpwuid(uid).pw_name
    subprocess.run(["sudo", "chown", "-R", f"{user}:{user}", str(deploy_dir.parent)])
    print(f"Propriété du dossier de déploiement restaurée pour {user}.")

    print("Installation terminée avec succès.")

if __name__ == "__main__":
    main()