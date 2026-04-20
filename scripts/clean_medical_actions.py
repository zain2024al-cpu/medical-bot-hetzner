# -*- coding: utf-8 -*-
"""
سكربت لمرة واحدة لتنظيف خطوط التزيين (━ ─ علامات RTL …) من قيم medical_action
في جدول reports.

التشغيل:
    python scripts/clean_medical_actions.py
"""
from __future__ import annotations

import os
import sys
import sqlite3

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from db.session import DATABASE_PATH  # type: ignore  # noqa: E402
from services.stats_service import normalize_action_name  # type: ignore  # noqa: E402


def main() -> int:
    if not os.path.exists(DATABASE_PATH):
        print(f"❌ قاعدة البيانات غير موجودة: {DATABASE_PATH}")
        return 1

    con = sqlite3.connect(DATABASE_PATH)
    cur = con.cursor()
    cur.execute(
        "SELECT id, medical_action FROM reports "
        "WHERE medical_action IS NOT NULL AND medical_action <> ''"
    )
    rows = cur.fetchall()
    changed = 0
    for rid, raw in rows:
        clean = normalize_action_name(raw)
        if clean and clean != raw:
            cur.execute(
                "UPDATE reports SET medical_action = ? WHERE id = ?",
                (clean, rid),
            )
            changed += 1
            print(f"  #{rid}: {raw!r} -> {clean!r}")
    con.commit()
    con.close()
    print(f"✅ تم التنظيف: {changed} صف/صفوف معدّلة من أصل {len(rows)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
