# ================================================
# fix_ptb_warnings.py
# 🔹 إصلاح تحذيرات PTBUserWarning في ConversationHandler
# ================================================

import os
import re
import glob
from pathlib import Path

def fix_conversation_handler_warnings():
    """
    إصلاح تحذيرات PTBUserWarning عن طريق تغيير per_message=True إلى per_message=True
    في جميع ConversationHandlers في المشروع
    """
    
    print("Starting PTBUserWarning fixes...")
    
    # البحث عن جميع ملفات Python التي تحتوي على ConversationHandler
    project_root = Path(__file__).parent
    python_files = list(project_root.rglob("*.py"))
    
    files_modified = 0
    
    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # التحقق إذا كان الملف يحتوي على ConversationHandler
            if 'ConversationHandler(' in content and 'per_message=True' in content:
                
                # حفظ النسخة الأصلية
                original_content = content
                
                # إصلاح per_message=True إلى per_message=True
                content = re.sub(
                    r'per_message=True',
                    'per_message=True',
                    content
                )
                
                # التحقق إذا تم تغيير شيء
                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    relative_path = file_path.relative_to(project_root)
                    print(f"Fixed: {relative_path}")
                    files_modified += 1
        
        except Exception as e:
            print(f"Error processing file {file_path}: {e}")
    
    print(f"\nFix completed! Modified {files_modified} files")
    
    if files_modified > 0:
        print("\nChanges made:")
        print("- Changed per_message=True to per_message=True")
        print("- This will prevent PTBUserWarning messages")
        print("- Will not affect bot functionality negatively")
    
    return files_modified

if __name__ == "__main__":
    fix_conversation_handler_warnings()