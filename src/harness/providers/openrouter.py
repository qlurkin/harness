import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

provider = "openrouter"
params = {
    "api_base": "https://openrouter.ai/api/v1",
    "custom_llm_provider": "openai",
    "temperature": 0.7,
    "max_tokens": 500,
    "drop_params": True,
}


context_limits = {}


# def get_context_limit(model):
#     return context_limits[model]


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

                # free_models.append(
                #     {
                #         "id": model.get("id"),
                #         "name": model.get("name"),
                #         "context_length": model.get("context_length"),
                #         "max_completion_tokens": model.get("top_provider", {}).get(
                #             "max_completion_tokens"
                #         ),
                #         "pricing": pricing,
                #     }
                # )

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
    params["api_key"] = key
    os.environ["OPENROUTER_API_KEY"] = key
    models = get_free_models(key)
except KeyError:
    models = []


def list_models():
    return ["openrouter/free"]
