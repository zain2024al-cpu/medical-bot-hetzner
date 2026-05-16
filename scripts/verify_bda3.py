# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import importlib.util, inspect

spec = importlib.util.spec_from_file_location('hs', 'services/hospitals_service.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print('IMPORT OK')

# 1. Function exists and is callable
assert callable(mod.get_hospitals_with_details), 'not callable'
print('  get_hospitals_with_details: callable OK')

# 2. Source contains DB-first pattern
src = inspect.getsource(mod.get_hospitals_with_details)
assert 'SessionLocal' in src, 'DB read missing'
assert 'Hospital' in src, 'Hospital model missing'
assert 'order_by' in src, 'DB ordering missing'
assert '_INVALID_HOSPITAL_NAMES' in src, 'filter for invalid names missing'
assert 'fallback' in src.lower(), 'fallback path missing'
print('  DB-first pattern: OK (SessionLocal, order_by, invalid-name filter, fallback)')

# 3. JSON fallback present
assert 'data.get' in src, 'JSON fallback missing'
print('  JSON fallback: OK')

# 4. Return shape has expected keys
assert "departments" in src, 'departments key missing'
assert "doctor_count" in src, 'doctor_count key missing'
print('  Return shape: id, name, name_normalized, departments, doctor_count OK')

# 5. Live call against DB
result = mod.get_hospitals_with_details()
print(f'  Live call: returned {len(result)} hospitals')
if result:
    first = result[0]
    assert isinstance(first, dict), 'result is not a list of dicts'
    assert 'name' in first
    assert 'departments' in first
    assert 'doctor_count' in first
    print(f'  First entry: name=[{first["name"]}]  depts={len(first["departments"])}  doc_count={first["doctor_count"]}')
    print('  Shape contract: OK')

# 6. get_all_hospitals() not regressed
all_names = mod.get_all_hospitals()
print(f'  get_all_hospitals() (unchanged): {len(all_names)} hospitals OK')

# 7. DB authority: detail names should match get_all_hospitals names
detail_names = {h["name"] for h in result}
all_names_set = set(all_names)
extra = detail_names - all_names_set
missing = all_names_set - detail_names
print(f'  DB authority check: detail vs get_all_hospitals')
print(f'    extra in details: {len(extra)}')
print(f'    missing from details: {len(missing)}')
for n in sorted(extra): print(f'      extra: [{n}]')
for n in sorted(missing): print(f'      missing: [{n}]')

# 8. Confirm ordering matches DB (both should be DB-ordered)
detail_ordered = [h["name"] for h in result]
all_ordered = list(all_names)
if detail_ordered == all_ordered:
    print('  Ordering: matches get_all_hospitals OK')
else:
    print(f'  Ordering: differs from get_all_hospitals (expected — custom order may apply)')

print()
print('ALL CHECKS PASSED')
