OPENROUTER_EXTRA = {"extra_body": {"provider": {"require_parameters": True}}}
GIGACHAT_EXTRA = {"ssl_verify": False}

MODELS = [
    {"label": "qwen3-8b", "family": "qwen3", "params_b": 8,
     "model": "openrouter/qwen/qwen3-vl-8b-instruct", "extra": OPENROUTER_EXTRA},
    {"label": "qwen3-14b", "family": "qwen3", "params_b": 14,
     "model": "openrouter/qwen/qwen3-14b", "extra": OPENROUTER_EXTRA},
    {"label": "qwen3-32b", "family": "qwen3", "params_b": 32,
     "model": "openrouter/qwen/qwen3-32b", "extra": OPENROUTER_EXTRA},

    {"label": "gigachat-lite", "family": "gigachat", "params_b": None, "rank": 1,
     "model": "gigachat/GigaChat-2-Lite", "extra": GIGACHAT_EXTRA},
    {"label": "gigachat-pro", "family": "gigachat", "params_b": None, "rank": 2,
     "model": "gigachat/GigaChat-2-Pro", "extra": GIGACHAT_EXTRA},
    {"label": "gigachat-max", "family": "gigachat", "params_b": None, "rank": 3,
     "model": "gigachat/GigaChat-2-Max", "extra": GIGACHAT_EXTRA},

    {"label": "llama-3.1-8b", "family": "llama", "params_b": 8,
     "model": "groq/llama-3.1-8b-instant", "extra": {}},
    {"label": "llama-3.3-70b", "family": "llama", "params_b": 70,
     "model": "groq/llama-3.3-70b-versatile", "extra": {}},
    {"label": "gpt-oss-20b", "family": "gpt-oss", "params_b": 20,
     "model": "groq/openai/gpt-oss-20b", "extra": {}},
    {"label": "gpt-oss-120b", "family": "gpt-oss", "params_b": 120,
     "model": "groq/openai/gpt-oss-120b", "extra": {}},
]

BY_LABEL = {m["label"]: m for m in MODELS}
