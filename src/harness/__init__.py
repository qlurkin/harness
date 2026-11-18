# TODO:
# - better compaction trigger
# - exec tools in subprocesses in parallele
# - dracula
# - Add Mistral Provider
# - Add Slash Commands
# - Add Agents.md
# - Add Skills
# - Add Trust Store
# - Add Session and Persistence
# - OSC 7501


def main() -> None:
    import sys

    args = sys.argv[1:]

    if args and args[0] == "connect_copilot":
        from harness.connect_copilot import main as connect_copilot

        connect_copilot()
        return

    if args and args[0] == "connect_openrouter":
        from harness.connect_openrouter import main as connect_openrouter

        connect_openrouter()
        return

    if args:
        sys.exit(
            f"Unknown command: {args[0]}\n"
            "Usage: harness [connect_copilot | connect_openrouter]"
        )

    from harness.ui import UI

    UI().run()
