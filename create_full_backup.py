#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إنشاء نسخة احتياطية كاملة للمشروع
"""

import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

def create_full_backup():
    """إنشاء نسخة احتياطية كاملة للمشروع"""
    
    # المجلدات والملفات المستثناة
    exclude_dirs = {
        '__pycache__',
        '.git',
        'node_modules',
        '.venv',
        'venv',
        'env',
        '.env',
        '.pytest_cache',
        '*.pyc',
        '*.pyo',
        '*.log',
        '*.db-journal',
        '.DS_Store',
        'Thumbs.db'
    }
    
    exclude_files = {
        '.gitignore',
        '.gitattributes',
        '.DS_Store',
        'Thumbs.db'
    }
    
    # اسم النسخة الاحتياطية
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"medical_reports_bot_backup_{timestamp}"
    backup_path = Path("..") / f"{backup_name}.zip"
    
    print(f"📦 إنشاء نسخة احتياطية للمشروع...")
    print(f"📁 الاسم: {backup_name}.zip")
    print(f"📂 المسار: {backup_path.absolute()}")
    print()
    
    # إنشاء ملف ZIP
    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        project_root = Path(".")
        files_count = 0
        dirs_count = 0
        
        for root, dirs, files in os.walk("."):
            # استثناء المجلدات
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
            
            # استثناء venv
            if 'venv' in root or '__pycache__' in root or '.git' in root:
                continue
            
            for file in files:
                # استثناء الملفات
                if file in exclude_files or file.endswith(('.pyc', '.pyo', '.log')):
                    continue
                
                file_path = Path(root) / file
                arcname = file_path
                
                try:
                    zipf.write(file_path, arcname)
                    files_count += 1
                    if files_count % 50 == 0:
                        print(f"  ✅ تم إضافة {files_count} ملف...")
                except Exception as e:
                    print(f"  ⚠️ تخطي {file_path}: {e}")
    
    # حجم الملف
    file_size = backup_path.stat().st_size
    size_mb = file_size / (1024 * 1024)
    
    print()
    print("=" * 60)
    print("✅ تم إنشاء النسخة الاحتياطية بنجاح!")
    print("=" * 60)
    print(f"📁 الاسم: {backup_name}.zip")
    print(f"📂 المسار: {backup_path.absolute()}")
    print(f"💾 الحجم: {size_mb:.2f} MB ({file_size:,} بايت)")
    print(f"📄 عدد الملفات: {files_count}")
    print("=" * 60)
    
    return str(backup_path.absolute())

if __name__ == "__main__":
    try:
        backup_path = create_full_backup()
        print(f"\n✅ النسخة الاحتياطية جاهزة في:\n{backup_path}")
    except Exception as e:
        print(f"\n❌ خطأ في إنشاء النسخة الاحتياطية: {e}")
        import traceback
        traceback.print_exc()

