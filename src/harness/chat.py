from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from litellm import acompletion, completion, get_model_info, token_counter
from litellm.litellm_core_utils.streaming_handler import CustomStreamWrapper
from litellm.types.utils import ChatCompletionDeltaToolCall, ModelResponse

from harness.config import NUM_CTX
from harness.providers import get_api_base
from harness.system_prompt import system_prompt
from harness.tools import get_tools


@dataclass
class Message:
    role: str = "user"
    content: str = ""
    thinking: str = ""
    tool_calls: list = field(default_factory=list)
    tool_call_id: str = ""
    tool_name: str = ""
    thinking_blocks: list = field(default_factory=list)
    used: int = 0


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
    if len(msg.thinking_blocks) > 0:
        res["thinking_blocks"] = msg.thinking_blocks
    return res


def get_context_limit(model_id) -> int:
    model_info = get_model_info(model_id)
    context_limit = model_info.get("max_input_tokens")
    if context_limit is None:
        return NUM_CTX
    return context_limit


class ContextLimitExceeded(Exception):
    pass


def is_anthropic_model(model_id):
    return model_id.split("/")[1].startswith("claude")


async def chat(
    model_id: str,
    effort: str,
    messages: list[Message],
    log: Callable[[str], Awaitable],
) -> AsyncGenerator[tuple[Message, int]]:

    raw_messages = [dump_message(m) for m in messages]

    # with open("raw_messages.json", "w") as file:
    #     json.dump(raw_messages, file, indent=4, ensure_ascii=False)

    message_tokens = token_counter(
        model=model_id,
        messages=raw_messages,
    )

    context_limit = get_context_limit(model_id)

    if context_limit is not None and message_tokens >= context_limit:
        raise ContextLimitExceeded(
            f"Context limit exceeded: {message_tokens}/{context_limit}"
        )

    api_base = get_api_base(model_id.split("/")[0])

    params = {
        "model": model_id,
        "api_base": api_base,
        "messages": raw_messages,
        "tools": get_tools(),
        "tool_choice": "auto",
        "stream": True,
        "stream_options": {"include_usage": True},
        "reasoning_effort": effort,
    }

    if is_anthropic_model(model_id):
        params["thinking"] = {"type": "enabled", "budget_tokens": 1024}

    stream = await acompletion(**params)

    assert isinstance(stream, CustomStreamWrapper)

    context_tokens = 0
    tool_calls: dict[int, dict[str, Any]] = {}

    async for chunk in stream:
        # log(chunk)
        usage = getattr(chunk, "usage", None)
        if usage:
            context_tokens = max(
                message_tokens,
                usage.prompt_tokens,
            )

        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta

        if delta.content:
            yield (
                Message(role="assistant", content=delta.content),
                context_tokens,
            )

        thinking = getattr(delta, "reasoning_content", None)
        if thinking:
            thinking_blocks = getattr(delta, "thinking_blocks", [])
            yield (
                Message(
                    role="assistant",
                    content="",
                    thinking=thinking,
                    thinking_blocks=thinking_blocks,
                ),
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


SUMMARY_INSTRUCTION = """\
Summarize the conversation above so that work can continue from your summary alone. Include:
- The user's goals and requests, and the decisions made along the way.
- Every file touched (read, created, edited) and how each one changed.
- Important tool calls and their results (commands run, outputs, errors, test results).
- Any unfinished work, open questions, and the next steps.
Be concise but specific (paths, names, values). Do not call tools. Output only the summary."""


def summarize(model_id, messages: list[Message]) -> str:
    raw = [dump_message(m) for m in messages[1:]]
    raw.append({"role": "user", "content": SUMMARY_INSTRUCTION})

    params = {
        "model": model_id,
        "api_base": get_api_base(model_id.split("/")[0]),
        "messages": raw,
        "stream": False,
    }

    response = completion(**params)

    assert isinstance(response, ModelResponse)

    summary = response.choices[0].message.content
    if not summary or not summary.strip():
        raise ValueError("empty summary")
    return summary.strip()


SUMMARY_HEADER = (
    "[Context summary - earlier messages were compacted to save space. "
    "File contents mentioned below may be stale, re-read files before editing.]"
)


def compact(conversation: list[Message], summary: str, keep: int = 6) -> list[Message]:
    start = max(len(conversation) - keep, 1)
    while start > 1 and conversation[start].role == "tool":
        start -= 1
    return [
        Message("system", system_prompt()),
        Message("user", f"{SUMMARY_HEADER}\n\n{summary}"),
        *conversation[start:],
    ]
