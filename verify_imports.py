import os
import re

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

print("=" * 120)
print("TRACEBACK IMPORT VERIFICATION - DETAILED ANALYSIS")
print("=" * 120)

files_without_toplevel_import = []

for file_path in files_to_check:
    if not os.path.exists(file_path):
        continue
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Find all usages
    usage_lines = []
    for i, line in enumerate(lines, 1):
        if re.search(r'traceback\.(print_exc|format_exc|print_exception|extract_tb|extract_stack)', line):
            usage_lines.append(i)
    
    if not usage_lines:
        continue
    
    # Check for top-level imports (before first non-import, non-comment code)
    has_toplevel_import = False
    first_import_import_line = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip empty lines and comments
        if not stripped or stripped.startswith('#'):
            continue
        # Check if it's an import
        if stripped.startswith('import traceback') or stripped.startswith('from traceback'):
            has_toplevel_import = True
            first_import_import_line = i + 1
            break
        # If we hit non-import code and haven't found traceback import, it's not top-level
        if not (stripped.startswith('import ') or stripped.startswith('from ')):
            break
    
    if not has_toplevel_import:
        files_without_toplevel_import.append({
            'file': file_path,
            'usage_lines': usage_lines,
            'has_toplevel': False
        })
        print(f"\n{file_path}")
        print(f"  Traceback usage at lines: {usage_lines}")
        print(f"  Top-level import: NO")

print("\n" + "=" * 120)
print(f"FILES WITHOUT TOP-LEVEL TRACEBACK IMPORT: {len(files_without_toplevel_import)}")
print("=" * 120)

for item in files_without_toplevel_import:
    print(f"  - {item['file']}")

