import importlib
import pkgutil
from enum import Enum, auto

from harness import tools

_TOOLS = []
_TOOL_FUNCTIONS = {}
_TOOL_SAFE = {}
_APPROVED = {}


class Permission(Enum):
    ALLOW = auto()
    ALWAYS = auto()
    DENIED = auto()


def register_tool(mod):
    _TOOLS.append(mod.description)
    _TOOL_FUNCTIONS[mod.description["function"]["name"]] = mod.function
    _TOOL_SAFE[mod.description["function"]["name"]] = mod.SAFE


def get_tools():
    return _TOOLS


async def ask_permission(name, ask_function):
    ans = await ask_function(name)
    if ans is Permission.ALLOW:
        return True
    if ans is Permission.ALWAYS:
        _APPROVED[name] = True
        return True
    return False


async def call_tool(name, args, ask_function):
    if (
        _TOOL_SAFE[name]
        or _APPROVED.get("name", False)
        or await ask_permission(name, ask_function)
    ):
        try:
            result = _TOOL_FUNCTIONS[name](args)
        except KeyError:
            result = f"error: unknown tool {name}"
        return result
    else:
        return f"Call to {name} denied by the user. Do not retry the same call. Explain what you want to do, or try a different approach."


def get_registered_tools():
    return [t.function.name for t in _TOOLS]


for info in pkgutil.iter_modules(tools.__path__):
    module = importlib.import_module(f"{__name__}.{info.name}")
    register_tool(module)
