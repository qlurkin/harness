"""Generic modal screens."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList
from textual.widgets.option_list import Option


class Dialog(ModalScreen):
    DEFAULT_CSS = """
    Dialog {
        align: center middle;
    }

    Dialog > Vertical {
        width: 70;
        height: auto;
        max-height: 80%;
        border: round $primary;
        background: $surface;
        padding: 1 2;
    }

    Dialog .title {
        text-style: bold;
        margin-bottom: 1;
    }

    Dialog .hint {
        color: $text-muted;
        margin-top: 1;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]  # noqa: RUF012

    def action_cancel(self) -> None:
        self.dismiss(None)



class ChoiceScreen(Dialog):
    """Pick one value from a (filterable) list. Dismisses with the value or None."""

    BINDINGS = [  # noqa: RUF012
        Binding("down", "move(1)", show=False),
        Binding("up", "move(-1)", show=False),
    ]

    def __init__(self, title: str, choices: list[str], current: str | None = None):
        super().__init__()
        self.title_text = title
        self.choices = choices
        self.current = current

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.title_text, classes="title")
            yield Input(placeholder="Filter...", id="filter")
            yield OptionList(id="choices")
            yield Label("Enter to select, Esc to cancel", classes="hint")

    def on_mount(self) -> None:
        self._fill("")
        self.query_one(Input).focus()

    def _fill(self, text: str) -> None:
        options = self.query_one(OptionList)
        options.clear_options()
        matching = [c for c in self.choices if text.lower() in c.lower()]
        options.add_options(
            Option(f"{c}  (current)" if c == self.current else c, id=c)
            for c in matching
        )
        if matching:
            options.highlighted = matching.index(self.current) if self.current in matching else 0

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self._fill(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        options = self.query_one(OptionList)
        if options.highlighted is not None:
            self.dismiss(options.get_option_at_index(options.highlighted).id)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_move(self, delta: int) -> None:
        options = self.query_one(OptionList)
        if delta > 0:
            options.action_cursor_down()
        else:
            options.action_cursor_up()
