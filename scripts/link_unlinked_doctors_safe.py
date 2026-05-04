# -*- coding: utf-8 -*-
"""
Safely link existing Doctor rows that have NULL hospital_id/department_id.

Safety rules:
- Only link doctors whose normalized name appears exactly once in doctors_unified.json.
- Never guess for duplicate names (skip them).
- Dry-run by default. Use --apply to commit.

Run (server):
  python scripts/link_unlinked_doctors_safe.py
  python scripts/link_unlinked_doctors_safe.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import func  # noqa: E402

from db.session import SessionLocal, DATABASE_PATH  # noqa: E402
from db.models import Doctor, Hospital, Department  # noqa: E402


def _norm(s: Optional[str]) -> str:
    return " ".join((s or "").strip().split()).casefold()


def _load_unified(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_name_to_target(unified: dict) -> Tuple[Dict[str, Tuple[str, str]], Dict[str, int]]:
    """
    Returns:
      - unique_map: norm_name -> (hospital_name, department_name) ONLY when unique
      - counts: norm_name -> occurrences in unified doctors list
    """
    counts: Dict[str, int] = defaultdict(int)
    last_seen: Dict[str, Tuple[str, str]] = {}

    for d in unified.get("doctors", []) or []:
        name = _norm(d.get("name"))
        if not name:
            continue
        h = (d.get("hospital_name") or "").strip()
        dept = (d.get("department") or "").strip()
        if not h or not dept:
            continue
        counts[name] += 1
        last_seen[name] = (h, dept)

    unique_map = {k: v for k, v in last_seen.items() if counts.get(k, 0) == 1}
    return unique_map, dict(counts)


def main() -> int:
    ap = argparse.ArgumentParser(description="Safely link unlinked doctors using unique name matches.")
    ap.add_argument("--json", default=os.path.join("data", "doctors_unified.json"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    json_path = args.json
    if not os.path.isabs(json_path):
        json_path = os.path.join(PROJECT_ROOT, json_path)
    if not os.path.exists(json_path):
        raise SystemExit(f"JSON not found: {json_path}")

    unified = _load_unified(json_path)
    unique_map, counts = _build_name_to_target(unified)

    print("DB:", DATABASE_PATH)
    print("JSON:", json_path)
    print("MODE:", "APPLY" if args.apply else "DRY-RUN")
    print("Unique doctor names in unified:", len(unique_map))

    with SessionLocal() as s:
        # Build lookup for hospital + department IDs by normalized name
        hospital_id_by_name = {
            _norm(h.name): int(h.id)
            for h in s.query(Hospital).filter(Hospital.name.isnot(None)).all()
            if _norm(h.name)
        }
        dept_id_by_name = {
            _norm(d.name): int(d.id)
            for d in s.query(Department).filter(Department.name.isnot(None)).all()
            if _norm(d.name)
        }

        q = (
            s.query(Doctor)
            .filter(Doctor.name.isnot(None))
            .filter((Doctor.hospital_id.is_(None)) | (Doctor.department_id.is_(None)))
        )
        candidates: List[Doctor] = q.all()
        print("Candidates (doctor rows with missing links):", len(candidates))

        will_link = 0
        skipped_dup = 0
        skipped_missing_target = 0
        skipped_no_match = 0

        for doc in candidates:
            n = _norm(doc.name)
            if not n:
                skipped_no_match += 1
                continue
            if counts.get(n, 0) == 0:
                skipped_no_match += 1
                continue
            if counts.get(n, 0) > 1:
                skipped_dup += 1
                continue

            hosp_name, dept_name = unique_map.get(n, ("", ""))
            hid = hospital_id_by_name.get(_norm(hosp_name))
            did = dept_id_by_name.get(_norm(dept_name))
            if not hid or not did:
                skipped_missing_target += 1
                continue

            # Apply updates (only fill missing)
            if doc.hospital_id is None:
                doc.hospital_id = hid
            if doc.department_id is None:
                doc.department_id = did
            will_link += 1

        print("Plan/Result:")
        print(" - would link:", will_link)
        print(" - skipped (duplicate name in unified):", skipped_dup)
        print(" - skipped (missing hospital/department in DB):", skipped_missing_target)
        print(" - skipped (no match in unified):", skipped_no_match)

        if not args.apply:
            s.rollback()
            return 0

        s.commit()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

