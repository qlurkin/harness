"""Credentials storage: ~/.config/harness/auth.json"""

import json

from harness.config import CONFIG_PATH

AUTH_PATH = CONFIG_PATH / "auth.json"


def load_auth() -> dict:
    try:
        return json.loads(AUTH_PATH.read_text())
    except FileNotFoundError:
        return {}


def save_entry(name: str, entry: dict) -> None:
    data = load_auth()
    data[name] = entry
    AUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTH_PATH.write_text(json.dumps(data, indent=2))
    AUTH_PATH.chmod(0o600)
