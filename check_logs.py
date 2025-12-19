# ================================================
# check_logs.py
# 🔍 فحص وتحليل الـ Logs
# ================================================

import os
import re
from datetime import datetime
from pathlib import Path

def analyze_logs():
    """تحليل الـ logs للبحث عن مشاكل"""
    
    log_files = [
        "logs/bot.log",
        "logs/errors.log",
        "logs/all_events.log"
    ]
    
    print("=" * 60)
    print("🔍 تحليل الـ Logs")
    print("=" * 60)
    print()
    
    # فحص كل ملف
    for log_file in log_files:
        if os.path.exists(log_file):
            print(f"📄 فحص: {log_file}")
            print("-" * 60)
            
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    
                # البحث عن معلومات مهمة
                patient_related = []
                database_related = []
                errors = []
                warnings = []
                
                for line in lines[-100:]:  # آخر 100 سطر
                    line_lower = line.lower()
                    
                    # معلومات عن المرضى
                    if any(keyword in line_lower for keyword in ['patient', 'مريض', 'patient_names', 'أسماء المرضى']):
                        patient_related.append(line.strip())
                    
                    # معلومات عن قاعدة البيانات
                    if any(keyword in line_lower for keyword in ['database', 'قاعدة البيانات', 'db', 'sqlite', 'medical_reports']):
                        database_related.append(line.strip())
                    
                    # أخطاء
                    if 'error' in line_lower or '❌' in line or 'خطأ' in line:
                        errors.append(line.strip())
                    
                    # تحذيرات
                    if 'warning' in line_lower or '⚠️' in line or 'تحذير' in line:
                        warnings.append(line.strip())
                
                # عرض النتائج
                if patient_related:
                    print(f"  👤 معلومات عن المرضى ({len(patient_related)} سطر):")
                    for item in patient_related[-5:]:  # آخر 5
                        print(f"     {item[:100]}")
                    print()
                
                if database_related:
                    print(f"  💾 معلومات عن قاعدة البيانات ({len(database_related)} سطر):")
                    for item in database_related[-5:]:  # آخر 5
                        print(f"     {item[:100]}")
                    print()
                
                if errors:
                    print(f"  ❌ أخطاء ({len(errors)} سطر):")
                    for item in errors[-5:]:  # آخر 5
                        print(f"     {item[:100]}")
                    print()
                
                if warnings:
                    print(f"  ⚠️ تحذيرات ({len(warnings)} سطر):")
                    for item in warnings[-5:]:  # آخر 5
                        print(f"     {item[:100]}")
                    print()
                
                # عرض آخر 10 أسطر
                print(f"  📋 آخر 10 أسطر:")
                for line in lines[-10:]:
                    print(f"     {line.strip()[:100]}")
                print()
                
            except Exception as e:
                print(f"  ❌ خطأ في قراءة الملف: {e}")
                print()
        else:
            print(f"⚠️ الملف غير موجود: {log_file}")
            print()
    
    print("=" * 60)
    print("✅ انتهى التحليل")
    print("=" * 60)


def check_patient_names_loading():
    """التحقق من تحميل أسماء المرضى"""
    
    print()
    print("=" * 60)
    print("🔍 التحقق من تحميل أسماء المرضى")
    print("=" * 60)
    print()
    
    keywords = [
        "تم تحميل",
        "تم استيراد",
        "patient_names",
        "أسماء المرضى",
        "init_patient_names",
        "ensure_patients_in_database",
        "import_patient_names"
    ]
    
    log_files = ["logs/bot.log", "logs/errors.log", "logs/all_events.log"]
    
    found = False
    for log_file in log_files:
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                for keyword in keywords:
                    if keyword in content:
                        print(f"  ✅ وجد: '{keyword}' في {log_file}")
                        found = True
                        
                        # عرض السياق
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if keyword in line.lower():
                                print(f"     السطر {i+1}: {line.strip()[:150]}")
                                # عرض السطور المجاورة
                                for j in range(max(0, i-1), min(len(lines), i+2)):
                                    if j != i:
                                        print(f"     السطر {j+1}: {lines[j].strip()[:150]}")
                                print()
                                break
            except Exception as e:
                print(f"  ❌ خطأ في قراءة {log_file}: {e}")
    
    if not found:
        print("  ⚠️ لم يتم العثور على معلومات عن تحميل أسماء المرضى")
        print("  💡 قد يعني هذا أن البوت لم يبدأ بعد أو أن الـ logs غير متوفرة")
    
    print()


