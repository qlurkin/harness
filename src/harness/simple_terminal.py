from harness.harness import harness

from .config import MODEL
from .structs import Message
from .system_prompt import system_prompt
from .tools import Permission, get_registered_tools


async def simple_terminal() -> None:
    print(f"harness v0.5 — chatting with {MODEL} (ctrl-c to quit)")
    print(f"Loaded Tools: {', '.join(get_registered_tools())}")

    conversation: list[Message] = [Message("system", system_prompt())]
    last_write = None

    def commit():
        if last_write != "you":
            print()

    def write_response(content):
        nonlocal last_write
        if last_write != "response":
            commit()
            print("\nHarness:")
        last_write = "response"
        print(content, end="")

    def format_thinking(content):
        return f"\033[90m{content}\033[0m"

    def write_thinking(content):
        nonlocal last_write
        if last_write != "thinking":
            commit()
            print(format_thinking("\nTinking:"))
        last_write = "thinking"
        print(format_thinking(content), end="")

    def format_tool_call(content):
        return f"\033[33m{content}\033[0m"

    def write_tool_call(name, args):
        nonlocal last_write
        commit()
        print(format_tool_call(f"  ⚙{name}({args})"), end="")
        last_write = "tool_call"

    async def ask_permission(name) -> Permission:
        nonlocal last_write
        ans = input(f"allow {name}? [y]es once / [a]lways / [n]o\n")
        if ans.lower() == "y":
            return Permission.ALLOW
        if ans.lower() == "a":
            return Permission.ALWAYS
        return Permission.DENIED

    def context_info(used, total):
        nonlocal last_write
        commit()
        marker = ""
        if used > total * 8 / 10:
            marker = " ⚠ context nearly full"
        print(f"  [ctx {used}/{total}{marker}]", end="")
        last_write = "context_info"

    try:
        while True:
            msg = input("\nYou:\n")
            last_write = "you"
            conversation.append(Message("user", msg))

            await harness(
                MODEL,
                conversation,
                write_response,
                write_thinking,
                write_tool_call,
                ask_permission,
                context_info,
                commit,
            )

    except KeyboardInterrupt:
        write_response("Bye")
        commit()
