import argparse
import json
import sys
import time

from common import ROOT
from settings import load_env, has_key
from models import MODELS, BY_LABEL

RESULTS_DIR = ROOT / "data" / "results"


def run_one(completion_fn, model_cfg, repeat_idx, step_budget, out_dir):
    from agent import run_episode
    from evaluate import evaluate_rules

    label = model_cfg["label"]
    t0 = time.time()
    episode = run_episode(completion_fn, model_cfg, step_budget=step_budget)
    elapsed = time.time() - t0

    record = {"model": label, "family": model_cfg["family"], "params_b": model_cfg.get("params_b"),
              "rank": model_cfg.get("rank"), "model_id": model_cfg["model"], "repeat": repeat_idx,
              "status": episode["status"], "n_steps": episode["n_steps"],
              "n_sql_calls": sum(1 for e in episode["log"] if e["event"] == "run_sql"),
              "tokens_in": episode["tokens_in"], "tokens_out": episode["tokens_out"],
              "elapsed_s": round(elapsed, 1), "rules": episode["rules"], "log": episode["log"]}

    if episode["status"] == "ok":
        evaluation = evaluate_rules(episode["rules"] or [])
        record["evaluation"] = evaluation["summary"]
        record["rule_reports"] = [{k: v for k, v in r.items() if k != "keys"} for r in evaluation["rules"]]

    (out_dir / f"{label}_run{repeat_idx}.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (out_dir / "transcripts").mkdir(exist_ok=True)
    (out_dir / "transcripts" / f"{label}_run{repeat_idx}.json").write_text(
        json.dumps(episode["messages"], ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", help="labels from models.py; default: all with keys")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--steps", type=int, default=15)
    ap.add_argument("--force", action="store_true", help="rerun even if result file exists")
    args = ap.parse_args()

    load_env()
    from litellm import completion
    import litellm
    litellm.drop_params = True
    litellm.suppress_debug_info = True

    if args.models:
        unknown = [m for m in args.models if m not in BY_LABEL]
        if unknown:
            sys.exit(f"unknown models: {unknown}; available: {list(BY_LABEL)}")
        models = [BY_LABEL[m] for m in args.models]
    else:
        models = [m for m in MODELS if has_key(m["model"])]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for cfg in models:
        if not has_key(cfg["model"]):
            print(f"[{cfg['label']}] skip: no API key", file=sys.stderr)
            continue
        for k in range(args.repeats):
            path = RESULTS_DIR / f"{cfg['label']}_run{k}.json"
            if path.exists() and not args.force:
                print(f"[{cfg['label']}] run {k}: exists, skip", file=sys.stderr)
                continue
            print(f"[{cfg['label']}] run {k + 1}/{args.repeats} ...", file=sys.stderr, flush=True)
            try:
                rec = run_one(completion, cfg, k, args.steps, RESULTS_DIR)
            except Exception as e:
                print(f"[{cfg['label']}] run {k} FAILED: {e}", file=sys.stderr)
                continue
            ev = rec.get("evaluation")
            line = f"[{cfg['label']}] run {k + 1}: {rec['status']}, {rec['n_steps']} steps, {rec['elapsed_s']}s"
            if ev:
                c = ev["coverage_by_level"]
                line += (f" | rules={ev['n_rules']} exec={ev['execution_rate']:.2f} "
                         f"prec={ev['precision_overall']:.2f} "
                         f"cov L1={c.get('L1', 0):.2f} L2={c.get('L2', 0):.2f} L3={c.get('L3', 0):.2f}")
            print(line, file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
