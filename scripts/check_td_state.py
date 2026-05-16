# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from db.session import SessionLocal
from db.models import TranslatorDirectory
with SessionLocal() as s:
    rows = s.query(TranslatorDirectory).order_by(TranslatorDirectory.name).all()
    print("DB rows (%d):" % len(rows))
    for r in rows:
        print("  translator_id=%-15s  name=[%s]" % (r.translator_id, r.name))
