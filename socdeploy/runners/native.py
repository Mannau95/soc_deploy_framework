"""Gestionnaire des installations natives (paquets système Linux et services systemd)."""

import os
import shutil
import subprocess
from typing import List
from loguru import logger
from socdeploy.system import system


class NativeRunner:
    """Gère l'installation de paquets et le contrôle des services système."""

    def __init__(self):
        self.pkg_mgr = system.package_manager
        self.is_root = system.is_root

    def _run_cmd(self, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Exécute une commande avec sudo si l'utilisateur n'est pas root."""
        cmd = args
        if not self.is_root and shutil.which("sudo"):
            cmd = ["sudo"] + args

        logger.debug(f"Commande native : {' '.join(cmd)}")
        return subprocess.run(cmd, capture_output=True, text=True, check=check)

    def install_packages(self, packages: List[str]) -> None:
        """Installe des paquets via le gestionnaire natif."""
        if not packages:
            return

        if not self.pkg_mgr:
            raise RuntimeError("Aucun gestionnaire de paquets reconnu (apt, dnf, zypper).")

        logger.info(f"Installation native des paquets : {', '.join(packages)}")

        if "apt" in self.pkg_mgr:
            # Mise à jour préalable silencieuse du cache
            self._run_cmd(["apt-get", "update", "-qq"], check=False)
            cmd = ["apt-get", "install", "-y"] + packages
        elif "dnf" in self.pkg_mgr:
            cmd = ["dnf", "install", "-y"] + packages
        elif "yum" in self.pkg_mgr:
            cmd = ["yum", "install", "-y"] + packages
        elif "zypper" in self.pkg_mgr:
            cmd = ["zypper", "--non-interactive", "install"] + packages
        elif "pacman" in self.pkg_mgr:
            cmd = ["pacman", "-S", "--noconfirm"] + packages
        else:
            raise RuntimeError(f"Gestionnaire non supporté : {self.pkg_mgr}")

        res = self._run_cmd(cmd, check=False)
        if res.returncode != 0:
            logger.error(f"Erreur d'installation : {res.stderr}")
            raise RuntimeError(f"Échec de l'installation des paquets {packages} :\n{res.stderr}")

    def remove_packages(self, packages: List[str]) -> None:
        """Désinstalle des paquets."""
        if not packages or not self.pkg_mgr:
            return

        logger.info(f"Désinstallation des paquets : {', '.join(packages)}")
        if "apt" in self.pkg_mgr:
            cmd = ["apt-get", "purge", "-y"] + packages
        elif "dnf" in self.pkg_mgr:
            cmd = ["dnf", "remove", "-y"] + packages
        elif "yum" in self.pkg_mgr:
            cmd = ["yum", "remove", "-y"] + packages
        elif "zypper" in self.pkg_mgr:
            cmd = ["zypper", "--non-interactive", "remove"] + packages
        else:
            cmd = [self.pkg_mgr, "remove", "-y"] + packages

        self._run_cmd(cmd, check=False)

    def start_service(self, service_name: str, enable: bool = True) -> None:
        """Démarre et active un service systemd."""
        if enable:
            self._run_cmd(["systemctl", "enable", "--now", service_name], check=False)
        else:
            self._run_cmd(["systemctl", "start", service_name], check=False)

    def stop_service(self, service_name: str, disable: bool = True) -> None:
        """Arrête et désactive un service systemd."""
        if disable:
            self._run_cmd(["systemctl", "disable", "--now", service_name], check=False)
        else:
            self._run_cmd(["systemctl", "stop", service_name], check=False)

    def is_service_active(self, service_name: str) -> bool:
        """Vérifie si un service systemd est actif."""
        res = subprocess.run(["systemctl", "is-active", service_name], capture_output=True, text=True)
        return res.stdout.strip() == "active"
