"""Tests pour la génération de rapport."""

from pathlib import Path
from socdeploy.reporter import DeploymentReporter
from socdeploy.models import UserConfig, ServiceState


def test_markdown_report_generation(tmp_path):
    reporter = DeploymentReporter(templates_dir=Path("templates"))
    config = UserConfig(stack_name="mon-lab")
    services = [
        ServiceState(
            plugin="suricata",
            mode="ids",
            method="docker",
            version="8.0",
            description="NIDS Suricata",
            status="installed",
            urls=[],
            credentials={"interface": "eth0"},
            logs=["/var/log/suricata/eve.json"]
        )
    ]
    report_file = tmp_path / "report.md"
    reporter.generate_markdown(config, services, report_file)

    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "mon-lab" in content
    assert "suricata" in content
    assert "/var/log/suricata/eve.json" in content
