import gzip
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_university_bench import parse_create_tables, parse_inserts  # noqa: E402

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "uni_raw"
CLEAN_DB = ROOT / "data" / "clean.duckdb"
DIRTY_DB = ROOT / "data" / "dirty.duckdb"
CLEAN_CSV_DIR = ROOT / "data" / "clean_csv"
DIRTY_CSV_DIR = ROOT / "data" / "dirty_csv"
JOURNAL = ROOT / "data" / "journal.json"
SCHEMA_SQL = ROOT / "schema.sql"

FK_SUFFIX_TO_TABLE = {
    "address_id": "addresses", "book_id": "books", "building_id": "buildings",
    "club_id": "clubs", "fee_type_id": "fee_types", "person_id": "people",
    "library_card_id": "library_cards", "room_id": "rooms", "office_room_id": "rooms",
    "department_id": "departments", "course_id": "courses",
    "prerequisite_course_id": "courses", "instructor_id": "instructors",
    "advisor_instructor_id": "instructors", "program_id": "programs",
    "semester_id": "semesters", "section_id": "sections", "exam_id": "exams",
    "student_id": "students", "invoice_id": "invoices", "assignment_id": "assignments",
    "scholarship_id": "scholarships",
}
DATE_LIKE_SUFFIXES = ("_date", "_at", "_time")
DIGITS8_RE = re.compile(r'^\d{8}$')
SLASH_DATE_RE = re.compile(r'^\d{1,2}/\d{1,2}/\d{4}(\s+\d{1,2}:\d{2})?$')
MONTH_NAME_RE = re.compile(r'^[A-Za-z]{3} \d{1,2}, \d{4}(\s+\d{1,2}:\d{2})?$')

KIND_TITLES = {
    "missing_value": "Пропущенное значение в обязательном поле",
    "case_anomaly": "Значение в нехарактерном регистре (ВСЕ ЗАГЛАВНЫЕ)",
    "sign_flip_outlier": "Числовое значение с инвертированным знаком",
    "scale_outlier": "Числовое значение, увеличенное на порядок (x10)",
    "mixed_date_format": "Дата/время в нестандартном текстовом формате",
    "fk_orphan": "Внешний ключ ссылается на несуществующую строку",
    "value_changed_other": "Искажённое текстовое значение (опечатка/иное)",
    "duplicate_row": "Дублирующая (или почти дублирующая) строка",
}


def try_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def classify(col, old, new):
    if new is None and old is not None:
        return "missing_value", "L1", "completeness"
    if old is not None and new is not None and isinstance(old, str) and isinstance(new, str):
        if new == old.upper() and new != old:
            return "case_anomaly", "L1", "validity"
    ov, nv = try_float(old), try_float(new)
    if ov is not None and nv is not None:
        if ov != 0 and abs(nv + ov) < 1e-6:
            return "sign_flip_outlier", "L1", "accuracy"
        if ov != 0 and abs(nv / ov - 10) < 1e-6:
            return "scale_outlier", "L1", "accuracy"
    if any(col.endswith(suf) for suf in DATE_LIKE_SUFFIXES) and isinstance(new, str):
        if DIGITS8_RE.match(new) or SLASH_DATE_RE.match(new) or MONTH_NAME_RE.match(new):
            return "mixed_date_format", "L1", "validity"
    if col in FK_SUFFIX_TO_TABLE and new is not None:
        return "fk_orphan_candidate", "L3", "referential_integrity"
    return "value_changed_other", "L1", "validity"


PG_TO_DUCKDB = [
    (re.compile(r'\bvarchar\s*\(\s*\d+\s*\)', re.IGNORECASE), "VARCHAR"),
    (re.compile(r'\bcharacter varying\b', re.IGNORECASE), "VARCHAR"),
    (re.compile(r'\bnumeric\s*\(', re.IGNORECASE), "DECIMAL("),
    (re.compile(r'\bdouble precision\b', re.IGNORECASE), "DOUBLE"),
    (re.compile(r'\binteger\b', re.IGNORECASE), "INTEGER"),
    (re.compile(r'\bboolean\b', re.IGNORECASE), "BOOLEAN"),
    (re.compile(r'\btimestamp\b', re.IGNORECASE), "TIMESTAMP"),
    (re.compile(r'\bdate\b', re.IGNORECASE), "DATE"),
    (re.compile(r'\btime\b', re.IGNORECASE), "TIME"),
]


DATE_TYPE_RE = re.compile(r'\b(date|timestamp|time)\b', re.IGNORECASE)


def pg_type_to_duckdb(t):
    for pat, repl in PG_TO_DUCKDB:
        t = pat.sub(repl, t)
    return t.strip()


def pg_type_to_duckdb_relaxed(t):
    if DATE_TYPE_RE.search(t):
        return "VARCHAR"
    return pg_type_to_duckdb(t)


def to_duckdb_literal(v, col_type):
    if v is None:
        return "NULL"
    ct = col_type.upper()
    if "VARCHAR" in ct:
        return "'" + v.replace("'", "''") + "'"
    if ct in ("BOOLEAN",):
        return "TRUE" if v == "true" or v is True else "FALSE"
    if ct in ("DATE",) or "TIMESTAMP" in ct or "TIME" in ct:
        return "'" + v + "'"
    return v


