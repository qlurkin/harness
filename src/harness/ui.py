from rich.markdown import Markdown
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Input, RichLog

from harness import harness
from harness.structs import Message
from harness.system_prompt import system_prompt
from harness.tools import Permission


class UI(App):
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        self.title = "Harness"
        self.build_str = ""
        self.mode = None
        self.conversation = [Message("system", system_prompt())]

        yield Header()
        self.chats = RichLog(wrap=True)
        yield self.chats
        self.builder = RichLog(wrap=True)
        yield self.builder
        yield Input(placeholder="Prompt")
        yield Footer()

    def write(self, content):
        self.chats.write(content, scroll_end=True, animate=True)

    def format_response(self, content):
        return Markdown(content)

    def format_thinking(self, content):
        text = Text(content)
        text.stylize("magenta")
        return text

    def write_response(self, content):
        if self.mode != "response":
            self.commit()
            self.mode = "response"
        self.builder.clear()
        self.build_str += content
        self.builder.write(self.format_response(self.build_str))

    def write_thinking(self, content):
        if self.mode != "thinking":
            self.commit()
            self.mode = "thinking"
        self.builder.clear()
        self.build_str += content
        self.builder.write(self.format_thinking(self.build_str))

    def commit(self):
        if self.mode == "thinking":
            self.chats.write(self.format_thinking(self.build_str))
        elif self.mode == "response":
            self.chats.write(self.format_response(self.build_str))
        self.build_str = ""
        self.builder.clear()

    def write_tool_call(self, name, args):
        self.commit()
        self.write(f"tool: {name}({args})")

    def context_info(self, used, total):
        self.commit()
        self.write(f"context: {used}/{total}")

    def ask_permission(self, name):
        return Permission.DENIED

    def on_input_submitted(self, event: Input.Submitted) -> None:
        prompt = event.value
        self.write(Markdown(prompt))
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


if __name__ == "__main__":
    UI().run()
