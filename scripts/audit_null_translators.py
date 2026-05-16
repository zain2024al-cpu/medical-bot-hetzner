# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from db.session import SessionLocal
from db.models import Report, TranslatorDirectory
from sqlalchemy import func, text

with SessionLocal() as s:
    # NULL by month
    rows = s.execute(text("""
        SELECT strftime('%Y-%m', report_date) as month,
               COUNT(*) as null_cnt
        FROM reports
        WHERE translator_id IS NULL
        GROUP BY month
        ORDER BY month
    """)).fetchall()

    all_rows = s.execute(text("""
        SELECT strftime('%Y-%m', report_date) as month,
               COUNT(*) as total
        FROM reports
        GROUP BY month
        ORDER BY month
    """)).fetchall()

    all_dict = {r[0]: r[1] for r in all_rows}

    print("NULL translator_id by month (vs total):")
    for month, cnt in rows:
        total = all_dict.get(month, 0)
        pct = 100 * cnt / total if total else 0
        print(f"  {month}: {cnt} NULL out of {total} total ({pct:.0f}%)")

    # Reports with submitted_by but no translator_id
    submitter_rows = s.execute(text("""
        SELECT submitted_by_user_id, COUNT(*) as cnt
        FROM reports
        WHERE translator_id IS NULL
          AND submitted_by_user_id IS NOT NULL
        GROUP BY submitted_by_user_id
        ORDER BY cnt DESC
    """)).fetchall()

    print(f"\nReports with submitted_by_user_id but no translator_id:")
    for sid, cnt in submitter_rows:
        print(f"  submitted_by={sid}  count={cnt}")

    # Check if any of those submitted_by IDs are in TranslatorDirectory
    td_ids = {r.translator_id for r in s.query(TranslatorDirectory).all()}
    for sid, cnt in submitter_rows:
        match = "IN-TD" if sid in td_ids else "NOT-IN-TD"
        print(f"    -> {sid}: {match}")

    # Most recent NULL report
    latest_null = s.execute(text("""
        SELECT id, translator_name, submitted_by_user_id, report_date
        FROM reports
        WHERE translator_id IS NULL
        ORDER BY report_date DESC
        LIMIT 5
    """)).fetchall()
    print("\nMost recent NULL translator_id reports:")
    for row in latest_null:
        print(f"  id={row[0]}  name=[{row[1]}]  submitter={row[2]}  date={row[3]}")

    # Oldest non-NULL report for comparison
    oldest_nonnull = s.execute(text("""
        SELECT id, translator_id, translator_name, submitted_by_user_id, report_date
        FROM reports
        WHERE translator_id IS NOT NULL
        ORDER BY report_date ASC
        LIMIT 3
    """)).fetchall()
    print("\nOldest non-NULL translator_id reports:")
    for row in oldest_nonnull:
        print(f"  id={row[0]}  tid={row[1]}  name=[{row[2]}]  submitter={row[3]}  date={row[4]}")
