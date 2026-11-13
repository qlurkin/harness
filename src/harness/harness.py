import json

from .chat import Message, chat
from .tools import call_tool


async def process_tool_calls(tool_calls, stream_tool_call, ask_permission):
    results = []
    for tc in tool_calls:
        if len(tc["function"]["arguments"]) > 0:
            args = json.loads(tc["function"]["arguments"])
        else:
            args = {}
        stream_tool_call(tc["function"]["name"], args)
        result = await call_tool(
            tc["function"]["name"],
            args,
            ask_permission,
        )
        results.append(
            Message(
                "tool", result, tool_call_id=tc["id"], tool_name=tc["function"]["name"]
            )
        )
    return results


async def harness(
    model,
    effort,
    conversation,
    stream_response,
    stream_thinking,
    stream_tool_call,
    ask_permission,
    context_info,
    commit,
    log,
):
    try:
        while True:
            chunks = chat(model, effort, conversation, log)
            used = 0
            reply = Message("assistant", "")
            tool_results = []
            for chunk, usage in chunks:
                used += usage
                if len(chunk.thinking) > 0:
                    stream_thinking(chunk.thinking)
                    reply.thinking += chunk.thinking
                    reply.thinking_blocks.extend(chunk.thinking_blocks)
                if len(chunk.content) > 0:
                    stream_response(chunk.content)
                    reply.content += chunk.content
                reply.tool_calls.extend(chunk.tool_calls)

            conversation.append(reply)

            context_info(used)

            if len(reply.tool_calls) == 0:
                break

            conversation.extend(
                await process_tool_calls(
                    reply.tool_calls, stream_tool_call, ask_permission
                )
            )
    except KeyboardInterrupt:
        print("\n(interrupted)")
    commit()
