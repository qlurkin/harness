import json
import uuid
from collections.abc import AsyncGenerator

from ollama import AsyncClient, Client

from harness.config import NUM_CTX
from harness.message import Message

provider = "ollama"
HOST = "http://localhost:11434"


def list_models() -> list[str]:
    return [f"{provider}/{m.model}" for m in Client(host=HOST).list().models if m.model]


def get_context_limit(model: str) -> int:
    # Ollama only uses the context size we ask for (num_ctx).
    return NUM_CTX


def _think(model: str, effort: str):
    if effort == "default":
        return None
    if effort == "none":
        return False
    if "gpt-oss" in model:  # only supports levels
        return effort if effort in ("low", "medium", "high") else "high" if effort in ("xhigh", "max") else "low"
    return True


def _convert(messages: list[dict]) -> list[dict]:
    out = []
    for m in messages:
        msg = {"role": m["role"], "content": m.get("content") or ""}
        if m.get("tool_calls"):
            msg["tool_calls"] = [
                {
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": json.loads(tc["function"]["arguments"] or "{}"),
                    }
                }
                for tc in m["tool_calls"]
            ]
        if m["role"] == "tool":
            msg["tool_name"] = m.get("name", "")
        out.append(msg)
    return out


async def chat(
    model: str,
    effort: str,
    messages: list[dict],
    tools: list[dict] | None = None,
) -> AsyncGenerator[tuple[Message, int]]:
    stream = await AsyncClient(host=HOST).chat(
        model=model,
        messages=_convert(messages),
        tools=tools or None,
        think=_think(model, effort),
        stream=True,
        options={"num_ctx": NUM_CTX},
    )

    used = 0
    async for chunk in stream:
        if chunk.prompt_eval_count:
            used = chunk.prompt_eval_count
        msg = chunk.message

        if msg.thinking:
            yield Message("assistant", thinking=msg.thinking), 0
        if msg.content:
            yield Message("assistant", msg.content), 0
        if msg.tool_calls:
            calls = [
                {
                    "id": f"call_{uuid.uuid4().hex[:24]}",
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": json.dumps(dict(tc.function.arguments)),
                    },
                }
                for tc in msg.tool_calls
            ]
            yield Message("assistant", tool_calls=calls), 0

    yield Message("assistant"), used
