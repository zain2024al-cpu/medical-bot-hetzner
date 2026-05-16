# -*- coding: utf-8 -*-
"""
B-DA.1 Stage 0 — Reconciliation Audit Script
Read-only. No writes. No mutations.
"""
import sys
import io
import unicodedata

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from db.session import SessionLocal
from db.models import TranslatorDirectory, User

# ── Source 1: File ────────────────────────────────────────────────────────────
with open('data/translator_names.txt', 'r', encoding='utf-16') as f:
    file_names_raw = [line.strip() for line in f
                      if line.strip() and not line.startswith('#')]

# ── Source 2: DB ──────────────────────────────────────────────────────────────
with SessionLocal() as s:
    db_rows = s.query(TranslatorDirectory).order_by(TranslatorDirectory.name).all()

# ── Source 3: priority_order (from translators_service.py lines 239-243) ─────
priority_order = [
    "معتز", "ادم", "هاشم", "مصطفى", "حسن", "نجم الدين", "محمد علي",
    "صبري", "عزي", "سعيد", "عصام", "زيد", "مهدي", "ادريس",
    "واصل", "عزالدين", "عبدالسلام", "يحيى العنسي", "ياسر"
]

# ── Source 4: TRANSLATORS_SEED (from translators_service.py lines 20-37) ─────
TRANSLATORS_SEED = [
    {"translator_id": 7345544036, "name": "ادريس"},
    {"translator_id": 1997643031, "name": "حسن"},
    {"translator_id": 6002303025, "name": "مصطفى"},
    {"translator_id": 8172870113, "name": "صبري"},
    {"translator_id": 5713657641, "name": "عزي"},
    {"translator_id": 591202186,  "name": "زيد"},
    {"translator_id": 7504265481, "name": "نجم الدين"},
    {"translator_id": 7350590873, "name": "مهدي"},
    {"translator_id": 1938862867, "name": "واصل"},
    {"translator_id": 1982219162, "name": "ادم"},
    {"translator_id": 8310133494, "name": "هاشم"},
    {"translator_id": 7392642953, "name": "سعيد"},
    {"translator_id": 6043664891, "name": "محمد علي"},
    {"translator_id": 8054012415, "name": "عصام"},
    {"translator_id": 6979080725, "name": "معتز"},
    {"translator_id": 7536360652, "name": "عزالدين"},
]

# ── Source 5: ensure_default_translators (flows/shared.py lines 87-108) ──────
ensure_defaults = [
    "مصطفى", "واصل", "نجم الدين", "محمد علي", "سعيد", "مهدي",
    "صبري", "عزي", "معتز", "ادريس", "هاشم", "ادم", "زيد", "عصام",
    "عزالدين", "حسن", "زين العابدين", "عبدالسلام", "ياسر", "يحيى"
]

# ── Source 6: monolith fallback (user_reports_add_new_system.py line 12226) ───
monolith_fallback = [
    "معتز", "ادم", "هاشم", "مصطفى", "حسن", "نجم الدين", "محمد علي",
    "صبري", "عزي", "سعيد", "عصام", "زيد", "مهدي", "ادريس",
    "واصل", "عزالدين", "عبدالسلام", "يحيى العنسي", "ياسر"
]

# ── Index maps ────────────────────────────────────────────────────────────────
file_lower  = {n.lower(): n for n in file_names_raw}
db_lower    = {r.name.lower(): r for r in db_rows if r.name}
seed_lower  = {e['name'].lower(): e for e in TRANSLATORS_SEED}
seed_ids    = {e['translator_id'] for e in TRANSLATORS_SEED}

# ═════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print("SECTION 1 — SOURCE COUNTS")
print("=" * 70)
print(f"  File (translator_names.txt)   : {len(file_names_raw)} names")
print(f"  DB (TranslatorDirectory)      : {len(db_rows)} rows")
print(f"  priority_order list           : {len(priority_order)} names")
print(f"  TRANSLATORS_SEED              : {len(TRANSLATORS_SEED)} entries")
print(f"  ensure_default_translators    : {len(ensure_defaults)} names")
print(f"  monolith fallback list        : {len(monolith_fallback)} names")

# ═════════════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("SECTION 2 — FILE vs DB DIVERGENCE")
print("=" * 70)

in_file_not_db = [n for k, n in file_lower.items() if k not in db_lower]
in_db_not_file = [r.name for k, r in db_lower.items() if k not in file_lower]
in_both        = [(n, db_lower[k]) for k, n in file_lower.items() if k in db_lower]

