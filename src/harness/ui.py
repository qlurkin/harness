import asyncio

from rich.align import Align
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.color import Gradient
from textual.containers import (
    HorizontalGroup,
    VerticalGroup,
    VerticalScroll,
)
from textual.widgets import (
    Button,
    Collapsible,
    Footer,
    Header,
    Input,
    Label,
    Markdown,
    ProgressBar,
    Select,
    Static,
)

from harness.agent import (
    Agent,
    BusyError,
    Content,
    Event,
    Log,
    LogLevel,
    Prompt,
    Thinking,
    ToolCall,
    ToolPermisionRequest,
    Usage,
)
from harness.config import MAX_WIDGETS
from harness.serialisation import dumps
from harness.tools import Permission


class AskPermissionWidget(VerticalGroup):
    DEFAULT_CSS = """
    HorizontalGroup {
        width: 100%;
        align: center middle;
    }
    """

    def __init__(self, event: ToolPermisionRequest):
        self.event = event
        super().__init__()

    def compose(self):
        yield Static(Align.center(f"Permission to use {self.event.name} tool ?"))
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


class UI(App):
    CSS = """
    #menu {
        background: $surface;
    }

    #context {
        padding: 1;
        align-horizontal: center;
    }
    """

    BINDINGS = [  # noqa: RUF012
        ("d", "dump_conversation", "Dump Conversation"),
    ]

    def __init__(self):
        super().__init__()
        self.title = "Harness"
        self.agent = Agent()
        self.agent.subscribe(self.handle_agent_event)

    async def handle_agent_event(self, event: Event):
        if isinstance(event, Usage):
            self.query_one(ProgressBar).update(progress=event.used, total=event.total)
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
        if isinstance(event, ToolPermisionRequest):
            self.append(AskPermissionWidget(event))
        if isinstance(event, Log):
            self.write(event.msg, event.level)
        if isinstance(event, Prompt):
            self.need(PromptWidget).append(event)

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""

        gradient = Gradient.from_colors(
            "#881177",
            "#aa3355",
            "#cc6666",
            "#ee9944",
            "#eedd00",
            "#99dd55",
            "#44dd88",
            "#22ccbb",
            "#00bbcc",
            "#0099cc",
            "#3366bb",
            "#663399",
        )

        yield Header()
        with HorizontalGroup(id="menu"):
            yield Select(
                ((model, model) for model in self.agent.models),
                prompt="Model",
                value=self.agent.model,
                id="model",
            )
            yield Select(
                ((effort, effort) for effort in self.agent.efforts),
                prompt="Effort",
                value=self.agent.effort,
                id="effort",
            )
            with HorizontalGroup(id="context"):
                yield Label("Context: ")
                yield ProgressBar(
                    show_eta=False,
                    total=self.agent.context_limit,
                    gradient=gradient,
                    name="Context",
                )
        chats = VerticalScroll(id="chats")
        chats.anchor(True)
        yield chats
        yield Input(placeholder="Prompt", id="prompt")
        yield Footer()

    def on_select_changed(self, event: Select.Changed):
        if event.select.id == "model":
            self.agent.model = str(event.value)
        elif event.select.id == "effort":
            self.agent.effort = str(event.value)

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
        prompt = event.value
        event.input.clear()
        try:
            asyncio.create_task(self.agent.submit_prompt(prompt))
        except BusyError:
            event.input.value = prompt
            self.write("Already busy")

    def write(self, msg: str, level: LogLevel = LogLevel.NORMAL):
        text = Text(msg)
        if level is LogLevel.DANGER:
            text.stylize("red")
        elif level is LogLevel.WARNING:
            text.stylize("yellow")
        elif level is LogLevel.DIMMED:
            text.stylize("#808080")
        self.append(Static(text))

    def on_mount(self) -> None:
        prompt = self.query_one("#prompt")
        prompt.focus()

    def action_dump_conversation(self):
        with open("conversation.json", "w") as file:
            file.write(dumps(self.agent.conversation, indent=3))


if __name__ == "__main__":
    UI().run()
