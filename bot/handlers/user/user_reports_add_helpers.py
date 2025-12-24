# =============================
# bot/handlers/user/user_reports_add_helpers.py
# دوال مساعدة لإضافة التقارير
# =============================
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from db.session import SessionLocal
from db.models import Report, Patient, Hospital, Department, Doctor, Translator
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# =============================
# 📋 قوائم البيانات الثابتة
# =============================

# =============================
# 🏥 قائمة المستشفيات
# =============================
PREDEFINED_HOSPITALS = [
    "Manipal Hospital - Old Airport Road",
    "Manipal Hospital - Millers Road",
    "Manipal Hospital - Whitefield",
    "Manipal Hospital - Yeshwanthpur",
    "Manipal Hospital - Sarjapur Road",
    "Aster CMI",
    "Aster RV",
    "Aster Whitefield",
    "Sakra World Hospital, Bangalore",
    "Fortis Hospital BG Road, Bangalore",
    "Apollo Hospital, Bannerghatta, Bangalore",
    "SPARSH Hospital, Infantry Road",
    "SPARSH Hospital, Hennur Road",
    "Sankara Eye Hospital, Bengaluru",
    "St John Hospital, Bangalore",
    "Trilife Hospital, Bangalore",
    "Silverline Diagnostics Kalyan Nagar",
    "M S Ramaiah Memorial Hospital, Bangalore",
    "Narayana Hospital, Bommasandra",
    "Gleneagles Global Hospital, Kengeri, Bangalore",
    "Rela Hospital, Chennai",
    "Rainbow Children's Hospital, Marathahalli",
    "HCG Hospital K R Road, Bangalore",
    "L V Prasad Eye Institute, Hyderabad",
    "NU Hospitals, Rajajinagar",
    "Zion Hospital, Kammanahalli",
    "Cura Hospital, Kammanahalli",
    "KIMS Hospital, Mahadevapura",
    "KARE Prosthetics & Orthotics, Bangalore",
    "Nueclear Diagnostics, Bangalore",
    "BLK-Max Super Specialty Hospital, Delhi",
    "Max Super Speciality Hospital, Saket, Delhi",
    "Artemis Hospital, Delhi",
    "Bhagwan Mahaveer Jain Hospital - Millers Road",
    "AIG Hospitals, Hyderabad"
]


# =============================
# 🏥 الأقسام الطبية - نظام هرمي
# =============================
# الصيغة: "عربي | إنجليزي"
# الترتيب: 1- الجراحة، 2- الباطنية، 3- طب وجراحة العيون، 4- طب الأطفال
# تم نقل الأقسام الرئيسية إلى ملفات منفصلة

# استيراد الأقسام من الملفات المنفصلة
from .departments_surgery import SURGERY_DEPARTMENTS
from .departments_internal import INTERNAL_DEPARTMENTS
from .departments_ophthalmology import OPHTHALMOLOGY_DEPARTMENTS
from .departments_pediatrics import PEDIATRICS_DEPARTMENTS

# دمج جميع الأقسام الرئيسية
PREDEFINED_DEPARTMENTS = {}
PREDEFINED_DEPARTMENTS.update(SURGERY_DEPARTMENTS)
PREDEFINED_DEPARTMENTS.update(INTERNAL_DEPARTMENTS)
PREDEFINED_DEPARTMENTS.update(OPHTHALMOLOGY_DEPARTMENTS)
PREDEFINED_DEPARTMENTS.update(PEDIATRICS_DEPARTMENTS)


# =============================
# 🏥 الأقسام المباشرة (بدون فروع)
# =============================
# الصيغة: "عربي | إنجليزي"
# الترتيب: الأذن والأنف والحنجرة، أشعة وفحوصات، الأمراض الجلدية، النساء والتوليد، 
#          علاج وإدارة الألم، الطب النفسي، الطوارئ، التخدير، العناية المركزة
DIRECT_DEPARTMENTS = [
    "الأذن والأنف والحنجرة | ENT",
    "أشعة وفحوصات | Radiology",
    "الأمراض الجلدية | Dermatology",
    "النساء والتوليد | Obstetrics & Gynecology",
    "العلاج الطبيعي وإعادة التأهيل | Physical Therapy & Rehabilitation",
    "علاج وإدارة الألم | Pain Management",
    "الطب النفسي | Psychiatry",
    "الطوارئ | Emergency",
    "التخدير | Anesthesia",
    "العناية المركزة | Critical Care / ICU"
]


