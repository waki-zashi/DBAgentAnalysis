import csv
import datetime as dt
import json
import sys
from collections import Counter

import numpy as np
import pandas as pd

from common import (CHANGES_CSV, CHANGES_MD, CLEAN_DB, CLEAN_MANIFEST, DIRTY_CSV, DIRTY_DB,
                    DIRTY_MANIFEST, JOURNAL, ROOT, TABLES, export_csv, read_db, write_db,
                    write_manifest)

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
PAID_STATUSES = ["paid", "shipped", "delivered"]
STATUS_TYPOS = {"new": "NEW ", "paid": "PAID", "shipped": "shiped",
                "delivered": "Delivered", "cancelled": "canceled"}
CITY_PLACEHOLDERS = ["", " ", "N/A", "-", "нет данных"]
HOUR = pd.Timedelta(hours=1)
DAY = pd.Timedelta(days=1)


def plain(x):
    if x is None:
        return None
    if isinstance(x, (pd.Timestamp, dt.datetime)):
        return None if pd.isna(x) else pd.Timestamp(x).isoformat(sep=" ")
    if isinstance(x, dt.date):
        return x.isoformat()
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if np.isnan(x) else round(float(x), 2)
    return x


class Injector:
    def __init__(self, frames, rng):
        self.t = {name: df.set_index(pk, drop=False) for name, (pk, df)
                  in ((n, (TABLES[n], frames[n])) for n in TABLES)}
        self.rng = rng
        self.used = {name: set() for name in TABLES}
        self.next_id = {name: int(self.t[name].index.max()) + 1 for name in TABLES}
        self.entries = []
        self.changes = []

    def pick(self, table, candidates, n):
        pool = sorted(k for k in candidates if k not in self.used[table])
        if len(pool) < n:
            raise RuntimeError(f"not enough rows in {table}: need {n}, have {len(pool)}")
        chosen = [int(k) for k in self.rng.choice(pool, n, replace=False)]
        self.used[table].update(chosen)
        return chosen

    def pick_items(self, candidates, n):
        items = self.t["order_items"]
        pool = [k for k in sorted(candidates)
                if k not in self.used["order_items"]
                and items.at[k, "order_id"] not in self.used["orders"]]
        self.rng.shuffle(pool)
        chosen = []
        for k in pool:
            oid = int(items.at[k, "order_id"])
            if oid in self.used["orders"]:
                continue
            chosen.append(int(k))
            self.used["order_items"].add(int(k))
            self.used["orders"].add(oid)
            if len(chosen) == n:
                return chosen
        raise RuntimeError(f"not enough order_items: need {n}, have {len(chosen)}")

    def set(self, table, pk, column, value):
        old = self.t[table].at[pk, column]
        self.t[table].at[pk, column] = value
        self.changes.append({"op": "update", "table": table, "pk": int(pk), "column": column,
                             "old": plain(old), "new": plain(value)})

    def delete(self, table, pk):
        row = {c: plain(v) for c, v in self.t[table].loc[pk].items()}
        self.t[table] = self.t[table].drop(index=pk)
        self.changes.append({"op": "delete", "table": table, "pk": int(pk), "column": None,
                             "old": row, "new": None})

    def insert(self, table, row):
        pk_col = TABLES[table]
        pk = self.next_id[table]
        self.next_id[table] += 1
        self.used[table].add(pk)
        row = dict(row)
        row[pk_col] = pk
        new = pd.DataFrame([row], columns=self.t[table].columns).set_index(pk_col, drop=False)
        new = new.astype(self.t[table].dtypes.to_dict())
        self.t[table] = pd.concat([self.t[table], new])
        self.changes.append({"op": "insert", "table": table, "pk": pk, "column": None,
                             "old": None, "new": {c: plain(v) for c, v in row.items()}})
        return pk

    def record(self, fault, targets, note=None):
        self.entries.append({"fault": fault["id"], "level": fault["level"],
                             "dimension": fault["dimension"],
                             "targets": [{"table": t, "pk": int(k)} for t, k in targets],
                             "note": note, "changes": self.changes})
        self.changes = []

    def payment_of(self, oid):
        p = self.t["payments"]
        hit = p.index[p["order_id"] == oid]
        return int(hit[0]) if len(hit) else None

    def recompute_order(self, oid):
        items = self.t["order_items"]
        rows = items[items["order_id"] == oid]
        cents = int(np.round(rows["quantity"] * rows["unit_price"] * 100).sum())
        total = cents / 100.0
        self.set("orders", oid, "total_amount", total)
        pid = self.payment_of(oid)
        if pid is not None:
            self.used["payments"].add(pid)
            self.set("payments", pid, "amount", total)
        return total

    def frames(self):
        return {name: df.reset_index(drop=True) for name, df in self.t.items()}


