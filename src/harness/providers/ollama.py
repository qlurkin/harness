import json
import urllib.request

provider = "ollama_chat"
api_base = "http://localhost:11434"


def list_models():
    request = urllib.request.Request(
        api_base + "/api/tags",
        method="GET",
    )

    with urllib.request.urlopen(request, timeout=90) as response:
        if response.status != 200:
            raise ValueError("Error while listing Ollama Models")

        models = json.load(response)["models"]

    return [f"{provider}/{m['name']}" for m in models]
