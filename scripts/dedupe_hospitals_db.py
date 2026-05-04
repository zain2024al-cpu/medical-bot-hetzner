# -*- coding: utf-8 -*-
"""
Deduplicate hospitals in SQLite by a normalized name key.

Safety defaults:
- Dry-run by default (prints planned merges; no DB writes).
- Use --apply to execute.

What it updates:
- reports.hospital_id / reports.hospital_name (when the row matches the duplicate cluster)
- departments.hospital_id (+ optional hospital_name alignment)
- doctors.hospital_id

Canonical row selection:
- Smallest hospital.id in each duplicate group (stable + predictable).

Notes:
- Stop the bot (or run during maintenance) to avoid concurrent writes while merging.
"""

from __future__ import annotations

import argparse
import os
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Ensure project root is importable when running as: python scripts/dedupe_hospitals_db.py
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from sqlalchemy import func, text  # noqa: E402

from db.models import Department, Doctor, Hospital, Report  # noqa: E402
from db.session import SessionLocal  # noqa: E402


_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_hospital_key(name: Optional[str]) -> str:
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", str(name))
    s = s.translate(_AR_DIGITS)
    s = s.replace("\u0640", "")  # tatweel
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ى", "ي").replace("ة", "ه")
    s = " ".join(s.split())
    return s.casefold()


def _pick_canonical_name(rows: Sequence[Hospital]) -> str:
    non_empty = [r.name.strip() for r in rows if (r.name or "").strip()]
    if not non_empty:
        return ""
    # Prefer the canonical row's name (smallest id) if present
    rows_sorted = sorted(rows, key=lambda r: (r.id or 0))
    if (rows_sorted[0].name or "").strip():
        return rows_sorted[0].name.strip()
    return max(non_empty, key=len)


@dataclass(frozen=True)
class DupGroup:
    key: str
    canonical_id: int
    duplicate_ids: Tuple[int, ...]
    names: Tuple[str, ...]


def _build_groups(session) -> List[DupGroup]:
    hospitals: List[Hospital] = session.query(Hospital).order_by(Hospital.id.asc()).all()
    buckets: Dict[str, List[Hospital]] = defaultdict(list)
    for h in hospitals:
        k = normalize_hospital_key(h.name)
        if not k:
            continue
        buckets[k].append(h)

    groups: List[DupGroup] = []
    for k, rows in buckets.items():
        if len(rows) < 2:
            continue
        rows_sorted = sorted(rows, key=lambda r: (r.id or 0))
        canonical = rows_sorted[0]
        dups = tuple(r.id for r in rows_sorted[1:] if r.id is not None)
        if not dups:
            continue
        names = tuple((r.name or "").strip() for r in rows_sorted)
        groups.append(
            DupGroup(
                key=k,
                canonical_id=int(canonical.id),
                duplicate_ids=dups,
                names=names,
            )
        )

    groups.sort(key=lambda g: (g.canonical_id, g.key))
    return groups


def _count_for_hospital_ids(session, ids: Iterable[int]) -> Dict[str, int]:
    ids = list(ids)
    if not ids:
        return {}

    reports_by_hid = (
        session.query(func.count(Report.id)).filter(Report.hospital_id.in_(ids)).scalar() or 0
    )
    doctors_by_hid = (
        session.query(func.count(Doctor.id)).filter(Doctor.hospital_id.in_(ids)).scalar() or 0
    )
    depts_by_hid = (
        session.query(func.count(Department.id)).filter(Department.hospital_id.in_(ids)).scalar()
        or 0
    )

    # Reports that only carry hospital_name (no hospital_id) — expensive-ish but bounded to duplicate keys
    # Caller should pass ids empty for this path; kept for API symmetry
    return {
        "reports_with_hospital_id": int(reports_by_hid),
        "doctors_with_hospital_id": int(doctors_by_hid),
        "departments_with_hospital_id": int(depts_by_hid),
    }


def _iter_name_only_report_candidates(session):
    q = (
        session.query(Report.id, Report.hospital_name)
        .filter(Report.hospital_id.is_(None))
        .filter(Report.hospital_name.isnot(None))
        .filter(func.trim(Report.hospital_name) != "")
    )
    return q.all()


