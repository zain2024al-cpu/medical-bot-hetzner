# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from db.session import SessionLocal
from db.models import TranslatorDirectory
from sqlalchemy import text

with SessionLocal() as s:
    count = s.query(TranslatorDirectory).count()
    tg_count = s.execute(text('SELECT COUNT(*) FROM translators WHERE translator_id > 1000000000')).scalar()
    seq_count = s.execute(text('SELECT COUNT(*) FROM translators WHERE translator_id <= 1000000000')).scalar()
    named_count = s.execute(text('SELECT COUNT(*) FROM translators WHERE name IS NOT NULL')).scalar()
    test_artifacts = s.execute(text("SELECT COUNT(*) FROM translators WHERE name LIKE '__test_%'")).scalar()

print(f'Total TD rows:              {count}')
print(f'tg_user_id-style IDs >1B:   {tg_count}')
print(f'sequential IDs <=1B:        {seq_count}')
print(f'rows with non-NULL name:     {named_count}')
print(f'test artifact rows:          {test_artifacts}')

import os
FILE = 'data/translator_names.txt'
if os.path.exists(FILE):
    with open(FILE, encoding='utf-16') as f:
        file_names = {l.strip() for l in f if l.strip() and not l.strip().startswith('#')}
    print(f'File rows (UTF-16 read):     {len(file_names)}')
    with SessionLocal() as s:
        db_names = {r.name for r in s.query(TranslatorDirectory).all()}
    divergence = len(db_names.symmetric_difference(file_names))
    print(f'DB/file divergence:          {divergence}')

assert test_artifacts == 0, 'test artifacts remain in DB'
print()
print('B-DA.1.5 VERIFICATION COMPLETE — DB clean, no test artifacts.')
