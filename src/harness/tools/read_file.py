from typing import Any

SAFE = True

description = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file and return its contents as text. Use this whenever you need to see what a file contains.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to the file"}
            },
            "required": ["path"],
        },
    },
}


def function(args: dict[str, Any]):
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
