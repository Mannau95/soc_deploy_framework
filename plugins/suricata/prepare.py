#!/usr/bin/env python3
"""Préparation Suricata – création du dossier de logs."""

import sys, json, os
from pathlib import Path

import subprocess

def get_default_interface():
    try:
        result = subprocess.run(
            "ip route show default | awk '{print $5}'",
            shell=True, capture_output=True, text=True
        )
        iface = result.stdout.strip()
        if iface:
            return iface
    except:
        pass
    return "eth0"  # fallback

def main():
    deploy_dir = Path(sys.argv[1])
    variables = json.loads(sys.argv[2])
    interface = variables.get("interface") or get_default_interface()
    variables["interface"] = interface  # on met à jour pour le template

    # Créer le dossier pour les logs Suricata
    log_dir = deploy_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    # Rendre accessible en écriture au conteneur
    os.chmod(log_dir, 0o777)
    print("Dossier de logs créé.")

if __name__ == "__main__":
    main()