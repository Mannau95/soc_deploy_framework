"""Catalogue des plugins SOC disponibles."""

from pathlib import Path
from typing import Dict, List, Optional
import yaml
from loguru import logger
from socdeploy.models import PluginManifest, ModeConfig


CATEGORY_LABELS = {
    "siem": "SIEM / XDR",
    "network": "Analyse Réseau & Détection (NIDS/NIPS)",
    "edr": "Détection & Réponse Endpoint (EDR)",
    "incident": "Gestion des Incidents (IR / Case Management)",
    "threat-intel": "Cyber Threat Intelligence (CTI)",
    "soar": "Automatisation & Orchestration (SOAR)",
    "logs": "Collecte & Analyse de Logs",
    "other": "Autres outils SOC",
}


class PluginCatalog:
    """Gestionnaire de découverte et d'accès aux plugins."""

    def __init__(self, plugins_dir: Path = Path("plugins")):
        self.plugins_dir = plugins_dir
        self._plugins: Dict[str, PluginManifest] = {}
        self.reload()

    def reload(self) -> None:
        """Parcourt le dossier plugins/ et charge tous les manifestes valides."""
        self._plugins.clear()
        if not self.plugins_dir.exists():
            logger.warning(f"Dossier des plugins introuvable : {self.plugins_dir}")
            return

        for manifest_path in self.plugins_dir.glob("*/manifest.yaml"):
            try:
                plugin_name = manifest_path.parent.name
                with open(manifest_path, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f)
                if not raw:
                    continue
                # Forcer le nom correspondant au dossier si absent
                if "name" not in raw:
                    raw["name"] = plugin_name
                manifest = PluginManifest(**raw)
                # On référence par le nom de dossier pour cohérence avec le filesystem
                self._plugins[plugin_name] = manifest
            except Exception as e:
                logger.error(f"Erreur lors du chargement du plugin {manifest_path} : {e}")

    def list_plugins(self) -> List[PluginManifest]:
        """Retourne la liste de tous les plugins chargés."""
        return list(self._plugins.values())

    def get_plugin(self, name: str) -> Optional[PluginManifest]:
        """Récupère un plugin par son nom (identifiant de dossier)."""
        return self._plugins.get(name)

    def get_by_category(self) -> Dict[str, List[PluginManifest]]:
        """Groupe les plugins par catégorie."""
        grouped: Dict[str, List[PluginManifest]] = {k: [] for k in CATEGORY_LABELS}
        for plugin in self._plugins.values():
            cat = plugin.category if plugin.category in grouped else "other"
            grouped[cat].append(plugin)
        return {k: v for k, v in grouped.items() if v}

    def get_compatible_methods(self, plugin_name: str, mode_name: str, os_family: str) -> List[str]:
        """Retourne les méthodes d'installation (docker, native) compatibles avec l'OS donné."""
        plugin = self.get_plugin(plugin_name)
        if not plugin or mode_name not in plugin.modes:
            return []
        mode = plugin.modes[mode_name]
        compatible = []
        for method_name, method_cfg in mode.methods.items():
            if not method_cfg.supported_os or "all" in method_cfg.supported_os or os_family in method_cfg.supported_os:
                compatible.append(method_name)
        # S'il n'y a aucune restriction spécifiée, autoriser
        if not compatible and "docker" in mode.methods:
            compatible.append("docker")
        return compatible
