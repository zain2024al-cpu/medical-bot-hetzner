import sqlite3

conn = sqlite3.connect("db/medical_reports.db")
cursor = conn.cursor()

# Get existing columns
cursor.execute("PRAGMA table_info(reports)")
existing = [row[1] for row in cursor.fetchall()]
print("Existing columns:", len(existing))
print("Columns:", existing)

# All columns that should exist
new_columns = [
    ("app_reschedule_reason", "TEXT"),
    ("app_reschedule_return_date", "TEXT"),
    ("app_reschedule_return_reason", "TEXT"),
    ("group_message_id", "INTEGER"),
    ("radiology_type", "TEXT"),
    ("radiology_delivery_date", "TEXT"),
    ("submitted_by_user_id", "INTEGER"),
    ("case_status", "TEXT"),
    ("diagnosis", "TEXT"),
    ("treatment_plan", "TEXT"),
    ("medications", "TEXT"),
]

for col_name, col_type in new_columns:
    if col_name not in existing:
        try:
            cursor.execute(f"ALTER TABLE reports ADD COLUMN {col_name} {col_type}")
            print(f"Added: {col_name}")
        except Exception as e:
            print(f"Error adding {col_name}: {e}")
    else:
        print(f"Exists: {col_name}")

conn.commit()
conn.close()
print("Done!")