# =============================
# 👨‍⚕️ قائمة الأطباء (اختيارية - للاستخدام المستقبلي)
# =============================
PREDEFINED_DOCTORS = [
    "د. أحمد", "د. محمد", "د. علي", "د. خالد", "د. يوسف",
    "د. راجيش", "د. سانجاي", "د. براشانت", "د. أنيل", "د. فيجاي"
]


# =============================
# 📝 قائمة الإجراءات الطبية (اختيارية - للاستخدام المستقبلي)
# =============================
PREDEFINED_ACTIONS = [
    "استشارة جديدة",
    "استشارة مع قرار عملية",
    "استشارة أخيرة",
    "طوارئ",
    "متابعة في الرقود",
    "مراجعة / عودة دورية",
    "عملية",
    "علاج طبيعي وإعادة تأهيل",
    "ترقيد",
    "خروج من المستشفى"
]


# =============================
# 🔧 الدوال المساعدة
# =============================

def validate_text_input(text, min_length=3, max_length=1000):
    """فحص صحة النص المدخل"""
    if not text or len(text) < min_length:
        return False, f"النص قصير جداً (يجب أن يكون {min_length} أحرف على الأقل)"
    
    if len(text) > max_length:
        return False, f"النص طويل جداً ({len(text)} حرف، الحد الأقصى {max_length})"
    
    return True, "صحيح"


def validate_english_only(text, min_length=3, max_length=200):
    """فحص أن النص يحتوي على أحرف إنجليزية فقط (مع السماح ببعض الرموز الطبية)"""
    import re
    
    # التحقق من الطول أولاً
    if not text or len(text) < min_length:
        return False, f"النص قصير جداً (يجب أن يكون {min_length} أحرف على الأقل)"
    
    if len(text) > max_length:
        return False, f"النص طويل جداً ({len(text)} حرف، الحد الأقصى {max_length})"
    
    # السماح فقط بـ:
    # - أحرف إنجليزية (a-z, A-Z)
    # - أرقام (0-9)
    # - مسافات
    # - رموز شائعة في الأسماء الطبية: -, /, (, ), &, ., ', "
    pattern = r'^[a-zA-Z0-9\s\-/()&.\'"]+$'
    
    if not re.match(pattern, text):
        return False, "⚠️ يجب إدخال النص بالإنجليزية فقط (أحرف لاتينية، أرقام، ومسافات فقط)"
    
    # التحقق من وجود حرف إنجليزي واحد على الأقل (وليس فقط أرقام ورموز)
    if not re.search(r'[a-zA-Z]', text):
        return False, "⚠️ يجب أن يحتوي النص على حرف إنجليزي واحد على الأقل"
    
    return True, "صحيح"