def _build_name_only_report_index(session) -> Tuple[Dict[str, int], Dict[str, List[int]]]:
    counts: Dict[str, int] = defaultdict(int)
    ids_by_key: Dict[str, List[int]] = defaultdict(list)
    for rid, hname in _iter_name_only_report_candidates(session):
        k = normalize_hospital_key(hname)
        if not k:
            continue
        counts[k] += 1
        ids_by_key[k].append(int(rid))
    return counts, ids_by_key


def _print_group_plan(session, g: DupGroup, name_only_counts: Dict[str, int]) -> None:
    all_ids = (g.canonical_id, *g.duplicate_ids)
    counts = _count_for_hospital_ids(session, all_ids)
    name_only = int(name_only_counts.get(g.key, 0))

    print("\n=== Duplicate group ===")
    print(f"normalized_key: {g.key}")
    print(f"keep hospital.id: {g.canonical_id}")
    print(f"merge/delete hospital.id: {', '.join(str(x) for x in g.duplicate_ids)}")
    print(f"name variants ({len(g.names)}): {', '.join(repr(n) for n in g.names if n)}")
    print(
        "references: "
        f"reports.hospital_id={counts.get('reports_with_hospital_id', 0)}, "
        f"reports.hospital_id NULL name-match≈{name_only}, "
        f"doctors.hospital_id={counts.get('doctors_with_hospital_id', 0)}, "
        f"departments.hospital_id={counts.get('departments_with_hospital_id', 0)}"
    )


def _apply_group(session, g: DupGroup, canonical_name: str, name_only_ids_by_key: Dict[str, List[int]]) -> None:
    dup_ids = list(g.duplicate_ids)
    if not dup_ids:
        return

    # 1) Point foreign-ish references to canonical id
    session.query(Report).filter(Report.hospital_id.in_(dup_ids)).update(
        {Report.hospital_id: g.canonical_id, Report.hospital_name: canonical_name},
        synchronize_session=False,
    )

    session.query(Department).filter(Department.hospital_id.in_(dup_ids)).update(
        {Department.hospital_id: g.canonical_id},
        synchronize_session=False,
    )

    session.query(Doctor).filter(Doctor.hospital_id.in_(dup_ids)).update(
        {Doctor.hospital_id: g.canonical_id},
        synchronize_session=False,
    )

    # 2) Backfill reports that only stored hospital_name (no id), if normalized name matches this cluster
    ids = name_only_ids_by_key.get(g.key) or []
    if ids:
        session.query(Report).filter(Report.id.in_(ids)).update(
            {Report.hospital_id: g.canonical_id, Report.hospital_name: canonical_name},
            synchronize_session=False,
        )

    # 3) Align canonical hospital row name (optional but keeps UI consistent)
    canon = session.query(Hospital).filter(Hospital.id == g.canonical_id).one_or_none()
    if canon and canonical_name and (canon.name or "").strip() != canonical_name:
        canon.name = canonical_name

    # 4) Delete duplicate hospital rows
    session.query(Hospital).filter(Hospital.id.in_(dup_ids)).delete(synchronize_session=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deduplicate hospitals table in SQLite (safe dry-run).")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually perform merges/deletes. If omitted, dry-run only.",
    )
    parser.add_argument(
        "--vacuum",
        action="store_true",
        help="Run VACUUM after successful apply (SQLite maintenance; can take time/lock DB).",
    )
    args = parser.parse_args()

    dry_run = not args.apply

    with SessionLocal() as session:
        groups = _build_groups(session)
        if not groups:
            print("No duplicate hospital groups found (by normalized name key).")
            return 0

        name_only_counts, name_only_ids_by_key = _build_name_only_report_index(session)

        print(f"Found {len(groups)} duplicate group(s). mode={'DRY-RUN' if dry_run else 'APPLY'}")
        for g in groups:
            rows = session.query(Hospital).filter(Hospital.id.in_((g.canonical_id, *g.duplicate_ids))).all()
            canonical_name = _pick_canonical_name(rows)
            _print_group_plan(session, g, name_only_counts)

            if not dry_run:
                _apply_group(session, g, canonical_name, name_only_ids_by_key)

        if dry_run:
            print("\nDry-run complete. Re-run with --apply to execute.")
            return 0

        session.commit()
        print("\nApply complete: committed.")

    if args.vacuum:
        # VACUUM cannot run inside an open transaction on some SQLite setups; use a fresh connection.
        from db.session import engine

        with engine.connect() as conn:
            conn.execute(text("VACUUM"))
            conn.commit()
        print("VACUUM complete.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
