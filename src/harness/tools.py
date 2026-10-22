from typing import Any

from .structs import Tool, ToolFunction

readFileTool = Tool(
    "function",
    ToolFunction(
        "read_file",
        "Read a file and return its contents as text. Use this whenever you need to see what a file contains.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to the file"}
            },
            "required": ["path"],
        },
    ),
)


def read_file(args: dict[str, Any]):
    try:
        path = args["path"]
    except KeyError:
        return "error: read_file requires a string 'path' argument"

    try:
        with open(path) as file:
            data = file.read()
    except OSError as e:
        return f"error: {e}"

    return str(data)


TOOLS = [readFileTool]
TOOL_FUNCTIONS = {"read_file": read_file}
