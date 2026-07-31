#!/usr/bin/env python3
"""Préparation Suricata – création des dossiers et copie de la config."""

import sys, json, os, shutil
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

if __name__ == "__main__":
    main()