import asyncio

from rich.align import Align
from rich.table import Table
from textual.app import App, ComposeResult
from textual.color import Gradient
from textual.containers import (
    HorizontalGroup,
    VerticalGroup,
    VerticalScroll,
)
from textual.message import Message as TextualMessage
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

from harness.config import MAX_WIDGETS, MODELS, NUM_CTX
from harness.harness import harness
from harness.serialisation import dumps
from harness.structs import Message
from harness.system_prompt import system_prompt
from harness.tools import Permission


class AskPermissionWidget(VerticalGroup):
    DEFAULT_CSS = """
    HorizontalGroup {
        width: 100%;
        align: center middle;
    }
    """

    def __init__(self, event: AskPermissionMessage):
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


class ThinkingMessage(TextualMessage):
    def __init__(self, content: str) -> None:
        self.content = content
        super().__init__()


class ResponseMessage(TextualMessage):
    def __init__(self, content: str) -> None:
        self.content = content
        super().__init__()


class ToolCallMessage(TextualMessage):
    def __init__(self, name: str, args: dict) -> None:
        self.name = name
        self.args = args
        super().__init__()


class ContextInfoMessage(TextualMessage):
    def __init__(self, used: int, total: int) -> None:
        self.used = used
        self.total = total
        super().__init__()


class AskPermissionMessage(TextualMessage):
    def __init__(self, name, resolve) -> None:
        self.name = name
        self.resolve = resolve
        super().__init__()


class CommitMessage(TextualMessage):
    pass


class WriteMessage(TextualMessage):
    def __init__(self, content):
        self.content = content
        super().__init__()


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
        yield self.md

    def append(self, content):
        self.md.append(content)


class ThinkingWidget(VerticalGroup):
    # DEFAULT_CSS = """
    # ThinkingWidget {
    #     color: #808080;
    # }
    # """

    def compose(self):
        with Collapsible(title="Thinking", collapsed=False):
            self.md = Markdown()
            yield self.md

    def append(self, content):
        self.md.append(content)

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

    BINDINGS = [
        ("d", "dump_conversation", "Dump Conversation"),
    ]

    def __init__(self):
        super().__init__()
        self.title = "Harness"
        self.build_str = ""
        self.mode = None
        self.conversation = [Message("system", system_prompt())]
        self.current = None
        self.models = MODELS
        self.model = self.models[0]

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
                ((model, model) for model in self.models),
                prompt="Model",
                value=self.model,
            )
            with HorizontalGroup(id="context"):
                yield Label("Context: ")
                yield ProgressBar(
                    show_eta=False, total=NUM_CTX, gradient=gradient, name="Context"
                )
        self.chats = VerticalScroll()
        self.chats.anchor(True)
        yield self.chats
        self.input = Input(placeholder="Prompt")
        yield self.input
        yield Footer()

    def on_write_message(self, event: WriteMessage):
        self.chats.mount(Static(str(event.content), markup=False))

    def on_select_changed(self, event: Select.Changed):
        self.model = str(event.value)
        self.write(self.model)

    def set_context_info(self, value, total):
        self.query_one(ProgressBar).update(progress=value, total=total)

    def on_response_message(self, event: ResponseMessage):
        content = event.content
        if self.mode != "response":
            self.__commit()
            self.mode = "response"
            self.current = ResponseWidget()
            self.chats.mount(self.current)
        assert self.current is not None
        self.current.append(content)

    def on_thinking_message(self, event: ThinkingMessage):
        if self.mode != "thinking":
            self.__commit()
            self.mode = "thinking"
            self.current = ThinkingWidget()
            self.chats.mount(self.current)
        assert self.current is not None
        self.current.append(event.content)

    def on_tool_call_message(self, event: ToolCallMessage):
        self.__commit()
        table = Table(title=f"Call {event.name}")
        table.add_column("Arg", justify="right", no_wrap=True)
        table.add_column("Value", style="cyan")
        for key, value in event.args.items():
            table.add_row(key, value)
        wdg = Static(Align.center(table))
        self.chats.mount(wdg)

    def on_ask_permission_message(self, event: AskPermissionMessage):
        self.__commit()
        wdg = AskPermissionWidget(event)
        # self.current = wdg
        # self.mode = "ask"
        self.chats.mount(wdg)

    def __commit(self):
        if isinstance(self.current, ThinkingWidget):
            self.current.collapse()
        self.current = None
        self.build_str = ""
        self.mode = None

        children = list(self.chats.children)
        while len(children) > MAX_WIDGETS:
            oldest = children.pop(0)
            oldest.remove()

    def on_commit_message(self, event: CommitMessage):
        self.__commit()

    def on_context_info_message(self, event: ContextInfoMessage):
        self.__commit()
        # self.chats.mount(Static(f"context: {event.used}/{event.total}"))
        self.set_context_info(event.used, event.total)

    def write_response(self, content):
        self.post_message(ResponseMessage(content))

    def write_thinking(self, content):
        self.post_message(ThinkingMessage(content))

    def commit(self):
        self.post_message(CommitMessage())

    def write_tool_call(self, name, args):
        self.post_message(ToolCallMessage(name, args))

    def context_info(self, used, total):
        self.post_message(ContextInfoMessage(used, total))

    def write(self, content):
        self.post_message(WriteMessage(content))

    async def ask_permission(self, name):
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        def resolve(value):
            if not future.done():
                loop.call_soon_threadsafe(future.set_result, value)

        self.post_message(AskPermissionMessage(name, resolve))
        return await future

    def on_input_submitted(self, event: Input.Submitted) -> None:
        prompt = event.value
        wdg = PromptWidget()
        self.chats.mount(wdg)
        wdg.append(prompt)
        event.input.clear()
        self.conversation.append(Message("user", prompt))
        self.run_worker(self.process(), exclusive=True, thread=True)

    async def process(self):
        await harness(
            self.model,
            self.conversation,
            self.write_response,
            self.write_thinking,
            self.write_tool_call,
            self.ask_permission,
            self.context_info,
            self.commit,
            self.write,
        )

    def on_mount(self) -> None:
        self.input.focus()

    def action_dump_conversation(self):
        with open("conversation.json", "w") as file:
            file.write(dumps(self.conversation, indent=3))


if __name__ == "__main__":
    UI().run()