def build_schema_sql(schema):
    lines = []
    for t, cols in schema.items():
        lines.append(f"CREATE TABLE {t} (")
        col_lines = [f"    {c} {pg_type_to_duckdb_relaxed(ty)}" for c, ty in cols]
        lines.append(",\n".join(col_lines))
        lines.append(");\n")
    text = "\n".join(lines)
    SCHEMA_SQL.write_text(text, encoding="utf-8")
    return text


def write_db(path, schema, data):
    import duckdb
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    con = duckdb.connect(str(path))
    con.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
    for t, cols in schema.items():
        d = data.get(t)
        if not d or not d["rows"]:
            continue
        col_types = dict(cols)
        col_names = d["columns"]
        values_sql = []
        for row in d["rows"]:
            vals = [to_duckdb_literal(row.get(c), col_types.get(c, "VARCHAR")) for c in col_names]
            values_sql.append("(" + ", ".join(vals) + ")")
        cols_sql = ", ".join(col_names)
        for i in range(0, len(values_sql), 500):
            chunk = values_sql[i:i + 500]
            con.execute(f"INSERT INTO {t} ({cols_sql}) VALUES {', '.join(chunk)}")
    con.close()


def main():
    clean_sql = gzip.decompress((RAW / "clean.sql.gz").read_bytes()).decode("utf-8", errors="replace")
    dirty_sql = gzip.decompress((RAW / "dirty.sql.gz").read_bytes()).decode("utf-8", errors="replace")

    schema = parse_create_tables(clean_sql)
    schema_text = build_schema_sql(schema)
    print(f"schema.sql: {len(schema)} таблиц -> {SCHEMA_SQL}")

    clean_data = parse_inserts(clean_sql)
    dirty_data = parse_inserts(dirty_sql)

    print("пишу clean.duckdb ...")
    write_db(CLEAN_DB, schema, clean_data)
    print("пишу dirty.duckdb ...")
    write_db(DIRTY_DB, schema, dirty_data)

    from common import export_csv
    print("экспортирую clean CSV ...")
    export_csv(CLEAN_DB, CLEAN_CSV_DIR)
    print("экспортирую dirty CSV ...")
    export_csv(DIRTY_DB, DIRTY_CSV_DIR)

    clean_ids_by_table = {t: {int(r["id"]) for r in d["rows"]} for t, d in clean_data.items()}

    faults = {}
    entries = []
    counts = defaultdict(int)

    def fault_id(kind, table):
        fid = f"{kind.upper()}__{table}"
        if fid not in faults:
            faults[fid] = {"id": fid, "level": None, "dimension": None, "table": table,
                           "description": f"{KIND_TITLES[kind]} ({table})"}
        return fid

    for t in sorted(set(clean_data) | set(dirty_data)):
        cd, dd = clean_data.get(t), dirty_data.get(t)
        if not cd or "id" not in cd["columns"]:
            continue
        clean_by_id = {int(r["id"]): r for r in cd["rows"]}
        dirty_by_id = {int(r["id"]): r for r in dd["rows"]} if dd else {}
        common = set(clean_by_id) & set(dirty_by_id)
        added = set(dirty_by_id) - set(clean_by_id)

        for pk in common:
            crow, drow = clean_by_id[pk], dirty_by_id[pk]
            for col in cd["columns"]:
                if col == "id":
                    continue
                cv, dv = crow.get(col), drow.get(col)
                if cv == dv:
                    continue
                kind, level, dim = classify(col, cv, dv)
                if kind == "fk_orphan_candidate":
                    parent = FK_SUFFIX_TO_TABLE[col]
                    try:
                        is_orphan = int(dv) not in clean_ids_by_table.get(parent, set())
                    except (TypeError, ValueError):
                        is_orphan = False
                    kind = "fk_orphan" if is_orphan else "value_changed_other"
                    if kind == "value_changed_other":
                        level, dim = "L1", "validity"
                fid = fault_id(kind, t)
                faults[fid]["level"], faults[fid]["dimension"] = level, dim
                entries.append({"fault": fid, "level": level, "dimension": dim,
                                "targets": [{"table": t, "pk": pk}],
                                "note": f"{col}: {cv!r} -> {dv!r}", "changes": []})
                counts[kind] += 1

        for pk in added:
            new_row = dirty_by_id[pk]
            non_id_cols = [c for c in cd["columns"] if c != "id"]
            dup_of = None
            for cpk, crow in clean_by_id.items():
                if all(crow.get(c) == new_row.get(c) for c in non_id_cols):
                    dup_of = cpk
                    break
            fid = fault_id("duplicate_row", t)
            faults[fid]["level"], faults[fid]["dimension"] = "L2", "uniqueness"
            targets = [{"table": t, "pk": pk}]
            if dup_of is not None:
                targets.append({"table": t, "pk": dup_of})
            entries.append({"fault": fid, "level": "L2", "dimension": "uniqueness",
                            "targets": targets, "note": f"inserted, exact_dup_of={dup_of}", "changes": []})
            counts["duplicate_row"] += 1

    journal = {"source": "databasesample.com university-sample-database v2 flagship 1k",
               "faults": list(faults.values()), "entries": entries}
    JOURNAL.write_text(json.dumps(journal, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    print("\nраспределение по категориям:")
    for k, c in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k:24s} {c:4d}")
    print(f"\nвсего fault id (категория x таблица): {len(faults)}")
    print(f"всего entries: {len(entries)}")
    print(f"-> {JOURNAL}")


if __name__ == "__main__":
    main()
