#!/usr/bin/env python3
"""Préparation Wazuh – copie configs et génération des certificats."""

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

    # 1. Copier les configurations (opensearch.yml, ossec.conf, etc.)
    config_src = plugin_dir / "config"
    if not config_src.exists():
        print("Dossier config/ introuvable.")
        sys.exit(1)
    if (deploy_dir / "config").exists():
        shutil.rmtree(deploy_dir / "config")
    shutil.copytree(config_src, deploy_dir / "config")
    print("Configurations copiées.")

    # 2. Copier le générateur de certificats et son fichier de config
    for f in ["generate-indexer-certs.yml", "config.yml"]:
        src = plugin_dir / f
        if not src.exists():
            print(f"Fichier {f} introuvable.")
            sys.exit(1)
        shutil.copy(src, deploy_dir / f)

    # 3. Générer les certificats dans les volumes nommés
    print("Génération des certificats...")
    run("docker-compose -f generate-indexer-certs.yml run --rm generator", cwd=str(deploy_dir))
    print("Certificats générés avec succès.")

if __name__ == "__main__":
    main()