# -*- coding: utf-8 -*-
"""
Sync doctors_unified.json into SQLite DB (hospitals/departments/doctors).

هدف السكربت:
- جعل قاعدة بيانات الأطباء "مظبطة" بحيث يكون doctor.hospital_id و doctor.department_id مملوءين
- السكربت آمن للتشغيل عدة مرات (idempotent) قدر الإمكان

تشغيل:
  python scripts/sync_doctors_unified_to_db.py --apply
  python scripts/sync_doctors_unified_to_db.py --apply --json data/doctors_unified.json

ملاحظة:
- يفضّل تشغيله أثناء صيانة (إيقاف البوت مؤقتاً) لتفادي أي تعارضات.
"""

from __future__ import annotations

import argparse
import os
import sys
import json
from typing import Dict, Tuple, Optional

# Ensure project root importable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import func  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from db.session import SessionLocal, DATABASE_PATH  # noqa: E402
from db.models import Hospital, Department, Doctor  # noqa: E402


def _norm(s: Optional[str]) -> str:
    return " ".join((s or "").strip().split()).casefold()


def _load_unified(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_or_create_hospital(s, name: str, cache: Dict[str, int]) -> int:
    key = _norm(name)
    if not key:
        raise ValueError("empty hospital name")
    if key in cache:
        return cache[key]
    name_clean = name.strip()
    # fast path: exact match first (avoids UNIQUE(name) conflicts on weird spacing)
    row = s.query(Hospital).filter(Hospital.name == name_clean).first()
    if not row:
        row = s.query(Hospital).filter(func.lower(func.trim(Hospital.name)) == key).first()
    if not row:
        row = Hospital(name=name_clean)
        # Use a savepoint to survive UNIQUE(name) races/duplicates safely.
        try:
            with s.begin_nested():
                s.add(row)
                s.flush()
        except IntegrityError:
            # Someone (or earlier data) already inserted the same exact name.
            row = s.query(Hospital).filter(Hospital.name == name_clean).first()
            if not row:
                # Last resort: scan by normalized key
                row = s.query(Hospital).filter(func.lower(func.trim(Hospital.name)) == key).first()
            if not row:
                raise
    cache[key] = int(row.id)
    return int(row.id)


def _get_or_create_department(
    s, hospital_id: int, hospital_name: str, dept_name: str, cache: Dict[str, int]
) -> int:
    dkey = _norm(dept_name)
    if not dkey:
        raise ValueError("empty department name")
    # NOTE: departments.name appears to be UNIQUE globally in this DB schema,
    # so we cannot create the same department name for multiple hospitals.
    # We therefore treat department as a global dictionary entry and only
    # attach hospital_id/hospital_name when missing.
    if dkey in cache:
        return cache[dkey]
    row = (
        s.query(Department)
        .filter(func.lower(func.trim(Department.name)) == dkey)
        .first()
    )
    if not row:
        row = Department(name=dept_name.strip(), hospital_id=hospital_id, hospital_name=hospital_name.strip())
        s.add(row)
        s.flush()
    else:
        # attach hospital info only if missing (avoid fighting existing data)
        if row.hospital_id is None:
            row.hospital_id = hospital_id
        if not (row.hospital_name or "").strip():
            row.hospital_name = hospital_name.strip()

    cache[dkey] = int(row.id)
    return int(row.id)


def _doctor_exists(s, name: str, hospital_id: int, department_id: int) -> bool:
    n = _norm(name)
    if not n:
        return False
    row = (
        s.query(Doctor.id)
        .filter(func.lower(func.trim(Doctor.name)) == n)
        .filter(Doctor.hospital_id == hospital_id)
        .filter(Doctor.department_id == department_id)
        .first()
    )
    return row is not None


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync doctors_unified.json into DB.")
    parser.add_argument("--json", default=os.path.join("data", "doctors_unified.json"))
    parser.add_argument("--apply", action="store_true", help="Apply changes (otherwise dry-run).")
    args = parser.parse_args()

    unified_path = args.json
    if not os.path.isabs(unified_path):
        unified_path = os.path.join(PROJECT_ROOT, unified_path)
    if not os.path.exists(unified_path):
        raise SystemExit(f"JSON not found: {unified_path}")

    data = _load_unified(unified_path)

    dry = not args.apply
    print("DB:", DATABASE_PATH)
    print("JSON:", unified_path)
    print("MODE:", "DRY-RUN" if dry else "APPLY")

    hospitals_cache: Dict[str, int] = {}
    dept_cache: Dict[str, int] = {}

    created_h = 0
    created_d = 0
    created_doc = 0
    linked_doc = 0

    with SessionLocal() as s:
        # Preload existing hospitals/departments to avoid UNIQUE(name) conflicts with spacing/casing differences
        for row in s.query(Hospital).all():
            k = _norm(row.name)
            if k and k not in hospitals_cache:
                hospitals_cache[k] = int(row.id)
        for row in s.query(Department).all():
            k = _norm(row.name)
            if k and k not in dept_cache:
                dept_cache[k] = int(row.id)

        # 1) Ensure hospitals/departments exist
        for h in data.get("hospitals", []) or []:
            hname = (h.get("name") or "").strip()
            if not hname:
                continue
            hid_before = hospitals_cache.get(_norm(hname))
            hid = _get_or_create_hospital(s, hname, hospitals_cache)
            if hid_before is None:
                # might still exist already; count later using DB check
                pass
            for dept in h.get("departments", []) or []:
                dname = (dept.get("name") or "").strip()
                if not dname:
                    continue
                _get_or_create_department(s, hid, hname, dname, dept_cache)

        # Count created rows (approx) by comparing caches vs DB existence is expensive; skip exact counts here.

        # 2) Upsert doctors with linking
        for doc in data.get("doctors", []) or []:
            doc_name = (doc.get("name") or "").strip()
            hosp_name = (doc.get("hospital_name") or "").strip()
            dept_name = (doc.get("department") or "").strip()
            if not doc_name or not hosp_name or not dept_name:
                continue
            hid = _get_or_create_hospital(s, hosp_name, hospitals_cache)
            did = _get_or_create_department(s, hid, hosp_name, dept_name, dept_cache)

            if _doctor_exists(s, doc_name, hid, did):
                continue

            # try to reuse an existing doctor row with same name but null links
            n = _norm(doc_name)
            existing = (
                s.query(Doctor)
                .filter(func.lower(func.trim(Doctor.name)) == n)
                .filter((Doctor.hospital_id.is_(None)) | (Doctor.department_id.is_(None)))
                .first()
            )
            if existing:
                if existing.hospital_id is None:
                    existing.hospital_id = hid
                if existing.department_id is None:
                    existing.department_id = did
                linked_doc += 1
            else:
                # Some deployed DBs enforce NOT NULL on full_name
                s.add(Doctor(name=doc_name, full_name=doc_name, hospital_id=hid, department_id=did))
                created_doc += 1

        if dry:
            s.rollback()
            print("Planned changes:")
            print(" - new doctors to create:", created_doc)
            print(" - existing doctors to link:", linked_doc)
            return 0

        s.commit()

    print("Done.")
    print(" - new doctors created:", created_doc)
    print(" - existing doctors linked:", linked_doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

