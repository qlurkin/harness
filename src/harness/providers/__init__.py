import importlib
import pkgutil

from litellm import get_model_info

from harness import providers
from harness.config import NUM_CTX

_MODELS = []

_PROVIDERS = {}


def list_models():
    return _MODELS


def get_params(provider):
    return _PROVIDERS[provider].params


def _get_context_limit(model_id) -> int:
    model_info = get_model_info(model_id)
    context_limit = model_info.get("max_input_tokens")
    if context_limit is None:
        return NUM_CTX
    return context_limit


def get_context_limit(model_id):
    tokens = model_id.split("/")
    provider = tokens[0]
    module = _PROVIDERS[provider]
    if "get_context_limit" in dir(module):
        return module.get_context_limit("/".join(tokens[1:]))
    else:
        return _get_context_limit(model_id)


for info in pkgutil.iter_modules(providers.__path__):
    module = importlib.import_module(f"{__name__}.{info.name}")
    _MODELS.extend(module.list_models())
    _PROVIDERS[module.provider] = module
