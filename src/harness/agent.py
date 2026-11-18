import asyncio
import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from harness.config import MODEL
from harness.providers import get_context_limit, list_models
from harness.system_prompt import system_prompt

from .chat import Message, chat
from .tools import Permission, call_tool


class Content(str): ...


class Thinking(str): ...


class Prompt(str): ...


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass
class Usage:
    used: int
    total: int


@dataclass
class ToolPermisionRequest:
    name: str
    args: dict[str, Any]
    resolve: Callable[[Permission], None]


class LogLevel(Enum):
    DIMMED = auto()
    NORMAL = auto()
    WARNING = auto()
    DANGER = auto()


@dataclass
class Log:
    msg: str
    level: LogLevel = LogLevel.NORMAL


Event = Prompt | Content | Thinking | ToolCall | Usage | ToolPermisionRequest | Log

Handler = Callable[[Event], Any]


class BusyError(Exception): ...


class Agent:
    def __init__(self):
        self.handlers: list[Handler] = []
        self.conversation: list[Message] = [Message("system", system_prompt())]
        self.thinking = False
        self.models = list_models()
        self.__model = MODEL
        self.context_limit = get_context_limit(self.__model)
        self.efforts = [
            "none",
            "minimal",
            "low",
            "medium",
            "high",
            "xhigh",
            "max",
            "default",
        ]
        self.effort = "medium"

    @property
    def model(self):
        return self.__model

    @model.setter
    def model(self, value):
        self.__model = value
        self.context_limit = get_context_limit(self.__model)

    def subscribe(self, handler: Handler):
        self.handlers.append(handler)

    async def emit(self, event: Event):
        for handler in self.handlers:
            result = handler(event)
            if inspect.isawaitable(result):
                await result

    async def submit_prompt(self, prompt: str):
        if self.thinking:
            raise BusyError()

        await self.emit(Prompt(prompt))
        self.conversation.append(Message("user", prompt))
        try:
            await self.think()
        except Exception as e:  # noqa: BLE001
            self.thinking = False
            await self.danger(f"{type(e).__name__}: {e}")

    async def think(self):
        self.thinking = True
        while self.thinking:
            chunks = chat(self.model, self.effort, self.conversation, self.warning)
            used = 0
            reply = Message("assistant", "")
            async for chunk, usage in chunks:
                used += usage
                if len(chunk.thinking) > 0:
                    await self.emit(Thinking(chunk.thinking))
                    reply.thinking += chunk.thinking
                    reply.thinking_blocks.extend(chunk.thinking_blocks)
                if len(chunk.content) > 0:
                    await self.emit(Content(chunk.content))
                    reply.content += chunk.content
                reply.tool_calls.extend(chunk.tool_calls)

            self.conversation.append(reply)

            await self.emit(Usage(used, self.context_limit))

            if len(reply.tool_calls) == 0:
                break

            self.conversation.extend(await self.process_tool_calls(reply.tool_calls))
        self.thinking = False

    async def cancel(self):
        self.thinking = False

    async def process_tool_calls(self, tool_calls):
        results = []
        for tc in tool_calls:
            if len(tc["function"]["arguments"]) > 0:
                args = json.loads(tc["function"]["arguments"])
            else:
                args = {}
            await self.emit(ToolCall(tc["function"]["name"], args))
            result = await call_tool(
                tc["function"]["name"],
                args,
                self.ask_permission,
            )
            results.append(
                Message(
                    "tool",
                    result,
                    tool_call_id=tc["id"],
                    tool_name=tc["function"]["name"],
                )
            )
        return results

    async def ask_permission(self, name, args):
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        def resolve(value):
            if not future.done():
                future.set_result(value)

        await self.emit(ToolPermisionRequest(name, args, resolve))
        return await future

    async def log(self, msg: Any, level=LogLevel.NORMAL):
        await self.emit(Log(str(msg), level))

    async def danger(self, msg: Any):
        await self.log(msg, LogLevel.DANGER)

    async def warning(self, msg: Any):
        await self.log(msg, LogLevel.WARNING)

    async def dimmed(self, msg: Any):
        await self.log(msg, LogLevel.DIMMED)
