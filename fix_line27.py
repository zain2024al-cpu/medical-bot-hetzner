# Fix line 27 in admin_users_management.py

file_path = "bot/handlers/admin/admin_users_management.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# The correct line 27 should be:
correct_line = "    return re.sub(r'([{}])'.format(re.escape(escape_chars)), r'\\\\\\1', text)\n"

# Replace line 27 (index 26)
if len(lines) >= 27:
    print(f"Old line 27: {repr(lines[26])}")
    lines[26] = correct_line
    print(f"New line 27: {repr(lines[26])}")
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("Fixed!")
else:
    print("File too short!")

