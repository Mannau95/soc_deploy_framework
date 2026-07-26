#!/usr/bin/env python3
"""
Préparation Wazuh v4.14 :
- Copie les fichiers de configuration depuis plugins/wazuh/config
- Génère les certificats auto-signés nécessaires
"""

import sys
import json
import shutil
import subprocess
from pathlib import Path

def run(cmd, cwd=None):
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Erreur d'exécution : {cmd}\n{result.stderr}")
        sys.exit(1)
    return result.stdout.strip()

def main():
    deploy_dir = Path(sys.argv[1])
    variables = json.loads(sys.argv[2])
    password = variables.get("admin_password", "Admin123!")

    plugin_dir = Path(__file__).resolve().parent

    # 1. Copie des configurations (déjà fait dans ton cas)
    config_src = plugin_dir / "config"
    if not config_src.exists():
        print("Dossier config/ introuvable. Lancez d'abord : cp -r wazuh-docker/single-node/config plugins/wazuh/")
        sys.exit(1)
    if (deploy_dir / "config").exists():
        shutil.rmtree(deploy_dir / "config")
    shutil.copytree(config_src, deploy_dir / "config")
    print("Configurations copiées.")

    # 2. Génération des certificats
    certs_dir = deploy_dir / "certs"
    certs_dir.mkdir(exist_ok=True)

    # Crée les sous-dossiers pour chaque composant
    for comp in ["wazuh-indexer", "wazuh-manager", "wazuh-dashboard"]:
        (certs_dir / comp).mkdir(exist_ok=True)

    # Fichier de configuration OpenSSL
    ssl_conf = certs_dir / "openssl.cnf"
    ssl_conf.write_text("""
[ req ]
default_bits = 2048
distinguished_name = req_distinguished_name
x509_extensions = v3_ca
prompt = no

[ req_distinguished_name ]
C = FR
ST = IDF
L = Paris
O = SOCDeploy
OU = Wazuh
CN = wazuh.internal

[ v3_ca ]
basicConstraints = critical,CA:true
keyUsage = critical, keyCertSign, cRLSign
subjectAltName = DNS:wazuh.indexer, DNS:wazuh.manager, DNS:wazuh.dashboard, DNS:localhost, IP:127.0.0.1

[ v3_req ]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
subjectAltName = @alt_names

[ alt_names ]
DNS.1 = wazuh.indexer
DNS.2 = wazuh.manager
DNS.3 = wazuh.dashboard
DNS.4 = localhost
IP.1 = 127.0.0.1
""")

    # Génère la CA
    ca_key = certs_dir / "ca-key.pem"
    ca_cert = certs_dir / "ca.pem"
    run(f"openssl genrsa -out {ca_key} 2048")
    run(f"openssl req -new -x509 -days 3650 -key {ca_key} -out {ca_cert} -config {ssl_conf} -extensions v3_ca")

    # Génère les certificats pour chaque composant
    components = {
        "wazuh-indexer": "wazuh.indexer",
        "wazuh-manager": "wazuh.manager",
        "wazuh-dashboard": "wazuh.dashboard"
    }

    for folder, common_name in components.items():
        comp_dir = certs_dir / folder
        key = comp_dir / f"{folder}.key"
        csr = comp_dir / f"{folder}.csr"
        cert = comp_dir / f"{folder}.pem"

        run(f"openssl genrsa -out {key} 2048")
        run(f"openssl req -new -key {key} -out {csr} -subj '/CN={common_name}'")
        run(f"openssl x509 -req -days 3650 -in {csr} -CA {ca_cert} -CAkey {ca_key} -out {cert} -extfile {ssl_conf} -extensions v3_req")
        # Copie le CA cert dans le dossier du composant
        shutil.copy(ca_cert, comp_dir / "ca.pem")

    print("Certificats générés avec succès.")

if __name__ == "__main__":
    main()