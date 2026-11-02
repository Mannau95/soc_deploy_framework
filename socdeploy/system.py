"""Détection des caractéristiques système et de l'environnement d'exécution."""

import os
import sys
import socket
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger


class SystemInfo:
    """Informations sur la machine hôte."""

    def __init__(self):
        self.os_family = self._detect_os_family()
        self.distro_name = self._detect_distro_name()
        self.is_root = self._check_root()
        self.ram_mb = self._detect_ram_mb()
        self.cpu_count = os.cpu_count() or 1
        self.package_manager = self._detect_pkg_manager()
        self._docker_available: Optional[bool] = None

    def is_docker_available(self) -> bool:
        """Vérifie si Docker est installé et accessible avec cache et timeout rapide."""
        if self._docker_available is not None:
            return self._docker_available

        try:
            import docker
            client = docker.from_env(timeout=1.5)
            client.ping()
            self._docker_available = True
        except Exception:
            self._docker_available = False

        return self._docker_available

    def _detect_os_family(self) -> str:
        """Détecte la famille d'OS (debian, rhel, suse, arch, windows, etc.)."""
        if sys.platform == "win32":
            return "windows"
        if sys.platform == "darwin":
            return "darwin"

        os_release = Path("/etc/os-release")
        if os_release.exists():
            try:
                content = os_release.read_text().lower()
                if any(x in content for x in ["ubuntu", "debian", "kali", "mint", "raspbian"]):
                    return "debian"
                if any(x in content for x in ["rhel", "centos", "rocky", "almalinux", "fedora"]):
                    return "rhel"
                if any(x in content for x in ["suse", "sles", "opensuse"]):
                    return "suse"
                if "arch" in content or "manjaro" in content:
                    return "arch"
            except Exception as e:
                logger.warning(f"Impossible de lire /etc/os-release : {e}")

        # Fallback via les gestionnaires de paquets
        if shutil.which("apt") or shutil.which("apt-get"):
            return "debian"
        if shutil.which("dnf") or shutil.which("yum"):
            return "rhel"
        if shutil.which("zypper"):
            return "suse"
        if shutil.which("pacman"):
            return "arch"

        return "unknown"

    def _detect_distro_name(self) -> str:
        """Récupère le nom joli de la distribution."""
        if sys.platform == "win32":
            return f"Windows {sys.getwindowsversion().major}"

        os_release = Path("/etc/os-release")
        if os_release.exists():
            try:
                for line in os_release.read_text().splitlines():
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=", 1)[1].strip('"\'')
            except Exception:
                pass
        return sys.platform

    def _check_root(self) -> bool:
        """Vérifie si le script tourne avec les privilèges root."""
        try:
            return os.geteuid() == 0
        except AttributeError:
            return False

    def _detect_ram_mb(self) -> int:
        """Détecte la mémoire RAM totale en Mo."""
        if sys.platform != "win32":
            meminfo = Path("/proc/meminfo")
            if meminfo.exists():
                try:
                    for line in meminfo.read_text().splitlines():
                        if line.startswith("MemTotal:"):
                            parts = line.split()
                            kb = int(parts[1])
                            return kb // 1024
                except Exception:
                    pass
        # Fallback grossier (4Go par défaut si indétectable)
        return 4096

    def _detect_pkg_manager(self) -> Optional[str]:
        """Détecte la commande du gestionnaire de paquets natif."""
        for cmd in ["apt-get", "apt", "dnf", "yum", "zypper", "pacman"]:
            if shutil.which(cmd):
                return cmd
        return None

    def get_network_interfaces(self) -> List[str]:
        """Retourne la liste des interfaces réseau disponibles."""
        interfaces: List[str] = []
        if sys.platform != "win32":
            # Via /sys/class/net
            net_dir = Path("/sys/class/net")
            if net_dir.exists():
                for p in net_dir.iterdir():
                    name = p.name
                    if name != "lo" and not name.startswith("docker") and not name.startswith("veth") and not name.startswith("br-"):
                        interfaces.append(name)
        if not interfaces:
            # Essai via ip route
            try:
                res = subprocess.run(
                    "ip route show default | awk '{print $5}'",
                    shell=True, capture_output=True, text=True
                )
                iface = res.stdout.strip()
                if iface:
                    interfaces.append(iface)
            except Exception:
                pass

        if not interfaces:
            interfaces = ["eth0"]
        return list(dict.fromkeys(interfaces))

    def get_default_interface(self) -> str:
        """Retourne l'interface réseau par défaut."""
        ifaces = self.get_network_interfaces()
        return ifaces[0] if ifaces else "eth0"

    def is_port_free(self, port: int) -> bool:
        """Vérifie si un port TCP est disponible."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            # Vérifier sur 0.0.0.0 et 127.0.0.1
            res_local = s.connect_ex(('127.0.0.1', port))
            return res_local != 0

    def check_ports(self, ports: List[int]) -> List[int]:
        """Retourne la liste des ports qui sont occupés."""
        occupied = []
        for port in ports:
            if not self.is_port_free(port):
                occupied.append(port)
        return occupied

    def to_dict(self) -> Dict[str, Any]:
        return {
            "distro": self.distro_name,
            "os_family": self.os_family,
            "is_root": self.is_root,
            "ram_mb": self.ram_mb,
            "cpu_count": self.cpu_count,
            "pkg_manager": self.package_manager,
            "docker_available": self.is_docker_available(),
            "default_interface": self.get_default_interface(),
        }


# Instance globale réutilisable
system = SystemInfo()
