#!/usr/bin/env python3
"""Préparation Suricata – détection automatique de l'interface."""

import sys, json, os, subprocess
from pathlib import Path

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
    return "eth0"

def main():
    deploy_dir = Path(sys.argv[1])
    variables = json.loads(sys.argv[2])

    # 1. Créer le dossier de logs
    log_dir = deploy_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(log_dir, 0o777)
    print("Dossier de logs créé.")

    # 2. Déterminer l'interface à utiliser
    interface = variables.get("interface") or get_default_interface()
    print(f"Interface utilisée : {interface}")

    # 3. Mettre à jour le docker-compose.yml (remplacer eth0 par l'interface réelle)
    compose_file = deploy_dir / "docker-compose.yml"
    if compose_file.exists():
        content = compose_file.read_text()
        # Remplacer la ligne de commande : suricata -i eth0 ... -> suricata -i <interface> ...
        content = content.replace("-i eth0", f"-i {interface}")
        compose_file.write_text(content)
        print(f"Commande mise à jour avec l'interface {interface}")
    else:
        print("Fichier docker-compose.yml introuvable.")

if __name__ == "__main__":
    main()