import json

from .chat import ChatError
from .chat2 import chat
from .config import NUM_CTX
from .structs import Message
from .tools import call_tool


async def process_tool_calls(tool_calls, stream_tool_call, ask_permission):
    results = []
    for tc in tool_calls:
        args = json.loads(tc["function"]["arguments"])
        stream_tool_call(tc["function"]["name"], args)
        result = await call_tool(
            tc["function"]["name"],
            args,
            ask_permission,
        )
        results.append(Message("tool", result, tool_name=tc["function"]["name"]))
    return results


async def harness(
    model,
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
            try:
                chunks = chat(model, conversation, log)
                used = 0
                reply = Message("assistant", "")
                tool_results = []
                for chunk, usage in chunks:
                    used += usage
                    if len(chunk.thinking) > 0:
                        stream_thinking(chunk.thinking)
                    if len(chunk.content) > 0:
                        stream_response(chunk.content)
                        reply.content += chunk.content
                    reply.tool_calls.extend(chunk.tool_calls)
                    tool_results.extend(
                        await process_tool_calls(
                            chunk.tool_calls, stream_tool_call, ask_permission
                        )
                    )

            except ChatError as e:
                print(f"ChatError: {e}")
                break

            conversation.append(reply)

            context_info(used, NUM_CTX)

            if len(tool_results) == 0:
                break

            conversation.extend(tool_results)
    except KeyboardInterrupt:
        print("\n(interrupted)")
    commit()
