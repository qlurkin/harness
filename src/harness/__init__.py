from .chat import ChatError, chat
from .config import MODEL, NUM_CTX
from .structs import Message
from .system_prompt import system_prompt
from .tools import call_tool, print_tools


def main() -> None:
    print(f"harness v0.2 — chatting with {MODEL} (ctrl-c to quit)")
    print_tools()
    conversation: list[Message] = [Message("system", system_prompt())]

    try:
        while True:
            msg = input("\nYou: ")
            conversation.append(Message("user", msg))

            while True:
                try:
                    content_started = False
                    used = 0
                    reply = Message("assistant", "")
                    chunks = chat(conversation)
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
                        for tc in chunk.tool_calls:
                            print(f"  ⚙{tc.function.name}({tc.function.arguments})")
                            try:
                                result = call_tool(
                                    tc.function.name, tc.function.arguments
                                )
                            except KeyError:
                                result = f"error: unknown tool {tc.function.name}"
                            tool_results.append(
                                Message("tool", result, tool_name=tc.function.name)
                            )

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

    except KeyboardInterrupt:
        print("\n\nHarness: Bye")
