import httpx

r = httpx.get("https://openrouter.ai/api/v1/models", timeout=30)
r.raise_for_status()
models = r.json()["data"]

free = [m for m in models if m["id"].endswith(":free")]
free.sort(key=lambda m: m["id"])

print(f"всего бесплатных моделей: {len(free)}\n")
for m in free:
    sp = m.get("supported_parameters", [])
    tools = "tools" in sp
    ctx = m.get("context_length", "?")
    print(f"{m['id']:55s} tools={'да ' if tools else 'нет'} ctx={ctx}")
