from dataclasses import dataclass, field
from typing import Any

from .serialisation import make_object_hook


@dataclass
class ToolFunction:
    name: str
    description: str
    parameters: Any


@dataclass
class Tool:
    type: str
    function: ToolFunction


@dataclass
class ToolCallFunction:
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolCall:
    function: ToolCallFunction


@dataclass
class Message:
    role: str
    content: str
    thinking: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_name: str = ""


@dataclass
class ChatRequest:
    model: str
    messages: list[Message]
    stream: bool = False
    tools: list[Tool] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponse:
    message: Message
    done: bool
    prompt_eval_count: int = 0
    eval_count: int = 0


make_object_hook(
    [Message, ChatRequest, ChatResponse, Tool, ToolCall, ToolCallFunction, ToolFunction]
)
