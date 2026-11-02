"""Interconnexion et ingestion des logs Zeek (NSM) dans Wazuh (SIEM).

Wazuh intègre nativement des décodeurs pour Zeek (conn, dns, http, ssl, notice, etc.).
Ce module configure Wazuh pour ingérer et corréler en temps réel les journaux Zeek.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, Tuple
from loguru import logger
from socdeploy.utils import run_command


def inject_zeek_localfiles(ossec_conf_text: str, zeek_logs_dir: str) -> Tuple[str, bool]:
    """Injecte les blocs <localfile> pour les journaux clés de Zeek (notice.log, conn.log, dns.log)."""
    normalized_dir = str(Path(zeek_logs_dir).as_posix())

    if f"<location>{normalized_dir}/notice.log</location>" in ossec_conf_text:
        return ossec_conf_text, False

    block = (
        "\n  <!-- Interconnexion Zeek NSM -> Wazuh (SOC Deploy Framework) -->\n"
        "  <localfile>\n"
        "    <log_format>json</log_format>\n"
        f"    <location>{normalized_dir}/notice.log</location>\n"
        "  </localfile>\n"
        "  <localfile>\n"
        "    <log_format>json</log_format>\n"
        f"    <location>{normalized_dir}/dns.log</location>\n"
        "  </localfile>\n"
        "  <localfile>\n"
        "    <log_format>json</log_format>\n"
        f"    <location>{normalized_dir}/conn.log</location>\n"
        "  </localfile>\n"
    )

    if "</ossec_config>" in ossec_conf_text:
        idx = ossec_conf_text.rfind("</ossec_config>")
        return ossec_conf_text[:idx] + block + ossec_conf_text[idx:], True
    else:
        return ossec_conf_text + f"\n<ossec_config>{block}</ossec_config>\n", True


def setup_wazuh_zeek_integration(
    deploy_dir: Path,
    wazuh_method: str = "native",
    zeek_dir: Path = None
) -> Dict[str, Any]:
    """Configure la surveillance des logs Zeek par Wazuh."""
    if zeek_dir is None:
        zeek_dir = deploy_dir / "zeek"

    logs_dir = zeek_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Pré-créer les fichiers si non existants
    for log_name in ["notice.log", "dns.log", "conn.log"]:
        f = logs_dir / log_name
        if not f.exists():
            f.touch()
        if os.name != "nt":
            try:
                os.chmod(f, 0o666)
            except Exception:
                pass

    if os.name != "nt":
        try:
            os.chmod(logs_dir, 0o777)
        except Exception:
            pass

    logs_path_str = str(logs_dir.resolve())
    result = {
        "status": "configured",
        "zeek_logs_path": logs_path_str,
        "format": "json",
        "description": "Ingestion et analyse des métadonnées réseau Zeek (notices, requêtes DNS et flux TCP/UDP)"
    }

    if wazuh_method == "native":
        ossec_conf = Path("/var/ossec/etc/ossec.conf")
        if ossec_conf.exists():
            try:
                content = ossec_conf.read_text(encoding="utf-8")
                new_content, modified = inject_zeek_localfiles(content, logs_path_str)
                if modified:
                    shutil.copy(ossec_conf, ossec_conf.with_suffix(".conf.bak"))
                    ossec_conf.write_text(new_content, encoding="utf-8")
                    if os.name != "nt":
                        run_command(["systemctl", "restart", "wazuh-manager"], check=False)
                    logger.info("Configuration Wazuh mise à jour pour Zeek.")
                result["status"] = "active"
            except Exception as e:
                result["status"] = "partial"
                result["error"] = str(e)
    elif wazuh_method == "docker":
        wazuh_conf = deploy_dir / "wazuh" / "config" / "wazuh_cluster" / "wazuh_manager.conf"
        if wazuh_conf.exists():
            content = wazuh_conf.read_text(encoding="utf-8")
            container_zeek_path = "/var/log/zeek"
            new_content, modified = inject_zeek_localfiles(content, container_zeek_path)
            if modified:
                wazuh_conf.write_text(new_content, encoding="utf-8")
            result["status"] = "active"

    return result
