import sqlite3, os
from datetime import date, timedelta

src = '/home/botuser/medical-bot/db/medical_reports.db'
out = '/tmp/feb_reports_to_today.db'
if os.path.exists(out):
    os.remove(out)

con = sqlite3.connect(src)
cur = con.cursor()
start = '2026-02-01 00:00:00'
end = (date.today() + timedelta(days=1)).isoformat() + ' 00:00:00'

cur.execute("ATTACH DATABASE ? AS sub", (out,))
cur.execute(
    "CREATE TABLE sub.reports AS "
    "SELECT * FROM main.reports "
    "WHERE COALESCE(report_date, created_at) >= ? "
    "AND COALESCE(report_date, created_at) < ?",
    (start, end),
)
cur.execute("CREATE INDEX sub.idx_reports_id ON reports(id)")
cur.execute("CREATE INDEX sub.idx_reports_date ON reports(report_date)")
cur.execute("SELECT COUNT(*) FROM sub.reports")
count = cur.fetchone()[0]
cur.execute("SELECT MIN(COALESCE(report_date, created_at)), MAX(COALESCE(report_date, created_at)) FROM sub.reports")
mn, mx = cur.fetchone()
con.commit()
con.close()
print(f"EXPORT_OK count={count} min={mn} max={mx} out={out}")
