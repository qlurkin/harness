"""Set the OpenRouter API key: harness connect_openrouter"""

import sys
from getpass import getpass

from harness.auth import AUTH_PATH, save_entry


def main() -> None:
    key = getpass("OpenRouter API key: ").strip()
    if not key:
        sys.exit("Empty key, nothing saved.")
    save_entry("openrouter", {"type": "api_key", "key": key})
    print(f"Key saved in {AUTH_PATH}")
