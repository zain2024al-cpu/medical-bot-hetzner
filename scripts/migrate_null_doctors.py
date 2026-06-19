#!/usr/bin/env python3
# scripts/migrate_null_doctors.py
#
# Safe migration: fix doctors with hospital_id=NULL using reports data.
#
# Usage:
#   python scripts/migrate_null_doctors.py --dry-run   # preview only
#   python scripts/migrate_null_doctors.py --apply     # run migration

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

# Fix encoding on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

_HERE    = os.path.dirname(os.path.abspath(__file__))
_PROJECT = os.path.dirname(_HERE)
DB_PATH  = os.environ.get("DATABASE_PATH") or os.path.join(_PROJECT, "db", "medical_reports.db")


def run(apply: bool) -> None:
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"\n{'='*60}")
    print(f"  migrate_null_doctors — {mode}")
    print(f"  DB: {DB_PATH}")
    print(f"{'='*60}\n")

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database not found: {DB_PATH}")
        sys.exit(1)

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # ── 0. Pre-migration stats ────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM doctors")
    total_doctors = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM doctors WHERE hospital_id IS NULL")
    null_hospital_before = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM doctors WHERE department_id IS NULL")
    null_dept_before = cur.fetchone()[0]

    print(f"[PRE]  Total doctors:            {total_doctors}")
    print(f"[PRE]  hospital_id = NULL:       {null_hospital_before}")
    print(f"[PRE]  department_id = NULL:     {null_dept_before}\n")

    # ── 1. Backup ─────────────────────────────────────────────────────────────
    if apply:
        ts         = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(_PROJECT, "db", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, f"pre_migrate_null_doctors_{ts}.db")
        # Close connection temporarily to get a clean copy
        con.close()
        shutil.copy2(DB_PATH, backup_path)
        print(f"[BACKUP] Saved to: {backup_path}")
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        cur = con.cursor()

    # ── 2. Compute fixes from reports ─────────────────────────────────────────
    # For each NULL doctor, find the most frequent hospital_id in reports.
    cur.execute("""
        SELECT
            d.id        AS doctor_id,
            d.full_name AS doctor_name,
            r.hospital_id,
            COUNT(*)    AS freq
        FROM doctors d
        JOIN reports r ON r.doctor_name = d.full_name
        WHERE d.hospital_id IS NULL
          AND r.hospital_id IS NOT NULL
        GROUP BY d.id, r.hospital_id
        ORDER BY d.id, freq DESC
    """)
    rows = cur.fetchall()

    # Keep best (most frequent) hospital per doctor
    best_hospital: dict[int, tuple[int, str, int]] = {}  # doctor_id -> (hospital_id, name, freq)
    for row in rows:
        did = row["doctor_id"]
        if did not in best_hospital:
            # Fetch hospital name for reporting
            cur2 = con.cursor()
            cur2.execute("SELECT name FROM hospitals WHERE id = ?", (row["hospital_id"],))
            hr = cur2.fetchone()
            h_name = hr["name"] if hr else "?"
            best_hospital[did] = (row["hospital_id"], row["doctor_name"], h_name, row["freq"])

    print(f"[INFO]  Doctors with recoverable hospital: {len(best_hospital)}")
    print(f"[INFO]  Doctors with no reports (will remain NULL): "
          f"{null_hospital_before - len(best_hospital)}\n")

    # Preview top 10
    print("[PREVIEW] First 10 recoveries:")
    for i, (did, (hid, dname, hname, freq)) in enumerate(list(best_hospital.items())[:10]):
        print(f"  doctor_id={did:5d}  '{dname[:30]:30s}'  → hospital_id={hid} '{hname[:35]}'  (via {freq} reports)")
    if len(best_hospital) > 10:
        print(f"  ... and {len(best_hospital) - 10} more")

    if not apply:
        print(f"\n[DRY-RUN] No changes made. Re-run with --apply to execute.")
        con.close()
        return

    # ── 3. Apply hospital_id fix ──────────────────────────────────────────────
    print("\n[APPLY] Updating hospital_id ...")
    hospital_fixed = 0
    for did, (hid, dname, hname, freq) in best_hospital.items():
        cur.execute("UPDATE doctors SET hospital_id = ? WHERE id = ? AND hospital_id IS NULL",
                    (hid, did))
        if cur.rowcount:
            hospital_fixed += 1

    # ── 4. Apply department_id fix (most common dept per doctor+hospital) ─────
    print("[APPLY] Updating department_id ...")
    cur.execute("""
        SELECT
            d.id            AS doctor_id,
            r.department_id,
            COUNT(*)        AS freq
        FROM doctors d
        JOIN reports r ON r.doctor_name = d.full_name
        WHERE d.department_id IS NULL
          AND d.hospital_id IS NOT NULL
          AND r.hospital_id = d.hospital_id
          AND r.department_id IS NOT NULL
        GROUP BY d.id, r.department_id
        ORDER BY d.id, freq DESC
    """)
    dept_rows = cur.fetchall()

    best_dept: dict[int, int] = {}
    for row in dept_rows:
        did = row["doctor_id"]
        if did not in best_dept:
            best_dept[did] = row["department_id"]

    dept_fixed = 0
    for did, dept_id in best_dept.items():
        cur.execute("UPDATE doctors SET department_id = ? WHERE id = ? AND department_id IS NULL",
                    (dept_id, did))
        if cur.rowcount:
            dept_fixed += 1

    con.commit()

    # ── 5. Post-migration stats ───────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM doctors WHERE hospital_id IS NULL")
    null_hospital_after = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM doctors WHERE department_id IS NULL")
    null_dept_after = cur.fetchone()[0]

    print(f"\n{'='*60}")
    print("  MIGRATION REPORT")
    print(f"{'='*60}")
    print(f"  hospital_id fixed:     {hospital_fixed}")
    print(f"  department_id fixed:   {dept_fixed}")
    print(f"  hospital_id NULL before: {null_hospital_before}  →  after: {null_hospital_after}")
    print(f"  department_id NULL before: {null_dept_before}  →  after: {null_dept_after}")
    print(f"  Remaining NULL hospital (unrecoverable): {null_hospital_after}")
    print(f"  Backup: {backup_path if apply else 'N/A'}")
    print(f"{'='*60}\n")

    con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply",   action="store_true", help="Apply changes (default: dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Preview only (default)")
    args = parser.parse_args()
    run(apply=args.apply)
