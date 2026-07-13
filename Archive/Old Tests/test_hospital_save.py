# ================================================
# اختبار حفظ المستشفيات في قاعدة البيانات
# ================================================

import sys
import os

# إصلاح الترميز في Windows
if sys.platform == 'win32':
    os.system('chcp 65001 >nul')
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv("config.env")

from db.session import get_db, init_database, DATABASE_PATH
from db.models import Hospital
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_hospital_save():
    """اختبار حفظ مستشفى في قاعدة البيانات"""
    
    print("\n" + "="*60)
    print("اختبار حفظ المستشفيات في قاعدة البيانات")
    print("="*60 + "\n")
    
    # تهيئة قاعدة البيانات
    print("1. تهيئة قاعدة البيانات...")
    if not init_database():
        print("❌ فشل في تهيئة قاعدة البيانات")
        return False
    print(f"✅ قاعدة البيانات جاهزة: {DATABASE_PATH}\n")
    
    # اختبار إضافة مستشفى
    test_hospital_name = "Test Hospital - " + str(os.getpid())
    print(f"2. إضافة مستشفى تجريبي: {test_hospital_name}")
    
    try:
        with get_db() as s:
            # التحقق من عدم وجود المستشفى
            existing = s.query(Hospital).filter_by(name=test_hospital_name).first()
            if existing:
                print(f"⚠️ المستشفى موجود مسبقاً، سيتم حذفه أولاً...")
                s.delete(existing)
            
            # إضافة مستشفى جديد
            new_hospital = Hospital(name=test_hospital_name)
            s.add(new_hospital)
            # get_db() يقوم بالـ commit تلقائياً
        
        print("✅ تم إضافة المستشفى بنجاح\n")
        
        # التحقق من الحفظ
        print("3. التحقق من الحفظ...")
        with get_db() as s:
            saved_hospital = s.query(Hospital).filter_by(name=test_hospital_name).first()
            if saved_hospital:
                print(f"✅ المستشفى محفوظ بنجاح!")
                print(f"   - ID: {saved_hospital.id}")
                print(f"   - الاسم: {saved_hospital.name}")
                print(f"   - تاريخ الإنشاء: {saved_hospital.created_at}")
                
                # حذف المستشفى التجريبي
                print("\n4. حذف المستشفى التجريبي...")
                s.delete(saved_hospital)
                print("✅ تم حذف المستشفى التجريبي")
                return True
            else:
                print("❌ المستشفى غير موجود في قاعدة البيانات!")
                return False
                
    except Exception as e:
        print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_existing_hospitals():
    """فحص المستشفيات الموجودة"""
    print("\n" + "="*60)
    print("فحص المستشفيات الموجودة في قاعدة البيانات")
    print("="*60 + "\n")
    
    try:
        with get_db() as s:
            hospitals = s.query(Hospital).order_by(Hospital.name).all()
            print(f"📊 عدد المستشفيات: {len(hospitals)}\n")
            
            if hospitals:
                print("قائمة المستشفيات:")
                for i, hospital in enumerate(hospitals[:10], 1):  # أول 10 فقط
                    print(f"  {i}. {hospital.name} (ID: {hospital.id})")
                if len(hospitals) > 10:
                    print(f"  ... و {len(hospitals) - 10} مستشفى آخر")
            else:
                print("⚠️ لا توجد مستشفيات في قاعدة البيانات")
            
            return True
    except Exception as e:
        print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n🔍 اختبار نظام حفظ المستشفيات\n")
    
    # فحص المستشفيات الموجودة
    check_existing_hospitals()
    
    # اختبار الحفظ
    success = test_hospital_save()
    
    print("\n" + "="*60)
    if success:
        print("✅ جميع الاختبارات نجحت!")
    else:
        print("❌ فشل أحد الاختبارات")
    print("="*60 + "\n")
