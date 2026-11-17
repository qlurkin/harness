from dataclasses import dataclass, field


@dataclass
class Message:
    role: str = "user"
    content: str = ""
    thinking: str = ""
    tool_calls: list = field(default_factory=list)
    tool_call_id: str = ""
    tool_name: str = ""
    thinking_blocks: list = field(default_factory=list)
    used: int = 0


def dump_message(msg: Message) -> dict:
    """Internal (OpenAI-like) wire format. Providers convert from it."""
    res: dict = {"role": msg.role, "content": msg.content or None}
    if msg.tool_calls:
        res["tool_calls"] = msg.tool_calls
    if msg.tool_call_id:
        res["tool_call_id"] = msg.tool_call_id
    if msg.tool_name:
        res["name"] = msg.tool_name
    if msg.thinking_blocks:
        res["thinking_blocks"] = msg.thinking_blocks
    return res