def orders_where(inj, mask):
    o = inj.t["orders"]
    return o.index[mask(o)].tolist()


def f01(inj, f):
    for cid in inj.pick("customers", inj.t["customers"].index, f["count"]):
        inj.set("customers", cid, "email", None)
        inj.record(f, [("customers", cid)])


def f02(inj, f):
    for cid in inj.pick("customers", inj.t["customers"].index, f["count"]):
        inj.set("customers", cid, "city", str(inj.rng.choice(CITY_PLACEHOLDERS)))
        inj.record(f, [("customers", cid)])


def f03(inj, f):
    def corrupt(email, kind):
        local, domain = email.split("@")
        return {0: local + domain,
                1: f"{local}@@{domain}",
                2: f"{local} @{domain}",
                3: f"{local}@{domain.replace('.', '')}"}[kind]

    for cid in inj.pick("customers", inj.t["customers"].index, f["count"]):
        kind = int(inj.rng.integers(0, 4))
        inj.set("customers", cid, "email", corrupt(inj.t["customers"].at[cid, "email"], kind))
        inj.record(f, [("customers", cid)])


def f04(inj, f):
    for pid in inj.pick("products", inj.t["products"].index, f["count"]):
        price = float(inj.t["products"].at[pid, "price"])
        inj.set("products", pid, "price", 0.0 if inj.rng.random() < 0.5 else -price)
        inj.record(f, [("products", pid)])


def f05(inj, f):
    items = inj.t["order_items"]
    sizes = items.groupby("order_id")["order_item_id"].transform("count")
    for iid in inj.pick_items(items.index[sizes >= 2], f["count"]):
        oid = int(items.at[iid, "order_id"])
        rows = items[items["order_id"] == oid]
        others = float((rows["quantity"] * rows["unit_price"]).sum()
                       - items.at[iid, "quantity"] * items.at[iid, "unit_price"])
        qty = int(inj.rng.choice([0, -1, -2]))
        if others + qty * float(items.at[iid, "unit_price"]) <= 0:
            qty = 0
        inj.set("order_items", iid, "quantity", qty)
        inj.recompute_order(oid)
        inj.record(f, [("order_items", iid)])


def f06(inj, f):
    for oid in inj.pick("orders", inj.t["orders"].index, f["count"]):
        inj.set("orders", oid, "status", STATUS_TYPOS[inj.t["orders"].at[oid, "status"]])
        inj.record(f, [("orders", oid)])


def f07(inj, f):
    c = inj.t["customers"]
    for cid in inj.pick("customers", c.index, f["count"]):
        reg = c.at[cid, "registered_at"]
        if inj.rng.random() < 0.5:
            birth = (reg + pd.Timedelta(days=int(inj.rng.integers(30, 2000)))).normalize()
        else:
            birth = pd.Timestamp(int(inj.rng.integers(1850, 1900)), int(inj.rng.integers(1, 13)),
                                 int(inj.rng.integers(1, 29)))
        inj.set("customers", cid, "birth_date", birth)
        inj.record(f, [("customers", cid)])


def f08(inj, f):
    c = inj.t["customers"]
    for cid in inj.pick("customers", c.index, f["count"]):
        row = c.loc[cid].to_dict()
        new_id = inj.insert("customers", row)
        inj.record(f, [("customers", cid), ("customers", new_id)])


def f09(inj, f):
    c = inj.t["customers"]
    cities = sorted(set(c["city"].dropna()) - set(CITY_PLACEHOLDERS))
    for cid in inj.pick("customers", c.index, f["count"]):
        row = c.loc[cid].to_dict()
        local, domain = row["email"].split("@")
        row["email"] = f"{local[:1].upper()}{local[1:]}@{domain.upper()}"
        row["city"] = str(inj.rng.choice([x for x in cities if x != row["city"]]))
        row["phone"] = None
        row["registered_at"] = row["registered_at"] + pd.Timedelta(days=int(inj.rng.integers(30, 400)))
        new_id = inj.insert("customers", row)
        inj.record(f, [("customers", cid), ("customers", new_id)])


def f10(inj, f):
    o = inj.t["orders"]
    candidates = orders_where(inj, lambda d: d["status"].isin(["shipped", "delivered"]))
    for oid in inj.pick("orders", candidates, f["count"]):
        if o.at[oid, "status"] == "delivered" and inj.rng.random() < 0.5:
            hours = int(inj.rng.integers(1, 48))
            inj.set("orders", oid, "delivered_at", o.at[oid, "shipped_at"] - hours * HOUR)
        else:
            hours = int(inj.rng.integers(1, 72))
            inj.set("orders", oid, "shipped_at", o.at[oid, "ordered_at"] - hours * HOUR)
        inj.record(f, [("orders", oid)])