print(f"  In file but NOT in DB ({len(in_file_not_db)}):")
for n in in_file_not_db:
    print(f"    >> [{n}]")
if not in_file_not_db:
    print("    (none)")

print(f"  In DB but NOT in file ({len(in_db_not_file)}):")
for n in in_db_not_file:
    r = db_lower[n.lower()]
    print(f"    >> [{n}]  translator_id={r.translator_id}")
if not in_db_not_file:
    print("    (none)")

print(f"  In BOTH ({len(in_both)}) — spelling comparison:")
for file_name, db_row in sorted(in_both, key=lambda x: x[0]):
    same = (file_name == db_row.name)
    if same:
        print(f"    OK  [{file_name}]  id={db_row.translator_id}")
    else:
        print(f"    *** SPELLING DIFFERS  file=[{file_name}]  db=[{db_row.name}]  id={db_row.translator_id}")

# ═════════════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("SECTION 3 — INVISIBLE CHARACTER AND WHITESPACE SCAN")
print("=" * 70)
found_any = False
for source_label, name_list in [("FILE", file_names_raw),
                                  ("DB",   [r.name for r in db_rows if r.name])]:
    for n in name_list:
        if n != n.strip():
            print(f"  {source_label} WHITESPACE: [{repr(n)}]")
            found_any = True
        for i, ch in enumerate(n):
            cat = unicodedata.category(ch)
            if cat in ('Cc', 'Cf', 'Zs', 'Zl', 'Zp') and ch != ' ':
                print(f"  {source_label} INVISIBLE: [{repr(n)}] pos={i} U+{ord(ch):04X} cat={cat}")
                found_any = True
if not found_any:
    print("  None found. All names are clean.")

# ═════════════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("SECTION 4 — DUPLICATE DETECTION (within each source)")
print("=" * 70)
found_dup = False
for source_label, names in [("FILE", file_names_raw),
                              ("DB",   [r.name for r in db_rows if r.name]),
                              ("priority_order", priority_order),
                              ("ensure_defaults", ensure_defaults),
                              ("monolith_fallback", monolith_fallback)]:
    seen = {}
    for i, n in enumerate(names):
        k = n.lower()
        if k in seen:
            print(f"  {source_label} DUPLICATE: [{n}] at pos {seen[k]+1} and {i+1}")
            found_dup = True
        seen[k] = i
if not found_dup:
    print("  None found.")

# ═════════════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("SECTION 5 — translator_id PATTERN ANALYSIS")
print("=" * 70)
for r in sorted(db_rows, key=lambda x: x.translator_id or 0):
    tid = r.translator_id
    in_seed = tid in seed_ids if tid else False
    synthetic = (8310133490 <= tid <= 8310133510) if tid else False
    origin = []
    if in_seed:
        origin.append("SEED(service.py)")
    if synthetic:
        origin.append("SYNTHETIC-CONSECUTIVE")
    if not in_seed and not synthetic:
        origin.append("UNKNOWN-ORIGIN")
    print(f"  id={str(tid).ljust(15)} name=[{r.name}]  {' | '.join(origin)}")

# ═════════════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("SECTION 6 — SYNTHETIC ID BLOCK — User table cross-reference")
print("=" * 70)
print("  (IDs in range 8310133494–8310133498)")
with SessionLocal() as s:
    for tid in [8310133494, 8310133495, 8310133496, 8310133497, 8310133498]:
        td = s.query(TranslatorDirectory).filter_by(translator_id=tid).first()
        usr = s.query(User).filter_by(tg_user_id=tid).first()
        td_name  = td.name  if td  else "NOT-IN-TD"
        usr_name = usr.full_name if usr else "NOT-IN-USER-TABLE"
        id_match = "REAL-TELEGRAM-ID" if usr else "NO-TELEGRAM-USER — SYNTHETIC"
        print(f"  id={tid}  TD=[{td_name}]  User=[{usr_name}]  => {id_match}")

# ═════════════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("SECTION 7 — SEED IDs vs User table")
print("=" * 70)
with SessionLocal() as s:
    for entry in TRANSLATORS_SEED:
        tid   = entry['translator_id']
        sname = entry['name']
        usr   = s.query(User).filter_by(tg_user_id=tid).first()
        usr_name = usr.full_name if usr else "NOT-IN-USER-TABLE"
        name_match = "NAME-OK" if usr and sname in (usr.full_name or "") else "NAME-MISMATCH"
        print(f"  id={str(tid).ljust(15)} seed=[{sname}]  user=[{usr_name}]  {name_match}")

