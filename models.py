QWEN_LADDER = [
    ("qwen2.5-0.5b", 0.5, "qwen2.5-0.5b-instruct"),
    ("qwen2.5-1.5b", 1.5, "qwen2.5-1.5b-instruct"),
    ("qwen2.5-3b", 3, "qwen2.5-3b-instruct"),
    ("qwen2.5-7b", 7, "qwen2.5-7b-instruct"),
    ("qwen2.5-14b", 14, "qwen2.5-14b-instruct"),
    ("qwen2.5-32b", 32, "qwen2.5-32b-instruct"),
]

MODELS = [
    {"label": label, "family": "qwen2.5", "params_b": params_b, "rank": None,
     "model": f"openai/{served_name}", "extra": {"local": True}}
    for label, params_b, served_name in QWEN_LADDER
]

BY_LABEL = {m["label"]: m for m in MODELS}
