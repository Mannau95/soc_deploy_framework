"""Tests pour les fonctions utilitaires et de sécurité."""

import string
from pathlib import Path
from socdeploy.utils import generate_secure_password, save_secrets_env, format_bytes


def test_generate_secure_password():
    pwd1 = generate_secure_password(16)
    pwd2 = generate_secure_password(16)

    assert len(pwd1) == 16
    assert pwd1 != pwd2

    has_upper = any(c in string.ascii_uppercase for c in pwd1)
    has_lower = any(c in string.ascii_lowercase for c in pwd1)
    has_digit = any(c in string.digits for c in pwd1)
    has_special = any(c in "!@#$%^&*()-_=+" for c in pwd1)

    assert has_upper and has_lower and has_digit and has_special


def test_save_secrets_env(tmp_path):
    creds = {
        "wazuh": {
            "username": "admin",
            "password": "SecretPassword123!"
        },
        "thehive": {
            "api_key": "thehive_token_xyz"
        }
    }
    secrets_file = save_secrets_env(tmp_path, creds)
    assert secrets_file.exists()
    content = secrets_file.read_text(encoding="utf-8")
    assert "WAZUH_PASSWORD='SecretPassword123!'" in content
    assert "THEHIVE_API_KEY='thehive_token_xyz'" in content


def test_format_bytes():
    assert "1.0 Ko" in format_bytes(1024)
    assert "1.0 Mo" in format_bytes(1024 * 1024)
