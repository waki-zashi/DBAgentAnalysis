import hashlib
import json
import re
import sys
from collections import defaultdict

import duckdb

from common import CLEAN_CSV, CLEAN_DB, CLEAN_MANIFEST, DIRTY_DB, JOURNAL, ROOT, TABLES

RULE_HEADER = re.compile(r"^--\s*@rule\s+(\S+)\s+(\S+)\s*$", re.M)


def load_rules():
    text = (ROOT / "oracle_rules.sql").read_text(encoding="utf-8")
    heads = list(RULE_HEADER.finditer(text))
    rules = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        rules.append((h.group(1), h.group(2), text[h.end():end].strip().rstrip(";")))
    return rules


def run(db_path, sql):
    con = duckdb.connect(str(db_path), read_only=True)
    keys = {int(r[0]) for r in con.execute(sql).fetchall()}
    con.close()
    return keys


def check_reference():
    manifest = json.loads(CLEAN_MANIFEST.read_text(encoding="utf-8"))
    ok = True
    for t in TABLES:
        actual = hashlib.sha256((CLEAN_CSV / f"{t}.csv").read_bytes()).hexdigest()
        same = actual == manifest["tables"][t]["sha256"]
        ok &= same
        if not same:
            print(f"  FAIL clean/{t}.csv differs from clean_manifest.json")
    print(f"  {'OK  ' if ok else 'FAIL'} clean CSV snapshot matches clean_manifest.json")
    return ok


def main():
    journal = json.loads(JOURNAL.read_text(encoding="utf-8"))
    truth = defaultdict(set)
    for e in journal["entries"]:
        for t in e["targets"]:
            truth[e["fault"]].add((t["table"], t["pk"]))

    ok = check_reference()
    print(f"\n{'rule':5s} {'table':12s} {'clean':>6s} {'dirty':>6s} {'truth':>6s} {'missed':>6s} {'extra':>6s}")
    for fault, table, sql in load_rules():
        clean_hits = run(CLEAN_DB, sql)
        dirty_hits = {(table, k) for k in run(DIRTY_DB, sql)}
        expected = truth[fault]
        missed, extra = expected - dirty_hits, dirty_hits - expected
        good = not clean_hits and not missed and not extra
        ok &= good
        print(f"{fault:5s} {table:12s} {len(clean_hits):6d} {len(dirty_hits):6d} {len(expected):6d} "
              f"{len(missed):6d} {len(extra):6d}  {'OK' if good else 'FAIL'}")
        if not good:
            print(f"      missed={sorted(missed)[:5]} extra={sorted(extra)[:5]}")

    covered = {f for f, _, _ in load_rules()}
    unknown = set(truth) - covered
    if unknown:
        ok = False
        print(f"FAIL faults without oracle rule: {sorted(unknown)}")

    print("\nSTAND OK" if ok else "\nSTAND BROKEN")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
