import importlib
import pkgutil

from harness import tools

_TOOLS = []
_TOOL_FUNCTIONS = {}


def register_tool(mod):
    _TOOLS.append(mod.description)
    _TOOL_FUNCTIONS[mod.description.function.name] = mod.function


def get_tools():
    return _TOOLS


def call_tool(name, args):
    try:
        result = _TOOL_FUNCTIONS[name](args)
    except KeyError:
        result = f"error: unknown tool {name}"
    return result


def print_tools():
    print(f"Loaded Tools: {', '.join(_TOOL_FUNCTIONS.keys())}")


for info in pkgutil.iter_modules(tools.__path__):
    module = importlib.import_module(f"{__name__}.{info.name}")
    register_tool(module)
