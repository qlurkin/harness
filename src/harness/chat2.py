import json
from collections.abc import Generator
from dataclasses import asdict
from typing import Any

from litellm import completion, get_model_info, token_counter
from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
from litellm.types.utils import ChatCompletionDeltaToolCall

from harness.structs import Message
from harness.tools import get_tools


def chat(
    model_id: str,
    messages: list[Message],
    log,
) -> Generator[tuple[Message, int]]:

    raw_messages = [asdict(m) for m in messages]

    # Estimation du contexte avant l'appel
    context_tokens = token_counter(
        model=model_id,
        messages=raw_messages,
    )

    # Limite du modèle
    model_info = get_model_info(model_id)
    context_limit = model_info.get("max_input_tokens")

    if context_limit is not None and context_tokens >= context_limit:
        raise ValueError(f"Context limit exceeded: {context_tokens}/{context_limit}")

    stream = completion(
        model=model_id,
        api_base="http://localhost:11434",
        messages=raw_messages,
        tools=get_tools(),
        tool_choice="auto",
        stream=True,
        stream_options={"include_usage": True},
    )

    assert isinstance(stream, CustomStreamWrapper)

    context_tokens = 0
    tool_calls: dict[int, dict[str, Any]] = {}

    for chunk in stream:
        log(chunk)
        usage = getattr(chunk, "usage", None)
        if usage:
            context_tokens = usage.prompt_tokens

        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta

        if delta.content:
            yield (
                Message(role="assistant", content=delta.content),
                context_tokens,
            )

        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning:
            yield (
                Message(role="assistant", content="", thinking=reasoning),
                context_tokens,
            )

        for tc in delta.tool_calls or []:
            assert isinstance(tc, ChatCompletionDeltaToolCall)

            index = tc.index

            if index not in tool_calls:
                tool_calls[index] = {
                    "id": "",
                    "type": "function",
                    "function": {
                        "name": "",
                        "arguments": "",
                    },
                }

            current = tool_calls[index]

            if tc.id:
                current["id"] = tc.id

            if tc.function:
                if tc.function.name:
                    current["function"]["name"] += tc.function.name

                if tc.function.arguments:
                    current["function"]["arguments"] += tc.function.arguments

    # for tc in tool_calls.values():
    #     tc["function"]["arguments"] = json.loads(tc["function"]["arguments"])

    if tool_calls:
        yield (
            Message(
                role="assistant",
                content="",
                tool_calls=[tool_calls[i] for i in sorted(tool_calls)],
            ),
            context_tokens,
        )

    yield (
        Message(role="assistant", content=""),
        context_tokens,
    )
