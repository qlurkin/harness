import os
from typing import Any

SAFE = True

description = {
    "type": "function",
    "function": {
        "name": "list_files",
        "description": "Recursively list files under a directory. Use this to discover what exists before reading files.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory to list; defaults to the current directory",
                }
            },
        },
    },
}


def function(args: dict[str, Any]):
    dir = args.get("path", ".")
    if dir == "":
        dir = "."

    lines = []

    for root, folders, files in os.walk(dir):
        folders[:] = [f for f in folders if f not in {".git", "__pycache__", ".venv"}]
        for file in files:
            lines.append(os.path.relpath(os.path.join(root, file), dir))

    return "\n".join(lines)