def f11(inj, f):
    o = inj.t["orders"]
    n = f["count"]
    split = {"cancelled": n * 3 // 7, "delivered": n * 2 // 7}
    split["new"] = n - split["cancelled"] - split["delivered"]
    for status, k in split.items():
        for oid in inj.pick("orders", orders_where(inj, lambda d: d["status"] == status), k):
            if status == "cancelled":
                shipped = o.at[oid, "ordered_at"] + int(inj.rng.integers(6, 96)) * HOUR
                inj.set("orders", oid, "shipped_at", shipped)
                inj.set("orders", oid, "delivered_at", shipped + int(inj.rng.integers(1, 10)) * DAY)
            elif status == "delivered":
                inj.set("orders", oid, "delivered_at", pd.NaT)
            else:
                inj.set("orders", oid, "shipped_at",
                        o.at[oid, "ordered_at"] + int(inj.rng.integers(6, 96)) * HOUR)
            inj.record(f, [("orders", oid)], note=status)


def f12(inj, f):
    items = inj.t["order_items"]
    for iid in inj.pick_items(items.index, f["count"]):
        oid = int(items.at[iid, "order_id"])
        inj.set("order_items", iid, "unit_price", round(float(items.at[iid, "unit_price"]) * 100, 2))
        inj.recompute_order(oid)
        inj.record(f, [("order_items", iid)])


def f13(inj, f):
    for i, oid in enumerate(inj.pick("orders", inj.t["orders"].index, f["count"])):
        inj.set("orders", oid, "customer_id", 900000 + i)
        inj.record(f, [("orders", oid)])


def f14(inj, f):
    for i, iid in enumerate(inj.pick_items(inj.t["order_items"].index, f["count"])):
        inj.set("order_items", iid, "product_id", 90000 + i)
        inj.record(f, [("order_items", iid)])


def f15(inj, f):
    o = inj.t["orders"]
    for oid in inj.pick("orders", o.index, f["count"]):
        total = float(o.at[oid, "total_amount"])
        factor = inj.rng.uniform(0.5, 0.9) if inj.rng.random() < 0.5 else inj.rng.uniform(1.1, 1.5)
        new_total = round(total * factor, 2)
        inj.set("orders", oid, "total_amount", new_total)
        pid = inj.payment_of(oid)
        if pid is not None:
            inj.used["payments"].add(pid)
            inj.set("payments", pid, "amount", new_total)
        inj.record(f, [("orders", oid)])


def f16(inj, f):
    p = inj.t["payments"]
    o = inj.t["orders"]
    candidates = [pid for pid in p.index if int(p.at[pid, "order_id"]) not in inj.used["orders"]]
    for pid in inj.pick("payments", candidates, f["count"]):
        oid = int(p.at[pid, "order_id"])
        inj.used["orders"].add(oid)
        total = float(o.at[oid, "total_amount"])
        if inj.rng.random() < 0.5:
            amount = round(total * inj.rng.uniform(0.3, 0.95), 2)
        else:
            amount = round(total + float(inj.rng.integers(1, 500)), 2)
        inj.set("payments", pid, "amount", amount)
        inj.record(f, [("payments", pid)])


def f17(inj, f):
    candidates = orders_where(inj, lambda d: d["status"].isin(PAID_STATUSES))
    for oid in inj.pick("orders", candidates, f["count"]):
        pid = inj.payment_of(oid)
        inj.used["payments"].add(pid)
        inj.delete("payments", pid)
        inj.record(f, [("orders", oid)])


def f18(inj, f):
    o = inj.t["orders"]
    c = inj.t["customers"]
    for oid in inj.pick("orders", o.index, f["count"]):
        reg = c.at[int(o.at[oid, "customer_id"]), "registered_at"]
        ordered = reg - pd.Timedelta(days=int(inj.rng.integers(1, 60)), hours=int(inj.rng.integers(0, 24)))
        inj.set("orders", oid, "ordered_at", ordered)
        inj.record(f, [("orders", oid)])


def f19(inj, f):
    items = inj.t["order_items"]
    for oid in inj.pick("orders", inj.t["orders"].index, f["count"]):
        for iid in items.index[items["order_id"] == oid].tolist():
            inj.used["order_items"].add(int(iid))
            inj.delete("order_items", iid)
        items = inj.t["order_items"]
        inj.record(f, [("orders", oid)])


HANDLERS = {"F01": f01, "F02": f02, "F03": f03, "F04": f04, "F05": f05, "F06": f06, "F07": f07,
            "F08": f08, "F09": f09, "F10": f10, "F11": f11, "F12": f12, "F13": f13, "F14": f14,
            "F15": f15, "F16": f16, "F17": f17, "F18": f18, "F19": f19}


def write_changes_csv(entries):
    with CHANGES_CSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["fault", "level", "op", "table", "pk", "column", "old", "new"])
        for e in entries:
            for ch in e["changes"]:
                old = json.dumps(ch["old"], ensure_ascii=False) if isinstance(ch["old"], dict) else ch["old"]
                new = json.dumps(ch["new"], ensure_ascii=False) if isinstance(ch["new"], dict) else ch["new"]
                w.writerow([e["fault"], e["level"], ch["op"], ch["table"], ch["pk"], ch["column"], old, new])


