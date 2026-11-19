"""Modal screens used by /login. One screen per provider, all dismiss with a bool."""

import asyncio
import threading
from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from harness import copilot_auth
from harness.auth import save_entry


class _Dialog(ModalScreen):
    DEFAULT_CSS = """
    _Dialog {
        align: center middle;
    }

    _Dialog > Vertical {
        width: 70;
        height: auto;
        max-height: 80%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    _Dialog .title {
        text-style: bold;
        margin-bottom: 1;
    }

    _Dialog .hint {
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]  # noqa: RUF012

    def action_cancel(self) -> None:
        self.dismiss(None)


class ProviderSelectScreen(_Dialog):
    """Dismisses with the chosen provider id, or None."""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Login: choose a provider", classes="title")
            yield OptionList(
                *(Option(login.label, id=pid) for pid, login in LOGINS.items())
            )
            yield Label("Enter to select, Esc to cancel", classes="hint")

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)


class OpenRouterLoginScreen(_Dialog):
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("OpenRouter login", classes="title")
            yield Input(placeholder="API key", password=True, id="key")
            yield Label("Enter to save, Esc to cancel", classes="hint")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()  # don't let the app treat the key as a prompt
        key = event.value.strip()
        if not key:
            return
        save_entry("openrouter", {"type": "api_key", "key": key})
        self.dismiss(True)


class CopilotLoginScreen(_Dialog):
    def __init__(self) -> None:
        super().__init__()
        self._cancel = threading.Event()

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("GitHub Copilot login", classes="title")
            yield Static("Requesting a device code...", id="status")
            yield Label("Esc to cancel", classes="hint")

    def on_mount(self) -> None:
        self.run_worker(self._flow(), exclusive=True)

    def action_cancel(self) -> None:
        self._cancel.set()
        self.dismiss(None)

    async def _flow(self) -> None:
        status = self.query_one("#status", Static)
        try:
            dev = await asyncio.to_thread(copilot_auth.request_device_code)
            status.update(
                f"1. Open {dev['verification_uri']}\n"
                f"2. Enter the code: [b]{dev['user_code']}[/b]\n\n"
                "Waiting for authorization..."
            )
            await asyncio.to_thread(copilot_auth.poll_for_token, dev, self._cancel)
        except Exception as e:  # noqa: BLE001
            if not self._cancel.is_set():
                self.app.notify(f"Copilot login failed: {e}", severity="error")
                self.dismiss(False)
            return
        self.dismiss(True)


@dataclass(frozen=True)
class Login:
    label: str
    screen: type[ModalScreen]


# provider id (see providers/*.py) -> login UI
LOGINS: dict[str, Login] = {
    "github_copilot": Login("GitHub Copilot", CopilotLoginScreen),
    "openrouter": Login("OpenRouter", OpenRouterLoginScreen),
}
