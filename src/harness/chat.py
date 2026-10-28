import urllib.request
from collections.abc import Generator

from .config import MODEL, NUM_CTX, OLLAMA_URL
from .serialisation import dumps, loads
from .structs import ChatRequest, Message
from .tools import get_tools


class ChatError(Exception):
    pass


def chat(messages: list[Message]) -> Generator[tuple[Message, int]]:
    body = dumps(
        ChatRequest(
            model=MODEL,
            messages=messages,
            tools=get_tools(),
            options={"num_ctx": NUM_CTX},
            stream=True,
        ),
    ).encode("utf8")
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

            for line in response:
                line = line.strip()
                if not line:
                    continue

                obj = loads(line.decode("utf8"))
                if not obj.done:
                    yield obj.message, 0
                else:
                    yield obj.message, obj.prompt_eval_count + obj.eval_count
                    break

    except TimeoutError:
        raise ChatError("Timeout")
