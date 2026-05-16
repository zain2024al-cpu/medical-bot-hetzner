"""Audit: compare ORM model columns against live SQLite DB for all tables."""
import sqlite3
import os
import re

db_path = os.path.join(os.path.dirname(__file__), "..", "db", "medical_reports.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cursor.fetchall()]

db_schema = {}
for t in tables:
    cursor.execute(f"PRAGMA table_info({t})")
    db_schema[t] = set(r[1] for r in cursor.fetchall())
conn.close()

models_path = os.path.join(os.path.dirname(__file__), "..", "db", "models.py")
with open(models_path, encoding="utf-8") as f:
    content = f.read()

class_blocks = list(re.finditer(r"class (\w+)\(Base\):", content))
results = []
for i, m in enumerate(class_blocks):
    end = class_blocks[i + 1].start() if i + 1 < len(class_blocks) else len(content)
    block = content[m.start():end]
    tn_match = re.search(r'__tablename__\s*=\s*["\'](\w+)["\']', block)
    if not tn_match:
        continue
    tablename = tn_match.group(1)
    orm_cols = {cm.group(1) for cm in re.finditer(r"^\s+(\w+)\s*=\s*Column\(", block, re.MULTILINE)}
    db_cols = db_schema.get(tablename, set())
    missing = orm_cols - db_cols
    if missing:
        results.append((tablename, sorted(missing)))

if results:
    print("MISSING IN DB (ORM has, DB lacks):")
    for t, cols in results:
        print(f"  Table [{t}]:")
        for c in cols:
            print(f"    - {c}")
else:
    print("OK — all ORM columns exist in DB. No migrations needed.")
