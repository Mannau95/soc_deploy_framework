"""Fonctions utilitaires communes pour SOC Deploy Framework."""

import os
import shutil
import subprocess
import secrets
import string
from pathlib import Path
from typing import List, Optional, Dict, Any


def run_command(
    cmd: List[str],
    cwd: Optional[str] = None,
    with_sudo: bool = True,
    check: bool = True
) -> subprocess.CompletedProcess:
    """Exécute une commande shell avec sudo automatique si nécessaire sous Linux."""
    final_cmd = list(cmd)
    if with_sudo and os.name != "nt" and os.geteuid() != 0 and shutil.which("sudo"):
        final_cmd = ["sudo"] + final_cmd

    return subprocess.run(
        final_cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check
    )


def format_bytes(num_bytes: int) -> str:
    """Formate une taille d'octets de façon lisible."""
    for unit in ["o", "Ko", "Mo", "Go", "To"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} Po"


def generate_secure_password(length: int = 16) -> str:
    """Génère un mot de passe cryptographiquement robuste et aléatoire."""
    if length < 12:
        length = 12

    # Assurer au moins 1 majuscule, 1 minuscule, 1 chiffre, 1 caractère spécial
    uppers = string.ascii_uppercase
    lowers = string.ascii_lowercase
    digits = string.digits
    specials = "!@#$%^&*()-_=+"
    all_chars = uppers + lowers + digits + specials

    password = [
        secrets.choice(uppers),
        secrets.choice(lowers),
        secrets.choice(digits),
        secrets.choice(specials),
    ]
    password += [secrets.choice(all_chars) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


def save_secrets_env(deploy_dir: Path, credentials: Dict[str, Any]) -> Path:
    """Sauvegarde les mots de passe et clés secrètes dans un fichier secrets.env sécurisé (0600)."""
    deploy_dir.mkdir(parents=True, exist_ok=True)
    secrets_file = deploy_dir / "secrets.env"

    lines = [
        "# SOC Deploy Framework — Secrets et identifiants de la stack",
        "# ATTENTION: Ce fichier contient des identifiants sensibles. Ne pas versionner.",
        ""
    ]
    for key, val in credentials.items():
        if isinstance(val, dict):
            for sub_k, sub_v in val.items():
                if any(x in sub_k.lower() for x in ["pass", "secret", "key", "token"]):
                    lines.append(f"{key.upper()}_{sub_k.upper()}='{sub_v}'")
        elif any(x in key.lower() for x in ["pass", "secret", "key", "token"]):
            lines.append(f"{key.upper()}='{val}'")

    secrets_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if os.name != "nt":
        try:
            os.chmod(secrets_file, 0o600)
        except Exception:
            pass
    return secrets_file
