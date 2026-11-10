provider = "github_copilot"
api_base = None

anthropic = [
    "claude-haiku-5.5",
    "claude-sonnet-5.5",
    "claude-sonnet-5",
    "claude-haiku-4.5",
]


def list_models():
    models = [
        "gpt-5.3-codex",
        "claude-haiku-5.5",
        "claude-sonnet-5.5",
        "claude-sonnet-5",
        "claude-haiku-4.5",
        "gemini-3.8-flash",
        "gpt-5.6-luna",
        "gpt-5.6-terra",
        "gpt-6.1-terra",
        "gpt-6-luna",
        "grok-4.6",
        "grok-4.7",
        "kimi-k3",
        "mai-code-1.1-flash",
    ]

    return [f"{provider}/{m}" for m in models]
