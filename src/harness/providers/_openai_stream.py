"""Shared helper: turn an OpenAI-style chunk stream into (Message, used) pairs.

Works with chunks from the `openai` SDK.
"""

from collections.abc import AsyncGenerator, AsyncIterable
from typing import Any

from harness.message import Message


async def consume_stream(
    stream: AsyncIterable[Any],
) -> AsyncGenerator[tuple[Message, int]]:
    tool_calls: dict[int, dict[str, Any]] = {}
    used = 0

    async for chunk in stream:
        usage = getattr(chunk, "usage", None)
        if usage:
            used = usage.prompt_tokens

        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta

        if delta.content:
            yield Message("assistant", delta.content), 0

        thinking = getattr(delta, "reasoning_content", None) or getattr(
            delta, "reasoning", None
        )
        if thinking:
            blocks = getattr(delta, "thinking_blocks", None) or []
            yield Message("assistant", thinking=thinking, thinking_blocks=blocks), 0

        for tc in delta.tool_calls or []:
            current = tool_calls.setdefault(
                tc.index,
                {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
            )
            if tc.id:
                current["id"] = tc.id
            if tc.function:
                if tc.function.name:
                    current["function"]["name"] += tc.function.name
                if tc.function.arguments:
                    current["function"]["arguments"] += tc.function.arguments

    if tool_calls:
        yield (
            Message("assistant", tool_calls=[tool_calls[i] for i in sorted(tool_calls)]),
            0,
        )

    yield Message("assistant"), used
