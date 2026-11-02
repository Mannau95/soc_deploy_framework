#!/usr/bin/env python3
"""Compatibilité préparation Wazuh."""

import sys
import json
from pathlib import Path
from hooks import pre_install, install_native, post_install

def main():
    deploy_dir = Path(sys.argv[1])
    variables = json.loads(sys.argv[2])
    ctx = {
        "deploy_dir": deploy_dir,
        "variables": variables,
        "mode": variables.get("mode", "auto-install"),
        "method": "native"
    }
    pre_install(ctx)
    if ctx["mode"] == "auto-install":
        install_native(ctx)
        post_install(ctx)

if __name__ == "__main__":
    main()
