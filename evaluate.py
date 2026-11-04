import json
from collections import defaultdict

import duckdb

from common import DIRTY_DB, JOURNAL, TABLES
from tools import run_sql


def load_truth():
    journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
    truth_by_fault = defaultdict(set)
    truth_by_table = defaultdict(set)
    fault_meta = {f["id"]: f for f in journal["faults"]}
    for e in journal["entries"]:
        for t in e["targets"]:
            truth_by_fault[e["fault"]].add(t["pk"])
            truth_by_table[t["table"]].add(t["pk"])
    return fault_meta, truth_by_fault, truth_by_table


def evaluate_rules(rules, timeout_s: float = 10.0):
    fault_meta, truth_by_fault, truth_by_table = load_truth()
    con = duckdb.connect(str(DIRTY_DB), read_only=True)

    rule_reports = []
    for i, r in enumerate(rules):
        table = r.get("table")
        sql = r.get("sql", "")
        report = {"index": i, "table": table, "dimension": r.get("dimension"),
                  "description": r.get("description"), "sql": sql}

        if table not in TABLES:
            report.update(status="error", error_kind="schema",
                          error=f"unknown table '{table}'")
            rule_reports.append(report)
            continue

        result = run_sql(con, sql, timeout_s=timeout_s, row_cap=None)
        if not result["ok"]:
            report.update(status="error", error_kind=result["error_kind"], error=result["error"])
            rule_reports.append(report)
            continue

        try:
            keys = {int(row[0]) for row in result["rows"]}
        except (TypeError, ValueError, IndexError):
            report.update(status="error", error_kind="schema",
                          error="first column is not a single integer key")
            rule_reports.append(report)
            continue

        truth_table = truth_by_table[table]
        hit = keys & truth_table
        precision = len(hit) / len(keys) if keys else None
        report.update(status="ok", n_rows=len(keys), n_hit=len(hit), precision=precision,
                      keys=sorted(keys))
        rule_reports.append(report)

    con.close()

    coverage = {}
    for fid, fault in fault_meta.items():
        target = truth_by_fault[fid]
        best = 0.0
        best_rule = None
        for rep in rule_reports:
            if rep["status"] != "ok" or rep["table"] != fault["table"]:
                continue
            hit = len(set(rep["keys"]) & target)
            c = hit / len(target) if target else 0.0
            if c > best:
                best, best_rule = c, rep["index"]
        coverage[fid] = {"level": fault["level"], "dimension": fault["dimension"],
                         "coverage": best, "best_rule": best_rule, "n_targets": len(target)}

    n_total = len(rule_reports)
    n_ok = sum(1 for r in rule_reports if r["status"] == "ok")
    n_schema_err = sum(1 for r in rule_reports if r["status"] == "error" and r["error_kind"] == "schema")

    cov_by_level = defaultdict(list)
    for c in coverage.values():
        cov_by_level[c["level"]].append(c["coverage"])
    coverage_by_level = {lvl: sum(v) / len(v) for lvl, v in cov_by_level.items()}

    prec_by_table = defaultdict(list)
    for r in rule_reports:
        if r["status"] == "ok" and r["precision"] is not None:
            prec_by_table[r["table"]].append(r["precision"])
    precision_by_table = {t: sum(v) / len(v) for t, v in prec_by_table.items()}

    precise_rules = [r["precision"] for r in rule_reports if r["status"] == "ok" and r["precision"] is not None]
    n_fired = len(precise_rules)

    summary = {
        "n_rules": n_total,
        "execution_rate": n_ok / n_total if n_total else 0.0,
        "schema_hallucination_rate": n_schema_err / n_total if n_total else 0.0,
        "coverage_by_fault": coverage,
        "coverage_by_level": coverage_by_level,
        "precision_by_table": precision_by_table,
        "n_rules_fired": n_fired,
        "precision_overall": (sum(precise_rules) / n_fired) if n_fired else None,
    }
    return {"summary": summary, "rules": rule_reports}


def print_report(result):
    s = result["summary"]
    print(f"rules submitted: {s['n_rules']}")
    print(f"execution rate:  {s['execution_rate']:.2f}")
    print(f"schema halluc.:  {s['schema_hallucination_rate']:.2f}")
    prec_str = f"{s['precision_overall']:.2f}" if s['precision_overall'] is not None else "n/a (ни одно правило не нашло ни строки)"
    print(f"precision (all): {prec_str}")
    print("precision by table:")
    for t, p in sorted(s["precision_by_table"].items()):
        print(f"  {t:12s} {p:.2f}")
    print("coverage by level:")
    for lvl, c in sorted(s["coverage_by_level"].items()):
        print(f"  {lvl:4s} {c:.2f}")
    print("coverage by fault:")
    for fid, c in sorted(s["coverage_by_fault"].items()):
        print(f"  {fid:5s} {c['level']:4s} {c['coverage']:.2f}  (best_rule={c['best_rule']})")


if __name__ == "__main__":
    import sys
    rules = json.loads(sys.stdin.read())
    result = evaluate_rules(rules)
    print_report(result)
