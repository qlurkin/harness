"""GitHub Copilot, via the openai SDK against the Copilot API."""

import httpx
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI

from harness.message import Message
from harness import copilot_auth as auth
from harness.providers._openai_stream import consume_stream

provider = "github_copilot"

_context_limits: dict[str, int] = {}


def _fetch_models() -> list[dict]:
    session = auth.get_session()
    resp = httpx.get(
        f"{session['api_base']}/models",
        headers=auth.api_headers() | {"authorization": f"Bearer {session['token']}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def list_models() -> list[str]:
    if not auth.load_github_token():
        return []  # not logged in: harness connect_copilot

    try:
        data = _fetch_models()
    except (httpx.HTTPError, auth.CopilotAuthError) as e:
        print(f"Copilot: cannot list models: {e}")
        return []

    models = []
    for m in data:
        caps = m.get("capabilities", {})
        endpoints = m.get("supported_endpoints")
        if not m.get("model_picker_enabled", True):
            continue
        if caps.get("type") != "chat" or not caps.get("supports", {}).get("tool_calls"):
            continue
        if endpoints is not None and "/chat/completions" not in endpoints:
            continue  # e.g. codex models, /responses only

        limits = caps.get("limits", {})
        limit = limits.get("max_prompt_tokens") or limits.get("max_context_window_tokens")
        if limit:
            _context_limits[m["id"]] = limit
        models.append(f"{provider}/{m['id']}")
    return models


def get_context_limit(model: str) -> int | None:
    return _context_limits.get(model)


async def chat(
    model: str,
    effort: str,
    messages: list[dict],
    tools: list[dict] | None = None,
) -> AsyncGenerator[tuple[Message, int]]:
    session = await auth.aget_session()
    client = AsyncOpenAI(
        base_url=session["api_base"],
        api_key=session["token"],
        default_headers=auth.api_headers(),
    )

    kwargs: dict = {}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if effort in ("minimal", "low", "medium", "high"):
        kwargs["reasoning_effort"] = effort

    stream = await client.chat.completions.create(
        model=model,
        messages=[{k: v for k, v in m.items() if k != "thinking_blocks"} for m in messages],
        stream=True,
        stream_options={"include_usage": True},
        **kwargs,
    )
    async for item in consume_stream(stream):
        yield item
