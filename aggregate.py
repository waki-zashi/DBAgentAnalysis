import csv
import json
import statistics as st
from collections import defaultdict

from common import ROOT
from models import MODELS

RESULTS_DIR = ROOT / "data" / "results"
RUNS_CSV = ROOT / "data" / "results_runs.csv"
SUMMARY_CSV = ROOT / "data" / "results_summary.csv"
FAULTS_CSV = ROOT / "data" / "results_by_fault.csv"
PLOT = ROOT / "data" / "results_plot.png"

METRICS = ["completed", "n_rules", "execution_rate", "schema_hallucination_rate",
           "precision_overall", "coverage_L1", "coverage_L2", "coverage_L3", "n_sql_calls", "tokens_in"]
ORDER = {m["label"]: i for i, m in enumerate(MODELS)}


def load_runs():
    runs = []
    for path in sorted(RESULTS_DIR.glob("*_run*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        ev = rec.get("evaluation") or {}
        cov = ev.get("coverage_by_level", {})
        row = {"model": rec["model"], "family": rec.get("family"), "repeat": rec["repeat"],
               "status": rec["status"], "completed": 1.0 if rec["status"] == "ok" else 0.0,
               "n_steps": rec["n_steps"], "n_sql_calls": rec.get("n_sql_calls", 0),
               "tokens_in": rec.get("tokens_in", 0), "elapsed_s": rec.get("elapsed_s")}
        if ev:
            row.update(n_rules=ev["n_rules"], execution_rate=ev["execution_rate"],
                       schema_hallucination_rate=ev["schema_hallucination_rate"],
                       precision_overall=ev["precision_overall"],
                       coverage_L1=cov.get("L1", 0.0), coverage_L2=cov.get("L2", 0.0),
                       coverage_L3=cov.get("L3", 0.0))
        else:
            row.update(n_rules=0, execution_rate=None, schema_hallucination_rate=None,
                       precision_overall=None, coverage_L1=0.0, coverage_L2=0.0, coverage_L3=0.0)
        row["_fault_cov"] = {f: c["coverage"] for f, c in ev.get("coverage_by_fault", {}).items()}
        runs.append(row)
    return runs


def mean_std(values):
    values = [v for v in values if v is not None]
    if not values:
        return None, None
    return st.mean(values), (st.stdev(values) if len(values) > 1 else 0.0)


def write_csv(path, rows):
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    runs = load_runs()
    if not runs:
        print("no results in", RESULTS_DIR)
        return
    write_csv(RUNS_CSV, [{k: v for k, v in r.items() if k != "_fault_cov"} for r in runs])

    by_model = defaultdict(list)
    for r in runs:
        by_model[r["model"]].append(r)
    models = sorted(by_model, key=lambda m: ORDER.get(m, 999))

    summary = []
    for m in models:
        row = {"model": m, "family": by_model[m][0]["family"], "n_runs": len(by_model[m])}
        for metric in METRICS:
            mu, sd = mean_std([r[metric] for r in by_model[m]])
            row[f"{metric}_mean"] = None if mu is None else round(mu, 3)
            row[f"{metric}_std"] = None if sd is None else round(sd, 3)
        summary.append(row)
    write_csv(SUMMARY_CSV, summary)

    faults = sorted({f for r in runs for f in r["_fault_cov"]})
    fault_rows = []
    for m in models:
        row = {"model": m}
        for f in faults:
            mu, _ = mean_std([r["_fault_cov"].get(f, 0.0) for r in by_model[m]])
            row[f] = round(mu, 2)
        fault_rows.append(row)
    if faults:
        write_csv(FAULTS_CSV, fault_rows)

    header = f"{'model':16s} {'runs':>4s} {'done':>5s} {'rules':>6s} {'exec':>5s} {'prec':>5s} {'L1':>5s} {'L2':>5s} {'L3':>5s}"
    print(header)
    fmt = lambda v: "  -  " if v is None else f"{v:5.2f}"
    for s in summary:
        print(f"{s['model']:16s} {s['n_runs']:4d} {fmt(s['completed_mean'])} {s['n_rules_mean'] or 0:6.1f} "
              f"{fmt(s['execution_rate_mean'])} {fmt(s['precision_overall_mean'])} "
              f"{fmt(s['coverage_L1_mean'])} {fmt(s['coverage_L2_mean'])} {fmt(s['coverage_L3_mean'])}")
    print(f"\n-> {RUNS_CSV.name}, {SUMMARY_CSV.name}, {FAULTS_CSV.name}")
    plot(summary)


def plot(summary):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    metrics = [("coverage_L1", "Покрытие L1"), ("coverage_L2", "Покрытие L2"),
               ("coverage_L3", "Покрытие L3"), ("precision_overall", "Precision"),
               ("execution_rate", "Execution rate")]
    labels = [s["model"] for s in summary]
    fig, ax = plt.subplots(figsize=(max(6, 1.1 * len(labels) + 3), 4.5))
    width = 0.8 / len(metrics)
    for i, (key, name) in enumerate(metrics):
        means = [s[f"{key}_mean"] or 0 for s in summary]
        stds = [s[f"{key}_std"] or 0 for s in summary]
        xs = [j + (i - (len(metrics) - 1) / 2) * width for j in range(len(labels))]
        ax.bar(xs, means, width, yerr=stds, capsize=2, label=name)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("среднее по повторам")
    ax.legend(ncol=5, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.28))
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(PLOT, dpi=150)
    print(f"-> {PLOT.name}")


if __name__ == "__main__":
    main()
