import importlib
import pkgutil

from harness import tools

_TOOLS = []
_TOOL_FUNCTIONS = {}
_TOOL_SAFE = {}
_APPROVED = {}


def register_tool(mod):
    _TOOLS.append(mod.description)
    _TOOL_FUNCTIONS[mod.description.function.name] = mod.function
    _TOOL_SAFE[mod.description.function.name] = mod.SAFE


def get_tools():
    return _TOOLS


def ask_permission(name):
    ans = input(f"allow {name}? [y]es once / [a]lways / [n]o\n")
    if ans.lower() == "y":
        return True
    if ans.lower() == "a":
        _APPROVED[name] = True
        return True
    return False


def call_tool(name, args):
    if _TOOL_SAFE[name] or _APPROVED.get("name", False) or ask_permission(name):
        try:
            result = _TOOL_FUNCTIONS[name](args)
        except KeyError:
            result = f"error: unknown tool {name}"
        return result
    else:
        return f"Call to {name} denied by the user. Do not retry the same call. Explain what you want to do, or try a different approach."


def print_tools():
    print(f"Loaded Tools: {', '.join(_TOOL_FUNCTIONS.keys())}")


for info in pkgutil.iter_modules(tools.__path__):
    module = importlib.import_module(f"{__name__}.{info.name}")
    register_tool(module)
