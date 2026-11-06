import importlib
import pkgutil

from harness import providers

_MODELS = []
_API_BASE = {}


def list_models():
    return _MODELS


def get_api_base(provider):
    return _API_BASE[provider]


for info in pkgutil.iter_modules(providers.__path__):
    module = importlib.import_module(f"{__name__}.{info.name}")
    _MODELS.extend(module.list_models())
    _API_BASE[module.provider] = module.api_base
