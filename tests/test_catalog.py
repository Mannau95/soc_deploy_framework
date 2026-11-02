"""Tests unitaires pour le catalogue des plugins SOC."""

from pathlib import Path
from socdeploy.catalog import PluginCatalog


def test_catalog_loads_plugins():
    catalog = PluginCatalog(Path("plugins"))
    plugins = catalog.list_plugins()
    assert len(plugins) >= 6

    plugin_names = [p.name for p in plugins]
    expected_tools = ["suricata", "wazuh", "thehive", "misp", "zeek", "velociraptor"]
    for tool in expected_tools:
        assert tool in plugin_names, f"L'outil {tool} doit être présent dans le catalogue."


def test_new_plugins_manifests():
    catalog = PluginCatalog(Path("plugins"))
    thehive = catalog.get_plugin("thehive")
    assert thehive is not None
    assert "thehive-standalone" in thehive.modes
    assert "thehive-cortex" in thehive.modes

    misp = catalog.get_plugin("misp")
    assert misp is not None
    assert "standard" in misp.modes

    zeek = catalog.get_plugin("zeek")
    assert zeek is not None
    assert "live-capture" in zeek.modes

    velociraptor = catalog.get_plugin("velociraptor")
    assert velociraptor is not None
    assert "server" in velociraptor.modes


def test_suricata_modes_and_methods():
    catalog = PluginCatalog(Path("plugins"))
    suricata = catalog.get_plugin("suricata")
    assert suricata is not None
    assert "ids" in suricata.modes
    assert "ips" in suricata.modes

    # Vérification des méthodes compatibles
    methods = catalog.get_compatible_methods("suricata", "ids", "debian")
    assert "docker" in methods or "native" in methods


def test_wazuh_modes():
    catalog = PluginCatalog(Path("plugins"))
    wazuh = catalog.get_plugin("wazuh")
    assert wazuh is not None
    assert "auto-install" in wazuh.modes
    assert "single-node" in wazuh.modes
