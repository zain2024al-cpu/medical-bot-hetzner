# -*- coding: utf-8 -*-
"""
Verification: auto-select path fix (translator.id → translator.tg_user_id)
Simulates the save_report_to_database resolution chain with tg_user_id as input.
Read-only. No writes.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from db.session import SessionLocal
from db.models import TranslatorDirectory, User

print("=" * 60)
print("VERIFICATION: auto-select path fix")
print("=" * 60)

with SessionLocal() as s:
    td_rows = s.query(TranslatorDirectory).all()
    user_rows = s.query(User).filter(User.tg_user_id != None).all()

    # Build lookup maps
    td_by_tg_id = {r.translator_id: r for r in td_rows}  # tg_user_id → TD row
    users_in_td = [(u, td_by_tg_id[u.tg_user_id]) for u in user_rows if u.tg_user_id in td_by_tg_id]

    print(f"\nUsers whose tg_user_id is in TranslatorDirectory: {len(users_in_td)}")
    print()

    # Simulate: for each such user, what happens in save_report_to_database?
    # Step 1: report_tmp["translator_id"] = translator.tg_user_id  (the fix)
    # Step 2: save_report_to_database receives actual_translator_id = tg_user_id
    # Step 3: if actual_translator_id: → True
    # Step 4: TranslatorDirectory.filter_by(translator_id=actual_translator_id).first()
    # Step 5: uses td.name as translator_name, keeps translator_id = tg_user_id

    print("Resolution trace (OLD vs NEW):")
    print("-" * 60)
    for user, td in users_in_td:
        old_value = user.id          # translator.id (User PK — WRONG)
        new_value = user.tg_user_id  # translator.tg_user_id (Telegram ID — CORRECT)

        # OLD path: filter_by(translator_id=user.id) — looks up User PK as TD PK
        old_lookup = s.query(TranslatorDirectory).filter_by(translator_id=old_value).first()
        # NEW path: filter_by(translator_id=tg_user_id)
        new_lookup = s.query(TranslatorDirectory).filter_by(translator_id=new_value).first()

        old_result = f"FOUND name=[{old_lookup.name}]" if old_lookup else f"NOT-FOUND (would save translator_id={old_value} wrong-valid)"
        new_result = f"FOUND name=[{new_lookup.name}] id={new_value}" if new_lookup else "NOT-FOUND"

        print(f"  User: {user.full_name} (User.id={user.id}, tg_user_id={user.tg_user_id})")
        print(f"    OLD (translator.id={old_value}): {old_result}")
        print(f"    NEW (tg_user_id={new_value}):    {new_result}")
        print()

    # Confirm no existing reports used small-integer translator_ids (User.id range)
    from sqlalchemy import text
    small_id_reports = s.execute(text("""
        SELECT COUNT(*) FROM reports
        WHERE translator_id IS NOT NULL
          AND translator_id < 1000
    """)).scalar()
    print(f"Reports with translator_id < 1000 (User.id range): {small_id_reports}")
    print("  (expected: 0 — confirms old bug never produced corrupted data in production)")

    # Confirm all non-NULL translator_ids are in TranslatorDirectory
    orphan_reports = s.execute(text("""
        SELECT COUNT(*) FROM reports
        WHERE translator_id IS NOT NULL
          AND translator_id NOT IN (SELECT translator_id FROM translators)
    """)).scalar()
    print(f"Reports with translator_id NOT in TranslatorDirectory: {orphan_reports}")
    print("  (expected: 0 — confirms no wrong-valid-ID corruption exists)")

print()
print("=" * 60)
print("VERDICT")
print("=" * 60)
