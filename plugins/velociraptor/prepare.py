#!/usr/bin/env python3
"""Compatibilité préparation Velociraptor."""

import sys
import json
from pathlib import Path
from hooks import pre_install

def main():
    deploy_dir = Path(sys.argv[1])
    variables = json.loads(sys.argv[2])
    ctx = {
        "deploy_dir": deploy_dir,
        "variables": variables,
        "mode": variables.get("mode", "server"),
        "method": "docker"
    }
    pre_install(ctx)

if __name__ == "__main__":
    main()
