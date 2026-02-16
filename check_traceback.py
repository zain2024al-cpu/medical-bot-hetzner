import os
import re

# Files that use traceback (from grep results)
files_with_traceback_usage = [
    "bot/handlers/admin/admin_reports.py",
    "bot/handlers/admin/admin_schedule_management.py",
    "services/render_backup.py",
    "db/session.py",
    "bot/handlers/admin/admin_printing.py",
    "bot/handlers/user/user_reports_add_new_system/inline_query.py",
    "bot/handlers/user/user_reports_add_helpers.py",
    "bot/handlers/admin/admin_hospitals_management.py",
    "bot/handlers/user/user_reports_add_new_system/flows/stub_flows.py",
    "bot/handlers/user/user_reports_add_new_system/action_type_handlers.py",
    "bot/decorators.py",
    "services/error_monitoring.py",
    "bot/handlers/user/user_reports_add_new_system/patient_handlers.py",
    "bot/handlers/admin/decorators.py",
    "db/patient_names_importer.py",
]

# Also check main directories
print("CHECKING FOR TRACEBACK USAGE WITHOUT IMPORT\n")
print("=" * 80)

results = []

for file_path in files_with_traceback_usage:
    full_path = file_path
    if not os.path.exists(full_path):
        continue
    
    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Check if traceback is used
    if 'traceback.' not in content:
        continue
    
    # Check if traceback is imported at module level
    has_top_level_import = bool(re.search(r'^(import traceback|from traceback import)', content, re.MULTILINE))
    
    if not has_top_level_import:
        # Check if it's only imported locally
        has_local_import = bool(re.search(r'^\s+(import traceback|from traceback import)', content, re.MULTILINE))
        
        status = "LOCAL IMPORT ONLY (inside except/functions)"
        results.append((file_path, status))
        print(f"FILE: {file_path}")
        print(f"STATUS: {status}")
        print()

if results:
    print("\n" + "=" * 80)
    print("SUMMARY OF FILES WITH LOCAL TRACEBACK IMPORTS:")
    print("=" * 80)
    for file_path, status in results:
        print(f"  - {file_path}")
else:
    print("All files that use traceback have proper imports (either top-level or local).")

