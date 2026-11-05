# import asyncio

# from harness.simple_terminal import simple_terminal
from harness.ui import UI

# TODO:
# - ensure list_files and edit_file are in project
# - display context info in menu bar in UI
# - drop_down for model selection
# - dracula


def main() -> None:
    # asyncio.run(simple_terminal())
    UI().run()