async def save_report_to_db(query, context):
    """حفظ التقرير في قاعدة البيانات"""
    data_tmp = context.user_data.get("report_tmp", {})
    
    # التحقق من البيانات الأساسية
    if not data_tmp.get("patient_name"):
        print("❌ خطأ: لا يوجد اسم مريض")
        return None
    
    if not data_tmp.get("hospital_name"):
        print("❌ خطأ: لا يوجد مستشفى")
        return None
        
    if not data_tmp.get("department_name"):
        print("❌ خطأ: لا يوجد قسم")
        return None
    
    session = None
    try:
        session = SessionLocal()
        
        # جلب أو إنشاء المريض (مع get_or_create أسرع)
        patient = session.query(Patient).filter_by(full_name=data_tmp.get("patient_name")).first()
        if not patient:
            patient = Patient(full_name=data_tmp.get("patient_name"))
            session.add(patient)
        
        # جلب أو إنشاء المستشفى
        hospital = session.query(Hospital).filter_by(name=data_tmp.get("hospital_name")).first()
        if not hospital:
            hospital = Hospital(name=data_tmp.get("hospital_name"))
            session.add(hospital)
        
        # جلب أو إنشاء القسم
        department = session.query(Department).filter_by(name=data_tmp.get("department_name")).first()
        if not department:
            department = Department(name=data_tmp.get("department_name"))
            session.add(department)
        
        # جلب أو إنشاء الطبيب (إذا وجد)
        doctor = None
        doctor_name = data_tmp.get("doctor_name")
        if doctor_name:
            doctor = session.query(Doctor).filter_by(full_name=doctor_name).first()
            if not doctor:
                doctor = Doctor(
                    name=doctor_name,  # Use same value for name
                    full_name=doctor_name
                )
                session.add(doctor)
        
        # flush واحد لجميع الكائنات (أسرع)
        session.flush()
        
        # المترجم
        translator = None
        created_by_tg_user_id = None
        if query.from_user:
            translator = session.query(Translator).filter_by(tg_user_id=query.from_user.id).first()
            created_by_tg_user_id = query.from_user.id
        
        # إنشاء التقرير
        print("📝 إنشاء التقرير...")
        new_report = Report(
            patient_id=patient.id,
            hospital_id=hospital.id,
            department_id=department.id,
            doctor_id=doctor.id if doctor else None,
            translator_id=translator.id if translator else None,
            created_by_tg_user_id=created_by_tg_user_id,  # المستخدم الذي أنشأ التقرير
            complaint_text=data_tmp.get("complaint_text", ""),
            doctor_decision=data_tmp.get("doctor_decision", ""),
            medical_action=data_tmp.get("medical_action", ""),
            followup_date=data_tmp.get("followup_date"),
            followup_reason=data_tmp.get("followup_reason", ""),
            report_date=data_tmp.get("report_date") or datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        session.add(new_report)
        session.commit()
        session.refresh(new_report)
        
        print(f"✅ تم حفظ التقرير برقم: {new_report.id}")
        
        # حفظ الـ IDs قبل إغلاق الـ session
        report_id = new_report.id
        translator_id = translator.id if translator else None
        translator_name = translator.full_name if translator else None
        
        return (report_id, translator_id, translator_name)
        
    except Exception as e:
        if session:
            session.rollback()
        print(f"❌ خطأ في save_report_to_db: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if session:
            session.close()


async def broadcast_report(query_bot, data_tmp, translator):
    """إرسال التقرير لجميع المستخدمين"""
    try:
        from services.broadcast_service import broadcast_new_report
        
        report_date_obj = data_tmp.get('report_date')
        
        followup_display = 'لا يوجد'
        if data_tmp.get('followup_date_text'):
            followup_display = data_tmp.get('followup_date_text')
        elif data_tmp.get('followup_date'):
            followup_display = data_tmp.get('followup_date').strftime('%Y-%m-%d')
            if data_tmp.get('followup_time'):
                # تحويل الوقت من صيغة 24 ساعة (HH:MM) إلى صيغة 12 ساعة
                time_str = data_tmp.get('followup_time')
                try:
                    hour, minute = time_str.split(':')
                    hour_int = int(hour)
                    if hour_int == 0:
                        time_display = f"12:{minute} صباحاً"
                    elif hour_int < 12:
                        time_display = f"{hour_int}:{minute} صباحاً"
                    elif hour_int == 12:
                        time_display = f"12:{minute} ظهراً"
                    else:
                        time_display = f"{hour_int-12}:{minute} مساءً"
                    followup_display += f" الساعة {time_display}"
                except:
                    # في حالة الخطأ، استخدم الصيغة الأصلية
                    followup_display += f" الساعة {time_str}"
        
        broadcast_data = {
            'report_date': report_date_obj.strftime('%Y-%m-%d %H:%M') if report_date_obj and hasattr(report_date_obj, 'strftime') else 'غير محدد',
            'patient_name': data_tmp.get('patient_name', 'غير محدد'),
            'hospital_name': data_tmp.get('hospital_name', 'غير محدد'),
            'department_name': data_tmp.get('department_name', 'غير محدد'),
            'doctor_name': data_tmp.get('doctor_name', 'لم يتم التحديد'),
            'medical_action': data_tmp.get('medical_action', 'غير محدد'),
            'radiology_type': data_tmp.get('radiology_type', 'لا يوجد'),
            'radiology_delivery_date': data_tmp.get('radiology_delivery_date').strftime('%Y-%m-%d') if data_tmp.get('radiology_delivery_date') else 'لا يوجد',
            'complaint_text': data_tmp.get('complaint_text', 'غير محدد'),
            'doctor_decision': data_tmp.get('doctor_decision', 'غير محدد'),
            'case_status': data_tmp.get('case_status', 'لا يوجد'),
            'followup_date': followup_display,
            'followup_reason': data_tmp.get('followup_reason', 'لا يوجد'),
            'translator_name': data_tmp.get('translator_name') or (translator.full_name if translator else "غير محدد"),
        }
        
        await broadcast_new_report(query_bot, broadcast_data)
    except Exception as e:
        print(f"خطأ في بث التقرير: {e}")


async def create_evaluation(new_report, data_tmp, translator):
    """إنشاء تقييم يومي"""
    try:
        from services.evaluation_service import evaluation_service
        translator_name = data_tmp.get("translator_name") or (translator.full_name if translator else "غير محدد")
        evaluation_service.create_daily_evaluation(new_report, translator_name)
    except Exception as e:
        print(f"خطأ في التقييم: {e}")

