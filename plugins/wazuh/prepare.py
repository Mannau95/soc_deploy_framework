#!/usr/bin/env python3
"""Préparation Wazuh – copie configs, génère certificats, renomme les clés."""

import sys, json, shutil, subprocess
from pathlib import Path

def run(cmd, cwd=None):
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Erreur: {cmd}\n{result.stderr}")
        sys.exit(1)
    return result.stdout.strip()

def main():
    deploy_dir = Path(sys.argv[1])
    variables = json.loads(sys.argv[2])
    plugin_dir = Path(__file__).resolve().parent

    # 1. Copier les configurations
    config_src = plugin_dir / "config"
    if not config_src.exists():
        print("Dossier config/ introuvable.")
        sys.exit(1)
    if (deploy_dir / "config").exists():
        shutil.rmtree(deploy_dir / "config")
    shutil.copytree(config_src, deploy_dir / "config")
    print("Configurations copiées.")

    # 2. Copier le générateur de certificats et config.yml
    for f in ["generate-indexer-certs.yml", "config.yml"]:
        src = plugin_dir / f
        if not src.exists():
            print(f"Fichier {f} introuvable.")
            sys.exit(1)
        shutil.copy(src, deploy_dir / f)

    # 3. Générer les certificats dans le dossier ./certs/
    print("Génération des certificats...")
    run("docker-compose -f generate-indexer-certs.yml run --rm generator", cwd=str(deploy_dir))
    print("Certificats générés.")

    # 4. Renommer les clés privées (le générateur produit .key, les conteneurs attendent -key.pem)
    certs_dir = deploy_dir / "certs"
    renommage = {
        "wazuh-indexer/wazuh-indexer.key": "wazuh-indexer/wazuh-indexer-key.pem",
        "wazuh-manager/wazuh-manager.key": "wazuh-manager/wazuh-manager-key.pem",
        "wazuh-dashboard/wazuh-dashboard.key": "wazuh-dashboard/wazuh-dashboard-key.pem",
    }
    for ancien, nouveau in renommage.items():
        ancien_path = certs_dir / ancien
        nouveau_path = certs_dir / nouveau
        if ancien_path.exists():
            ancien_path.rename(nouveau_path)
            print(f"Renommé {ancien} -> {nouveau}")
        else:
            print(f"Attention : {ancien} introuvable dans {certs_dir}")

if __name__ == "__main__":
    main()