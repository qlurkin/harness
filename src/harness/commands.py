"""Slash commands, shared by the prompt (/name) and Textual's command palette.

Add a command with @command("name", "description"); the handler receives the
app and the argument string.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Command:
    name: str
    description: str
    run: Callable[[Any, str], Any]  # (app, args)


COMMANDS: dict[str, Command] = {}


def command(name: str, description: str):
    def register(fn: Callable[[Any, str], Any]):
        COMMANDS[name] = Command(name, description, fn)
        return fn

    return register


def parse(text: str) -> tuple[str, str] | None:
    """'/login openrouter' -> ('login', 'openrouter'); None if not a command."""
    text = text.strip()
    if not text.startswith("/"):
        return None
    name, _, args = text[1:].partition(" ")
    return name, args.strip()


@command("login", "Log in to a provider")
def login(app, args: str) -> None:
    from harness.login_screens import LOGINS, ProviderSelectScreen

    def open_login(provider: str | None) -> None:
        if provider is None:
            return
        app.push_screen(
            LOGINS[provider].screen(),
            lambda ok: app.on_login_done(provider, ok),
        )

    if args in LOGINS:
        open_login(args)
    else:
        app.push_screen(ProviderSelectScreen(), open_login)
