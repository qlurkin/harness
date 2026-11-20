import asyncio
import inspect
from pathlib import Path

from rich.align import Align
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult, SystemCommand
from textual.containers import (
    HorizontalGroup,
    VerticalGroup,
    VerticalScroll,
)
from textual.suggester import Suggester
from textual.widgets import (
    Button,
    Collapsible,
    Footer,
    Header,
    Input,
    Markdown,
    Static,
)

from harness.agent import (
    Agent,
    BusyError,
    Content,
    Event,
    Log,
    LogLevel,
    PermisionRequest,
    Prompt,
    Thinking,
    ToolCall,
    Usage,
)
from harness.commands import COMMANDS, parse
from harness.config import MAX_WIDGETS
from harness.providers import refresh_models
from harness.serialisation import dumps
from harness.settings import load_settings, save_setting
from harness.tools import Permission


class AskPermissionWidget(VerticalGroup):
    DEFAULT_CSS = """
    HorizontalGroup {
        width: 100%;
        align: center middle;
    }
    """

    def __init__(self, event: PermisionRequest):
        self.event = event
        super().__init__()

    def compose(self):
        yield Static(Align.center(self.event.msg))
        with HorizontalGroup():
            yield Button("Deny", id="deny", variant="error")
            yield Button("Allow", id="allow", variant="success")
            yield Button("Always", id="always", variant="warning")

    def on_button_pressed(self, event: Button.Pressed):
        button_id = event.button.id
        if button_id == "deny":
            self.event.resolve(Permission.DENIED)
        if button_id == "allow":
            self.event.resolve(Permission.ALLOW)
        if button_id == "always":
            self.event.resolve(Permission.ALWAYS)
        self.remove()


class PromptWidget(VerticalGroup):
    DEFAULT_CSS = """
    PromptWidget {
        border: round white;
        padding: 0;
    }

    PromptWidget Static {
        text-align: right;
    }
    """

    def compose(self):
        self.label = Static(":You\n", id="title")
        yield self.label
        self.md = Markdown()
        yield self.md

    def append(self, content):
        self.md.append(content)


class ResponseWidget(VerticalGroup):
    DEFAULT_CSS = """
    ResponseWidget {
        border: round green;
        padding: 0;
    }

    #title {
        color: green;
    }
    """

    def compose(self):
        self.label = Static("Harness:\n", id="title")
        yield self.label
        self.md = Markdown()
        self.stream = Markdown.get_stream(self.md)
        yield self.md

    async def append(self, content):
        await self.stream.write(content)


class ThinkingWidget(VerticalGroup):
    def compose(self):
        with Collapsible(title="Thinking", collapsed=False):
            self.md = Markdown()
            self.stream = Markdown.get_stream(self.md)
            yield self.md

    async def append(self, content):
        await self.stream.write(content)

    def collapse(self):
        self.query_one(Collapsible).collapsed = True


class CommandSuggester(Suggester):
    """Completes '/na' into '/name' in the prompt."""

    def __init__(self):
        super().__init__(use_cache=False, case_sensitive=False)

    async def get_suggestion(self, value: str) -> str | None:
        if not value.startswith("/") or " " in value:
            return None
        for name in COMMANDS:
            if f"/{name}".startswith(value.lower()) and f"/{name}" != value:
                return f"/{name}"
        return None


