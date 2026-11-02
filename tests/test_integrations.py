"""Tests pour les interconnexions SOC (Suricata, Zeek, TheHive, MISP)."""

from pathlib import Path
from socdeploy.integrations.wazuh_suricata import (
    inject_suricata_localfile,
    setup_wazuh_suricata_integration
)
from socdeploy.integrations.wazuh_zeek import (
    inject_zeek_localfiles,
    setup_wazuh_zeek_integration
)
from socdeploy.integrations.wazuh_thehive import (
    inject_thehive_integration,
    setup_wazuh_thehive_integration
)
from socdeploy.integrations.thehive_misp import (
    setup_thehive_misp_integration
)
from socdeploy.models import UserConfig, ToolConfig, ServiceState
from socdeploy.reporter import DeploymentReporter


def test_inject_suricata_localfile():
    initial_xml = "<ossec_config><global></global></ossec_config>"
    eve_path = "/var/log/suricata/eve.json"
    new_xml, modified = inject_suricata_localfile(initial_xml, eve_path)
    assert modified is True
    assert f"<location>{eve_path}</location>" in new_xml

    # Idempotent
    re_xml, modified_again = inject_suricata_localfile(new_xml, eve_path)
    assert modified_again is False


def test_inject_zeek_localfiles():
    initial_xml = "<ossec_config><global></global></ossec_config>"
    logs_dir = "/var/log/zeek"
    new_xml, modified = inject_zeek_localfiles(initial_xml, logs_dir)
    assert modified is True
    assert "notice.log" in new_xml
    assert "dns.log" in new_xml
    assert "conn.log" in new_xml

    # Idempotent
    _, modified_again = inject_zeek_localfiles(new_xml, logs_dir)
    assert modified_again is False


def test_inject_thehive_integration():
    initial_xml = "<ossec_config><global></global></ossec_config>"
    new_xml, modified = inject_thehive_integration(initial_xml, "http://localhost:9000", min_level=10)
    assert modified is True
    assert "custom-wazuh2thehive" in new_xml
    assert "<level>10</level>" in new_xml

    # Idempotent
    _, modified_again = inject_thehive_integration(new_xml, "http://localhost:9000", min_level=10)
    assert modified_again is False


def test_setup_thehive_misp_integration(tmp_path):
    thehive_dir = tmp_path / "thehive" / "config"
    thehive_dir.mkdir(parents=True, exist_ok=True)
    app_conf = thehive_dir / "application.conf"
    app_conf.write_text('play.http.secret.key = "test"', encoding="utf-8")

    res = setup_thehive_misp_integration(tmp_path, "https://localhost:8443")
    assert res["status"] in ["configured", "active"]

    content = app_conf.read_text(encoding="utf-8")
    assert "misp {" in content
    assert "https://localhost:8443" in content


def test_report_includes_all_integrations(tmp_path):
    reporter = DeploymentReporter(templates_dir=Path("templates"))
    config = UserConfig(
        stack_name="full-soc",
        tools=[
            ToolConfig(plugin="wazuh", mode="auto-install"),
            ToolConfig(plugin="suricata", mode="ids"),
            ToolConfig(plugin="zeek", mode="live-capture"),
            ToolConfig(plugin="thehive", mode="thehive-standalone"),
            ToolConfig(plugin="misp", mode="standard")
        ]
    )
    services = [
        ServiceState(plugin="wazuh", mode="auto-install", version="4.14", status="installed"),
        ServiceState(plugin="suricata", mode="ids", version="8.0", status="installed"),
        ServiceState(plugin="zeek", mode="live-capture", version="7.0", status="installed"),
        ServiceState(plugin="thehive", mode="thehive-standalone", version="5.3", status="installed"),
        ServiceState(plugin="misp", mode="standard", version="2.4", status="installed"),
    ]
    integrations_data = {
        "wazuh_suricata": {
            "status": "active",
            "description": "Corrélation Suricata -> Wazuh",
            "eve_path": "/path/to/eve.json"
        },
        "wazuh_zeek": {
            "status": "active",
            "description": "Corrélation Zeek -> Wazuh",
            "zeek_logs_path": "/path/to/zeek/logs"
        },
        "wazuh_thehive": {
            "status": "active",
            "description": "Escalade Wazuh -> TheHive",
            "thehive_url": "http://localhost:9000",
            "trigger_level": 10
        },
        "thehive_misp": {
            "status": "active",
            "description": "CTI TheHive <-> MISP",
            "misp_url": "https://localhost:8443"
        }
    }

    report_file = tmp_path / "report.md"
    reporter.generate_markdown(config, services, report_file, integrations=integrations_data)

    content = report_file.read_text(encoding="utf-8")
    assert "Suricata NIDS/NIPS ➔ Wazuh SIEM" in content
    assert "Zeek Network Monitor ➔ Wazuh SIEM" in content
    assert "Wazuh SIEM ➔ TheHive SIRP" in content
    assert "TheHive SIRP ↔ MISP Threat Intelligence" in content
