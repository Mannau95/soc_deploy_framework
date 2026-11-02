"""Tests pour les modèles de données Pydantic et la rétrocompatibilité v1/v2."""

from socdeploy.models import PluginManifest, UserConfig, ToolConfig


def test_v1_manifest_auto_adaptation():
    """Vérifie qu'un ancien manifeste v1 est converti sans erreur."""
    v1_raw = {
        "name": "test-tool",
        "version": "1.0",
        "description": "Un outil de test",
        "modes": {
            "default": {
                "description": "Mode par défaut",
                "prerequisites": {
                    "docker": True,
                    "ports": [8080]
                },
                "templates": ["docker-compose.yml.j2"],
                "post_install": {
                    "healthcheck": {
                        "type": "http",
                        "url": "http://localhost:8080"
                    }
                }
            }
        }
    }
    manifest = PluginManifest(**v1_raw)
    assert manifest.name == "test-tool"
    assert "default" in manifest.modes
    mode = manifest.modes["default"]
    assert mode.requirements.docker is True
    assert mode.requirements.ports == [8080]
    assert "docker" in mode.methods
    assert mode.healthcheck.type == "http"


def test_user_config_parsing():
    raw_config = {
        "stack_name": "test-soc",
        "tools": [
            {
                "plugin": "suricata",
                "mode": "ids",
                "method": "docker",
                "variables": {"interface": "eth0"}
            }
        ]
    }
    config = UserConfig(**raw_config)
    assert config.stack_name == "test-soc"
    assert len(config.tools) == 1
    assert config.tools[0].plugin == "suricata"
