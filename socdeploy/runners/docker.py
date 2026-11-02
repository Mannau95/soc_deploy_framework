"""Gestionnaire Docker Compose."""

import subprocess
import shutil
from pathlib import Path
from typing import List, Optional
from loguru import logger


class DockerComposeRunner:
    """Pilote Docker Compose (v2 plugin ou v1 binaire)."""

    def __init__(self):
        self.cmd = self._detect_compose_cmd()

    def _detect_compose_cmd(self) -> List[str]:
        """Détecte la commande docker compose disponible."""
        # 1. Tester docker compose (v2)
        if shutil.which("docker"):
            try:
                res = subprocess.run(
                    ["docker", "compose", "version"],
                    capture_output=True, text=True, check=False
                )
                if res.returncode == 0:
                    return ["docker", "compose"]
            except Exception:
                pass

        # 2. Tester docker-compose (v1)
        if shutil.which("docker-compose"):
            try:
                res = subprocess.run(
                    ["docker-compose", "version"],
                    capture_output=True, text=True, check=False
                )
                if res.returncode == 0:
                    return ["docker-compose"]
            except Exception:
                pass

        raise RuntimeError(
            "Ni 'docker compose' (v2) ni 'docker-compose' (v1) n'ont été trouvés sur la machine."
        )

    def up(self, compose_dir: Path) -> None:
        """Lance les conteneurs en arrière-plan."""
        compose_file = compose_dir / "docker-compose.yml"
        if not compose_file.exists():
            raise FileNotFoundError(f"Fichier docker-compose.yml introuvable dans {compose_dir}")

        cmd = self.cmd + ["up", "-d", "--remove-orphans"]
        logger.info(f"Exécution : {' '.join(cmd)} dans {compose_dir}")

        res = subprocess.run(
            cmd,
            cwd=str(compose_dir),
            capture_output=True,
            text=True
        )
        if res.returncode != 0:
            logger.error(f"Erreur Docker Compose up : {res.stderr}")
            raise RuntimeError(f"Échec de docker compose up :\n{res.stderr}")

        if res.stdout:
            logger.debug(res.stdout)
        logger.info("Conteneurs démarrés avec succès.")

    def down(self, compose_dir: Path, remove_volumes: bool = False) -> None:
        """Arrête et supprime les conteneurs."""
        compose_file = compose_dir / "docker-compose.yml"
        if not compose_file.exists():
            logger.warning(f"Pas de docker-compose.yml dans {compose_dir}, arrêt ignoré.")
            return

        cmd = self.cmd + ["down"]
        if remove_volumes:
            cmd.append("-v")

        logger.info(f"Arrêt des conteneurs : {' '.join(cmd)} dans {compose_dir}")
        res = subprocess.run(
            cmd,
            cwd=str(compose_dir),
            capture_output=True,
            text=True
        )
        if res.returncode != 0:
            logger.warning(f"Erreur lors de docker compose down : {res.stderr}")
        else:
            logger.info("Conteneurs arrêtés et nettoyés.")

    def ps(self, compose_dir: Path) -> str:
        """Retourne l'état des conteneurs."""
        res = subprocess.run(
            self.cmd + ["ps"],
            cwd=str(compose_dir),
            capture_output=True,
            text=True
        )
        return res.stdout if res.returncode == 0 else ""

    def logs(self, compose_dir: Path, tail: int = 50) -> str:
        """Retourne les derniers logs des conteneurs."""
        res = subprocess.run(
            self.cmd + ["logs", f"--tail={tail}"],
            cwd=str(compose_dir),
            capture_output=True,
            text=True
        )
        return res.stdout if res.returncode == 0 else ""
