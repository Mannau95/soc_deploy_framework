"""Hooks de cycle de vie pour Velociraptor."""

import os
from pathlib import Path
from typing import Dict, Any


def pre_install(ctx: Dict[str, Any]) -> None:
    """Création des dossiers de configuration et données."""
    deploy_dir = Path(ctx["deploy_dir"])
    (deploy_dir / "config").mkdir(parents=True, exist_ok=True)
    (deploy_dir / "data").mkdir(parents=True, exist_ok=True)


def post_install(ctx: Dict[str, Any]) -> None:
    """Actions post-démarrage."""
    pass


def uninstall(ctx: Dict[str, Any]) -> None:
    """Nettoyage."""
    pass


def credentials(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Retourne les identifiants pour le rapport."""
    variables = ctx.get("variables", {})
    gui_port = variables.get("gui_port", 8889)
    return {
        "gui_url": f"https://localhost:{gui_port}",
        "username": variables.get("admin_user", "admin"),
        "password": variables.get("admin_password", "Veloc1P@ss!"),
        "frontend_port": variables.get("frontend_port", 8000),
        "note": "Téléchargez et générez les binaires clients/agents directement depuis l'interface web (Server Artifacts)."
    }
