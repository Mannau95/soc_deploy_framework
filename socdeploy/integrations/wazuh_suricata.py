"""Interconnexion et corrélation automatique entre Suricata (NIDS/NIPS) et Wazuh (SIEM).

Wazuh intègre nativement des décodeurs et règles pour Suricata (règles 86600+).
Ce module configure Wazuh pour ingérer et corréler en temps réel les alertes issues de 'eve.json'.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from loguru import logger
from socdeploy.utils import run_command


def inject_suricata_localfile(ossec_conf_text: str, eve_path: str) -> Tuple[str, bool]:
    """Injecte un bloc <localfile> pour Suricata dans ossec.conf si absent.
    
    Retourne (nouveau_contenu, True) si modifié, ou (contenu_original, False) si déjà présent.
    """
    normalized_path = str(Path(eve_path).as_posix())

    # Vérifier si ce chemin est déjà présent
    if f"<location>{normalized_path}</location>" in ossec_conf_text or f"<location>{eve_path}</location>" in ossec_conf_text:
        return ossec_conf_text, False

    block = (
        "\n  <!-- Interconnexion Suricata IDS/IPS -> Wazuh (SOC Deploy Framework) -->\n"
        "  <localfile>\n"
        "    <log_format>json</log_format>\n"
        f"    <location>{normalized_path}</location>\n"
        "  </localfile>\n"
    )

    # Insérer avant la dernière balise </ossec_config>
    if "</ossec_config>" in ossec_conf_text:
        idx = ossec_conf_text.rfind("</ossec_config>")
        new_content = ossec_conf_text[:idx] + block + ossec_conf_text[idx:]
        return new_content, True
    else:
        # Fallback si pas de balise fermante
        return ossec_conf_text + f"\n<ossec_config>{block}</ossec_config>\n", True


def setup_wazuh_suricata_integration(
    deploy_dir: Path,
    wazuh_method: str = "native",
    suricata_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """Configure la corrélation Suricata vers Wazuh."""
    if suricata_dir is None:
        suricata_dir = deploy_dir / "suricata"

    logs_dir = suricata_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    eve_file = logs_dir / "eve.json"

    # Créer le fichier s'il n'existe pas encore
    if not eve_file.exists():
        eve_file.touch()

    # Rendre le fichier lisible par tous (pour que l'utilisateur ossec/wazuh puisse lire)
    if os.name != "nt":
        try:
            os.chmod(eve_file, 0o666)
            os.chmod(logs_dir, 0o777)
        except Exception:
            pass

    eve_path_str = str(eve_file.resolve())
    result = {
        "status": "configured",
        "eve_path": eve_path_str,
        "format": "json",
        "description": "Ingestion et corrélation temps réel des alertes réseau Suricata (règles Wazuh 86600+)"
    }

    # 1. Mode Natif Wazuh (installation sur l'hôte)
    if wazuh_method == "native":
        ossec_conf = Path("/var/ossec/etc/ossec.conf")
        if ossec_conf.exists():
            try:
                content = ossec_conf.read_text(encoding="utf-8")
                new_content, modified = inject_suricata_localfile(content, eve_path_str)
                if modified:
                    # Sauvegarde de sécurité
                    shutil.copy(ossec_conf, ossec_conf.with_suffix(".conf.bak"))
                    ossec_conf.write_text(new_content, encoding="utf-8")
                    logger.info("Configuration /var/ossec/etc/ossec.conf mise à jour avec eve.json.")

                    # Redémarrer Wazuh Manager pour appliquer
                    if os.name != "nt":
                        run_command(["systemctl", "restart", "wazuh-manager"], check=False)
                        logger.info("Service wazuh-manager redémarré.")
                else:
                    logger.info("Suricata eve.json est déjà configuré dans /var/ossec/etc/ossec.conf.")
                result["status"] = "active"
            except Exception as e:
                logger.warning(f"Impossible de modifier /var/ossec/etc/ossec.conf : {e}")
                result["status"] = "partial"
                result["error"] = str(e)
        else:
            logger.info("Wazuh natif non présent sur /var/ossec/etc/ossec.conf (peut-être en cours ou distant).")

    # 2. Mode Docker Wazuh
    elif wazuh_method == "docker":
        wazuh_conf = deploy_dir / "wazuh" / "config" / "wazuh_cluster" / "wazuh_manager.conf"
        if wazuh_conf.exists():
            content = wazuh_conf.read_text(encoding="utf-8")
            container_eve_path = "/var/log/suricata/eve.json"
            new_content, modified = inject_suricata_localfile(content, container_eve_path)
            if modified:
                wazuh_conf.write_text(new_content, encoding="utf-8")
                logger.info(f"Configuration Wazuh Docker mise à jour : {wazuh_conf}")
            result["status"] = "active"

    return result
