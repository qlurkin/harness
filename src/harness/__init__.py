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
    from harness.ui import UI

    UI().run()
