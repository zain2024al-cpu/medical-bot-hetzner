import sqlite3
from datetime import date, timedelta

con = sqlite3.connect('/home/botuser/medical-bot/db/medical_reports.db')
cur = con.cursor()
start = '2026-02-01 00:00:00'
end = (date.today() + timedelta(days=1)).isoformat() + ' 00:00:00'
cur.execute("SELECT COUNT(*) FROM reports WHERE COALESCE(report_date, created_at) >= ? AND COALESCE(report_date, created_at) < ?", (start, end))
count = cur.fetchone()[0]
cur.execute("SELECT MIN(COALESCE(report_date, created_at)), MAX(COALESCE(report_date, created_at)) FROM reports WHERE COALESCE(report_date, created_at) >= ? AND COALESCE(report_date, created_at) < ?", (start, end))
mn, mx = cur.fetchone()
print(f"COUNT_OK count={count} min={mn} max={mx}")
con.close()
