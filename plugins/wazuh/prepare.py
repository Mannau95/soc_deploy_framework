#!/usr/bin/env python3
"""Préparation Wazuh – copie configs, génère certificats, renomme les clés."""

import sys, json, shutil, subprocess
from pathlib import Path

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

    # 2. Copier le générateur et certs.yml
    for f in ["generate-indexer-certs.yml", "certs.yml"]:
        src = plugin_dir / f
        if not src.exists():
            print(f"Fichier {f} introuvable.")
            sys.exit(1)
        shutil.copy(src, deploy_dir / f)

    # 3. Créer le dossier local certs/ (sinon le générateur échoue)
    (deploy_dir / "certs").mkdir(exist_ok=True)

    # 4. Générer les certificats (on ignore le code de retour car une erreur non fatale peut s'afficher)
    print("Génération des certificats...")
    result = subprocess.run(
        "docker-compose -f generate-indexer-certs.yml run --rm generator",
        shell=True, cwd=str(deploy_dir), capture_output=True, text=True
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)

    certs_dir = deploy_dir / "certs"
    # Vérifier que les fichiers minimum existent
    required = [
        "wazuh-indexer/ca.pem", "wazuh-indexer/wazuh-indexer.pem", "wazuh-indexer/wazuh-indexer.key",
        "wazuh-manager/ca.pem", "wazuh-manager/wazuh-manager.pem", "wazuh-manager/wazuh-manager.key",
        "wazuh-dashboard/ca.pem", "wazuh-dashboard/wazuh-dashboard.pem", "wazuh-dashboard/wazuh-dashboard.key",
    ]
    missing = [f for f in required if not (certs_dir / f).exists()]
    if missing:
        print("Erreur : certificats manquants :")
        for f in missing:
            print(f"  - {f}")
        sys.exit(1)

    print("Tous les certificats sont présents.")

    # 5. Renommer les clés privées (le générateur produit .key, les conteneurs attendent -key.pem)
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
            print(f"Impossible de renommer {ancien} : fichier introuvable")

if __name__ == "__main__":
    main()