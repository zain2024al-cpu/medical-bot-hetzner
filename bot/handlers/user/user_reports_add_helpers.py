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
# 📋 قوائم البيانات الموحدة
# =============================

# =============================
# 🏥 قائمة المستشفيات - من الخدمة الموحدة
# =============================
def get_predefined_hospitals():
    """الحصول على المستشفيات من الخدمة الموحدة"""
    try:
        from services.hospitals_service import get_all_hospitals
        return get_all_hospitals()
    except Exception:
        return []

# للتوافق مع الكود القديم
PREDEFINED_HOSPITALS = get_predefined_hospitals()


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
# الترتيب: الأذن والأنف والحنجرة، الأمراض الجلدية، النساء والتوليد، 
#          علاج وإدارة الألم، الطب النفسي، الطوارئ، التخدير، العناية المركزة
# ملاحظة: تم نقل "أشعة وفحوصات" إلى قائمة أنواع الإجراءات (PREDEFINED_ACTIONS)
DIRECT_DEPARTMENTS = [
    "الأذن والأنف والحنجرة | ENT",
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
    "خروج من المستشفى",
    "أشعة وفحوصات",  # ✅ تم نقلها من قائمة الأقسام إلى قائمة أنواع الإجراءات
    "تأجيل موعد"
]


# =============================
# 🔧 الدوال المساعدة
# =============================

def validate_text_input(text, min_length=1, max_length=None):
    """
    فحص صحة النص المدخل - يقبل جميع النصوص والرموز بدون أي قيود
    ✅ يقبل: عربي، إنجليزي، أرقام، رموز، إيموجي، أي شيء
    ✅ بدون حد أدنى أو أقصى للطول
    """
    # ✅ يقبل أي نص - حتى لو فارغ سنقبله
    if text is None:
        text = ""
    
    text = str(text).strip()
    
    # ✅ لا يوجد أي قيود على الطول - نقبل أي نص
    # ✅ لا يوجد أي قيود على نوع الأحرف أو الرموز
    # ✅ نقبل الإيموجي والرموز الخاصة
    return True, "صحيح"


def validate_english_only(text, min_length=1, max_length=None):
    """
    فحص النص - يقبل جميع النصوص والرموز بدون أي قيود
    ✅ يقبل: عربي، إنجليزي، أرقام، رموز، إيموجي، أي شيء
    (اسم الدالة للتوافق مع الكود القديم فقط)
    """
    # ✅ يقبل أي نص - بدون قيود
    if text is None:
        text = ""
    
    # ✅ لا يوجد أي قيود - يقبل عربي، إنجليزي، أرقام، رموز، إيموجي، كل شيء
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
        if query.from_user:
            translator = session.query(Translator).filter_by(tg_user_id=query.from_user.id).first()
        
        # إنشاء التقرير
        print("📝 إنشاء التقرير...")
        # ✅ الحصول على معرف المستخدم الذي أنشأ التقرير
        submitted_by_user_id = None
        if query and query.from_user:
            submitted_by_user_id = query.from_user.id
        elif context.user_data.get('_user_id'):
            submitted_by_user_id = context.user_data.get('_user_id')
        
        # ✅ تحويل التواريخ إلى naive datetime (SQLite لا يقبل tzinfo)
        def to_naive_datetime(dt):
            """تحويل datetime مع tzinfo إلى naive datetime"""
            if dt is None:
                return None
            if isinstance(dt, str):
                try:
                    from dateutil import parser
                    dt = parser.parse(dt)
                except:
                    return None
            if hasattr(dt, 'year') and not hasattr(dt, 'hour'):
                dt = datetime.combine(dt, datetime.min.time())
            if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                try:
                    from zoneinfo import ZoneInfo
                    return dt.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
                except:
                    return dt.replace(tzinfo=None)
            return dt
        
        # معالجة التواريخ
        followup_date = to_naive_datetime(data_tmp.get("followup_date"))
        report_date = to_naive_datetime(data_tmp.get("report_date")) or datetime.utcnow()
        app_reschedule_return_date = to_naive_datetime(data_tmp.get("app_reschedule_return_date"))
        
        new_report = Report(
            patient_id=patient.id,
            hospital_id=hospital.id,
            department_id=department.id,
            doctor_id=doctor.id if doctor else None,
            translator_id=translator.id if translator else None,
            complaint_text=data_tmp.get("complaint_text", ""),
            doctor_decision=data_tmp.get("doctor_decision", ""),
            medical_action=data_tmp.get("medical_action", ""),
            followup_date=followup_date,
            followup_reason=data_tmp.get("followup_reason", ""),
            app_reschedule_reason=data_tmp.get("app_reschedule_reason"),
            app_reschedule_return_date=app_reschedule_return_date,
            app_reschedule_return_reason=data_tmp.get("app_reschedule_return_reason"),
            report_date=report_date,
            created_at=datetime.utcnow(),
            submitted_by_user_id=submitted_by_user_id,  # ✅ حفظ معرف المستخدم
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

