# -*- coding: utf-8 -*-
"""
Merge explicitly specified duplicate hospital names safely.

What it does:
- Ensure the KEEP hospital exists in DB (hospitals table)
- Repoint references:
  - reports.hospital_id + reports.hospital_name
  - doctors.hospital_id
  - departments.hospital_id + departments.hospital_name
- Delete the duplicate hospital row(s) (by exact name)

Safety:
- Dry-run by default; use --apply
- Uses exact-name matching only (no fuzzy guesses)

Run:
  python scripts/merge_hospitals_explicit.py
  python scripts/merge_hospitals_explicit.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import func  # noqa: E402

from db.session import SessionLocal, DATABASE_PATH  # noqa: E402
from db.models import Hospital, Report, Doctor, Department  # noqa: E402


MERGES: List[Tuple[str, str]] = [
    # (DELETE_NAME, KEEP_NAME)
    ("Apollo Hospital, Bannerghatta Bangalore", "Apollo Hospital, Bannerghatta, Bangalore"),
    ("Aster Whitefield", "Aster Whitefield Hospital, Bangalore"),
    ("Columbiaa Hsopital", "COLUMBIAA hospital"),
    ("Fortis Hospital , Gurgaon", "Fortis Hospital Gurgaon"),
    ("Fortis Hospital, BG Road Bangalore", "Fortis Hospital BG Road, Bangalore"),
    ("Intell Prosthetic Center", "Intell Prosthetic Intelligence"),
    ("Klinik Gluhen Dental Clinic", "Klinik Gluhen - Dental Clinic"),
    ("Klinik Gluhen clinic", "Klinik Gluhen - Dental Clinic"),
    ("Manipal Hospital, Old Airport Road", "Manipal Hospital - Old Airport Road"),
    ("Rainbow Hsopital Delhi", "Rainbow children’s Hospital, Delhi"),
    ("St John Hospital, Bangalore", "St. John's Medical College Hospital, Bangalore"),
    ("Zaion Hospital , Kammanahilli", "Zion Hospital, Kammanahalli"),
    ("Zaion Hospital, Kammanahilli", "Zion Hospital, Kammanahalli"),
]


def _get_or_create_hospital(s, name: str) -> Hospital:
    name = (name or "").strip()
    row = s.query(Hospital).filter(Hospital.name == name).first()
    if row:
        return row
    row = Hospital(name=name)
    s.add(row)
    s.flush()
    return row


def _merge_one(s, delete_name: str, keep_name: str) -> dict:
    delete_name = (delete_name or "").strip()
    keep_name = (keep_name or "").strip()
    if not delete_name or not keep_name or delete_name == keep_name:
        return {"delete": delete_name, "keep": keep_name, "skipped": True, "reason": "invalid names"}

    keep = _get_or_create_hospital(s, keep_name)
    delete = s.query(Hospital).filter(Hospital.name == delete_name).first()
    if not delete:
        return {"delete": delete_name, "keep": keep_name, "skipped": True, "reason": "delete hospital not found"}

    # Update references by hospital_id
    r1 = (
        s.query(Report)
        .filter(Report.hospital_id == delete.id)
        .update({Report.hospital_id: keep.id, Report.hospital_name: keep_name}, synchronize_session=False)
    )
    d1 = (
        s.query(Doctor)
        .filter(Doctor.hospital_id == delete.id)
        .update({Doctor.hospital_id: keep.id}, synchronize_session=False)
    )
    dep1 = (
        s.query(Department)
        .filter(Department.hospital_id == delete.id)
        .update({Department.hospital_id: keep.id, Department.hospital_name: keep_name}, synchronize_session=False)
    )

    # Also update reports that use hospital_name string (defensive)
    r2 = (
        s.query(Report)
        .filter(Report.hospital_name == delete_name)
        .update({Report.hospital_id: keep.id, Report.hospital_name: keep_name}, synchronize_session=False)
    )

    # Delete duplicate hospital row
    s.delete(delete)

    return {
        "delete": delete_name,
        "keep": keep_name,
        "skipped": False,
        "updated_reports_by_id": int(r1 or 0),
        "updated_reports_by_name": int(r2 or 0),
        "updated_doctors": int(d1 or 0),
        "updated_departments": int(dep1 or 0),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    print("DB:", DATABASE_PATH)
    print("MODE:", "APPLY" if args.apply else "DRY-RUN")
    print("MERGES:", len(MERGES))

    with SessionLocal() as s:
        results = []
        for delete_name, keep_name in MERGES:
            results.append(_merge_one(s, delete_name, keep_name))

        # Summarize
        skipped = sum(1 for r in results if r.get("skipped"))
        print("Skipped:", skipped)
        for r in results:
            if r.get("skipped"):
                print(f"- SKIP {r['delete']} => {r['keep']} ({r.get('reason')})")
            else:
                print(
                    f"- OK   {r['delete']} => {r['keep']} | reports(id)={r['updated_reports_by_id']} "
                    f"reports(name)={r['updated_reports_by_name']} doctors={r['updated_doctors']} depts={r['updated_departments']}"
                )

        if not args.apply:
            s.rollback()
            return 0

        s.commit()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

