import sqlite3
c = sqlite3.connect("db/medical_reports.db")
print("Integrity:", c.execute("PRAGMA integrity_check").fetchone()[0])
cur = c.cursor()
cur.execute("SELECT COUNT(*) FROM patients")
print("Patients:", cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM users")
print("Users:", cur.fetchone()[0])
c.close()

