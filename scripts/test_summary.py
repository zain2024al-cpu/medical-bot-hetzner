import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import text
from db.session import SessionLocal
from services.case_summary_service import build_full_summary

COLS = ("report_date, medical_action, complaint_text, doctor_decision, case_status, "
        "diagnosis, treatment_plan, medications, notes, hospital_name, department, "
        "doctor_name, room_number, followup_date, followup_department, followup_reason, "
        "followup_time, app_reschedule_reason, app_reschedule_return_date, "
        "app_reschedule_return_reason, radiology_type, radiology_delivery_date, "
        "radiation_therapy_type, radiation_therapy_session_number, "
        "radiation_therapy_remaining, radiation_therapy_recommendations, "
        "radiation_therapy_return_date, radiation_therapy_return_reason, "
        "radiation_therapy_final_notes, radiation_therapy_completed")
COL_NAMES = [c.strip() for c in COLS.split(",")]

for pid in [95, 90, 80]:
    with SessionLocal() as s:
        rows = s.execute(
            text(f"SELECT {COLS} FROM reports WHERE patient_id=:p "
                 "AND (status IS NULL OR status!='deleted') ORDER BY report_date DESC"),
            {"p": pid}
        ).fetchall()
        prow = s.execute(text("SELECT full_name FROM patients WHERE id=:p"), {"p": pid}).fetchone()

    reports = [dict(zip(COL_NAMES, r)) for r in rows]
    pname = prow[0] if prow else f"مريض #{pid}"
    hosp  = reports[0].get("hospital_name", "") if reports else ""
    last  = reports[0].get("report_date") if reports else None

    summary = build_full_summary(pname, hosp, reports, last)
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"Patient {pid} | {len(reports)} reports | {len(summary)} chars")
    print(sep)
    print(summary)
