# =============================
# bot/handlers/user/user_reports_add_helpers.py
# دوال مساعدة لإضافة التقارير
# =============================
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from db.session import SessionLocal
from db.models import Report, Patient, Hospital, Department, Doctor, Translator
from datetime import datetime, timedelta, timezone
import logging
from zoneinfo import ZoneInfo

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
    "العناية المركزة | Critical Care / ICU",
    "العلاج الإشعاعي | The radiation Therapy"
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
    "تأجيل موعد",
    "جلسة إشعاعي"  # ✅ مسار جديد للعلاج الإشعاعي
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

        translator_id_value = data_tmp.get("translator_id")
        translator_name_value = data_tmp.get("translator_name")
        if not translator_id_value and translator:
            translator_id_value = translator.tg_user_id or None
        if not translator_name_value and translator:
            translator_name_value = translator.full_name
        
        # إنشاء التقرير
        print("📝 إنشاء التقرير...")
        # ✅ الحصول على معرف المستخدم الذي أنشأ التقرير
        submitted_by_user_id = None
        if query and query.from_user:
            submitted_by_user_id = query.from_user.id
        elif context.user_data.get('_user_id'):
            submitted_by_user_id = context.user_data.get('_user_id')
        
        new_report = Report(
            # IDs للربط
            patient_id=patient.id,
            hospital_id=hospital.id,
            department_id=department.id,
            doctor_id=doctor.id if doctor else None,
            translator_id=translator_id_value,
            submitted_by_user_id=submitted_by_user_id,
            
            # ✅ الأسماء المكررة للبحث والطباعة السريعة
            patient_name=patient.full_name if patient else data_tmp.get("patient_name"),
            hospital_name=hospital.name if hospital else data_tmp.get("hospital_name"),
            department=department.name if department else data_tmp.get("department_name"),
            doctor_name=doctor.name if doctor else data_tmp.get("doctor_name"),
            translator_name=translator_name_value,
            
            # محتوى التقرير
            complaint_text=data_tmp.get("complaint_text", ""),
            doctor_decision=data_tmp.get("doctor_decision", ""),
            medical_action=data_tmp.get("medical_action", ""),
            
            # التواريخ
            followup_date=data_tmp.get("followup_date"),
            followup_reason=data_tmp.get("followup_reason", ""),
            report_date=data_tmp.get("report_date") or datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None),
            created_at=datetime.utcnow(),
            
            # حقول تأجيل الموعد
            app_reschedule_reason=data_tmp.get("app_reschedule_reason"),
            app_reschedule_return_date=data_tmp.get("app_reschedule_return_date"),
            app_reschedule_return_reason=data_tmp.get("app_reschedule_return_reason"),
        )
        session.add(new_report)
        session.commit()
        session.refresh(new_report)
        
        print(f"✅ تم حفظ التقرير برقم: {new_report.id}")
        
        # حفظ الـ IDs قبل إغلاق الـ session
        report_id = new_report.id
        translator_id = translator_id_value
        translator_name = translator_name_value
        
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
        from db.session import SessionLocal
        from db.models import Report

        # الحصول على report_id من البيانات المؤقتة بعد الحفظ
        report_id = data_tmp.get('report_id')
        if not report_id:
            print("❌ لا يوجد report_id في البيانات المؤقتة!")
            return

        # قراءة التقرير من قاعدة البيانات
        session = SessionLocal()
        report_obj = session.query(Report).filter(Report.id == report_id).first()
        if not report_obj:
            print(f"❌ لم يتم العثور على التقرير في قاعدة البيانات: {report_id}")
            session.close()
            return

        # تحويل كائن التقرير إلى dict (للتوافق مع broadcast_new_report)
        report_data = {c.name: getattr(report_obj, c.name) for c in report_obj.__table__.columns}
        # إضافة اسم المترجم إذا لم يكن موجودًا
        if not report_data.get('translator_name') and translator:
            report_data['translator_name'] = translator.full_name

        await broadcast_new_report(query_bot, report_data)
        session.close()
    except Exception as e:
        print(f"خطأ في بث التقرير: {e}")


async def create_evaluation(new_report, data_tmp, translator):
    """إنشاء تقييم يومي"""
    try:
        from services.evaluation_service import evaluation_service
        translator_id = data_tmp.get("translator_id") or (translator.tg_user_id if translator else None)
        translator_name = data_tmp.get("translator_name") or (translator.full_name if translator else "غير محدد")
        evaluation_service.create_daily_evaluation(new_report, translator_id, translator_name)
    except Exception as e:
        print(f"خطأ في التقييم: {e}")
