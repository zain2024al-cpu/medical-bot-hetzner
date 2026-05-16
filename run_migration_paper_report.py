#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration: add has_paper_report + no_paper_report_reason to reports table.

Safe to run multiple times (idempotent) — skips columns that already exist.

Run:
    python run_migration_paper_report.py
"""

import sqlite3
import os
import sys

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

possible_paths = [
    os.path.join(os.path.dirname(__file__), "db", "medical_reports.db"),
    "/home/botuser/medical-bot/db/medical_reports.db",
    "db/medical_reports.db",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "medical_reports.db"),
]

DB_PATH = None
for path in possible_paths:
    if os.path.exists(path):
        DB_PATH = path
        print(f"✅ قاعدة البيانات: {DB_PATH}")
        break

if not DB_PATH:
    print("❌ لم يتم العثور على قاعدة البيانات في المسارات:")
    for p in possible_paths:
        print(f"   - {p}")
    sys.exit(1)


# Columns to add: (name, DDL type, DEFAULT clause)
COLUMNS_TO_ADD = [
    ("has_paper_report",      "INTEGER", "NULL"),
    ("no_paper_report_reason","TEXT",    "NULL"),
]


def run_migration():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(reports)")
        existing = {row[1] for row in cursor.fetchall()}

        added = []
        skipped = []

        for col_name, col_type, default in COLUMNS_TO_ADD:
            if col_name in existing:
                skipped.append(col_name)
                continue

            if default == "NULL":
                sql = f"ALTER TABLE reports ADD COLUMN {col_name} {col_type}"
            else:
                sql = f"ALTER TABLE reports ADD COLUMN {col_name} {col_type} DEFAULT {default}"

            print(f"⏳ إضافة العمود: {col_name} ({col_type}) ...")
            cursor.execute(sql)
            added.append(col_name)

        conn.commit()

        # Verify
        cursor.execute("PRAGMA table_info(reports)")
        final_cols = {row[1] for row in cursor.fetchall()}
        conn.close()

        missing_after = [c for c, _, _ in COLUMNS_TO_ADD if c not in final_cols]

        print()
        if skipped:
            print(f"ℹ️  موجودة مسبقاً (تجاوز): {', '.join(skipped)}")
        if added:
            print(f"✅ تمت إضافتها: {', '.join(added)}")
        if missing_after:
            print(f"❌ فشل في إضافة: {', '.join(missing_after)}")
            return False

        return True

    except Exception as e:
        print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 55)
    print("  Migration: has_paper_report + no_paper_report_reason")
    print("=" * 55)

    if run_migration():
        print("\n✅ اكتملت عملية الترقية بنجاح!")
        sys.exit(0)
    else:
        print("\n❌ فشلت عملية الترقية!")
        sys.exit(1)