# ═════════════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("SECTION 8 — priority_order vs DB (all 19 positions)")
print("=" * 70)
for i, pname in enumerate(priority_order):
    r = db_lower.get(pname.lower())
    if r:
        spelling_ok = (r.name == pname)
        note = "" if spelling_ok else f"  *** SPELLING DIFFERS db=[{r.name}]"
        print(f"  P{i:02d}: [{pname}]  IN-DB  id={r.translator_id}{note}")
    else:
        print(f"  P{i:02d}: [{pname}]  *** MISSING FROM DB ***")

# ═════════════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("SECTION 9 — priority_order vs FILE")
print("=" * 70)
for i, pname in enumerate(priority_order):
    in_f = pname.lower() in file_lower
    if in_f:
        actual = file_lower[pname.lower()]
        note = "" if actual == pname else f"  *** SPELLING DIFFERS file=[{actual}]"
        print(f"  P{i:02d}: [{pname}]  IN-FILE{note}")
    else:
        print(f"  P{i:02d}: [{pname}]  *** MISSING FROM FILE ***")

# ═════════════════════════════════════════════════════════════════════════════
print()
print("=" * 70)
print("SECTION 10 — FULL FOUR-SOURCE MATRIX")
print("=" * 70)

# Union of all names
all_names_union = set()
for n in file_names_raw:       all_names_union.add(n.lower())
for r in db_rows:
    if r.name:                 all_names_union.add(r.name.lower())
for n in priority_order:       all_names_union.add(n.lower())
for n in monolith_fallback:    all_names_union.add(n.lower())
for n in ensure_defaults:      all_names_union.add(n.lower())

# Build lookup sets
file_set     = {n.lower() for n in file_names_raw}
db_set       = {r.name.lower() for r in db_rows if r.name}
prio_set     = {n.lower() for n in priority_order}
mono_set     = {n.lower() for n in monolith_fallback}
ensure_set   = {n.lower() for n in ensure_defaults}

# Canonical display name: prefer DB > file > priority_order > monolith_fallback
canonical = {}
for n in monolith_fallback:    canonical[n.lower()] = n
for n in priority_order:       canonical[n.lower()] = n
for n in file_names_raw:       canonical[n.lower()] = n
for r in db_rows:
    if r.name:                 canonical[r.name.lower()] = r.name

header = f"  {'Name':<20} {'FILE':^4} {'DB':^4} {'PRIO':^4} {'MONO':^4} {'ENSR':^4}  Notes"
print(header)
print("  " + "-" * 65)
for key in sorted(all_names_union):
    display = canonical.get(key, key)
    f = "Y" if key in file_set   else "-"
    d = "Y" if key in db_set     else "-"
    p = "Y" if key in prio_set   else "-"
    m = "Y" if key in mono_set   else "-"
    e = "Y" if key in ensure_set else "-"
    notes = []
    if d == "-":
        notes.append("NOT-IN-DB")
    if f == "-":
        notes.append("NOT-IN-FILE")
    if p == "-" and (f == "Y" or d == "Y"):
        notes.append("NOT-IN-PRIORITY-ORDER")
    note_str = "  *** " + ", ".join(notes) if notes else ""
    print(f"  {display:<20} {f:^4} {d:^4} {p:^4} {m:^4} {e:^4}{note_str}")

print()
print("=" * 70)
print("SECTION 11 — OPERATIONAL SUMMARY")
print("=" * 70)
print(f"  File count      : {len(file_names_raw)}")
print(f"  DB count        : {len(db_rows)}")
print(f"  File == DB      : {set(file_lower.keys()) == set(db_lower.keys())}")
print(f"  Divergence      : {len(in_file_not_db)} file-only, {len(in_db_not_file)} db-only")
print(f"  Spelling diffs  : {sum(1 for fn, dr in in_both if fn != dr.name)}")
print(f"  Synthetic IDs   : {sum(1 for r in db_rows if r.translator_id and 8310133490 <= r.translator_id <= 8310133510)}")
print(f"  Seed IDs        : {sum(1 for r in db_rows if r.translator_id and r.translator_id in seed_ids)}")
print(f"  No-User IDs     : see Section 6")
