"""
merge_duplicate_hospitals.py
────────────────────────────
دمج صفوف المستشفيات المكررة نهائياً في قاعدة البيانات.

لكل زوج (dead_id, keep_id):
  1. ينقل جميع Doctor.hospital_id   من dead → keep
  2. ينقل جميع Report.hospital_id   من dead → keep
  3. ينقل جميع Department.hospital_id من dead → keep
  4. يحذف صف Hospital المكرر (dead)

يطبع ملخصاً قبل التنفيذ ويطلب تأكيداً.
مراجعة: شغّله مرة، لا داعي لتشغيله مجدداً (الصفوف المدمجة لن تُعاد).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from db.session import SessionLocal
from db.models import Doctor, Hospital, Department, Report
from sqlalchemy import func, update

# ─── خطة الدمج: (dead_id, keep_id, الاسم الرسمي النهائي) ──────────────────
MERGE_PLAN = [
    # logical duplicates — same hospital, different name formatting
    (15, 35, "Manipal Hospital, Old Airport Road"),
    (20, 29, "Apollo Hospital, Bannerghatta Bangalore"),
    (38, 73, "Fortis Hospital, BG Road Bangalore"),
    (50, 63, "Klinik Gluhen Dental Clinic"),
    # short-name aliases → full official name
    (19, 48, "Aster CMI Hospital, Bangalore"),
    (17, 33, "Aster RV Hospital, Bangalore"),
    (14, 28, "Aster Whitefield Hospital, Bangalore"),
]


def count_refs(s, model, col, hid):
    return s.query(func.count(model.id)).filter(col == hid).scalar() or 0


def print_plan(s):
    print("=" * 65)
    print("MERGE PLAN — pre-run audit")
    print("=" * 65)
    for dead_id, keep_id, label in MERGE_PLAN:
        dead = s.get(Hospital, dead_id)
        keep = s.get(Hospital, keep_id)
        d_docs  = count_refs(s, Doctor,     Doctor.hospital_id,     dead_id)
        k_docs  = count_refs(s, Doctor,     Doctor.hospital_id,     keep_id)
        d_reps  = count_refs(s, Report,     Report.hospital_id,     dead_id)
        k_reps  = count_refs(s, Report,     Report.hospital_id,     keep_id)
        d_depts = count_refs(s, Department, Department.hospital_id, dead_id)
        k_depts = count_refs(s, Department, Department.hospital_id, keep_id)
        print(f"\n  MERGE  id={dead_id}  →  id={keep_id}  [{label}]")
        print(f"    DEAD ({dead_id}): {dead.name if dead else 'NOT FOUND'}")
        print(f"          docs={d_docs}  reports={d_reps}  depts={d_depts}")
        print(f"    KEEP ({keep_id}): {keep.name if keep else 'NOT FOUND'}")
        print(f"          docs={k_docs}  reports={k_reps}  depts={k_depts}")
    print()


def run_merge(s):
    total_moved = {"doctors": 0, "reports": 0, "depts": 0, "deleted": 0}

    for dead_id, keep_id, label in MERGE_PLAN:
        dead = s.get(Hospital, dead_id)
        keep = s.get(Hospital, keep_id)

        if not keep:
            print(f"  SKIP {dead_id}→{keep_id}: keep hospital not found")
            continue
        if not dead:
            print(f"  SKIP {dead_id}→{keep_id}: dead hospital already deleted")
            continue

        # 1. Move doctors
        moved_docs = (
            s.query(Doctor)
            .filter(Doctor.hospital_id == dead_id)
            .update({"hospital_id": keep_id}, synchronize_session=False)
        )

        # 2. Move reports
        moved_reps = (
            s.query(Report)
            .filter(Report.hospital_id == dead_id)
            .update({"hospital_id": keep_id}, synchronize_session=False)
        )

        # 3. Move departments
        moved_depts = (
            s.query(Department)
            .filter(Department.hospital_id == dead_id)
            .update({"hospital_id": keep_id}, synchronize_session=False)
        )

        # 4. Ensure canonical name on keep row
        keep.name = label

        # 5. Delete dead row
        s.delete(dead)

        print(
            f"  OK  {dead_id}→{keep_id}  [{label}]"
            f"  docs={moved_docs}  reports={moved_reps}  depts={moved_depts}"
        )
        total_moved["doctors"]  += moved_docs
        total_moved["reports"]  += moved_reps
        total_moved["depts"]    += moved_depts
        total_moved["deleted"]  += 1

    s.commit()
    return total_moved


def main():
    with SessionLocal() as s:
        print_plan(s)
        answer = input("Proceed with merge? [yes/no]: ").strip().lower()
        if answer != "yes":
            print("Aborted.")
            return

        print("\nRunning merge...")
        totals = run_merge(s)

    print(
        f"\nDone.  Merged {totals['deleted']} hospital pairs."
        f"  Moved: doctors={totals['doctors']}"
        f"  reports={totals['reports']}"
        f"  depts={totals['depts']}"
    )

    # Post-run verification
    print("\nPost-merge verification:")
    with SessionLocal() as s:
        for dead_id, keep_id, label in MERGE_PLAN:
            dead = s.get(Hospital, dead_id)
            keep = s.get(Hospital, keep_id)
            d_docs = count_refs(s, Doctor, Doctor.hospital_id, keep_id)
            d_reps = count_refs(s, Report, Report.hospital_id, keep_id)
            print(
                f"  id={keep_id} docs={d_docs} reports={d_reps}"
                f"  name={keep.name if keep else 'GONE'}"
                f"  | dead({dead_id})={'gone' if not dead else 'STILL EXISTS!'}"
            )


if __name__ == "__main__":
    main()
