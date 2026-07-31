#!/usr/bin/env python3
"""Préparation Suricata – création des dossiers, copie de la config, mise à jour optionnelle des règles."""

import sys, json, os, shutil, subprocess
from pathlib import Path

def main():
    deploy_dir = Path(sys.argv[1])
    variables = json.loads(sys.argv[2])

    # 1. Copier la configuration Suricata
    config_src = Path(__file__).resolve().parent / "config"
    if config_src.exists():
        dest = deploy_dir / "config"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(config_src, dest)
        print("Configuration Suricata copiée.")

    # 2. Créer le dossier de logs
    log_dir = deploy_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(log_dir, 0o777)
    print("Dossier de logs créé.")

    # 3. Mise à jour des règles si demandé (dans un conteneur éphémère)
    if variables.get("auto_rules", False):
        print("Mise à jour des règles Suricata...")
        subprocess.run(
            ["docker", "run", "--rm",
             "-v", f"{deploy_dir / 'config'}:/etc/suricata:ro",
             "-v", f"{deploy_dir / 'logs'}:/var/log/suricata",
             "jasonish/suricata:latest",
             "suricata-update"],
            check=False
        )
        print("Règles mises à jour.")

if __name__ == "__main__":
    main()