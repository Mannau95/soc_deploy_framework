"""Hooks de cycle de vie pour MISP."""

import os
from pathlib import Path
from typing import Dict, Any


def pre_install(ctx: Dict[str, Any]) -> None:
    """Création des dossiers de persistance."""
    deploy_dir = Path(ctx["deploy_dir"])
    data_dir = deploy_dir / "data"

    (data_dir / "mysql").mkdir(parents=True, exist_ok=True)
    (data_dir / "redis").mkdir(parents=True, exist_ok=True)
    (data_dir / "misp").mkdir(parents=True, exist_ok=True)


def post_install(ctx: Dict[str, Any]) -> None:
    """Actions post-installation."""
    pass


def uninstall(ctx: Dict[str, Any]) -> None:
    """Nettoyage."""
    pass


def credentials(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Retourne les identifiants pour le rapport."""
    variables = ctx.get("variables", {})
    port = variables.get("https_port", 8443)
    return {
        "url": f"https://localhost:{port}",
        "username": variables.get("admin_email", "admin@admin.test"),
        "password": variables.get("admin_password", "admin"),
        "note": "MISP vous demandera de modifier le mot de passe administrateur par défaut à la première connexion."
    }