def write_changes_md(catalog, entries, clean_manifest, dirty_tables):
    n_targets = Counter()
    n_changes = Counter()
    for e in entries:
        n_targets[e["fault"]] += len(e["targets"])
        n_changes[e["fault"]] += len(e["changes"])
    lines = [
        "# Журнал загрязнения БД",
        "",
        "Файл сгенерирован `inject_faults.py`, руками не редактируется.",
        "",
        f"- seed загрязнения: `{SEED}`",
        f"- seed чистой БД: `{clean_manifest['seed']}`",
        f"- дата генерации: {dt.datetime.now().isoformat(timespec='seconds')}",
        "- полный построчный журнал: `data/journal.json` (эталон для оценки), плоская таблица всех изменений: `data/changes.csv`",
        "",
        "## Размеры таблиц",
        "",
        "| Таблица | Чистая | Грязная | Δ |",
        "|---|---:|---:|---:|",
    ]
    for t in TABLES:
        a, b = clean_manifest["tables"][t]["rows"], dirty_tables[t]["rows"]
        lines.append(f"| {t} | {a} | {b} | {b - a:+d} |")
    lines += ["", "## Внедрённые дефекты", "",
              "| ID | Ур. | Измерение | Таблица | Дефект | Эпизодов | Строк-нарушителей | Изменений |",
              "|---|---|---|---|---|---:|---:|---:|"]
    episodes = Counter(e["fault"] for e in entries)
    for f in catalog:
        lines.append(f"| {f['id']} | {f['level']} | {f['dimension']} | {f['table']} | {f['description']} | "
                     f"{episodes[f['id']]} | {n_targets[f['id']]} | {n_changes[f['id']]} |")
    lines += ["", f"Всего строк-нарушителей: {sum(n_targets.values())}, "
                  f"атомарных изменений: {sum(n_changes.values())}.", "",
              "## Примеры изменений", ""]
    for f in catalog:
        sample = [e for e in entries if e["fault"] == f["id"]][:3]
        lines.append(f"### {f['id']} — {f['description']}")
        lines.append("")
        for e in sample:
            for ch in e["changes"][:3]:
                if ch["op"] == "update":
                    lines.append(f"- `{ch['table']}[{ch['pk']}].{ch['column']}`: `{ch['old']}` → `{ch['new']}`")
                elif ch["op"] == "insert":
                    lines.append(f"- insert `{ch['table']}[{ch['pk']}]` (копия `{e['targets'][0]['pk']}`)")
                else:
                    lines.append(f"- delete `{ch['table']}[{ch['pk']}]`")
        lines.append("")
    CHANGES_MD.write_text("\n".join(lines), encoding="utf-8")


def main():
    catalog = json.loads((ROOT / "faults.json").read_text(encoding="utf-8"))
    clean_manifest = json.loads(CLEAN_MANIFEST.read_text(encoding="utf-8"))
    inj = Injector(read_db(CLEAN_DB), np.random.default_rng(SEED))
    for fault in catalog:
        HANDLERS[fault["id"]](inj, fault)

    write_db(DIRTY_DB, inj.frames())
    journal = {"seed": SEED, "clean_seed": clean_manifest["seed"],
               "faults": catalog, "entries": inj.entries}
    JOURNAL.write_text(json.dumps(journal, ensure_ascii=False, indent=1), encoding="utf-8")
    write_changes_csv(inj.entries)
    dirty_tables = export_csv(DIRTY_DB, DIRTY_CSV)
    write_manifest(DIRTY_MANIFEST, SEED, dirty_tables,
                   {"clean_seed": clean_manifest["seed"],
                    "clean_tables": clean_manifest["tables"]})
    write_changes_md(catalog, inj.entries, clean_manifest, dirty_tables)

    print(f"dirty DB: {DIRTY_DB} (seed={SEED})")
    for fault in catalog:
        rows = sum(len(e["targets"]) for e in inj.entries if e["fault"] == fault["id"])
        print(f"  {fault['id']} {fault['level']} {fault['table']:12s} {rows:4d}  {fault['description'][:60]}")


if __name__ == "__main__":
    main()
