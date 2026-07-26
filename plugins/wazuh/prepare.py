#!/usr/bin/env python3
"""
Script de préparation pour le déploiement Wazuh single-node.
Il génère les certificats nécessaires et les fichiers de configuration de base.
Paramètres : 
  1. chemin du répertoire de déploiement
  2. variables JSON (contient au moins admin_password)
"""

import sys
import json
import os
import subprocess
from pathlib import Path

def run(cmd, cwd=None):
    subprocess.run(cmd, shell=True, check=True, cwd=cwd, capture_output=True, text=True)

def main():
    deploy_dir = Path(sys.argv[1])
    variables = json.loads(sys.argv[2])
    password = variables.get("admin_password", "Admin123!")

    print(f"Préparation Wazuh dans {deploy_dir}")

    # Création des sous-dossiers
    certs_dir = deploy_dir / "certs"
    certs_dir.mkdir(exist_ok=True)
    for sub in ["wazuh-indexer", "wazuh-manager", "wazuh-dashboard"]:
        (certs_dir / sub).mkdir(exist_ok=True)

    config_dir = deploy_dir / "config"
    config_dir.mkdir(exist_ok=True)
    for sub in ["wazuh-indexer", "wazuh-manager", "wazuh-dashboard"]:
        (config_dir / sub).mkdir(exist_ok=True)

    # --- Génération des certificats auto-signés ---
    # On utilise openssl en local (supposé installé). 
    # Génération d'une CA racine puis des certificats pour chaque composant.

    # Fichier de configuration pour openssl (simplifié)
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

    # Générer la clé privée et le certificat de la CA
    ca_key = certs_dir / "ca-key.pem"
    ca_cert = certs_dir / "ca.pem"
    run(f"openssl genrsa -out {ca_key} 2048")
    run(f"openssl req -new -x509 -days 3650 -key {ca_key} -out {ca_cert} -config {ssl_conf} -extensions v3_ca")

    # Composants à certifier
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

        # Générer clé et CSR
        run(f"openssl genrsa -out {key} 2048")
        run(f"openssl req -new -key {key} -out {csr} -subj '/CN={common_name}'")
        # Signer avec la CA
        run(f"openssl x509 -req -days 3650 -in {csr} -CA {ca_cert} -CAkey {ca_key} -out {cert} -extfile {ssl_conf} -extensions v3_req")
        # Copier aussi le CA cert dans le dossier du composant
        with open(comp_dir / "ca.pem", "w") as f:
            f.write(ca_cert.read_text())

    print("Certificats générés.")

    # --- Fichiers de configuration ---
    # Configuration de l'indexer (opensearch.yml)
    opensearch_yml = config_dir / "wazuh-indexer" / "opensearch.yml"
    opensearch_yml.write_text(f"""
network.host: "0.0.0.0"
node.name: "wazuh.indexer"
cluster.initial_master_nodes:
- "wazuh.indexer"
discovery.type: single-node

plugins.security.ssl.transport.pemcert_filepath: /usr/share/wazuh-indexer/certs/wazuh-indexer.pem
plugins.security.ssl.transport.pemkey_filepath: /usr/share/wazuh-indexer/certs/wazuh-indexer.key
plugins.security.ssl.transport.pemtrustedcas_filepath: /usr/share/wazuh-indexer/certs/ca.pem
plugins.security.ssl.http.pemcert_filepath: /usr/share/wazuh-indexer/certs/wazuh-indexer.pem
plugins.security.ssl.http.pemkey_filepath: /usr/share/wazuh-indexer/certs/wazuh-indexer.key
plugins.security.ssl.http.pemtrustedcas_filepath: /usr/share/wazuh-indexer/certs/ca.pem
plugins.security.allow_default_init_securityindex: true
plugins.security.authcz.admin_dn:
- CN=admin, O=Wazuh
plugins.security.nodes_dn:
- CN=wazuh.indexer, O=Wazuh
plugins.security.restapi.roles_enabled:
- "all_access"
- "security_rest_api_access"
""")

    # Configuration du dashboard
    dash_yml = config_dir / "wazuh-dashboard" / "opensearch_dashboards.yml"
    dash_yml.write_text(f"""
server.host: "0.0.0.0"
server.port: 5601
opensearch.hosts: https://wazuh.indexer:9200
opensearch.ssl.verificationMode: certificate
opensearch.username: kibanaserver
opensearch.password: {password}
opensearch.requestHeadersWhitelist: [ authorization,securitytenant ]
opensearch_security.multitenancy.enabled: false
opensearch_security.readonly_mode.roles: [kibana_read_only]
server.ssl.enabled: true
server.ssl.key: /usr/share/wazuh-dashboard/certs/wazuh-dashboard.key
server.ssl.certificate: /usr/share/wazuh-dashboard/certs/wazuh-dashboard.pem
wazuh.monitoring.enabled: true
wazuh.monitoring.frequency: 300
wazuh.monitoring.shards: 1
wazuh.monitoring.replicas: 0
""")

    # Configuration de base du manager
    ossec_conf = config_dir / "wazuh-manager" / "ossec.conf"
    ossec_conf.write_text("""<!-- ossec.conf minimal -->""")  # Laisser vide ou par défaut, le conteneur en utilisera une interne.

    print("Configuration générée.")

if __name__ == "__main__":
    main()