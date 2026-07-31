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

    # 1. Détection de l'interface (priorité à la variable utilisateur, sinon auto)
    interface = variables.get("interface") or get_default_interface()
    print(f"Interface utilisée : {interface}")

    # 2. Créer le dossier de logs
    log_dir = deploy_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(log_dir, 0o777)
    print("Dossier de logs créé.")

    # 3. Remplacer l'interface dans le docker-compose.yml déjà généré
    compose_file = deploy_dir / "docker-compose.yml"
    if compose_file.exists():
        content = compose_file.read_text()
        content = content.replace("{{ interface }}", interface)
        compose_file.write_text(content)
        print(f"Interface mise à jour dans {compose_file}")
    else:
        print("Fichier docker-compose.yml introuvable.")

if __name__ == "__main__":
    main()