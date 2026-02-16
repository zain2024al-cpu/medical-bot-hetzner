# ================================================
# fix_ptb_warnings_smart.py
# 🔹 إصلاح تحذيرات PTBUserWarning بشكل ذكي ودقيق
# ================================================

import os
import re
from pathlib import Path

def fix_per_message_settings():
    """
    إصلاح إعدادات per_message بشكل ذكي:
    - إذا كان ConversationHandler يستخدم MessageHandler في أي مكان → per_message=True
    - إذا كان يستخدم CallbackQueryHandler فقط → per_message=False
    """
    
    print("Starting smart PTBUserWarning fixes...")
    
    project_root = Path(__file__).parent
    files_modified = 0
    
    # البحث عن ملفات Python التي تحتوي على ConversationHandler
    for file_path in project_root.rglob("*.py"):
        if 'bot/handlers' not in str(file_path):
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # البحث عن كل ConversationHandler في الملف
            conv_pattern = r'conv(?:_handler)?\s*=\s*ConversationHandler\((.*?)\n\s*\)'
            conv_matches = re.findall(conv_pattern, content, re.DOTALL)
            
            for i, conv_content in enumerate(conv_matches):
                # التحقق من وجود MessageHandler
                has_message_handler = 'MessageHandler(' in conv_content
                
                # البحث عن per_message الحالي
                per_message_match = re.search(r'per_message\s*=\s*(True|False)', conv_content)
                
                if per_message_match:
                    current_setting = per_message_match.group(1)
                    correct_setting = 'True' if has_message_handler else 'False'
                    
                    # إذا كان الإعداد الحالي خطأ، قم بتصحيحه
                    if current_setting != correct_setting:
                        old_line = per_message_match.group(0)
                        new_line = old_line.replace(current_setting, correct_setting)
                        
                        # استبدال في المحتوى الأصلي
                        content = content.replace(old_line, new_line)
                        
                        rel_path = file_path.relative_to(project_root)
                        print(f"Fixed {rel_path}: MessageHandler={has_message_handler}, per_message={correct_setting}")
                else:
                    # إذا لم يوجد per_message، أضف الإعداد الصحيح
                    correct_setting = 'True' if has_message_handler else 'False'
                    
                    # البحث عن مكان إضافته (قبل الإغلاق)
                    insertion_point = conv_content.rfind(')')
                    if insertion_point != -1:
                        before_insertion = conv_content[:insertion_point]
                        after_insertion = conv_content[insertion_point:]
                        
                        new_per_message = f',\n        per_message={correct_setting}'
                        new_conv_content = before_insertion + new_per_message + after_insertion
                        
                        content = content.replace(conv_content, new_conv_content)
                        
                        rel_path = file_path.relative_to(project_root)
                        print(f"Added per_message={correct_setting} to {rel_path}: MessageHandler={has_message_handler}")
            
            # حفظ التغييرات
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                files_modified += 1
        
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    print(f"\nCompleted! Modified {files_modified} files")
    return files_modified

if __name__ == "__main__":
    fix_per_message_settings()