class UI(App):
    CSS = """
    #status {
        height: 1;
        padding: 0 1;
    }
    """

    BINDINGS = [  # noqa: RUF012
        ("d", "dump_conversation", "Dump Conversation"),
    ]

    def __init__(self):
        super().__init__()
        self.title = "Harness"
        self.agent = Agent()
        self.context_used = 0
        theme = load_settings().get("theme")
        if theme in self.available_themes:
            self.theme = theme
        self.agent.subscribe(self.handle_agent_event)

    async def handle_agent_event(self, event: Event):
        if isinstance(event, Usage):
            self.context_used = event.used
            self.update_status()
        if isinstance(event, Content):
            await self.need(ResponseWidget).append(event)
        if isinstance(event, Thinking):
            await self.need(ThinkingWidget).append(event)
        if isinstance(event, ToolCall):
            table = Table(title=f"Call {event.name}")
            table.add_column("Arg", justify="right", no_wrap=True)
            table.add_column("Value", style="cyan")
            for key, value in event.args.items():
                table.add_row(key, value)
            wdg = Static(Align.center(table))
            self.append(wdg)
        if isinstance(event, PermisionRequest):
            self.append(AskPermissionWidget(event))
        if isinstance(event, Log):
            self.write(event.msg, event.level)
        if isinstance(event, Prompt):
            self.need(PromptWidget).append(event)

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""

        yield Header()
        chats = VerticalScroll(id="chats")
        chats.anchor(True)
        yield chats
        yield Input(
            placeholder="Prompt (/ for commands)",
            id="prompt",
            suggester=CommandSuggester(),
        )
        yield Static(id="status")
        yield Footer()

    # def set_context_info(self, value):
    # self.query_one(ProgressBar).update(progress=value, total=self.context_limit)
    # self.write(f"  Context Used: {value}")
    # if value > 0.8 * self.context_limit:
    #     self.write("  Compacting started")
    #     summary = summarize(self.model, self.conversation)
    #     self.conversation = compact(self.conversation, summary)
    #     self.write("  Compacting done")

    def append(self, wgt):
        chats = self.query_one("#chats")
        chats.mount(wgt)

        children = list(chats.children)
        while len(children) > MAX_WIDGETS:
            oldest = children.pop(0)
            oldest.remove()

    def need(self, typ):
        chats = self.query_one("#chats")
        if len(chats.children) > 0:
            last = chats.children[-1]
            if isinstance(last, typ):
                return last
        wgt = typ()
        self.append(wgt)
        return wgt

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "prompt":
            self.write("pas prompt")
            return
        prompt = event.value
        event.input.clear()

        parsed = parse(prompt)
        if parsed is not None:
            self.write("command")
            await self.run_command(*parsed)
            return

        self.write("prompt")
        asyncio.create_task(self.agent.submit_prompt(prompt))

    async def run_command(self, name: str, args: str = "") -> None:
        cmd = COMMANDS.get(name)
        if cmd is None:
            self.write(f"Unknown command: /{name}", LogLevel.WARNING)
            return
        result = cmd.run(self, args)
        if inspect.isawaitable(result):
            await result

    def get_system_commands(self, screen):
        # Only our slash commands: Textual's defaults (Theme, Keys, Screenshot,
        # Quit) have been turned into commands, Maximize/Minimize dropped.
        for cmd in COMMANDS.values():
            yield SystemCommand(
                f"/{cmd.name}",
                cmd.description,
                lambda cmd=cmd: self.run_command(cmd.name),
            )

    def set_model(self, model: str) -> None:
        self.agent.model = model
        self.update_status()

    def set_effort(self, effort: str) -> None:
        self.agent.effort = effort
        self.update_status()

    async def on_login_done(self, provider: str, ok: bool | None) -> None:
        if not ok:
            return
        self.notify(f"Logged in ({provider})")
        self.agent.models = await asyncio.to_thread(refresh_models, provider)

    def update_status(self) -> None:
        used, total = self.context_used, self.agent.context_limit
        percent = round(100 * used / total) if total else 0
        text = Text(
            f"{self.agent.model} · effort: {self.agent.effort} "
            f"· context: {used:,}/{total:,} ({percent}%)",
            style="#808080",
        )
        self.query_one("#status", Static).update(text)

    def write(self, msg: str, level: LogLevel = LogLevel.NORMAL):
        text = Text(msg)
        if level is LogLevel.DANGER:
            text.stylize("red")
        elif level is LogLevel.WARNING:
            text.stylize("yellow")
        elif level is LogLevel.DIMMED:
            text.stylize("#808080")
        self.append(Static(text))

    async def on_mount(self) -> None:
        self.theme_changed_signal.subscribe(
            self, lambda theme: save_setting("theme", theme.name)
        )
        self.update_status()
        for warning in self.agent.startup_warnings:
            self.write(warning, LogLevel.WARNING)
        prompt = self.query_one("#prompt")
        prompt.focus()
        asyncio.create_task(self.agent.load(Path.cwd()))

    def action_dump_conversation(self):
        with open("conversation.json", "w") as file:
            file.write(dumps(self.agent.conversation, indent=3))


if __name__ == "__main__":
    UI().run()
