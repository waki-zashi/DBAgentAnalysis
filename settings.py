import os

from dotenv import load_dotenv

from common import ROOT

ALIASES = {
    "GROQ_API_KEY": ["GROQ_API_KEY", "GROQ_API_KEY_1", "GROQ_API_KEY_2", "GROQ_KEY", "GROQ_TOKEN", "GROQ_API_TOKEN"],
    "OPENROUTER_API_KEY": ["OPENROUTER_API_KEY", "OPENROUTER_KEY", "OPENROUTER_TOKEN",
                           "OPENROUTER_API_TOKEN", "OPEN_ROUTER_API_KEY"],
    "GIGACHAT_CREDENTIALS": ["GIGACHAT_CREDENTIALS", "GIGACHAT_AUTH_KEY", "GIGACHAT_AUTHORIZATION_KEY",
                             "GIGACHAT_API_KEY", "GIGACHAT_KEY", "GIGACHAT_TOKEN"],
}

PROVIDER_KEY = {"groq": "GROQ_API_KEY", "openrouter": "OPENROUTER_API_KEY", "gigachat": "GIGACHAT_CREDENTIALS"}


def load_env():
    load_dotenv(ROOT / ".env", override=False)
    found = {}
    for canonical, names in ALIASES.items():
        for name in names:
            value = os.environ.get(name, "").strip().strip('"').strip("'")
            if value:
                os.environ[canonical] = value
                found[canonical] = name
                break
    os.environ.setdefault("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    return found


def provider_of(model_id):
    return model_id.split("/", 1)[0]


def has_key(model_id):
    return bool(os.environ.get(PROVIDER_KEY[provider_of(model_id)]))


def mask(value):
    return f"{value[:4]}…{value[-2:]} (len {len(value)})" if len(value) > 8 else "***"
