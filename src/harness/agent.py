import asyncio
import inspect
import json
import platform
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from enum import Enum, auto
from pathlib import Path
from textwrap import dedent
from typing import Any

from harness.config import CONFIG_PATH, MODEL
from harness.message import dump_message
from harness.providers import count_tokens, get_context_limit, list_models
from harness.settings import load_settings

from .chat import Message, chat, summarize
from .tools import Permission, call_tool

SUMMARY_HEADER = (
    "[Context summary - earlier messages were compacted to save space. "
    "File contents mentioned below may be stale, re-read files before editing.]"
)


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
class PermisionRequest:
    msg: str
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


Event = Prompt | Content | Thinking | ToolCall | Usage | PermisionRequest | Log

Handler = Callable[[Event], Any]


class BusyError(Exception): ...


class Agent:
    def __init__(self):
        self.handlers: list[Handler] = []
        self.conversation: list[Message] = []
        self.models = list_models()
        settings = load_settings()
        self.startup_warnings: list[str] = []
        self.__model = MODEL
        wanted = settings.get("model")
        if wanted is not None:
            if wanted in self.models:
                self.__model = wanted
            else:
                self.startup_warnings.append(
                    f"Default model '{wanted}' from settings is not available, using {MODEL}"
                )
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
        wanted = settings.get("effort")
        if wanted is not None:
            if wanted in self.efforts:
                self.effort = wanted
            else:
                self.startup_warnings.append(
                    f"Unknown default effort '{wanted}' in settings "
                    f"(expected one of: {', '.join(self.efforts)})"
                )
        self.thinking = True

    async def load(self, root: Path):
        root = root.resolve()
        if root.exists():
            self.root = root
            self.thinking = False
            await self.clear()
            await self.dimmed(f"ROOT: {root}")
        else:
            await self.danger(f"ROOT `{root}` do not exists")

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
            await self.warning("Agent Busy")
            return

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

    async def clear(self):
        if self.thinking:
            await self.warning("Agent Busy")
            return

        self.conversation = [Message("system", await self.system_prompt())]
        used = count_tokens(self.model, [dump_message(m) for m in self.conversation])
        await self.emit(Usage(used, self.context_limit))

    async def compact(self):
        if self.thinking:
            raise BusyError()
        if len(self.conversation) <= 2:
            await self.dimmed("Nothing to compact")
            return

        self.thinking = True
        try:
            await self.dimmed("Compacting started")
            summary = await summarize(self.model, self.conversation)
            self.conversation = await self._compact(summary)
            used = count_tokens(
                self.model, [dump_message(m) for m in self.conversation]
            )
            await self.emit(Usage(used, self.context_limit))
            await self.dimmed("Compacting done")
        except Exception as e:  # noqa: BLE001
            await self.danger(f"Compaction failed: {type(e).__name__}: {e}")
        finally:
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

    async def ask_permission(self, msg):
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        def resolve(value):
            if not future.done():
                future.set_result(value)

        await self.emit(PermisionRequest(msg, resolve))
        return await future

    async def log(self, msg: Any, level=LogLevel.NORMAL):
        await self.emit(Log(str(msg), level))

    async def danger(self, msg: Any):
        await self.log(msg, LogLevel.DANGER)

    async def warning(self, msg: Any):
        await self.log(msg, LogLevel.WARNING)

    async def dimmed(self, msg: Any):
        await self.log(msg, LogLevel.DIMMED)

    async def agents_md(self):
        res = ""
        path = CONFIG_PATH / "AGENTS.md"
        if path.exists():
            user_notes = await load_file(path)
            res += f"## User notes\n\n{user_notes}\n"
        path = self.root / "AGENTS.md"
        if path.exists():
            trusted = False
            trusted_dirs_path = CONFIG_PATH / "trusted-dirs.json"
            try:
                trusted_dirs_json = await load_file(trusted_dirs_path)
                trusted_dirs = json.loads(trusted_dirs_json)
            except FileNotFoundError:
                trusted_dirs = {}
            if trusted_dirs.get(self.root, False):
                trusted = True
            else:
                permision = await self.ask_permission(f"Trust folder `{self.root}` ?")
                if permision is Permission.ALLOW:
                    trusted = True
                elif permision is Permission.ALWAYS:
                    trusted = True
                    trusted_dirs[self.root] = True
                    await save_file(trusted_dirs_path, json.dumps(trusted_dirs))
            if trusted:
                project_notes = await load_file(path)
                res += f"## Project notes\n\n{project_notes}\n"
        return res

    async def system_prompt(self):

        res = dedent(f"""
            You are Harness, a coding agent. You complete tasks by calling tools, not by describing what could be done.

            Environment:
            - Working directory: {self.root}
            - Platform: {platform.system()}/{platform.machine()}
            - Today's date: {date.today()}

            Rules:
            - Before editing a file, read it first. Quote old_string exactly, including whitespace.
            - After any code change, verify it: build or run tests with bash. Never claim a success you have not seen.
            - If a tool returns an error, read it and change your approach; never repeat the same call unchanged.
            - Prefer small, targeted edits over rewriting whole files.
            - When done, summarize what you changed and how you verified it, in a sentence or two.
        """)

        res += await self.agents_md()

        return res

    async def _compact(self, summary: str, keep: int = 6) -> list[Message]:
        start = max(len(self.conversation) - keep, 1)
        while start > 1 and self.conversation[start].role == "tool":
            start -= 1
        return [
            Message("system", await self.system_prompt()),
            Message("user", f"{SUMMARY_HEADER}\n\n{summary}"),
            *self.conversation[start:],
        ]


async def load_file(path: Path | str, encoding="utf8"):
    path = Path(path)

    def read_file(path: Path, encoding: str):
        with open(path, "r", encoding=encoding) as f:
            return f.read()

    return await asyncio.to_thread(read_file, path, encoding)


async def save_file(path: Path | str, content: str, encoding="utf8"):
    path = Path(path)

    def write_file(path: Path, content: str, encoding: str):
        with open(path, "w", encoding=encoding) as f:
            f.write(content)

    return await asyncio.to_thread(write_file, path, content, encoding)
