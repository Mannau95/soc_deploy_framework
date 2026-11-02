"""Gestion de la persistance de l'état des services déployés."""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger
from socdeploy.models import ServiceState


class StateManager:
    """Gère le fichier stack_state.json pour une stack donnée."""

    def __init__(self, deploy_dir: Path):
        self.deploy_dir = deploy_dir
        self.state_file = deploy_dir / "stack_state.json"

    def load(self) -> Dict[str, ServiceState]:
        """Charge l'état actuel de tous les services de la stack."""
        if not self.state_file.exists():
            return {}
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            result = {}
            for plugin_name, data in raw.items():
                result[plugin_name] = ServiceState(**data)
            return result
        except Exception as e:
            logger.warning(f"Erreur de lecture du fichier d'état {self.state_file} : {e}")
            return {}

    def save(self, state: Dict[str, ServiceState]) -> None:
        """Sauvegarde l'état des services."""
        self.deploy_dir.mkdir(parents=True, exist_ok=True)
        raw = {k: v.model_dump() for k, v in state.items()}
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2, ensure_ascii=False)

    def get_service(self, plugin_name: str) -> Optional[ServiceState]:
        """Récupère l'état d'un service spécifique."""
        state = self.load()
        return state.get(plugin_name)

    def is_installed(self, plugin_name: str) -> bool:
        """Vérifie si un plugin est marqué comme installé avec succès."""
        svc = self.get_service(plugin_name)
        return svc is not None and svc.status == "installed"

    def record_installed(self, service: ServiceState) -> None:
        """Enregistre ou met à jour l'installation d'un service."""
        state = self.load()
        if not service.installed_at:
            service.installed_at = datetime.now().isoformat()
        state[service.plugin] = service
        self.save(state)

    def remove_service(self, plugin_name: str) -> None:
        """Supprime un service du fichier d'état (après désinstallation)."""
        state = self.load()
        if plugin_name in state:
            del state[plugin_name]
            self.save(state)
