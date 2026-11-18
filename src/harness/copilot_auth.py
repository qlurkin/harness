"""GitHub Copilot authentication (device flow + short-lived session token).

The long-lived GitHub OAuth token is stored in ~/.config/harness/auth.json.
It is exchanged for a Copilot session token (~30 min) that is kept in memory.
"""

import asyncio
import json
import threading
import time
from pathlib import Path
from uuid import uuid4

import httpx

CLIENT_ID = "Iv1.b507a08c87ecfe98"  # VS Code's Copilot client id
DEVICE_CODE_URL = "https://github.com/login/device/code"
ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
SESSION_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"
DEFAULT_API_BASE = "https://api.githubcopilot.com"

COPILOT_VERSION = "0.26.7"
AUTH_PATH = Path.home() / ".config" / "harness" / "auth.json"
KEY = "github_copilot"


class CopilotAuthError(Exception):
    pass


# ---------- storage ----------


def _read_auth() -> dict:
    try:
        return json.loads(AUTH_PATH.read_text())
    except FileNotFoundError:
        return {}


def load_github_token() -> str | None:
    return _read_auth().get(KEY, {}).get("access_token")


def save_github_token(token: str) -> None:
    data = _read_auth()
    data[KEY] = {"type": "oauth", "access_token": token}
    AUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTH_PATH.write_text(json.dumps(data, indent=2))
    AUTH_PATH.chmod(0o600)


# ---------- device flow ----------


def _github_headers() -> dict[str, str]:
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "editor-version": "vscode/1.95.0",
        "editor-plugin-version": f"copilot-chat/{COPILOT_VERSION}",
        "user-agent": f"GitHubCopilotChat/{COPILOT_VERSION}",
    }


def login(print_fn=print) -> str:
    """Run the interactive device flow, store and return the GitHub token."""
    with httpx.Client(headers=_github_headers(), timeout=30) as http:
        resp = http.post(
            DEVICE_CODE_URL, json={"client_id": CLIENT_ID, "scope": "read:user"}
        )
        resp.raise_for_status()
        dev = resp.json()

        print_fn(f"Open {dev['verification_uri']} and enter the code: {dev['user_code']}")

        interval = dev.get("interval", 5)
        deadline = time.monotonic() + dev.get("expires_in", 900)

        while time.monotonic() < deadline:
            time.sleep(interval)
            resp = http.post(
                ACCESS_TOKEN_URL,
                json={
                    "client_id": CLIENT_ID,
                    "device_code": dev["device_code"],
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )
            resp.raise_for_status()
            body = resp.json()

            if "access_token" in body:
                save_github_token(body["access_token"])
                return body["access_token"]

            error = body.get("error")
            if error == "authorization_pending":
                continue
            if error == "slow_down":
                interval = body.get("interval", interval + 5)
                continue
            raise CopilotAuthError(f"{error}: {body.get('error_description', '')}")

    raise CopilotAuthError("Device code expired, please retry")


# ---------- session token ----------

_lock = threading.Lock()
_session: dict | None = None


def _session_valid(session: dict | None) -> bool:
    return session is not None and session["expires_at"] - 60 > time.time()


def get_session() -> dict:
    """Return {'token', 'expires_at', 'api_base'}; refresh when expired."""
    global _session
    with _lock:
        if _session_valid(_session):
            return _session  # type: ignore[return-value]

        github_token = load_github_token()
        if not github_token:
            raise CopilotAuthError(
                "Not logged in to GitHub Copilot. Run: harness connect_copilot"
            )

        headers = _github_headers() | {"authorization": f"token {github_token}"}
        resp = httpx.get(SESSION_TOKEN_URL, headers=headers, timeout=30)
        if resp.status_code in (401, 403):
            raise CopilotAuthError(
                f"GitHub token rejected ({resp.status_code}). Log in again."
            )
        resp.raise_for_status()
        body = resp.json()

        _session = {
            "token": body["token"],
            "expires_at": body["expires_at"],
            "api_base": body.get("endpoints", {}).get("api", DEFAULT_API_BASE),
        }
        return _session


async def aget_session() -> dict:
    return await asyncio.to_thread(get_session)


def api_headers() -> dict[str, str]:
    return {
        "copilot-integration-id": "vscode-chat",
        "editor-version": "vscode/1.95.0",
        "editor-plugin-version": f"copilot-chat/{COPILOT_VERSION}",
        "user-agent": f"GitHubCopilotChat/{COPILOT_VERSION}",
        "openai-intent": "conversation-panel",
        "x-github-api-version": "2025-04-01",
        "x-request-id": str(uuid4()),
    }
