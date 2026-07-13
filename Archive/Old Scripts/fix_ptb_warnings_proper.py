# ================================================
# fix_ptb_warnings_proper.py
# 🔹 إصلاح تحذيرات PTBUserWarning بشكل صحيح
# ================================================

import os
import re
import glob
from pathlib import Path

def fix_conversation_handler_warnings_proper():
    """
    إصلاح تحذيرات PTBUserWarning بشكل صحيح:
    - إذا كان ConversationHandler يحتوي على MessageHandlers → per_message=True
    - إذا كان يحتوي على CallbackQueryHandlers فقط → per_message=False
    """
    
    print("Starting proper PTBUserWarning fixes...")
    
    # البحث عن جميع ملفات Python التي تحتوي على ConversationHandler
    project_root = Path(__file__).parent
    python_files = list(project_root.rglob("*.py"))
    
    files_modified = 0
    
    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # التحقق إذا كان الملف يحتوي على ConversationHandler
            if 'ConversationHandler(' in content:
                original_content = content
                
                # البحث عن ConversationHandler blocks
                conv_pattern = r'conv\s*=\s*ConversationHandler\((.*?)\)'
                conv_matches = re.findall(conv_pattern, content, re.DOTALL)
                
                for conv_content in conv_matches:
                    # التحقق إذا كان يحتوي على MessageHandler
                    has_message_handler = 'MessageHandler(' in conv_content
                    
                    # تحديد per_message value الصحيح
                    correct_per_message = 'per_message=True' if has_message_handler else 'per_message=False'
                    
                    # استبدال per_message القديم بالجديد
                    old_per_message_pattern = r'per_message\s*=\s*(True|False)'
                    new_per_message = f'per_message={correct_per_message.split("=")[1]}'
                    
                    updated_conv_content = re.sub(old_per_message_pattern, new_per_message, conv_content)
                    
                    # تحديث content الرئيسي
                    content = content.replace(conv_content, updated_conv_content)
                
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
        print("- Fixed per_message settings based on handler types")
        print("- MessageHandlers need per_message=True")
        print("- CallbackQueryHandlers only need per_message=False")
        print("- This will prevent PTBUserWarning messages correctly")
    
    return files_modified

if __name__ == "__main__":
    fix_conversation_handler_warnings_proper()