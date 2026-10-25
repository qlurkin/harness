from typing import Any
from pathlib import Path

from ..structs import Tool, ToolFunction

description = Tool(
    "function",
    ToolFunction(
        "edit_file",
        "Edit a file by replacing old_string (which must occur exactly once) with new_string. If old_string is empty and the file does not exist, the file is created with new_string as its contents.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to the file"},
                "old_string": {
                    "type": "string",
                    "description": "The exact text to replace. Must match exactly once, including whitespace and indentation. Empty to create a new file.",
                },
                "new_string": {"type": "string", "description": "The replacement text"},
            },
            "required": ["path", "new_string"],
        },
    ),
)


def function(args: dict[str, Any]):
    try:
        path = Path(args["path"])
    except KeyError:
        return "error: edit_file requires a string 'path' argument"

    oldStr = args.get("old_string", "")

    try:
        newStr = args["new_string"]
    except KeyError:
        return "error: edit_file requires a string 'new_string' argument"

    try:
        with open(path, encoding="utf8") as file:
            content = file.read()
    except FileNotFoundError:
        try:
            if len(oldStr) == 0:
                path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                with open(path, "w", encoding="utf8") as file:
                    file.write(newStr)
                return f"ok, created {path}"
        except OSError as e:
            return f"error: {e}"

    except OSError as e:
        return f"error: {e}"

    n = content.count(oldStr)
    if n == 0 or len(oldStr) == 0:
        return f"error: old_string not found in {path} — re-read the file; it may have changed"
    if n > 1:
        return f"error: old_string appears {n} times in {path} — include more surrounding context to make it unique"

    try:
        with open(path, "w", encoding="utf8") as file:
            file.write(content.replace(oldStr, newStr))
    except OSError as e:
        return f"error: {e}"

    return f"ok, edited {path}"
