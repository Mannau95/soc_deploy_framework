#!/usr/bin/env python3
"""Préparation Suricata – création du dossier de logs."""

import sys, json, os
from pathlib import Path

def main():
    deploy_dir = Path(sys.argv[1])
    variables = json.loads(sys.argv[2])

    log_dir = deploy_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(log_dir, 0o777)
    print("Dossier de logs créé.")

if __name__ == "__main__":
    main()