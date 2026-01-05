import sqlite3
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\nalgu\OneDrive\Desktop\SERVER_BACKUP_2026-01-01\db\medical_reports.db'

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check integrity
    result = cursor.execute("PRAGMA integrity_check").fetchone()
    print(f"Database integrity: {result[0]}")
    
    # Count patients
    try:
        count = cursor.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        print(f"Patients count: {count}")
    except:
        print("No patients table found")
    
    # Count users
    try:
        count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        print(f"Users count: {count}")
    except:
        print("No users table found")
    
    # Count reports
    try:
        count = cursor.execute("SELECT COUNT(*) FROM medical_reports").fetchone()[0]
        print(f"Reports count: {count}")
    except:
        print("No medical_reports table found")
    
    # List tables
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"Tables: {[t[0] for t in tables]}")
    
    conn.close()
    print("\n✅ Database is valid!")
except Exception as e:
    print(f"❌ Error: {e}")

