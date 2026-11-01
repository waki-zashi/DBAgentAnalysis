GIGACHAT_EXTRA = {"ssl_verify": False}

MODELS = [
    {"label": "gigachat-lite", "family": "gigachat", "params_b": None, "rank": 1,
     "model": "gigachat/GigaChat-2", "extra": GIGACHAT_EXTRA},
    {"label": "gigachat-pro", "family": "gigachat", "params_b": None, "rank": 2,
     "model": "gigachat/GigaChat-2-Pro", "extra": GIGACHAT_EXTRA},
    {"label": "gigachat-max", "family": "gigachat", "params_b": None, "rank": 3,
     "model": "gigachat/GigaChat-2-Max", "extra": GIGACHAT_EXTRA},

    {"label": "gpt-oss-20b", "family": "gpt-oss", "params_b": 20,
     "model": "groq/openai/gpt-oss-20b", "extra": {}},
    {"label": "gpt-oss-120b", "family": "gpt-oss", "params_b": 120,
     "model": "groq/openai/gpt-oss-120b", "extra": {}},
]

BY_LABEL = {m["label"]: m for m in MODELS}
