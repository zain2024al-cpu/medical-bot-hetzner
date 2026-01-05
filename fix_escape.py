# Fix the escape issue in admin_users_management.py

file_path = "bot/handlers/admin/admin_users_management.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 27 (index 26)
for i, line in enumerate(lines):
    if "re.sub" in line and "r'\\" in line and "text)" in line:
        # Replace the problematic pattern
        old_part = "r'\\', text)"
        new_part = "r'\\\\\\1', text)"
        if old_part in line:
            lines[i] = line.replace(old_part, new_part)
            print(f"Fixed line {i+1}")

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Done!")

