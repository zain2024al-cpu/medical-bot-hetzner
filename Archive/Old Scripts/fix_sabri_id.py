"""
سكربت لتحديث ID صبري من 8172870113 إلى 1474333554
نفّذه مرة واحدة على السيرفر: python fix_sabri_id.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db", "medical_reports.db")

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

OLD_ID = 8172870113
NEW_ID = 1474333554

# تحديث جدول translators
cur.execute("UPDATE translators SET translator_id = ? WHERE translator_id = ?", (NEW_ID, OLD_ID))
print(f"translators: {cur.rowcount} rows updated")

# تحديث جدول reports
cur.execute("UPDATE reports SET translator_id = ? WHERE translator_id = ?", (NEW_ID, OLD_ID))
print(f"reports: {cur.rowcount} rows updated")

con.commit()

# التحقق
cur.execute("SELECT * FROM translators WHERE translator_id = ?", (NEW_ID,))
print(f"Result: {cur.fetchall()}")

con.close()
print("Done!")
