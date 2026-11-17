import json
from collections.abc import AsyncGenerator
from pathlib import Path
from urllib.request import Request, urlopen

from openai import AsyncOpenAI

from harness.message import Message
from harness.providers._openai_stream import consume_stream

provider = "openrouter"
BASE_URL = "https://openrouter.ai/api/v1"
TEMPERATURE = 0.7
MAX_TOKENS = 500
_api_key: str | None = None


context_limits = {}


def get_context_limit(model):
    return context_limits.get(model)


def get_free_models(api_key=None):
    url = "https://openrouter.ai/api/v1/models"

    headers = {
        "Accept": "application/json",
    }

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = Request(url, headers=headers)

    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))

        free_models = []
        context_limits.clear()

        for model in result.get("data", []):
            pricing = model.get("pricing", {})
            architecture = model.get("architecture", {})

            # Vérifier que le modèle est gratuit
            if (
                float(pricing.get("prompt", -1)) == 0
                and float(pricing.get("completion", -1)) == 0
            ):
                # Vérifier que le modèle génère du texte
                output_modalities = architecture.get("output_modalities", [])

                if "text" not in output_modalities:
                    continue

                free_models.append(f"{provider}/{model.get('id')}")
                context_limits[model.get("id")] = model.get("context_length")

        return free_models

    except OSError as e:
        print(f"Erreur API : {e}")
        return []


config_path = Path.home() / ".config" / "harness" / "auth.json"

try:
    with open(config_path) as file:
        config = json.load(file)
except FileNotFoundError:
    config = {}

try:
    key = config["openrouter"]["key"]
    _api_key = key
    models = get_free_models(key)
except KeyError:
    models = []


def list_models():
    return models


def _clean(m: dict) -> dict:
    return {k: v for k, v in m.items() if k != "thinking_blocks"}


async def chat(
    model: str,
    effort: str,
    messages: list[dict],
    tools: list[dict] | None = None,
) -> AsyncGenerator[tuple[Message, int]]:
    client = AsyncOpenAI(base_url=BASE_URL, api_key=_api_key or "missing")

    extra_body = {}
    if effort in ("none", "minimal", "low", "medium", "high", "xhigh"):
        extra_body["reasoning"] = {"effort": effort}

    kwargs = {}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    stream = await client.chat.completions.create(
        model=model,
        messages=[_clean(m) for m in messages],
        stream=True,
        stream_options={"include_usage": True},
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        extra_body=extra_body,
        **kwargs,
    )  # ty: ignore[no-matching-overload]
    async for item in consume_stream(stream):
        yield item
