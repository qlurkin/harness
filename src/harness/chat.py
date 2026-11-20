from collections.abc import AsyncGenerator, Awaitable, Callable

from harness.message import Message, dump_message
from harness.providers import (
    count_tokens,
    get_context_limit,
    get_provider,
    split_model_id,
)
from harness.tools import get_tools

__all__ = ["ContextLimitExceeded", "Message", "chat", "compact", "summarize"]


class ContextLimitExceeded(Exception):
    pass


async def chat(
    model_id: str,
    effort: str,
    messages: list[Message],
    log: Callable[[str], Awaitable],
    tools: list[dict] | None = None,
) -> AsyncGenerator[tuple[Message, int]]:
    raw_messages = [dump_message(m) for m in messages]

    estimate = count_tokens(model_id, raw_messages)
    context_limit = get_context_limit(model_id)
    if estimate >= context_limit:
        raise ContextLimitExceeded(
            f"Context limit exceeded: {estimate}/{context_limit}"
        )

    _, model = split_model_id(model_id)
    stream = get_provider(model_id).chat(
        model, effort, raw_messages, get_tools() if tools is None else tools
    )
    async for message, used in stream:
        yield message, max(used, estimate) if used else 0


SUMMARY_INSTRUCTION = """\
Summarize the conversation above so that work can continue from your summary alone. Include:
- The user's goals and requests, and the decisions made along the way.
- Every file touched (read, created, edited) and how each one changed.
- Important tool calls and their results (commands run, outputs, errors, test results).
- Any unfinished work, open questions, and the next steps.
Be concise but specific (paths, names, values). Do not call tools. Output only the summary."""


async def summarize(model_id, messages: list[Message]) -> str:
    raw = [*messages[1:], Message("user", SUMMARY_INSTRUCTION)]

    async def noop(_):
        pass

    parts = []
    async for chunk, _ in chat(model_id, "default", raw, noop, tools=[]):
        parts.append(chunk.content)
    summary = "".join(parts).strip()
    if not summary:
        raise ValueError("empty summary")
    return summary
