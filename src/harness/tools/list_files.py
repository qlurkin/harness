import os
from pathlib import Path
from typing import Any

from harness.config import ROOT

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

    dir = Path(dir).resolve()

    if not dir.is_relative_to(ROOT):
        return "error: 'path' is not inside the project"

    lines = []

    for root, folders, files in os.walk(dir):
        folders[:] = [f for f in folders if f not in {".git", "__pycache__", ".venv"}]
        for file in files:
            lines.append(os.path.relpath(os.path.join(root, file), dir))

    return "\n".join(lines)
