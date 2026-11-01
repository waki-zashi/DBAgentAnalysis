import gzip
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_university_bench import parse_inserts  # noqa: E402

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "uni_raw"

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


def try_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def classify(table, col, old, new):
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


def main():
    clean_sql = gzip.decompress((RAW / "clean.sql.gz").read_bytes()).decode("utf-8", errors="replace")
    dirty_sql = gzip.decompress((RAW / "dirty.sql.gz").read_bytes()).decode("utf-8", errors="replace")

    clean_data = parse_inserts(clean_sql)
    dirty_data = parse_inserts(dirty_sql)

    clean_ids_by_table = {t: {int(r["id"]) for r in d["rows"]} for t, d in clean_data.items()}

    counts = defaultdict(int)
    fk_confirmed = 0
    fk_false = 0
    entries = []

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
                kind, level, dim = classify(t, col, cv, dv)
                if kind == "fk_orphan_candidate":
                    parent = FK_SUFFIX_TO_TABLE[col]
                    try:
                        is_orphan = int(dv) not in clean_ids_by_table.get(parent, set())
                    except (TypeError, ValueError):
                        is_orphan = False
                    if is_orphan:
                        kind = "fk_orphan"
                        fk_confirmed += 1
                    else:
                        kind = "value_changed_other"
                        level, dim = "L1", "validity"
                        fk_false += 1
                counts[kind] += 1
                entries.append({"kind": kind, "level": level, "dimension": dim,
                                 "table": t, "column": col, "pk": pk,
                                 "old": cv, "new": dv})

        for pk in added:
            counts["duplicate_row"] += 1
            entries.append({"kind": "duplicate_row", "level": "L2", "dimension": "uniqueness",
                             "table": t, "column": None, "pk": pk, "old": None, "new": "inserted"})

    print("распределение по категориям:")
    for k, c in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k:24s} {c:4d}")
    print(f"\nfk_orphan подтверждено: {fk_confirmed}, ложных срабатываний (id существует): {fk_false}")

    out = RAW / "journal_draft.json"
    out.write_text(json.dumps(entries, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"\n-> {out} ({len(entries)} записей)")


if __name__ == "__main__":
    main()
