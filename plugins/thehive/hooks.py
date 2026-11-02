"""Hooks de cycle de vie pour TheHive et Cortex."""

import os
import shutil
from pathlib import Path
from typing import Dict, Any


def pre_install(ctx: Dict[str, Any]) -> None:
    """Création des répertoires de données et copie des configurations."""
    deploy_dir = Path(ctx["deploy_dir"])
    plugin_dir = Path(__file__).resolve().parent

    config_dest = deploy_dir / "config"
    data_dest = deploy_dir / "data"

    config_dest.mkdir(parents=True, exist_ok=True)
    (data_dest / "cassandra").mkdir(parents=True, exist_ok=True)
    (data_dest / "minio").mkdir(parents=True, exist_ok=True)
    (data_dest / "thehive").mkdir(parents=True, exist_ok=True)
    (data_dest / "es-cortex").mkdir(parents=True, exist_ok=True)

    # Copier les fichiers de configuration
    for cfg in (plugin_dir / "config").glob("*.conf"):
        target = config_dest / cfg.name
        if not target.exists():
            shutil.copy(cfg, target)

    # Remplacer le mot de passe minio dans application.conf si personnalisé
    admin_pw = ctx.get("variables", {}).get("admin_password", "secret123")
    app_conf = config_dest / "application.conf"
    if app_conf.exists():
        content = app_conf.read_text(encoding="utf-8")
        content = content.replace('secret-key = "secret123"', f'secret-key = "{admin_pw}"')
        app_conf.write_text(content, encoding="utf-8")


def post_install(ctx: Dict[str, Any]) -> None:
    """Actions post-démarrage."""
    pass


def uninstall(ctx: Dict[str, Any]) -> None:
    """Nettoyage des conteneurs TheHive / Cortex."""
    pass


def credentials(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Retourne les identifiants pour le rapport."""
    variables = ctx.get("variables", {})
    http_port = variables.get("http_port", 9000)
    return {
        "url": f"http://localhost:{http_port}",
        "username": "admin@thehive.local",
        "password": variables.get("admin_password", "secret123"),
        "note": "Connectez-vous avec admin@thehive.local pour configurer votre première organisation."
    }
