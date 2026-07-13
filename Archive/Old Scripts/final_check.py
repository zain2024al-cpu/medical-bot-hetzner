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

print("=" * 100)
print("FINAL TRACEBACK IMPORT ANALYSIS - CHECKING FOR USAGE WITHOUT ANY IMPORT")
print("=" * 100)

files_without_any_import = []

for file_path in files_to_check:
    full_path = file_path
    if not os.path.exists(full_path):
        continue
    
    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        content = ''.join(lines)
    
    # Find all usages of traceback.xxx
    usage_pattern = r'traceback\.(print_exc|format_exc|print_exception|extract_tb|extract_stack)'
    usages = [(m.start(), i+1) for i, line in enumerate(lines) for m in re.finditer(usage_pattern, line)]
    
    if not usages:
        continue
    
    # Check if ANY import of traceback exists BEFORE the first usage
    first_usage_pos = usages[0][0] if usages else len(content)
    content_before_usage = content[:first_usage_pos]
    
    import_found = bool(re.search(r'(import traceback|from traceback import)', content_before_usage))
    
    if not import_found:
        usage_lines = [u[1] for u in usages]
        files_without_any_import.append({
            'file': file_path,
            'usage_lines': usage_lines,
        })
        print(f"\n[ISSUE] {file_path}")
        print(f"  Lines where traceback is used: {usage_lines}")

print("\n" + "=" * 100)

if files_without_any_import:
    print("CRITICAL: FILES WITH TRACEBACK USAGE BUT NO IMPORT BEFORE USAGE:")
    print("=" * 100)
    for item in files_without_any_import:
        print(f"  {item['file']}")
        print(f"    Usage at lines: {item['usage_lines']}")
    print()
    print(f"TOTAL ISSUES FOUND: {len(files_without_any_import)}")
else:
    print("✓ NO ISSUES FOUND")
    print("  All files that use traceback import it before (or at point of) usage")

