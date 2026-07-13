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
print("FINAL COMPREHENSIVE ANALYSIS")
print("=" * 120)
print()

properly_imported = []
has_local_import = []
truly_missing = []

for file_path in files_to_check:
    if not os.path.exists(file_path):
        continue
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        content = ''.join(lines)
    
    # Find all usages
    usage_lines = []
    for i, line in enumerate(lines, 1):
        if re.search(r'traceback\.(print_exc|format_exc|print_exception|extract_tb|extract_stack)', line):
            usage_lines.append(i)
    
    if not usage_lines:
        continue
    
    # Check for top-level imports
    has_toplevel_import = bool(re.search(r'^(import traceback|from traceback import)', content, re.MULTILINE))
    
    if has_toplevel_import:
        properly_imported.append((file_path, usage_lines))
        continue
    
    # Check for local imports in exception blocks before first usage
    first_usage_line = usage_lines[0]
    local_import_before_usage = False
    
    for i in range(first_usage_line - 1):
        line = lines[i]
        if 'import traceback' in line or 'from traceback import' in line:
            # Verify it's in an exception handler (simple check)
            context_start = max(0, i - 5)
            context = ''.join(lines[context_start:i+1])
            if 'except' in context:
                local_import_before_usage = True
                break
    
    if local_import_before_usage:
        has_local_import.append((file_path, usage_lines))
    else:
        truly_missing.append((file_path, usage_lines))

print("CATEGORY 1: FILES WITH TOP-LEVEL IMPORT (GOOD)")
print("-" * 120)
for file_path, usage_lines in properly_imported:
    print(f"  ✓ {file_path}")
    print(f"    Usage at lines: {usage_lines}")

print()
print("CATEGORY 2: FILES WITH LOCAL IMPORT IN EXCEPTION HANDLER (ACCEPTABLE)")
print("-" * 120)
for file_path, usage_lines in has_local_import:
    print(f"  ◐ {file_path}")
    print(f"    Usage at lines: {usage_lines}")

print()
print("CATEGORY 3: FILES WITH TRACEBACK USAGE BUT NO IMPORT (CRITICAL - MISSING IMPORT)")
print("-" * 120)
if truly_missing:
    for file_path, usage_lines in truly_missing:
        print(f"  ✗ {file_path}")
        print(f"    Usage at lines: {usage_lines}")
else:
    print("  NONE - All files have proper imports!")

print()
print("=" * 120)
print(f"SUMMARY:")
print(f"  Top-level imports: {len(properly_imported)}")
print(f"  Local imports: {len(has_local_import)}")
print(f"  MISSING IMPORTS: {len(truly_missing)}")
print("=" * 120)

