
from db.session import SessionLocal
from db.models import Report
from sqlalchemy import func

with SessionLocal() as session:
    latest = session.query(func.max(Report.created_at)).scalar()
    count = session.query(Report).count()
    print(f"Total reports: {count}")
    print(f"Latest report created_at: {latest}")
    
    # Get last 5 reports with dates
    rows = session.query(Report.id, Report.report_date, Report.created_at, Report.translator_name).order_by(Report.created_at.desc()).limit(5).all()
    for r in rows:
        print(f"ID: {r[0]}, Report Date: {r[1]}, Created At: {r[2]}, Translator: {r[3]}")
