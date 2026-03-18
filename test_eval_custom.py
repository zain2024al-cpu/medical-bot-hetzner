
import asyncio
import sys
import os
from datetime import date, timedelta
from sqlalchemy import func

# Add project root to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from db.session import SessionLocal
from db.models import Report
from services.stats_service import get_translator_stats
from bot.handlers.admin.admin_evaluation import _compute_rating, _generate_pdf, _generate_excel

async def test_custom_eval():
    print("Testing custom evaluation range...")

    with SessionLocal() as session:
        latest_report_dt = session.query(func.max(Report.created_at)).scalar()
        if not latest_report_dt:
            print("No reports found in database. Test cannot continue.")
            return

        end_date = latest_report_dt.date()
        start_date = end_date - timedelta(days=14)
        print(f"Range: {start_date} to {end_date}")

        # 1. Get stats
        raw_stats = get_translator_stats(session, start_date, end_date)
        print(f"Found {len(raw_stats)} translators with reports in this range.")
        
        if not raw_stats:
            print("No reports found in this range. Test cannot continue with files.")
            return

        # 2. Compute ratings
        results = _compute_rating(raw_stats)
        print("Ratings computed.")

        # 3. Test PDF generation
        period_label = f"من {start_date} إلى {end_date}"
        start_date_str = start_date.strftime("%d/%m/%Y")
        end_date_str = end_date.strftime("%d/%m/%Y")
        
        try:
            pdf_bytes, file_ext = _generate_pdf(results, period_label, start_date.year, 0, start_date_str, end_date_str)
            print(f"PDF generated successfully (size: {len(pdf_bytes)} bytes, ext: {file_ext})")
            
            # Save to disk for manual check
            with open("test_eval.pdf", "wb") as f:
                f.write(pdf_bytes)
            print("Saved to test_eval.pdf")
        except Exception as e:
            print(f"PDF Generation Failed: {e}")
            import traceback
            traceback.print_exc()

        # 4. Test Excel generation
        try:
            excel_bytes = _generate_excel(results, period_label, start_date.year, 0)
            print(f"Excel generated successfully (size: {len(excel_bytes)} bytes)")
            
            # Save to disk for manual check
            with open("test_eval.xlsx", "wb") as f:
                f.write(excel_bytes)
            print("Saved to test_eval.xlsx")
        except Exception as e:
            print(f"Excel Generation Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_custom_eval())
