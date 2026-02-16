import os
import re

# All files from grep that mentioned traceback usage
files_to_check = [
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

# Check only main source directories as requested
main_dirs = ["bot/", "services/", "db/", "app.py"]

print("=" * 100)
print("COMPREHENSIVE TRACEBACK IMPORT ANALYSIS")
print("=" * 100)

files_without_any_import = []

for file_path in files_to_check:
    full_path = file_path
    if not os.path.exists(full_path):
        continue
    
    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        content = ''.join(lines)
    
    # Check if traceback is used anywhere
    traceback_usage_lines = [i+1 for i, line in enumerate(lines) if 'traceback.' in line]
    
    if not traceback_usage_lines:
        continue
    
    # Check if traceback is imported at module level (before first usage)
    has_top_level_import = bool(re.search(r'^(import traceback|from traceback import)', content, re.MULTILINE))
    
    # Check for local imports
    local_imports = []
    for i, line in enumerate(lines):
        if 'import traceback' in line and i > 0:
            # Check context
            context_start = max(0, i - 3)
            context = ''.join(lines[context_start:i+1])
            if 'except' in context or 'def ' in context:
                local_imports.append(i + 1)
    
    if not has_top_level_import and not local_imports:
        files_without_any_import.append({
            'file': file_path,
            'usage_lines': traceback_usage_lines,
            'import_lines': []
        })
        print(f"\nFILE: {file_path}")
        print(f"STATUS: TRACEBACK USED BUT NOT IMPORTED (MISSING IMPORT)")
        print(f"Usage lines: {traceback_usage_lines}")
        print()

print("\n" + "=" * 100)

if files_without_any_import:
    print("FILES WITH MISSING TRACEBACK IMPORTS (CRITICAL ISSUE):")
    print("=" * 100)
    for item in files_without_any_import:
        print(f"  - {item['file']}")
        print(f"    Used at lines: {item['usage_lines']}")
    print()
    print("TOTAL PROBLEMS FOUND:", len(files_without_any_import))
else:
    print("✓ ALL FILES THAT USE TRACEBACK HAVE IT IMPORTED (either at module level or locally)")
    print("  Total files checked: ", len([f for f in files_to_check if os.path.exists(f)]))

