
import asyncio
import sys
import os
from datetime import datetime, timedelta
import pytz

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.session import SessionLocal
from db.models import Report
from services.notification_service import send_daily_appointments_reminder
from config.settings import TIMEZONE

class MockBot:
    async def send_message(self, chat_id, text, parse_mode=None):
        print(f"--- Sending to {chat_id} ---")
        print(text)
        print("----------------------------")

class MockApplication:
    def __init__(self):
        self.bot = MockBot()

async def test_reminder():
    print(f"Testing daily reminder with timezone: {TIMEZONE}")
    
    # Create a test report for tomorrow if none exists
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    tomorrow = (now + timedelta(days=1)).date()
    tomorrow_dt = datetime.combine(tomorrow, datetime.min.time())
    
    with SessionLocal() as session:
        # Check if we have any reports for tomorrow
        from sqlalchemy import or_
        reports = session.query(Report).filter(
            or_(
                Report.followup_date.between(tomorrow_dt, tomorrow_dt + timedelta(hours=23, minutes=59)),
                Report.app_reschedule_return_date.between(tomorrow_dt, tomorrow_dt + timedelta(hours=23, minutes=59)),
                Report.radiation_therapy_return_date.between(tomorrow_dt, tomorrow_dt + timedelta(hours=23, minutes=59)),
                Report.radiology_delivery_date.between(tomorrow_dt, tomorrow_dt + timedelta(hours=23, minutes=59))
            )
        ).all()
        
        if not reports:
            print("No reports found for tomorrow. Creating a temporary test report...")
            test_report = Report(
                patient_name="مريض تجريبي",
                translator_name="مترجم تجريبي",
                hospital_name="مستشفى التجربة",
                followup_date=tomorrow_dt + timedelta(hours=10), # 10 AM tomorrow
                followup_time="10:00 AM",
                medical_action="متابعة دورية"
            )
            session.add(test_report)
            session.commit()
            print("Test report created.")
        else:
            print(f"Found {len(reports)} existing reports for tomorrow.")

    # Run the reminder
    app = MockApplication()
    await send_daily_appointments_reminder(app)
    
    # Clean up test report if we created one
    # (Optional: search for the name and delete)

if __name__ == "__main__":
    asyncio.run(test_reminder())
