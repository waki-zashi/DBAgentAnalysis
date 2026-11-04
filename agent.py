import json
import time

import duckdb

from common import DIRTY_DB
from prompt import SYSTEM_PROMPT
from tools import TOOLS, format_for_model, run_sql

KICKOFF = ("Начинай исследование БД и формирование правил проверки качества данных. "
           "Когда закончишь, вызови submit_rules.")
REMINDER = "Используй один из инструментов: run_sql для исследования или submit_rules для финального ответа."
FINAL_NUDGE = ("Бюджет шагов почти исчерпан. Следующим действием вызови submit_rules "
               "со всеми правилами, которые ты успел сформировать.")


def call_model(completion_fn, model_cfg, messages, retries=4):
    kwargs = dict(model=model_cfg["model"], messages=messages, tools=TOOLS,
                  tool_choice="auto", timeout=180)
    kwargs.update(model_cfg.get("extra", {}))
    delay = 5.0
    for attempt in range(retries + 1):
        try:
            return completion_fn(**kwargs)
        except Exception as e:
            text = str(e).lower()
            transient = any(s in text for s in ("rate", "429", "timeout", "overloaded", "503", "502",
                                                  "temporar", "tool_use_failed",
                                                  "failed to parse tool call arguments"))
            if not transient or attempt == retries:
                raise
            time.sleep(delay)
            delay *= 2


def tool_call_to_dict(tc):
    return {"id": tc.id, "type": "function",
            "function": {"name": tc.function.name, "arguments": tc.function.arguments}}


def parse_args(raw):
    if isinstance(raw, dict):
        return raw
    return json.loads(raw or "{}")


def usage_of(response):
    u = getattr(response, "usage", None)
    if u is None:
        return 0, 0
    return getattr(u, "prompt_tokens", 0) or 0, getattr(u, "completion_tokens", 0) or 0


def run_episode(completion_fn, model_cfg, step_budget: int = 25, row_cap: int = 20):
    con = duckdb.connect(str(DIRTY_DB), read_only=True)
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": KICKOFF}]
    log = []
    status = "incomplete"
    rules = None
    tokens_in = tokens_out = 0

    for step in range(step_budget):
        t0 = time.time()
        try:
            response = call_model(completion_fn, model_cfg, messages)
        except Exception as e:
            log.append({"step": step, "event": "api_error", "error": " ".join(str(e).split())[:500]})
            status = "api_error"
            break
        latency = round(time.time() - t0, 2)
        p_in, p_out = usage_of(response)
        tokens_in += p_in
        tokens_out += p_out

        choice = response.choices[0].message
        tool_calls = getattr(choice, "tool_calls", None) or []

        if not tool_calls:
            messages.append({"role": "assistant", "content": choice.content or ""})
            messages.append({"role": "user", "content": REMINDER})
            log.append({"step": step, "event": "no_tool_call", "latency": latency,
                        "content": (choice.content or "")[:500]})
            continue

        messages.append({"role": "assistant", "content": choice.content or "",
                         "tool_calls": [tool_call_to_dict(tc) for tc in tool_calls]})

        stop = False
        for tc in tool_calls:
            name = tc.function.name
            try:
                args = parse_args(tc.function.arguments)
            except json.JSONDecodeError as e:
                messages.append({"role": "tool", "tool_call_id": tc.id, "name": name,
                                 "content": f"ERROR: could not parse arguments as JSON: {e}"})
                log.append({"step": step, "event": "bad_args", "tool": name, "latency": latency})
                continue

            if name == "run_sql":
                sql = args.get("sql", "")
                result = run_sql(con, sql, timeout_s=5.0, row_cap=row_cap)
                messages.append({"role": "tool", "tool_call_id": tc.id, "name": name,
                                 "content": format_for_model(result)})
                log.append({"step": step, "event": "run_sql", "sql": sql, "ok": result["ok"],
                            "error_kind": result.get("error_kind"), "latency": latency})

            elif name == "submit_rules":
                rules = args.get("rules", [])
                if isinstance(rules, str):
                    try:
                        rules = json.loads(rules)
                    except json.JSONDecodeError:
                        rules = []
                messages.append({"role": "tool", "tool_call_id": tc.id, "name": name,
                                 "content": "Rules received. Episode finished."})
                log.append({"step": step, "event": "submit_rules", "n_rules": len(rules),
                            "latency": latency})
                status = "ok"
                stop = True
                break

            else:
                messages.append({"role": "tool", "tool_call_id": tc.id, "name": name,
                                 "content": f"ERROR: unknown tool '{name}'"})
                log.append({"step": step, "event": "unknown_tool", "tool": name, "latency": latency})

        if stop:
            break
        if step == step_budget - 2:
            messages.append({"role": "user", "content": FINAL_NUDGE})

    con.close()
    return {"status": status, "rules": rules, "log": log, "messages": messages,
            "n_steps": len(log), "tokens_in": tokens_in, "tokens_out": tokens_out}
