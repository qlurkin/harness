from textual.app import App, ComposeResult
from textual.containers import VerticalGroup, VerticalScroll
from textual.message import Message as TextualMessage
from textual.widgets import Collapsible, Footer, Header, Input, Markdown, Static

from harness import harness
from harness.config import MAX_WIDGETS
from harness.structs import Message
from harness.system_prompt import system_prompt
from harness.tools import Permission


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


class CommitMessage(TextualMessage):
    pass


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


class UI(App):
    CSS = """
    #builder {
        height: auto;
        width: 100%;
    }

    RichLog, Label {
        background: $surface;
        color: $foreground;
    }
    """

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        self.title = "Harness"
        self.build_str = ""
        self.mode = None
        self.conversation = [Message("system", system_prompt())]
        self.current = None

        yield Header()
        self.chats = VerticalScroll()
        self.chats.anchor(True)
        yield self.chats
        self.input = Input(placeholder="Prompt")
        yield self.input
        yield Footer()

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
        wdg = Static(f"tool_call: {event.name}({event.args})")
        wdg.styles.color = "yellow"
        wdg.styles.text_align = "center"
        self.chats.mount(wdg)

    def __commit(self):
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
        self.chats.mount(Static(f"context: {event.used}/{event.total}"))

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

    def ask_permission(self, name):
        return Permission.DENIED

    def on_input_submitted(self, event: Input.Submitted) -> None:
        prompt = event.value
        wdg = PromptWidget()
        self.chats.mount(wdg)
        wdg.append(prompt)
        event.input.clear()
        self.conversation.append(Message("user", prompt))
        self.run_worker(self.process(), exclusive=True, thread=True)

    async def process(self):
        harness(
            self.conversation,
            self.write_response,
            self.write_thinking,
            self.write_tool_call,
            self.ask_permission,
            self.context_info,
            self.commit,
        )

    def on_mount(self) -> None:
        self.input.focus()


if __name__ == "__main__":
    UI().run()