def check_database_status():
    """التحقق من حالة قاعدة البيانات"""
    
    print()
    print("=" * 60)
    print("🔍 التحقق من حالة قاعدة البيانات")
    print("=" * 60)
    print()
    
    keywords = [
        "database loaded",
        "قاعدة البيانات",
        "medical_reports.db",
        "medical_reports_initial.db",
        "Database loaded",
        "Database tables created"
    ]
    
    log_files = ["logs/bot.log", "logs/errors.log", "logs/all_events.log"]
    
    found = False
    for log_file in log_files:
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                for keyword in keywords:
                    if keyword in content:
                        print(f"  ✅ وجد: '{keyword}' في {log_file}")
                        found = True
                        
                        # عرض السياق
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if keyword in line.lower():
                                print(f"     {line.strip()[:150]}")
                                print()
            except Exception as e:
                print(f"  ❌ خطأ في قراءة {log_file}: {e}")
    
    if not found:
        print("  ⚠️ لم يتم العثور على معلومات عن قاعدة البيانات")
    
    print()


def check_render_logs(file_path: str = "render_logs.txt"):
    """فحص الـ logs من Render (إذا تم نسخها)"""
    
    if not os.path.exists(file_path):
        return
    
    print()
    print("=" * 60)
    print("🔍 فحص الـ Logs من Render")
    print("=" * 60)
    print()
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
        
        # البحث عن معلومات مهمة
        success_markers = []
        error_markers = []
        patient_markers = []
        database_markers = []
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # علامات النجاح
            if any(marker in line_lower for marker in ['database loaded', 'تم تحميل', 'تم استيراد', 'تم تهيئة']):
                success_markers.append((i+1, line.strip()))
            
            # علامات الأخطاء
            if any(marker in line_lower for marker in ['error', '❌', 'خطأ', 'failed', 'فشل']):
                error_markers.append((i+1, line.strip()))
            
            # معلومات عن المرضى
            if any(marker in line_lower for marker in ['patient', 'مريض', 'patient_names', 'أسماء المرضى']):
                patient_markers.append((i+1, line.strip()))
            
            # معلومات عن قاعدة البيانات
            if any(marker in line_lower for marker in ['database', 'قاعدة البيانات', 'medical_reports']):
                database_markers.append((i+1, line.strip()))
        
        # عرض النتائج
        print(f"📊 إحصائيات:")
        print(f"   ✅ علامات النجاح: {len(success_markers)}")
        print(f"   ❌ علامات الأخطاء: {len(error_markers)}")
        print(f"   👤 معلومات عن المرضى: {len(patient_markers)}")
        print(f"   💾 معلومات عن قاعدة البيانات: {len(database_markers)}")
        print()
        
        # عرض علامات النجاح
        if success_markers:
            print("✅ علامات النجاح (آخر 10):")
            for line_num, line in success_markers[-10:]:
                print(f"   السطر {line_num}: {line[:150]}")
            print()
        
        # عرض علامات الأخطاء
        if error_markers:
            print("❌ علامات الأخطاء (آخر 10):")
            for line_num, line in error_markers[-10:]:
                print(f"   السطر {line_num}: {line[:150]}")
            print()
        
        # فحص خاص لأسماء المرضى
        patient_imported = False
        patient_count = 0
        for line_num, line in patient_markers:
            if 'استيراد' in line or 'imported' in line.lower():
                patient_imported = True
                # محاولة استخراج العدد
                import re
                match = re.search(r'(\d+)\s*اسم', line)
                if match:
                    patient_count = int(match.group(1))
        
        if patient_imported:
            print(f"✅ تم استيراد أسماء المرضى: {patient_count} اسم")
        else:
            print("⚠️ لم يتم العثور على معلومات عن استيراد أسماء المرضى")
        print()
        
        # فحص قاعدة البيانات
        db_loaded = False
        for line_num, line in database_markers:
            if 'loaded' in line.lower() or 'تم تحميل' in line:
                db_loaded = True
                print(f"✅ قاعدة البيانات: {line[:150]}")
        
        if not db_loaded:
            print("⚠️ لم يتم العثور على معلومات عن تحميل قاعدة البيانات")
        print()
        
    except Exception as e:
        print(f"❌ خطأ في قراءة الملف: {e}")
        print()


if __name__ == "__main__":
    print()
    analyze_logs()
    check_patient_names_loading()
    check_database_status()
    check_render_logs()
    
    print()
    print("💡 نصيحة: لفحص الـ logs من Render:")
    print("   1. اذهب إلى https://dashboard.render.com")
    print("   2. اختر الـ Service")
    print("   3. اضغط 'Logs'")
    print("   4. انسخ الـ Logs واحفظها في ملف 'render_logs.txt'")
    print("   5. شغّل: python check_logs.py")
    print()
    print("   أو ابحث يدوياً عن:")
    print("      - 'تم تحميل X اسم مريض'")
    print("      - 'Database loaded'")
    print("      - 'init_patient_names'")
    print("      - 'تم استيراد X اسم مريض'")
    print()

