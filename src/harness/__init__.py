import json
from dataclasses import dataclass
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:e4b-mlx"


@dataclass
class Message:
    role: str
    content: str


@dataclass
class ChatRequest:
    model: str
    messages: list[Message]
    stream: bool = False


@dataclass
class ChatResponse:
    message: Message


def json_encoder(obj):
    if isinstance(obj, Message):
        return obj.__dict__.copy()
    if isinstance(obj, ChatRequest):
        d = obj.__dict__.copy()
        d["messages"] = [json_encoder(elem) for elem in d["messages"]]
        return d
    if isinstance(obj, ChatResponse):
        return {"message": json_encoder(obj.message)}


def dumps(obj):
    return json.dumps(obj, default=json_encoder)


def json_decoder(dct: dict):
    if "role" in dct:
        return Message(dct["role"], dct["content"])
    if "model" in dct and "messages" in dct and "stream" in dct:
        return ChatRequest(dct["model"], dct["messages"], dct["stream"])
    if "message" in dct and "model" not in dct:
        return ChatResponse(dct["message"])
    return dct


def loads(doc):
    return json.loads(doc, object_hook=json_decoder)


class ChatError(Exception):
    pass


def chat(messages: list[Message]):
    body = dumps(ChatRequest(model=MODEL, messages=messages)).encode("utf8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status != 200:
                raise ChatError(f"Status: {response.status}")

            txt = response.read().decode("utf8")
            print(txt)
            obj = loads(txt)
            print(obj)

            return obj["message"]
    except TimeoutError:
        raise ChatError("Timeout")


def main() -> None:
    print(f"harness v0.1 — chatting with {MODEL} (ctrl-c to quit)")
    conversation: list[Message] = []

    try:
        while True:
            msg = input("\nYou: ")
            conversation.append(Message("user", msg))

            try:
                reply = chat(conversation)
                conversation.append(reply)
                print(f"\nharness:\n{reply.content}")
            except ChatError as e:
                print(f"ChatError: {e}")
    except KeyboardInterrupt:
        print("\nBye\n")
