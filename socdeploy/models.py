"""Modèles de données Pydantic pour SOC Deploy Framework (manifeste v2 et config)."""

from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, model_validator


class ManifestVariable(BaseModel):
    """Définition d'une variable configurable pour un outil/mode."""
    name: str
    prompt: str
    type: str = "str"  # str, int, bool, choice, password
    default: Optional[Any] = None
    choices: Optional[List[str]] = None
    choices_from: Optional[str] = None  # ex: network_interfaces
    required: bool = True
    help: Optional[str] = None


class HealthcheckConfig(BaseModel):
    """Configuration d'un healthcheck dans un manifeste."""
    type: str = "http"  # http, command, tcp
    url: Optional[str] = None
    command: Optional[str] = None
    port: Optional[int] = None
    expected_status: Optional[int] = 200
    expected_stdout: Optional[str] = None
    timeout: int = 30
    retries: int = 10
    interval: int = 5


class MethodConfig(BaseModel):
    """Configuration d'une méthode de déploiement (docker, native)."""
    templates: List[str] = []
    supported_os: Optional[List[str]] = None  # ex: ["debian", "rhel", "suse", "all"]


class ModeRequirements(BaseModel):
    """Exigences matérielles et système d'un mode."""
    min_ram_mb: int = 1024
    min_cpu: int = 1
    ports: List[int] = []
    root: bool = False
    docker: bool = False


class ModeConfig(BaseModel):
    """Configuration d'un mode d'installation pour un outil."""
    description: str
    methods: Dict[str, MethodConfig] = Field(default_factory=dict)
    requirements: ModeRequirements = Field(default_factory=ModeRequirements)
    variables: List[ManifestVariable] = Field(default_factory=list)
    healthcheck: Optional[HealthcheckConfig] = None
    # Rétrocompatibilité avec manifestes v1
    prerequisites: Optional[Dict[str, Any]] = None
    templates: Optional[List[str]] = None
    post_install: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def adapt_v1_manifest(cls, data: Any) -> Any:
        """Adapte automatiquement un mode défini au format v1 vers v2."""
        if not isinstance(data, dict):
            return data

        # Si v1 : "prerequisites" et "templates" à la racine du mode
        if "prerequisites" in data and "requirements" not in data:
            pre = data.get("prerequisites", {})
            data["requirements"] = {
                "min_ram_mb": pre.get("min_ram_mb", 1024),
                "min_cpu": pre.get("min_cpu", 1),
                "ports": pre.get("ports", []),
                "docker": pre.get("docker", False),
                "root": pre.get("root", False),
            }

        # Méthodes (docker / native)
        if "methods" not in data or not data["methods"]:
            templates = data.get("templates", [])
            data["methods"] = {
                "docker": {
                    "templates": templates,
                    "supported_os": ["all"]
                }
            }

        # Healthcheck dans post_install
        if "healthcheck" not in data and "post_install" in data:
            post = data.get("post_install", {})
            if isinstance(post, dict) and "healthcheck" in post:
                data["healthcheck"] = post["healthcheck"]

        return data


class PluginManifest(BaseModel):
    """Structure d'un fichier manifest.yaml pour un plugin SOC."""
    name: str
    display_name: Optional[str] = None
    version: str = "1.0.0"
    category: str = "other"  # siem, network, edr, incident, threat-intel, soar, logs
    description: str = ""
    homepage: Optional[str] = None
    modes: Dict[str, ModeConfig]

    @property
    def label(self) -> str:
        return self.display_name or self.name.capitalize()


class ToolConfig(BaseModel):
    """Configuration d'un outil dans le fichier de déploiement."""
    plugin: str
    mode: str
    method: str = "docker"  # "docker" ou "native"
    variables: Dict[str, Any] = Field(default_factory=dict)


class UserConfig(BaseModel):
    """Configuration complète de la stack choisie par l'utilisateur."""
    stack_name: str = "lab-soc"
    tools: List[ToolConfig] = Field(default_factory=list)
    integrations: List[str] = Field(default_factory=list)


class ServiceState(BaseModel):
    """État d'un service enregistré dans stack_state.json."""
    plugin: str
    mode: str
    method: str = "docker"
    version: str
    description: str = ""
    status: str = "installed"  # installed, failed, stopped
    installed_at: Optional[str] = None
    urls: List[str] = Field(default_factory=list)
    credentials: Dict[str, Any] = Field(default_factory=dict)
    logs: List[str] = Field(default_factory=list)
    variables: Dict[str, Any] = Field(default_factory=dict)
