import json
import os
import sys
import time
import traceback

import httpx

from common import ROOT
from settings import load_env, has_key, mask, provider_of
from models import MODELS

PING_TOOL = [{
    "type": "function",
    "function": {
        "name": "ping",
        "description": "Health check. Always call this tool.",
        "parameters": {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]},
    },
}]
PING_MESSAGES = [{"role": "user", "content": "Вызови инструмент ping с аргументом x=1. Ничего не пиши текстом."}]
ERROR_LOG = ROOT / "data" / "check_providers_errors.log"


def check_env():
    found = load_env()
    print("ключи окружения:")
    for canonical in ("GROQ_API_KEY", "OPENROUTER_API_KEY", "GIGACHAT_CREDENTIALS"):
        if canonical in found:
            print(f"  OK   {canonical:22s} из {found[canonical]:28s} {mask(os.environ[canonical])}")
        else:
            print(f"  --   {canonical:22s} не найден")
    print()


def check_openrouter_catalog():
    if not os.environ.get("OPENROUTER_API_KEY"):
        return
    try:
        r = httpx.get("https://openrouter.ai/api/v1/models", timeout=30)
        r.raise_for_status()
        catalog = {m["id"]: m for m in r.json()["data"]}
    except Exception as e:
        print(f"каталог OpenRouter недоступен: {e}\n")
        return
    print("каталог OpenRouter (семейство qwen3, плотные модели):")
    for mid, m in sorted(catalog.items()):
        if mid.startswith("qwen/qwen3-") and "-a" not in mid.split("qwen3-")[1]:
            tools = "tools" in m.get("supported_parameters", [])
            p = m.get("pricing", {})
            price = f"${float(p.get('prompt', 0)) * 1e6:.2f}/${float(p.get('completion', 0)) * 1e6:.2f} за 1M"
            print(f"  {mid:40s} tools={'да ' if tools else 'нет'} {price}")
    for cfg in MODELS:
        if provider_of(cfg["model"]) == "openrouter":
            mid = cfg["model"].split("/", 1)[1]
            if mid not in catalog:
                print(f"  ВНИМАНИЕ: {mid} из models.py нет в каталоге")
    print()


def ping(cfg):
    from litellm import completion
    kwargs = dict(model=cfg["model"], messages=PING_MESSAGES, tools=PING_TOOL,
                  tool_choice="auto", max_tokens=1024, timeout=60)
    kwargs.update(cfg.get("extra", {}))
    t0 = time.time()
    resp = completion(**kwargs)
    dt = time.time() - t0
    msg = resp.choices[0].message
    calls = getattr(msg, "tool_calls", None) or []
    if calls and calls[0].function.name == "ping":
        args = calls[0].function.arguments
        return "OK", f"tool_call ping({args}) за {dt:.1f}s"
    return "WARN", f"ответил без tool_call за {dt:.1f}s: {(msg.content or '')[:80]!r}"


def main():
    check_env()
    check_openrouter_catalog()
    import litellm
    litellm.drop_params = True
    litellm.suppress_debug_info = True
    only = set(sys.argv[1:])
    print("проверка моделей (один вызов с инструментом):")
    summary = {}
    error_blocks = []
    for cfg in MODELS:
        if only and cfg["label"] not in only:
            continue
        if not has_key(cfg["model"]):
            status, info = "SKIP", "нет ключа провайдера"
        else:
            try:
                status, info = ping(cfg)
            except Exception as e:
                tb = traceback.format_exc()
                error_blocks.append(f"==== {cfg['label']} ({cfg['model']}) ====\n{tb}")
                last_lines = tb.strip().splitlines()[-3:]
                status, info = "FAIL", " | ".join(last_lines)
        summary[cfg["label"]] = status
        print(f"  {status:4s} {cfg['label']:16s} {info}")

    if error_blocks:
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        ERROR_LOG.write_text("\n\n".join(error_blocks), encoding="utf-8")
        print(f"\nполные трейсбеки -> {ERROR_LOG}")

    usable = [k for k, v in summary.items() if v == "OK"]
    print(f"\nготовы к прогону: {', '.join(usable) if usable else 'нет'}")
    if usable:
        print(f"запуск: python run_matrix.py --models {' '.join(usable)}")


if __name__ == "__main__":
    main()
