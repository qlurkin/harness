from .chat import ChatError, chat
from .config import MODEL, NUM_CTX
from .structs import Message
from .system_prompt import system_prompt
from .tools import call_tool, print_tools


def process_tool_calls(tool_calls):
    results = []
    for tc in tool_calls:
        print(f"  ⚙{tc.function.name}({tc.function.arguments})")
        result = call_tool(tc.function.name, tc.function.arguments)
        results.append(Message("tool", result, tool_name=tc.function.name))
    return results


def harness(conversation):
    while True:
        try:
            chunks = chat(conversation)
            content_started = False
            used = 0
            reply = Message("assistant", "")
            tool_results = []
            for chunk, usage in chunks:
                used += usage
                if len(chunk.content) > 0:
                    if not content_started:
                        print("\nHarness:")
                        content_started = True
                    print(chunk.content, end="")
                    reply.content += chunk.content
                reply.tool_calls.extend(chunk.tool_calls)
                tool_results.extend(process_tool_calls(chunk.tool_calls))
            if content_started:
                print()

        except ChatError as e:
            print(f"ChatError: {e}")
            break

        conversation.append(reply)

        marker = ""
        if used > NUM_CTX * 8 / 10:
            marker = " ⚠ context nearly full"
        print(f"  [ctx {used}/{NUM_CTX}{marker}]")

        if len(tool_results) == 0:
            break

        conversation.extend(tool_results)


def main() -> None:
    print(f"harness v0.2 — chatting with {MODEL} (ctrl-c to quit)")
    print_tools()
    conversation: list[Message] = [Message("system", system_prompt())]

    try:
        while True:
            msg = input("\nYou: ")
            conversation.append(Message("user", msg))

            harness(conversation)

    except KeyboardInterrupt:
        print("\n\nHarness: Bye")
