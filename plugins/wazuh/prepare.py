#!/usr/bin/env python3
"""Préparation Wazuh – copie configs et génération des certificats."""

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

    # 2. Copier le générateur de certificats et config.yml
    for f in ["generate-indexer-certs.yml", "config.yml"]:
        src = plugin_dir / f
        if not src.exists():
            print(f"Fichier {f} introuvable.")
            sys.exit(1)
        shutil.copy(src, deploy_dir / f)

    # 3. Générer les certificats dans les volumes nommés
    print("Génération des certificats...")
    result = subprocess.run(
        "docker-compose -f generate-indexer-certs.yml run --rm generator",
        shell=True, cwd=str(deploy_dir), capture_output=True, text=True
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if result.returncode != 0:
        print("Le générateur a renvoyé un code d'erreur, mais les certificats peuvent avoir été créés malgré tout.")
    print("Génération terminée.")

if __name__ == "__main__":
    main()