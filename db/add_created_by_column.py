#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to add created_by_tg_user_id column to reports table
"""
import sqlite3
import os
import sys

# Find the database file
import sys
from pathlib import Path

# Try different paths
base_path = Path(__file__).parent.parent
db_paths = [
    base_path / "db" / "medical_reports.db",
    Path("db/medical_reports.db"),
    Path("medical_reports.db"),
]

db_path = None
for path in db_paths:
    if path.exists():
        db_path = str(path)
        break

if not db_path:
    print(f"Error: Database file not found. Tried: {[str(p) for p in db_paths]}")
    sys.exit(1)

if not os.path.exists(db_path):
    print(f"Error: Database file not found at {db_path}")
    sys.exit(1)

print(f"Using database: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(reports)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "created_by_tg_user_id" in columns:
        print("Column created_by_tg_user_id already exists")
    else:
        print("Adding column created_by_tg_user_id to reports table...")
        cursor.execute("""
            ALTER TABLE reports 
            ADD COLUMN created_by_tg_user_id INTEGER
        """)
        
        # Create index for the new column
        print("Creating index for created_by_tg_user_id...")
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS ix_reports_created_by_tg_user_id 
                ON reports(created_by_tg_user_id)
            """)
        except Exception as e:
            print(f"Warning: Could not create index: {e}")
        
        conn.commit()
        print("Column added successfully!")
    
    conn.close()
    print("Done!")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
