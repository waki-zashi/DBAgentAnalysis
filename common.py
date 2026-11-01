import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CLEAN_DB = DATA / "clean.duckdb"
DIRTY_DB = DATA / "dirty.duckdb"
CLEAN_CSV = DATA / "clean"
DIRTY_CSV = DATA / "dirty"
JOURNAL = DATA / "journal.json"
CHANGES_CSV = DATA / "changes.csv"
CHANGES_MD = ROOT / "CHANGES.md"
CLEAN_MANIFEST = DATA / "clean_manifest.json"
DIRTY_MANIFEST = DATA / "dirty_manifest.json"

TABLES = {
    "customers": "customer_id",
    "products": "product_id",
    "orders": "order_id",
    "order_items": "order_item_id",
    "payments": "payment_id",
}


def write_db(path, frames):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    con = duckdb.connect(str(path))
    con.execute((ROOT / "schema.sql").read_text(encoding="utf-8"))
    for name in TABLES:
        con.register("df_tmp", frames[name])
        con.execute(f"INSERT INTO {name} SELECT * FROM df_tmp")
        con.unregister("df_tmp")
    con.close()


def read_db(path):
    con = duckdb.connect(str(path), read_only=True)
    frames = {t: con.execute(f"SELECT * FROM {t} ORDER BY {pk}").df() for t, pk in TABLES.items()}
    con.close()
    return frames


def export_csv(db_path, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path), read_only=True)
    info = {}
    for t, pk in TABLES.items():
        target = out_dir / f"{t}.csv"
        con.execute(f"COPY (SELECT * FROM {t} ORDER BY {pk}) TO '{target.as_posix()}' (HEADER, DELIMITER ',')")
        rows = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        info[t] = {"rows": rows, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    con.close()
    return info


def write_manifest(path, seed, tables, extra=None):
    manifest = {
        "seed": seed,
        "python": platform.python_version(),
        "packages": {p: version(p) for p in ("duckdb", "faker", "numpy", "pandas")},
        "tables": tables,
    }
    if extra:
        manifest.update(extra)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
