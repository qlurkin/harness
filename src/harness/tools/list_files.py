import os
from typing import Any

from ..structs import Tool, ToolFunction

description = Tool(
    "function",
    ToolFunction(
        "list_files",
        "Recursively list files under a directory. Use this to discover what exists before reading files.",
        {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory to list; defaults to the current directory",
                }
            },
        },
    ),
)


def function(args: dict[str, Any]):
    dir = args.get("path", ".")
    if dir == "":
        dir = "."

    lines = []

    for root, folders, files in os.walk(dir):
        folders[:] = [f for f in folders if f not in {".git", "__pycache__"}]
        for file in files:
            lines.append(os.path.relpath(os.path.join(root, file), dir))

    return "\n".join(lines)
