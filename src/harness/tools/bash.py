from subprocess import PIPE, STDOUT, run
from typing import Any

from ..structs import Tool, ToolFunction

description = Tool(
    "function",
    ToolFunction(
        "bash",
        "Execute a shell command and return its combined stdout and stderr. Use for running tests, builds, git, and anything without a dedicated tool.",
        {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run"}
            },
            "required": ["command"],
        },
    ),
)


def function(args: dict[str, Any]):
    try:
        cmd = args["command"]
    except KeyError:
        return "error: bash requires a string 'command' argument"

    res = run(
        ["bash", "-c", cmd],
        stdout=PIPE,
        stderr=STDOUT,
        text=True,
        check=False,
    )

    if len(res.stdout) == 0:
        out = "(no output)"
    else:
        out = res.stdout

    if res.returncode != 0:
        out += f"\nerror: return code {res.returncode}"

    return out
