import urllib.request

from .config import MODEL, OLLAMA_URL
from .serialisation import dumps, loads
from .structs import ChatRequest, Message
from .tools import TOOLS


class ChatError(Exception):
    pass


def chat(messages: list[Message]) -> Message:
    body = dumps(ChatRequest(model=MODEL, messages=messages, tools=TOOLS)).encode(
        "utf8"
    )
    req = urllib.request.Request(
        OLLAMA_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            if response.status != 200:
                raise ChatError(f"Status: {response.status}")

            txt = response.read().decode("utf8")
            obj = loads(txt)
            return obj.message

    except TimeoutError:
        raise ChatError("Timeout")
