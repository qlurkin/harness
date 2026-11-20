# TODO:
# - add a async load method to agent to set its ROOT and create the system prompt find a good place to call it in UI
# - better compaction trigger
# - exec tools in subprocesses in parallele
# - Add Mistral Provider
# - Add Skills
# - Add Trust Store
# - Add Session and Persistence
# - OSC 7501


def main() -> None:
    from harness.ui import UI

    UI().run()
