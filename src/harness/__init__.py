from .chat import ChatError, chat
from .config import MODEL
from .structs import Message
from .tools import call_tool, print_tools


def main() -> None:
    print(f"harness v0.2 — chatting with {MODEL} (ctrl-c to quit)")
    print_tools()
    conversation: list[Message] = []

    try:
        while True:
            msg = input("\nYou: ")
            conversation.append(Message("user", msg))

            while True:
                try:
                    reply = chat(conversation)
                except ChatError as e:
                    print(f"ChatError: {e}")
                    break

                conversation.append(reply)

                if len(reply.tool_calls) == 0:
                    print(f"\nHarness:\n{reply.content}")
                    break

                for tc in reply.tool_calls:
                    print(f"  ⚙{tc.function.name}({tc.function.arguments})")
                    try:
                        result = call_tool(tc.function.name, tc.function.arguments)
                    except KeyError:
                        result = f"error: unknown tool {tc.function.name}"
                    conversation.append(
                        Message("tool", result, tool_name=tc.function.name)
                    )
    except KeyboardInterrupt:
        print("\n\nHarness: Bye")
