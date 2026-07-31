#!/usr/bin/env python3
"""Préparation Suricata – configuration IDS ou IPS."""

import sys, json, os, shutil, subprocess
from pathlib import Path

def main():
    deploy_dir = Path(sys.argv[1])
    variables = json.loads(sys.argv[2])
    mode = variables.get("mode", "ids")

    # 1. Copier la configuration Suricata
    config_src = Path(__file__).resolve().parent / "config"
    if config_src.exists():
        dest = deploy_dir / "config"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(config_src, dest)
        print("Configuration Suricata copiée.")

    # 2. Créer le dossier de logs
    log_dir = deploy_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(log_dir, 0o777)
    print("Dossier de logs créé.")

    # 3. Mise à jour des règles si demandé
    if variables.get("auto_rules", False):
        print("Mise à jour des règles Suricata...")
        subprocess.run(
            ["docker", "run", "--rm",
             "-v", f"{deploy_dir / 'config'}:/etc/suricata:ro",
             "-v", f"{deploy_dir / 'logs'}:/var/log/suricata",
             "jasonish/suricata:latest",
             "suricata-update"],
            check=False
        )
        print("Règles mises à jour.")

    # 4. Configuration IPS : règles iptables NFQUEUE
    if mode == "ips":
        interface = variables.get("interface") or get_default_interface()
        print(f"Configuration IPS pour l'interface {interface}...")
        subprocess.run(["sudo", "iptables", "-I", "INPUT", "-i", interface, "-j", "NFQUEUE", "--queue-num", "0"], check=False)
        subprocess.run(["sudo", "iptables", "-I", "OUTPUT", "-o", interface, "-j", "NFQUEUE", "--queue-num", "0"], check=False)
        print("Règles iptables ajoutées.")
        # Sauvegarde des règles pour suppression au rollback
        with open(deploy_dir / "iptables_cleanup.sh", "w") as f:
            f.write(f"#!/bin/bash\nsudo iptables -D INPUT -i {interface} -j NFQUEUE --queue-num 0\nsudo iptables -D OUTPUT -o {interface} -j NFQUEUE --queue-num 0\n")
        os.chmod(deploy_dir / "iptables_cleanup.sh", 0o755)

def get_default_interface():
    import subprocess
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

if __name__ == "__main__":
    main()