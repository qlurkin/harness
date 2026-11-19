import importlib
import pkgutil

from harness import providers
from harness.config import NUM_CTX

_MODELS: dict[str, list[str]] = {}

_PROVIDERS = {}


def list_models():
    return [m for models in _MODELS.values() for m in models]


def refresh_models(provider: str) -> list[str]:
    """Re-query one provider's models (e.g. after a login). Blocking."""
    _MODELS[provider] = _PROVIDERS[provider].list_models()
    return list_models()


def split_model_id(model_id: str) -> tuple[str, str]:
    provider, _, model = model_id.partition("/")
    return provider, model


def get_provider(model_id: str):
    return _PROVIDERS[split_model_id(model_id)[0]]


def get_context_limit(model_id: str) -> int:
    provider, model = split_model_id(model_id)
    module = _PROVIDERS[provider]
    limit = module.get_context_limit(model) if hasattr(module, "get_context_limit") else None
    return limit or NUM_CTX


def count_tokens(model_id: str, messages: list[dict]) -> int:
    provider, model = split_model_id(model_id)
    module = _PROVIDERS[provider]
    if hasattr(module, "count_tokens"):
        return module.count_tokens(model, messages)
    return len(str(messages)) // 4  # rough estimate


for info in pkgutil.iter_modules(providers.__path__):
    if info.name.startswith("_"):
        continue
    module = importlib.import_module(f"{__name__}.{info.name}")
    _PROVIDERS[module.provider] = module
    _MODELS[module.provider] = module.list_models()
