#!/usr/bin/env python3
"""Préparation Suricata – création du dossier de logs et mise à jour optionnelle des règles."""

import sys, json, os, subprocess
from pathlib import Path

def main():
    deploy_dir = Path(sys.argv[1])
    variables = json.loads(sys.argv[2])

    # Créer le dossier de logs
    log_dir = deploy_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(log_dir, 0o777)
    print("Dossier de logs créé.")

    # Mettre à jour les règles si demandé
    if variables.get("auto_rules", False):
        print("Mise à jour des règles Suricata...")
        subprocess.run(
            ["docker", "exec", "suricata", "suricata-update"],
            check=False
        )
        print("Règles mises à jour.")
    else:
        print("Mise à jour des règles ignorée (auto_rules=false).")

if __name__ == "__main__":
    main()