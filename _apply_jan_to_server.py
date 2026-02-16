import sqlite3

TARGET_DB = '/home/botuser/medical-bot/db/medical_reports.db'
SOURCE_DB = '/tmp/local_medical_reports_for_jan.db'
START = '2026-01-01 00:00:00'
END = '2026-02-01 00:00:00'

src = sqlite3.connect(SOURCE_DB)
src_cur = src.cursor()
src_cur.execute("SELECT * FROM reports WHERE COALESCE(report_date, created_at) >= ? AND COALESCE(report_date, created_at) < ?", (START, END))
rows = src_cur.fetchall()
columns = [d[0] for d in src_cur.description]

if not rows:
    print('NO_SOURCE_ROWS')
    src.close()
    raise SystemExit(0)

placeholders = ','.join(['?'] * len(columns))
col_list = ','.join(columns)
insert_sql = f"INSERT OR REPLACE INTO reports ({col_list}) VALUES ({placeholders})"

tgt = sqlite3.connect(TARGET_DB)
tgt_cur = tgt.cursor()

applied = 0
failed = 0
for r in rows:
    try:
        tgt_cur.execute(insert_sql, r)
        applied += 1
    except Exception:
        failed += 1

tgt.commit()

check_count = None
try:
    tgt_cur.execute("SELECT COUNT(*) FROM reports WHERE COALESCE(report_date, created_at) >= ? AND COALESCE(report_date, created_at) < ?", (START, END))
    check_count = tgt_cur.fetchone()[0]
except Exception as e:
    check_count = f'CHECK_FAILED: {e}'

src.close()
tgt.close()
print(f'JAN_UPSERT_DONE source_rows={len(rows)} applied={applied} failed={failed} server_jan_count={check_count}')
