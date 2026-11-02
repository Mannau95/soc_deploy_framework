"""Hooks de cycle de vie pour Zeek."""

import os
import shutil
from pathlib import Path
from typing import Dict, Any


def pre_install(ctx: Dict[str, Any]) -> None:
    """Préparation des dossiers de logs et copie de la configuration."""
    deploy_dir = Path(ctx["deploy_dir"])
    plugin_dir = Path(__file__).resolve().parent

    log_dir = deploy_dir / "logs"
    config_dir = deploy_dir / "config"

    log_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)

    if os.name != "nt":
        try:
            os.chmod(log_dir, 0o777)
        except Exception:
            pass

    # Copier local.zeek
    shutil.copy(plugin_dir / "config" / "local.zeek", config_dir / "local.zeek")


def post_install(ctx: Dict[str, Any]) -> None:
    """Actions post-démarrage."""
    pass


def uninstall(ctx: Dict[str, Any]) -> None:
    """Nettoyage."""
    pass


def credentials(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Retourne l'emplacement des logs Zeek pour le rapport."""
    deploy_dir = Path(ctx["deploy_dir"])
    return {
        "logs_directory": str(deploy_dir / "logs"),
        "key_logs": "conn.log (connexions), dns.log (requêtes DNS), http.log, ssl.log, notice.log",
        "format": "JSON structuré"
    }
