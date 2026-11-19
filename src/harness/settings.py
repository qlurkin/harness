"""User settings: ~/.config/harness/settings.json"""

import json
from pathlib import Path
from typing import Any

SETTINGS_PATH = Path.home() / ".config" / "harness" / "settings.json"


def load_settings() -> dict[str, Any]:
    try:
        return json.loads(SETTINGS_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_setting(key: str, value: Any) -> None:
    data = load_settings()
    data[key] = value
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(data, indent=2))
