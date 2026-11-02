"""Tests pour la génération de templates Jinja2 par le moteur."""

from pathlib import Path
import tempfile
import yaml
from socdeploy.engine import SOCDeployEngine
from socdeploy.models import UserConfig


def test_template_rendering(tmp_path):
    config_data = {
        "stack_name": "test-stack",
        "tools": [
            {
                "plugin": "suricata",
                "mode": "ids",
                "method": "docker",
                "variables": {
                    "interface": "eth0",
                    "auto_rules": False
                }
            }
        ]
    }
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump(config_data), encoding="utf-8")

    engine = SOCDeployEngine(cfg_file, plugins_dir=Path("plugins"), deploy_base_dir=tmp_path / "deployments")
    engine.load_config()

    output_dir = tmp_path / "deployments" / "test-stack" / "suricata"
    output_dir.mkdir(parents=True, exist_ok=True)

    engine.render_templates("suricata", "ids", output_dir, {"interface": "eth0"})

    compose_file = output_dir / "docker-compose.yml"
    assert compose_file.exists()
    content = compose_file.read_text(encoding="utf-8")
    assert "image: jasonish/suricata:latest" in content
    assert "eth0" in content
