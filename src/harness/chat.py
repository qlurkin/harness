from collections.abc import Generator
from typing import Any

from litellm import completion, get_model_info, token_counter
from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
from litellm.types.utils import ChatCompletionDeltaToolCall

from harness.config import NUM_CTX
from harness.providers import get_api_base
from harness.structs import Message
from harness.tools import get_tools


def dump_message(msg: Message):
    res = {"role": msg.role}
    if len(msg.content) > 0:
        res["content"] = msg.content
    else:
        res["content"] = None
    if len(msg.tool_calls) > 0:
        res["tool_calls"] = msg.tool_calls
    if len(msg.tool_call_id) > 0:
        res["tool_call_id"] = msg.tool_call_id
    if len(msg.tool_name) > 0:
        res["name"] = msg.tool_name
    return res


def get_context_limit(model_id) -> int:
    model_info = get_model_info(model_id)
    context_limit = model_info.get("max_input_tokens")
    if context_limit is None:
        return NUM_CTX
    return context_limit


class ContextLimitExceeded(Exception):
    pass


def chat(
    model_id: str,
    messages: list[Message],
    log,
) -> Generator[tuple[Message, int]]:

    raw_messages = [dump_message(m) for m in messages]

    # with open("raw_messages.json", "w") as file:
    #     json.dump(raw_messages, file, indent=4, ensure_ascii=False)

    context_tokens = token_counter(
        model=model_id,
        messages=raw_messages,
    )

    context_limit = get_context_limit(model_id)

    if context_limit is not None and context_tokens >= context_limit:
        raise ContextLimitExceeded(
            f"Context limit exceeded: {context_tokens}/{context_limit}"
        )

    api_base = get_api_base(model_id.split("/")[0])

    stream = completion(
        model=model_id,
        api_base=api_base,
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
        # log(chunk)
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
