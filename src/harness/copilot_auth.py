"""GitHub Copilot authentication (device flow + short-lived session token).

The long-lived GitHub OAuth token is stored in ~/.config/harness/auth.json.
It is exchanged for a Copilot session token (~30 min) that is kept in memory.
"""

import asyncio
import threading
import time
from uuid import uuid4

import httpx

from harness.auth import load_auth, save_entry

CLIENT_ID = "Iv1.b507a08c87ecfe98"  # VS Code's Copilot client id
DEVICE_CODE_URL = "https://github.com/login/device/code"
ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
SESSION_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"
DEFAULT_API_BASE = "https://api.githubcopilot.com"

COPILOT_VERSION = "0.26.7"
KEY = "github_copilot"


class CopilotAuthError(Exception):
    pass


# ---------- storage ----------


def load_github_token() -> str | None:
    return load_auth().get(KEY, {}).get("access_token")


def save_github_token(token: str) -> None:
    save_entry(KEY, {"type": "oauth", "access_token": token})


# ---------- device flow ----------

_lock = threading.Lock()
_session: dict | None = None


def _github_headers() -> dict[str, str]:
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "editor-version": "vscode/1.95.0",
        "editor-plugin-version": f"copilot-chat/{COPILOT_VERSION}",
        "user-agent": f"GitHubCopilotChat/{COPILOT_VERSION}",
    }


def request_device_code() -> dict:
    """Step 1: returns {'device_code', 'user_code', 'verification_uri', ...}."""
    resp = httpx.post(
        DEVICE_CODE_URL,
        headers=_github_headers(),
        json={"client_id": CLIENT_ID, "scope": "read:user"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def poll_for_token(dev: dict, cancel: threading.Event | None = None) -> str:
    """Step 2 (blocking): wait for the user to authorize, store and return the token.

    Set `cancel` from another thread to abort.
    """
    global _session
    cancel = cancel or threading.Event()
    interval = dev.get("interval", 5)
    deadline = time.monotonic() + dev.get("expires_in", 900)

    with httpx.Client(headers=_github_headers(), timeout=30) as http:
        while time.monotonic() < deadline:
            if cancel.wait(interval):
                raise CopilotAuthError("Cancelled")
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
                with _lock:
                    _session = None
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
                "Not logged in to GitHub Copilot. Run: /login"
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
