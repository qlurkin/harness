from collections.abc import AsyncGenerator

from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper

from harness.message import Message
from harness.providers._openai_stream import consume_stream

provider = "github_copilot"


def list_models():
    models = [
        "gpt-5.3-codex",
        "claude-haiku-5.5",
        "claude-sonnet-5.5",
        "claude-sonnet-5",
        "claude-haiku-4.5",
        "gemini-3.8-flash",
        "gpt-5.6-luna",
        "gpt-5.6-terra",
        "gpt-6.1-terra",
        "gpt-6-luna",
        "kimi-k3",
        "mai-code-1.1-flash",
    ]

    return [f"{provider}/{m}" for m in models]


def get_context_limit(model: str):
    from litellm import get_model_info

    return get_model_info(f"{provider}/{model}").get("max_input_tokens")


def count_tokens(model: str, messages: list[dict]) -> int:
    from litellm import token_counter

    return token_counter(model=f"{provider}/{model}", messages=messages)


async def chat(
    model: str,
    effort: str,
    messages: list[dict],
    tools: list[dict] | None = None,
) -> AsyncGenerator[tuple[Message, int]]:
    from litellm import acompletion

    params = {
        "model": f"{provider}/{model}",
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        "reasoning_effort": effort,
        "drop_params": True,
    }
    if tools:
        params["tools"] = tools
        params["tool_choice"] = "auto"
    if model.startswith("claude"):
        params["thinking"] = {"type": "enabled", "budget_tokens": 1024}

    stream = await acompletion(**params)
    assert isinstance(stream, CustomStreamWrapper)
    async for item in consume_stream(stream):
        yield item
