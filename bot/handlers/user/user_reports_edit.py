# ================================================
# bot/handlers/user/user_reports_edit.py
# تعديل التقارير الموجودة - نظام بسيط
# ================================================

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, 
    CallbackQueryHandler, filters
)
from telegram.constants import ParseMode
from datetime import datetime, date, timedelta
from db.session import SessionLocal
from db.models import Report, Translator, Patient, Hospital, Department, Doctor
from bot.shared_auth import is_admin
from services.inline_calendar import create_calendar_keyboard, create_quick_date_buttons, MONTHS_AR
from sqlalchemy import or_, and_

# حالات المحادثة
SELECT_REPORT, SELECT_FIELD, EDIT_VALUE, CONFIRM_EDIT, EDIT_DATE_CALENDAR, EDIT_DATE_TIME, EDIT_TRANSLATOR = range(7)


def format_time_12h(time_str):
    """تحويل الوقت لصيغة 12 ساعة مع صباحاً/ظهراً/مساءً"""
    if not time_str:
        return None
    try:
        if ':' in str(time_str):
            parts = str(time_str).split(':')
            hour = int(parts[0])
            minute = parts[1] if len(parts) > 1 else '00'
        else:
            hour = int(time_str)
            minute = '00'
        
        if hour == 0:
            return f"12:{minute} صباحاً"
        elif hour < 12:
            return f"{hour}:{minute} صباحاً"
        elif hour == 12:
            return f"12:{minute} ظهراً"
        else:
            return f"{hour-12}:{minute} مساءً"
    except:
        return str(time_str)


def escape_markdown(text):
    """تنظيف النص من الأحرف الخاصة بـ Markdown"""
    if not text:
        return text
    text = str(text)
    # الأحرف الخاصة التي تحتاج escape في Markdown
    special_chars = ['*', '_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, '\\' + char)
    return text


def get_all_editable_fields():
    """إرجاع جميع الحقول القابلة للتعديل من جميع أنواع الإجراءات"""
    return [
        ('complaint_text', '💬 شكوى المريض / تفاصيل'),
        ('diagnosis', '🔬 التشخيص الطبي'),
        ('doctor_decision', '📝 قرار الطبيب'),
        ('notes', '🧪 الفحوصات والأشعة / اسم العملية'),
        ('treatment_plan', '📋 التوصيات / نسبة النجاح'),
        ('medications', '💊 الأدوية'),
        ('followup_date', '📅 موعد العودة'),
        ('followup_reason', '✍️ سبب العودة'),
        ('case_status', '🚨 حالة الطوارئ'),
    ]

def test_editable_fields_mapping():
    """
    دالة اختبار للتأكد من أن كل نوع إجراء يحصل على الحقول الصحيحة
    ✅ تم تحديث عدد الحقول ليتطابق مع get_editable_fields_by_action_type
    """
    test_cases = [
        ('استشارة جديدة', 7),  # 7 حقول (complaint, diagnosis, decision, notes, followup_date, followup_reason, translator)
        ('استشارة مع قرار عملية', 10),  # 10 حقول
        ('استشارة أخيرة', 4),  # 4 حقول (diagnosis, decision, treatment_plan, translator)
        ('طوارئ', 7),  # 7 حقول (complaint, diagnosis, decision, case_status, followup_date, followup_reason, translator)
        ('متابعة في الرقود', 6),  # 6 حقول (complaint, decision, room, followup_date, followup_reason, translator)
        ('مراجعة / عودة دورية', 6),  # 6 حقول (complaint, diagnosis, decision, followup_date, followup_reason, translator)
        ('عملية', 6),  # 6 حقول (operation_details, operation_name_en, notes, followup_date, followup_reason, translator)
        ('علاج طبيعي وإعادة تأهيل', 4),  # 4 حقول (therapy_details, followup_date, followup_reason, translator)
        ('علاج طبيعي', 4),  # 4 حقول
        ('أجهزة تعويضية', 4),  # 4 حقول
        ('ترقيد', 6),  # 6 حقول (admission_reason, room, notes, followup_date, followup_reason, translator)
        ('خروج من المستشفى', 6),  # 6 حقول
        ('تأجيل موعد', 4),  # 4 حقول
        ('أشعة وفحوصات', 3),  # 3 حقول
        ('جلسة إشعاعي', 6),  # 6 حقول
        ('نوع غير معروف', 4),  # 4 حقول افتراضية
    ]

    print("🧪 اختبار تعيين الحقول القابلة للتعديل:")
    print("=" * 50)

    all_passed = True
    for action_type, expected_count in test_cases:
        fields = get_editable_fields_by_action_type(action_type)
        actual_count = len(fields)

        status = "✅" if actual_count == expected_count else "❌"
        print(f"{status} {action_type}: {actual_count} حقل (متوقع: {expected_count})")

        if actual_count != expected_count:
            all_passed = False
            print(f"   الحقول: {[field[0] for field in fields]}")

    print("=" * 50)
    if all_passed:
        print("✅ جميع اختبارات تعيين الحقول نجحت!")
    else:
        print("❌ بعض الاختبارات فشلت - يرجى المراجعة!")

    return all_passed

def _has_field_value_in_report(report, current_report_data, field_name):
    """
    التحقق من وجود قيمة فعلية للحقل في التقرير المنشور
    يعيد True فقط إذا كان للحقل قيمة حقيقية (ليست فارغة، None، أو "لا يوجد")
    
    منطق العمل:
    1. الحقول الأساسية (report_date, patient_name, hospital_name, department_name, doctor_name) تكون دائماً موجودة
    2. الحقول الأخرى يتم التحقق منها في current_report_data أولاً
    3. إذا لم توجد في current_report_data، يتم التحقق من report مباشرة
    4. يتم التحقق من الحقول المشتقة (مثل complaint_text مقابل complaint)
    """
    # ✅ الحقول الأساسية تكون دائماً موجودة (لا نعرضها في قائمة التعديل لأنها غير قابلة للتعديل)
    # لكن إذا كانت في القائمة، نتحقق من وجودها
    
    # ✅ التحقق من current_report_data أولاً (البيانات المحملة)
    value = current_report_data.get(field_name)
    
    # ✅ التحقق من الحقول المشتقة
    field_aliases = {
        # الحقول الأساسية (عادة موجودة، لكن نتحقق منها)
        "report_date": ["report_date"],
        "patient_name": ["patient_name"],
        "hospital_name": ["hospital_name"],
        "department_name": ["department_name"],
        "doctor_name": ["doctor_name"],
        
        # الحقول المشتقة
        "complaint_text": ["complaint_text", "complaint"],
        "diagnosis": ["diagnosis"],
        "doctor_decision": ["doctor_decision", "decision"],
        "notes": ["notes", "tests"],  # في بعض المسارات، tests محفوظ في notes
        "treatment_plan": ["treatment_plan"],
        "medications": ["medications", "tests"],  # في استشارة جديدة، tests محفوظ في medications
        "followup_date": ["followup_date", "app_reschedule_return_date"],
        "followup_time": ["followup_time"],
        "followup_reason": ["followup_reason", "app_reschedule_return_reason"],
        "case_status": ["case_status"],
        "room_number": ["room_number", "room_floor"],
        "radiology_type": ["radiology_type"],
        "radiology_delivery_date": ["radiology_delivery_date", "delivery_date"],
        "app_reschedule_reason": ["app_reschedule_reason"],
        "app_reschedule_return_date": ["app_reschedule_return_date", "followup_date"],
        "app_reschedule_return_reason": ["app_reschedule_return_reason", "followup_reason"],
        "translator_name": ["translator_name"],
        # ✅ حقول المسارات الخاصة
        "operation_details": ["operation_details", "notes", "doctor_decision"],
        "operation_name_en": ["operation_name_en", "notes"],
        "admission_reason": ["admission_reason", "complaint_text", "complaint"],
        "admission_summary": ["admission_summary", "notes"],
        "therapy_details": ["therapy_details", "complaint_text", "notes"],
        "device_details": ["device_details", "device_name", "complaint_text", "notes"],
        # ✅ حقول استشارة مع قرار عملية
        "decision": ["decision", "doctor_decision"],
        "success_rate": ["success_rate"],
        "benefit_rate": ["benefit_rate"],
        "tests": ["tests", "medications", "notes"],
        # ✅ حقول العلاج الإشعاعي
        "radiation_therapy_type": ["radiation_therapy_type"],
        "radiation_therapy_session_number": ["radiation_therapy_session_number"],
        "radiation_therapy_remaining": ["radiation_therapy_remaining"],
        "radiation_therapy_recommendations": ["radiation_therapy_recommendations", "notes"],
    }
    
    # ✅ البحث في الحقول المشتقة
    aliases = field_aliases.get(field_name, [field_name])
    for alias in aliases:
        alias_value = current_report_data.get(alias)
        if alias_value is not None:
            if isinstance(alias_value, (date, datetime)):
                return True  # التاريخ موجود
            value_str = str(alias_value).strip()
            if value_str and value_str not in ["غير محدد", "لا يوجد", "None", "null", "", "⚠️ فارغ"]:
                return True
    
    # ✅ التحقق من التقرير نفسه مباشرة (fallback)
    if report:
        if hasattr(report, field_name):
            attr_value = getattr(report, field_name, None)
            if attr_value is not None:
                if isinstance(attr_value, (date, datetime)):
                    return True
                value_str = str(attr_value).strip()
                if value_str and value_str not in ["غير محدد", "لا يوجد", "None", "null", "", "⚠️ فارغ"]:
                    return True
    
    return False


def get_editable_fields_by_action_type(medical_action):
    """
    تحديد الحقول القابلة للتعديل حسب نوع الإجراء بدقة عالية
    - كل نوع إجراء له حقوله المحددة فقط
    - لا حقول إضافية أو غير ضرورية
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🔍 get_editable_fields_by_action_type: received medical_action = {repr(medical_action)}")
    
    if not medical_action:
        # الحد الأدنى من الحقول للحالات غير المحددة
        logger.warning("⚠️ get_editable_fields_by_action_type: medical_action is empty!")
        return [
            ('complaint_text', '💬 شكوى المريض'),
            ('doctor_decision', '📝 قرار الطبيب'),
        ]

    action_clean = medical_action.strip()
    logger.info(f"🔍 get_editable_fields_by_action_type: action_clean = {repr(action_clean)}")

    # ===========================================
    # 1. استشارة جديدة - الحقول الأساسية للتشخيص
    # ===========================================
    if action_clean == 'استشارة جديدة':
        return [
            ('complaint_text', '💬 شكوى المريض'),
            ('diagnosis', '🔬 التشخيص'),
            ('doctor_decision', '📝 قرار الطبيب'),
            ('notes', '🧪 الفحوصات'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 2. استشارة مع قرار عملية - التركيز على العملية
    # ===========================================
    elif action_clean == 'استشارة مع قرار عملية':
        return [
            ('complaint_text', '💬 شكوى المريض'),
            ('diagnosis', '🔬 التشخيص'),
            ('decision', '📝 قرار الطبيب'),
            ('operation_name_en', '🔤 اسم العملية بالإنجليزي'),
            ('success_rate', '📊 نسبة نجاح العملية'),
            ('benefit_rate', '💡 نسبة الاستفادة'),
            ('tests', '🧪 الفحوصات والأشعة'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 3. استشارة أخيرة - التركيز على النتائج النهائية
    # ===========================================
    elif action_clean == 'استشارة أخيرة':
        return [
            ('diagnosis', '🔬 التشخيص'),
            ('doctor_decision', '📝 قرار الطبيب'),
            ('treatment_plan', '📋 التوصيات'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 4. طوارئ - التركيز على الحالة العاجلة
    # ===========================================
    elif action_clean == 'طوارئ':
        return [
            ('complaint_text', '💬 شكوى المريض'),
            ('diagnosis', '🔬 التشخيص'),
            ('doctor_decision', '📝 قرار الطبيب'),
            ('case_status', '🚨 وضع الحالة'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 5. متابعة في الرقود - التركيز على المتابعة اليومية
    # ===========================================
    elif 'متابعة في الرقود' in action_clean:
        return [
            ('complaint_text', '🛏️ حالة المريض اليومية'),
            ('doctor_decision', '📝 قرار الطبيب اليومي'),
            ('room_number', '🏥 رقم الغرفة والطابق'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 6. مراجعة / عودة دورية - بدون رقم الغرفة
    # ===========================================
    elif action_clean == 'مراجعة / عودة دورية':
        return [
            ('complaint_text', '💬 شكوى المريض'),
            ('diagnosis', '🔬 التشخيص'),
            ('doctor_decision', '📝 قرار الطبيب'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 7. عملية - التركيز على تفاصيل العملية
    # ✅ لا يوجد قرار طبيب في هذا المسار
    # ===========================================
    elif action_clean == 'عملية':
        return [
            ('operation_details', '⚕️ تفاصيل العملية'),
            ('operation_name_en', '🔤 اسم العملية بالإنجليزي'),
            ('notes', '📝 ملاحظات'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 8. علاج طبيعي وإعادة تأهيل - التركيز على العلاج
    # ✅ لا يوجد قرار طبيب في هذا المسار
    # ===========================================
    elif action_clean == 'علاج طبيعي وإعادة تأهيل':
        return [
            ('therapy_details', '🏃 تفاصيل جلسة العلاج الطبيعي'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 9. ترقيد - التركيز على أسباب الرقود
    # ✅ لا يوجد قرار طبيب في هذا المسار
    # ===========================================
    elif action_clean == 'ترقيد':
        return [
            ('admission_reason', '🛏️ سبب الرقود'),
            ('room_number', '🏥 رقم الغرفة والطابق'),
            ('notes', '📝 ملاحظات'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 10. خروج من المستشفى - التركيز على الخروج
    # ✅ لا يوجد قرار طبيب في هذا المسار
    # ===========================================
    elif action_clean == 'خروج من المستشفى' or action_clean == 'خروج':
        return [
            ('admission_summary', '📋 ملخص الرقود'),
            ('operation_details', '⚕️ تفاصيل العملية'),
            ('operation_name_en', '🔤 اسم العملية بالإنجليزي'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 11. تأجيل موعد - التركيز على سبب التأجيل
    # ===========================================
    elif action_clean == 'تأجيل موعد':
        return [
            ('app_reschedule_reason', '📅 سبب تأجيل الموعد'),
            ('app_reschedule_return_date', '📅 موعد العودة الجديد'),
            ('app_reschedule_return_reason', '✍️ سبب العودة'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 12. أشعة وفحوصات - التركيز على الفحوصات
    # ===========================================
    elif action_clean == 'أشعة وفحوصات':
        return [
            ('radiology_type', '🔬 نوع الأشعة والفحوصات'),
            ('radiology_delivery_date', '📅 تاريخ التسليم'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 13. علاج طبيعي - التركيز على الجلسة
    # ✅ لا يوجد قرار طبيب في هذا المسار
    # ===========================================
    elif action_clean == 'علاج طبيعي':
        return [
            ('therapy_details', '🏃 تفاصيل الجلسة'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 14. أجهزة تعويضية - التركيز على الجهاز
    # ✅ لا يوجد قرار طبيب في هذا المسار
    # ===========================================
    elif action_clean == 'أجهزة تعويضية':
        return [
            ('device_details', '🦾 تفاصيل الجهاز'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 15. جلسة إشعاعي - التركيز على العلاج الإشعاعي
    # ===========================================
    elif action_clean == 'جلسة إشعاعي':
        return [
            ('radiation_therapy_type', '☢️ نوع الإشعاعي'),
            ('radiation_therapy_session_number', '🔢 رقم الجلسة'),
            ('radiation_therapy_remaining', '📊 الجلسات المتبقية'),
            ('radiation_therapy_recommendations', '📝 ملاحظات / توصيات'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # الحقول الافتراضية - للحالات غير المعروفة
    # ===========================================
    else:
        logger.warning(f"⚠️ نوع إجراء غير معروف: '{action_clean}' - استخدام الحقول الافتراضية")
        print(f"⚠️ نوع إجراء غير معروف: '{action_clean}' - استخدام الحقول الافتراضية")
        return [
            ('complaint_text', '💬 شكوى المريض'),
            ('doctor_decision', '📝 قرار الطبيب'),
            ('followup_date', '📅 موعد العودة'),
            ('translator_name', '👤 المترجم'),
        ]

async def start_edit_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بداية عملية تعديل التقارير"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        user = update.effective_user
        logger.info(f"🔧 start_edit_reports: بدء عملية تعديل التقارير للمستخدم {user.id}")
        
        # التحقق من أن المستخدم أدمن أولاً
        if is_admin(user.id):
            logger.info("ℹ️ المستخدم أدمن - توجيه إلى لوحة الأدمن")
            from bot.handlers.admin.admin_start import admin_start
            await admin_start(update, context)
            return ConversationHandler.END
        
        with SessionLocal() as s:
            # ✅ البحث عن تقارير اليوم المقدمة من هذا المستخدم (بغض النظر عن اسم المترجم)
            today = date.today()
            
            # ✅ إصلاح مشكلة التوقيت: توسيع النطاق ليشمل 24 ساعة الماضية + 12 ساعة قادمة
            # هذا يضمن ظهور التقارير حتى لو كان هناك فرق كبير في التوقيت
            now_utc = datetime.utcnow()
            today_start = now_utc - timedelta(hours=24)
            today_end = now_utc + timedelta(hours=12)
            
            logger.info(f"🔍 نطاق البحث (UTC - Expanded): من {today_start} إلى {today_end}")

            # ✅ البحث بمعرف المستخدم الذي أنشأ التقرير (submitted_by_user_id)
            # هذا الحقل يتم حفظه عند إنشاء التقرير بغض النظر عن اسم المترجم المختار
            # للتقارير القديمة: البحث عن translator_id الذي يطابق tg_user_id للمستخدم الحالي
            translator = s.query(Translator).filter_by(tg_user_id=user.id).first()
            translator_id = translator.id if translator else None
            
            logger.info(f"🔍 البحث عن تقارير للمستخدم (اليوم):")
            logger.info(f"   - Telegram user.id: {user.id}")
            logger.info(f"   - translator found: {translator.full_name if translator else 'None'}")
            logger.info(f"   - translator_id: {translator_id}")
            logger.info(f"   - today_start: {today_start}")
            logger.info(f"   - today_end: {today_end}")
            
            # ✅ البحث عن التقارير:
            # 1. submitted_by_user_id == user.id (للتقارير الجديدة - الأفضل)
            # 2. translator_id == translator_id AND submitted_by_user_id IS NULL (للتقارير القديمة فقط)
            try:
                if translator_id:
                    reports = s.query(Report).filter(
                        or_(
                            Report.submitted_by_user_id == user.id,  # التقارير الجديدة
                            and_(
                                Report.submitted_by_user_id.is_(None),  # التقارير القديمة فقط
                                Report.translator_id == translator_id  # المترجم يطابق المستخدم الحالي
                            )
                        ),
                        Report.report_date >= today_start,
                        Report.report_date <= today_end
                    ).order_by(Report.report_date.desc()).all()
                else:
                    # إذا لم يكن المستخدم مسجلاً كـ translator، نبحث فقط عن submitted_by_user_id
                    reports = s.query(Report).filter(
                        Report.submitted_by_user_id == user.id,
                        Report.report_date >= today_start,
                        Report.report_date <= today_end
                    ).order_by(Report.report_date.desc()).all()
                    
                logger.info(f"✅ تم العثور على {len(reports)} تقرير للمستخدم {user.id} (translator_id: {translator_id})")
                
                # طباعة تفاصيل التقارير المكتشفة
                for r in reports:
                    logger.info(f"   📄 Report #{r.id}: submitted_by={r.submitted_by_user_id}, translator_id={r.translator_id}")
            except Exception as e:
                # إذا فشل (مثلاً العمود غير موجود)، نستخدم translator_id فقط
                logger.warning(f"⚠️ Error using submitted_by_user_id, falling back to translator_id: {e}")
                if translator_id:
                    reports = s.query(Report).filter(
                        Report.translator_id == translator_id,
                        Report.report_date >= today_start,
                        Report.report_date <= today_end
                    ).order_by(Report.report_date.desc()).all()
                else:
                    reports = []

            if not reports:
                await update.message.reply_text(
                    "📋 **لا توجد تقارير لليوم**\n\n"
                    f"📅 **التاريخ:** {today.strftime('%Y-%m-%d')}\n\n"
                    "لم تقم بإضافة أي تقارير اليوم.\n"
                    "استخدم زر '📝 إضافة تقرير جديد' لإضافة تقرير.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return ConversationHandler.END

            # حفظ معرف المستخدم للتحقق لاحقاً
            context.user_data['submitted_by_user_id'] = user.id

            # إنشاء قائمة بالتقارير
            text = "✏️ **تعديل التقارير - اليوم**\n\n"
            text += f"📅 **{today.strftime('%Y-%m-%d')}** ({len(reports)} تقرير)\n\n"
            text += "اختر التقرير الذي تريد تعديله:\n\n"
            
            keyboard = []
            for report in reports:
                # جلب بيانات المريض
                patient = s.query(Patient).filter_by(id=report.patient_id).first()
                patient_name = patient.full_name if patient else "غير معروف"
                
                # تنسيق التاريخ
                date_str = report.report_date.strftime('%Y-%m-%d %H:%M')
                
                # نص الزر
                button_text = f"#{report.id} | {patient_name} | {date_str}"
                keyboard.append([
                    InlineKeyboardButton(
                        button_text, 
                        callback_data=f"edit_report:{report.id}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="edit_cancel")])
            
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"✅ تم عرض قائمة التقارير ({len(reports)} تقرير)")
            return SELECT_REPORT
            
    except Exception as e:
        logger.error(f"❌ خطأ في start_edit_reports: {e}", exc_info=True)
        try:
            await update.message.reply_text(
                "❌ **حدث خطأ أثناء تحميل التقارير**\n\n"
                "يرجى المحاولة مرة أخرى أو التواصل مع الإدارة.",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
        return ConversationHandler.END

async def handle_report_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار التقرير"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        query = update.callback_query
        await query.answer()
        
        logger.info(f"🔧 handle_report_selection: callback_data='{query.data}'")
        
        if query.data == "edit_cancel":
            await query.edit_message_text("❌ **تم إلغاء عملية التعديل**")
            return ConversationHandler.END
        
        # استخراج رقم التقرير
        report_id = int(query.data.split(':')[1])
        context.user_data['edit_report_id'] = report_id
        logger.info(f"✅ تم اختيار التقرير رقم {report_id}")
        
        with SessionLocal() as s:
            report = s.query(Report).filter_by(id=report_id).first()
            
            if not report:
                await query.edit_message_text("⚠️ **خطأ:** لم يتم العثور على التقرير")
                return ConversationHandler.END
            
            # ✅ التحقق من أن المستخدم هو من أنشأ التقرير
            # السماح بالتعديل إذا كان submitted_by_user_id مطابقاً أو None (للتقارير القديمة)
            current_user_id = context.user_data.get('submitted_by_user_id')
            report_user_id = getattr(report, 'submitted_by_user_id', None)
            if report_user_id is not None and report_user_id != current_user_id:
                await query.edit_message_text("⚠️ **خطأ:** لا يمكنك تعديل هذا التقرير")
                return ConversationHandler.END
            
            # جلب بيانات التقرير الكاملة
            patient = s.query(Patient).filter_by(id=report.patient_id).first()
            hospital = s.query(Hospital).filter_by(id=report.hospital_id).first()
            department = s.query(Department).filter_by(id=report.department_id).first() if report.department_id else None
            doctor = s.query(Doctor).filter_by(id=report.doctor_id).first() if report.doctor_id else None
            translator = s.query(Translator).filter_by(id=report.translator_id).first() if report.translator_id else None
            
            # ✅ استخدام اسم المترجم المحفوظ في التقرير أولاً، وإذا لم يكن موجوداً نجلبه من جدول Translator
            translator_name = report.translator_name
            if not translator_name and report.translator_id:
                translator = s.query(Translator).filter_by(id=report.translator_id).first()
                translator_name = translator.full_name if translator else "غير محدد"
            translator_name = translator_name or "غير محدد"
            
            # ✅ تحميل notes و medications - للتأكد من عرض القيمة الصحيحة
            # ✅ لحقل "استشارة جديدة": notes و medications يجب أن يكونا متطابقين (tests)
            notes_value = report.notes or "لا يوجد"
            medications_value = report.medications or "لا يوجد"
            if report.medical_action == 'استشارة جديدة':
                # ✅ إذا كان notes فارغاً و medications موجوداً، استخدم medications
                if (not notes_value or notes_value == "لا يوجد") and medications_value and medications_value != "لا يوجد":
                    notes_value = medications_value
                # ✅ إذا كان medications فارغاً و notes موجوداً، استخدم notes (للتطابق بعد التعديل)
                elif (not medications_value or medications_value == "لا يوجد") and notes_value and notes_value != "لا يوجد":
                    medications_value = notes_value
            
            # حفظ البيانات الحالية
            # ✅ استخراج الحقول المحددة من doctor_decision حسب نوع الإجراء
            doctor_decision_text = report.doctor_decision or ""
            extracted_operation_details = "لا يوجد"
            extracted_operation_name_en = "لا يوجد"
            extracted_notes = notes_value
            extracted_therapy_details = "لا يوجد"
            extracted_device_details = "لا يوجد"
            extracted_admission_reason = "لا يوجد"
            extracted_admission_summary = "لا يوجد"
            # ✅ حقول استشارة مع قرار عملية
            extracted_decision = "لا يوجد"
            extracted_success_rate = "لا يوجد"
            extracted_benefit_rate = "لا يوجد"
            extracted_tests = "لا يوجد"

            medical_action_for_extraction = report.medical_action or ""

            # ✅ استخراج حقول مسار العملية
            if medical_action_for_extraction == 'عملية':
                if 'تفاصيل العملية:' in doctor_decision_text:
                    try:
                        parts = doctor_decision_text.split('تفاصيل العملية:', 1)
                        if len(parts) > 1:
                            rest = parts[1]
                            if 'اسم العملية بالإنجليزي:' in rest:
                                extracted_operation_details = rest.split('اسم العملية بالإنجليزي:')[0].strip()
                                rest2 = rest.split('اسم العملية بالإنجليزي:', 1)[1]
                                if 'ملاحظات:' in rest2:
                                    extracted_operation_name_en = rest2.split('ملاحظات:')[0].strip()
                                    extracted_notes = rest2.split('ملاحظات:', 1)[1].strip()
                                else:
                                    extracted_operation_name_en = rest2.strip()
                            else:
                                extracted_operation_details = rest.strip()
                    except Exception as e:
                        logger.warning(f"⚠️ فشل استخراج حقول العملية: {e}")
                elif doctor_decision_text and doctor_decision_text != "لا يوجد":
                    # ✅ إذا لم يكن هناك تنسيق، استخدم doctor_decision كـ operation_details
                    extracted_operation_details = doctor_decision_text

            # ✅ استخراج حقول مسار خروج من المستشفى
            elif medical_action_for_extraction in ['خروج من المستشفى', 'خروج']:
                if 'ملخص الرقود:' in doctor_decision_text:
                    try:
                        parts = doctor_decision_text.split('ملخص الرقود:', 1)
                        if len(parts) > 1:
                            rest = parts[1]
                            if 'تفاصيل العملية:' in rest:
                                extracted_admission_summary = rest.split('تفاصيل العملية:')[0].strip()
                                rest2 = rest.split('تفاصيل العملية:', 1)[1]
                                if 'اسم العملية بالإنجليزي:' in rest2:
                                    extracted_operation_details = rest2.split('اسم العملية بالإنجليزي:')[0].strip()
                                    extracted_operation_name_en = rest2.split('اسم العملية بالإنجليزي:', 1)[1].strip()
                                else:
                                    extracted_operation_details = rest2.strip()
                            else:
                                extracted_admission_summary = rest.strip()
                    except Exception as e:
                        logger.warning(f"⚠️ فشل استخراج حقول الخروج: {e}")

            # ✅ استخراج حقول مسار علاج طبيعي
            elif medical_action_for_extraction in ['علاج طبيعي', 'علاج طبيعي وإعادة تأهيل']:
                if 'تفاصيل جلسة العلاج الطبيعي:' in doctor_decision_text:
                    try:
                        extracted_therapy_details = doctor_decision_text.split('تفاصيل جلسة العلاج الطبيعي:', 1)[1].strip()
                    except:
                        pass
                elif 'تفاصيل الجلسة:' in doctor_decision_text:
                    try:
                        extracted_therapy_details = doctor_decision_text.split('تفاصيل الجلسة:', 1)[1].strip()
                    except:
                        pass
                elif doctor_decision_text and doctor_decision_text != "لا يوجد":
                    extracted_therapy_details = doctor_decision_text

            # ✅ استخراج حقول مسار أجهزة تعويضية
            elif medical_action_for_extraction == 'أجهزة تعويضية':
                if 'تفاصيل الجهاز:' in doctor_decision_text:
                    try:
                        extracted_device_details = doctor_decision_text.split('تفاصيل الجهاز:', 1)[1].strip()
                    except:
                        pass
                elif doctor_decision_text and doctor_decision_text != "لا يوجد":
                    extracted_device_details = doctor_decision_text

            # ✅ استخراج حقول مسار ترقيد
            elif medical_action_for_extraction == 'ترقيد':
                if 'سبب الرقود:' in doctor_decision_text:
                    try:
                        parts = doctor_decision_text.split('سبب الرقود:', 1)
                        if len(parts) > 1:
                            rest = parts[1]
                            if 'ملاحظات:' in rest:
                                extracted_admission_reason = rest.split('ملاحظات:')[0].strip()
                                extracted_notes = rest.split('ملاحظات:', 1)[1].strip()
                            else:
                                extracted_admission_reason = rest.strip()
                    except:
                        pass
                elif doctor_decision_text and doctor_decision_text != "لا يوجد":
                    extracted_admission_reason = doctor_decision_text

            # ✅ أيضاً استخدام complaint_text كـ fallback لـ admission_reason
            if extracted_admission_reason == "لا يوجد" and medical_action_for_extraction == 'ترقيد':
                if report.complaint_text and report.complaint_text != "لا يوجد":
                    extracted_admission_reason = report.complaint_text

            # ✅ استخراج حقول مسار استشارة مع قرار عملية
            elif medical_action_for_extraction == 'استشارة مع قرار عملية':
                try:
                    sections = doctor_decision_text.split('\n\n')
                    for section in sections:
                        section = section.strip()
                        if section.startswith('قرار الطبيب:'):
                            extracted_decision = section.replace('قرار الطبيب:', '', 1).strip()
                        elif section.startswith('اسم العملية بالإنجليزي:'):
                            extracted_operation_name_en = section.replace('اسم العملية بالإنجليزي:', '', 1).strip()
                        elif section.startswith('نسبة نجاح العملية:'):
                            extracted_success_rate = section.replace('نسبة نجاح العملية:', '', 1).strip()
                        elif section.startswith('نسبة الاستفادة من العملية:'):
                            extracted_benefit_rate = section.replace('نسبة الاستفادة من العملية:', '', 1).strip()
                        elif section.startswith('الفحوصات المطلوبة:'):
                            extracted_tests = section.replace('الفحوصات المطلوبة:', '', 1).strip()
                except Exception as e:
                    logger.warning(f"⚠️ فشل استخراج حقول استشارة مع قرار عملية: {e}")

            logger.info(f"✅ [EDIT] استخراج الحقول - medical_action: {medical_action_for_extraction}")
            logger.info(f"✅ [EDIT] operation_details: {extracted_operation_details[:50] if extracted_operation_details else 'None'}...")
            logger.info(f"✅ [EDIT] therapy_details: {extracted_therapy_details[:50] if extracted_therapy_details else 'None'}...")

            context.user_data['current_report_data'] = {
                'patient_name': patient.full_name if patient else "غير معروف",
                'hospital_name': hospital.name if hospital else "غير معروف",
                'department_name': department.name if department else "غير محدد",
                'doctor_name': doctor.full_name if doctor else "لم يتم التحديد",
                'medical_action': report.medical_action or "غير محدد",
                'complaint_text': report.complaint_text or "لا يوجد",
                'doctor_decision': report.doctor_decision or "لا يوجد",
                'diagnosis': report.diagnosis or "لا يوجد",
                'treatment_plan': report.treatment_plan or "لا يوجد",
                'medications': medications_value,  # ✅ استخدام القيمة المحسّنة
                'notes': extracted_notes,  # ✅ استخدام القيمة المستخرجة
                'case_status': report.case_status or "لا يوجد",
                'followup_date': report.followup_date.strftime('%Y-%m-%d') if report.followup_date else None,
                'followup_time': report.followup_time,
                'followup_reason': report.followup_reason or "لا يوجد",
                'report_date': report.report_date.strftime('%Y-%m-%d %H:%M'),
                'translator_name': translator_name,  # ✅ استخدام الاسم المحفوظ في التقرير
                'translator_id': report.translator_id,
                # حقول إضافية
                'room_number': getattr(report, 'room_number', None) or "لا يوجد",
                'radiology_type': getattr(report, 'radiology_type', None) or "لا يوجد",
                'radiology_delivery_date': getattr(report, 'radiology_delivery_date', None),
                'app_reschedule_reason': getattr(report, 'app_reschedule_reason', None) or "لا يوجد",
                'app_reschedule_return_date': getattr(report, 'app_reschedule_return_date', None),
                'app_reschedule_return_reason': getattr(report, 'app_reschedule_return_reason', None) or "لا يوجد",
                # ✅ حقول مستخرجة من doctor_decision
                'operation_details': extracted_operation_details,
                'operation_name_en': extracted_operation_name_en,
                'therapy_details': extracted_therapy_details,
                'device_details': extracted_device_details,
                'admission_reason': extracted_admission_reason,
                'admission_summary': extracted_admission_summary,
                # ✅ حقول استشارة مع قرار عملية (مستخرجة من doctor_decision)
                'decision': extracted_decision,
                'success_rate': extracted_success_rate,
                'benefit_rate': extracted_benefit_rate,
                'tests': extracted_tests,
                # ✅ حقول العلاج الإشعاعي
                'radiation_therapy_type': getattr(report, 'radiation_therapy_type', None) or "لا يوجد",
                'radiation_therapy_session_number': getattr(report, 'radiation_therapy_session_number', None) or "لا يوجد",
                'radiation_therapy_remaining': getattr(report, 'radiation_therapy_remaining', None) or "لا يوجد",
                'radiation_therapy_recommendations': getattr(report, 'radiation_therapy_recommendations', None) or getattr(report, 'notes', None) or "",
                'radiation_therapy_return_reason': getattr(report, 'radiation_therapy_return_reason', None) or "لا يوجد",
                'radiation_therapy_final_notes': getattr(report, 'radiation_therapy_final_notes', None) or "",
                'radiation_therapy_completed': getattr(report, 'radiation_therapy_completed', False) or False,
            }
            
            # تحويل موعد العودة إلى صيغة 12 ساعة للعرض
            followup_display = "لا يوجد"
            if context.user_data['current_report_data']['followup_date']:
                date_part = context.user_data['current_report_data']['followup_date']
                followup_time = context.user_data['current_report_data']['followup_time']
                
                if followup_time:
                    try:
                        # تحويل الوقت من صيغة 24 ساعة (HH:MM) إلى صيغة 12 ساعة
                        hour, minute = followup_time.split(':')
                        hour_int = int(hour)
                        if hour_int == 0:
                            time_display = f"12:{minute} صباحاً"
                        elif hour_int < 12:
                            time_display = f"{hour_int}:{minute} صباحاً"
                        elif hour_int == 12:
                            time_display = f"12:{minute} ظهراً"
                        else:
                            time_display = f"{hour_int-12}:{minute} مساءً"
                        followup_display = f"{date_part} - {time_display}"
                    except:
                        followup_display = f"{date_part} - {followup_time}"
                else:
                    followup_display = date_part
            
            # عرض بيانات التقرير
            medical_action = context.user_data['current_report_data']['medical_action']
            
            text = f"📋 **بيانات التقرير #{report_id}**\n\n"
            text += f"📅 **تاريخ التقرير:** {context.user_data['current_report_data']['report_date']}\n"
            text += f"👤 **اسم المريض:** {context.user_data['current_report_data']['patient_name']}\n"
            text += f"🏥 **المستشفى:** {context.user_data['current_report_data']['hospital_name']}\n"
            text += f"🏷️ **القسم:** {context.user_data['current_report_data']['department_name']}\n"
            text += f"👨‍⚕️ **الطبيب:** {context.user_data['current_report_data']['doctor_name']}\n"
            text += f"⚕️ **نوع الإجراء:** {medical_action}\n\n"
            
            # ✅ بناء الأزرار - عرض فقط الحقول التي لها قيمة فعلية
            keyboard = []
            all_fields = get_editable_fields_by_action_type(medical_action)
            logger.info(f"🔍 [EDIT_DEBUG] medical_action: '{medical_action}'")
            logger.info(f"🔍 [EDIT_DEBUG] fields found: {[f[0] for f in all_fields]}")
            
            fields_with_values = []
            for field_name, field_display in all_fields:
                # ✅ التحقق من وجود قيمة فعلية للحقل
                if _has_field_value_in_report(report, context.user_data['current_report_data'], field_name):
                    fields_with_values.append((field_name, field_display))
                    logger.info(f"✅ [EDIT_AFTER_PUBLISH] إضافة حقل '{field_name}' للقائمة (له قيمة)")
                else:
                    logger.info(f"⏭️ [EDIT_AFTER_PUBLISH] تخطي حقل '{field_name}' (لا توجد قيمة)")
            
            # ✅ التحقق من وجود حقول مدخلة
            if not fields_with_values:
                await query.edit_message_text(
                    "⚠️ **لا توجد حقول مدخلة للتعديل**\n\n"
                    f"📋 **رقم التقرير:** #{report_id}\n"
                    f"⚕️ **نوع الإجراء:** {medical_action}\n\n"
                    "لم يتم إدخال أي بيانات في هذا التقرير.\n"
                    "يرجى استخدام زر '🔙 رجوع' للرجوع إلى قائمة التقارير.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return SELECT_REPORT
            
            text += "اختر الحقل الذي تريد تعديله:\n"
            
            # ✅ عرض فقط الحقول التي لها قيمة
            for field_name, field_display in fields_with_values:
                current_value = context.user_data['current_report_data'].get(field_name, "")
                
                # ✅ تنسيق القيمة للعرض
                if isinstance(current_value, date):
                    display_value = current_value.strftime('%Y-%m-%d')
                elif isinstance(current_value, datetime):
                    display_value = current_value.strftime('%Y-%m-%d')
                elif current_value and len(str(current_value)) > 15:
                    display_value = str(current_value)[:12] + "..."
                else:
                    display_value = str(current_value) if current_value else ""
                
                button_text = f"{field_display}: {display_value}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"edit_field:{field_name}")])
            
            # إضافة زر إعادة النشر
            keyboard.append([InlineKeyboardButton("📢 إعادة نشر التقرير", callback_data="edit_republish")])
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="edit_back")])
            keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="edit_cancel")])
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"✅ تم عرض بيانات التقرير #{report_id}")
            return SELECT_FIELD
            
    except Exception as e:
        logger.error(f"❌ خطأ في handle_report_selection: {e}", exc_info=True)
        try:
            await query.edit_message_text(
                "❌ **حدث خطأ أثناء تحميل التقرير**\n\n"
                "يرجى المحاولة مرة أخرى.",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
        return ConversationHandler.END

async def handle_republish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إعادة نشر التقرير بعد التعديل"""
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    await query.answer()
    
    try:
        report_id = context.user_data.get('edit_report_id')
        
        with SessionLocal() as s:
            report = s.query(Report).filter_by(id=report_id).first()
            
            if not report:
                await query.edit_message_text("⚠️ **خطأ:** لم يتم العثور على التقرير")
                return ConversationHandler.END
            
            # جلب البيانات الكاملة
            patient = s.query(Patient).filter_by(id=report.patient_id).first()
            hospital = s.query(Hospital).filter_by(id=report.hospital_id).first()
            department = s.query(Department).filter_by(id=report.department_id).first() if report.department_id else None
            doctor = s.query(Doctor).filter_by(id=report.doctor_id).first() if report.doctor_id else None
            
            # ✅ استخدام اسم المترجم المحفوظ في التقرير، وإذا لم يكن موجوداً نجلبه من جدول Translator
            translator_name = report.translator_name
            if not translator_name and report.translator_id:
                translator = s.query(Translator).filter_by(id=report.translator_id).first()
                translator_name = translator.full_name if translator else 'غير محدد'
            translator_name = translator_name or 'غير محدد'
            
            # تجهيز بيانات البث - جميع الحقول
            followup_display = 'لا يوجد'
            if report.followup_date:
                followup_display = report.followup_date.strftime('%Y-%m-%d')
                if report.followup_time:
                    time_12h = format_time_12h(report.followup_time)
                    followup_display += f" - {time_12h}"
            
            # ✅ استخراج tests من medications أو notes إذا كان medical_action = "استشارة جديدة"
            # ✅ أو من doctor_decision إذا كان يحتوي على "الفحوصات المطلوبة"
            tests_value = ''
            if report.medical_action == 'استشارة جديدة':
                # ✅ محاولة استخراج من medications أولاً (حيث يتم حفظ tests لـ new_consult عند الإنشاء)
                if report.medications and str(report.medications).strip():
                    tests_value = str(report.medications).strip()
                # ✅ محاولة استخراج من notes (حيث يتم حفظ tests عند التعديل بعد النشر)
                elif report.notes and str(report.notes).strip():
                    tests_value = str(report.notes).strip()
                # ✅ محاولة استخراج من doctor_decision إذا لم يكن موجوداً في medications أو notes
                elif report.doctor_decision and 'الفحوصات المطلوبة:' in str(report.doctor_decision):
                    try:
                        parts = str(report.doctor_decision).split('الفحوصات المطلوبة:', 1)
                        if len(parts) > 1:
                            tests_value = parts[1].strip()
                    except:
                        pass
                logger.info(f"✅ استخراج tests لتقرير 'استشارة جديدة' #{report_id}: tests_value='{tests_value[:50] if tests_value else 'فارغ'}...'")
            elif report.medical_action == 'استشارة مع قرار عملية':
                # محاولة استخراج من doctor_decision
                if report.doctor_decision and 'الفحوصات المطلوبة:' in str(report.doctor_decision):
                    try:
                        parts = str(report.doctor_decision).split('الفحوصات المطلوبة:', 1)
                        if len(parts) > 1:
                            tests_value = parts[1].strip()
                    except:
                        pass

            # ✅ استخراج الحقول الخاصة من doctor_decision بناءً على نوع الإجراء
            operation_details = ''
            operation_name_en = ''
            therapy_details = ''
            device_details = ''
            admission_reason = ''
            admission_summary = ''
            success_rate = ''
            benefit_rate = ''
            extracted_notes = report.notes or ''

            doctor_decision_text = report.doctor_decision or ''

            if report.medical_action == 'عملية':
                # استخراج تفاصيل العملية واسم العملية والملاحظات
                if 'تفاصيل العملية:' in doctor_decision_text:
                    try:
                        parts = doctor_decision_text.split('تفاصيل العملية:', 1)
                        if len(parts) > 1:
                            rest = parts[1]
                            if 'اسم العملية بالإنجليزي:' in rest:
                                operation_details = rest.split('اسم العملية بالإنجليزي:')[0].strip()
                                rest2 = rest.split('اسم العملية بالإنجليزي:', 1)[1]
                                if 'ملاحظات:' in rest2:
                                    operation_name_en = rest2.split('ملاحظات:')[0].strip()
                                    extracted_notes = rest2.split('ملاحظات:', 1)[1].strip()
                                else:
                                    operation_name_en = rest2.strip()
                            else:
                                operation_details = rest.strip()
                    except:
                        pass

            elif report.medical_action in ['علاج طبيعي', 'علاج طبيعي وإعادة تأهيل']:
                # استخراج تفاصيل الجلسة - يدعم عدة صيغ
                if 'تفاصيل جلسة العلاج الطبيعي:' in doctor_decision_text:
                    try:
                        therapy_details = doctor_decision_text.split('تفاصيل جلسة العلاج الطبيعي:', 1)[1].strip()
                    except:
                        pass
                elif 'تفاصيل الجلسة:' in doctor_decision_text:
                    try:
                        therapy_details = doctor_decision_text.split('تفاصيل الجلسة:', 1)[1].strip()
                    except:
                        pass
                elif doctor_decision_text and doctor_decision_text.strip():
                    # إذا لم يكن هناك تنسيق، استخدم القيمة كاملة
                    therapy_details = doctor_decision_text.strip()

            elif report.medical_action == 'أجهزة تعويضية':
                # استخراج تفاصيل الجهاز
                if 'تفاصيل الجهاز:' in doctor_decision_text:
                    try:
                        device_details = doctor_decision_text.split('تفاصيل الجهاز:', 1)[1].strip()
                    except:
                        pass

            elif report.medical_action == 'ترقيد':
                # استخراج سبب الرقود
                if 'سبب الرقود:' in doctor_decision_text:
                    try:
                        parts = doctor_decision_text.split('سبب الرقود:', 1)
                        if len(parts) > 1:
                            rest = parts[1]
                            if 'رقم الغرفة:' in rest:
                                admission_reason = rest.split('رقم الغرفة:')[0].strip()
                            elif 'ملاحظات:' in rest:
                                admission_reason = rest.split('ملاحظات:')[0].strip()
                            else:
                                admission_reason = rest.strip()
                    except:
                        pass

            elif report.medical_action == 'خروج من المستشفى':
                # استخراج ملخص الرقود أو تفاصيل العملية
                if 'ملخص الرقود:' in doctor_decision_text:
                    try:
                        admission_summary = doctor_decision_text.split('ملخص الرقود:', 1)[1].strip()
                    except:
                        pass
                elif 'تفاصيل العملية:' in doctor_decision_text:
                    try:
                        parts = doctor_decision_text.split('تفاصيل العملية:', 1)
                        if len(parts) > 1:
                            rest = parts[1]
                            if 'اسم العملية بالإنجليزي:' in rest:
                                operation_details = rest.split('اسم العملية بالإنجليزي:')[0].strip()
                                operation_name_en = rest.split('اسم العملية بالإنجليزي:', 1)[1].strip()
                            else:
                                operation_details = rest.strip()
                    except:
                        pass

            # ✅ استخراج حقول استشارة مع قرار عملية
            elif report.medical_action == 'استشارة مع قرار عملية':
                success_rate = ''
                benefit_rate = ''
                try:
                    sections = doctor_decision_text.split('\n\n')
                    for section in sections:
                        section = section.strip()
                        if section.startswith('اسم العملية بالإنجليزي:'):
                            operation_name_en = section.replace('اسم العملية بالإنجليزي:', '', 1).strip()
                        elif section.startswith('نسبة نجاح العملية:'):
                            success_rate = section.replace('نسبة نجاح العملية:', '', 1).strip()
                        elif section.startswith('نسبة الاستفادة من العملية:'):
                            benefit_rate = section.replace('نسبة الاستفادة من العملية:', '', 1).strip()
                except Exception as e:
                    logger.warning(f"⚠️ فشل استخراج حقول استشارة مع قرار عملية (republish): {e}")

            # ✅ المسارات التي تحفظ البيانات مباشرة في الحقول (لا تحتاج استخراج)
            # - استشارة جديدة (new_consult): complaint_text, diagnosis, decision
            # - متابعة (followup): complaint_text, diagnosis, decision
            # - طوارئ (emergency): complaint_text, diagnosis, decision, case_status
            # - استشارة مع قرار عملية (surgery_consult): diagnosis, decision (في doctor_decision)
            # - استشارة أخيرة (final_consult): diagnosis, decision, recommendations
            # - تأجيل موعد (appointment_reschedule): app_reschedule_reason (حقل مباشر)
            # - أشعة وفحوصات (radiology): radiology_type, radiology_delivery_date (حقول مباشرة)

            # ✅ بناء broadcast_data مع جميع الحقول المطلوبة
            broadcast_data = {
                'report_id': report_id,
                'report_date': report.report_date.strftime('%Y-%m-%d %H:%M') if report.report_date else datetime.now().strftime('%Y-%m-%d %H:%M'),
                'patient_name': patient.full_name if patient else 'غير معروف',
                'hospital_name': hospital.name if hospital else 'غير معروف',
                'department_name': department.name if department else 'غير محدد',
                'doctor_name': doctor.full_name if doctor else 'لم يتم التحديد',
                'medical_action': report.medical_action or 'غير محدد',
                # ✅ جميع الحقول النصية (فقط القيم غير الفارغة)
                'complaint_text': report.complaint_text or '',
                'complaint': report.complaint_text or '',  # نسخة للتوافق
                'diagnosis': report.diagnosis or '',
                'doctor_decision': report.doctor_decision or '',
                'decision': '',  # ✅ يتم استخراجه تلقائياً من doctor_decision في broadcast_service لمنع التكرار
                'treatment_plan': report.treatment_plan or '',
                'recommendations': report.treatment_plan or '',  # ✅ نسخة للتوافق مع broadcast_service
                'notes': report.notes or '',
                'medications': report.medications or '',
                'case_status': report.case_status or '',
                # ✅ موعد العودة
                'followup_date': followup_display if followup_display and followup_display != 'لا يوجد' else '',
                'followup_time': report.followup_time or '',
                'followup_reason': report.followup_reason or '',
                # ✅ حقول خاصة - استخدام القيم المستخرجة من doctor_decision
                'room_number': getattr(report, 'room_number', '') or '',
                'operation_name_en': operation_name_en or getattr(report, 'operation_name_en', '') or '',
                'operation_details': operation_details or getattr(report, 'operation_details', '') or '',
                'success_rate': (success_rate if report.medical_action == 'استشارة مع قرار عملية' else '') or getattr(report, 'success_rate', '') or '',
                'benefit_rate': (benefit_rate if report.medical_action == 'استشارة مع قرار عملية' else '') or getattr(report, 'benefit_rate', '') or '',
                # ✅ حقول الفحوصات (مهمة لاستشارة جديدة)
                'tests': tests_value,
                # ✅ حقول تأجيل الموعد
                'app_reschedule_reason': getattr(report, 'app_reschedule_reason', '') or '',
                'app_reschedule_return_date': getattr(report, 'app_reschedule_return_date', '') or '',
                'app_reschedule_return_reason': getattr(report, 'app_reschedule_return_reason', '') or '',
                # ✅ حقول الأشعة
                'radiology_type': getattr(report, 'radiology_type', '') or '',
                'radiology_delivery_date': getattr(report, 'radiology_delivery_date', '') or '',
                # ✅ حقول العلاج الطبيعي - استخدام القيمة المستخرجة
                'therapy_details': therapy_details or getattr(report, 'therapy_details', '') or '',
                # ✅ حقول الأجهزة التعويضية - استخدام القيمة المستخرجة
                'device_details': device_details or getattr(report, 'device_details', '') or '',
                # ✅ حقول الخروج - استخدام القيم المستخرجة
                'discharge_type': getattr(report, 'discharge_type', '') or '',
                'admission_summary': admission_summary or getattr(report, 'admission_summary', '') or '',
                # ✅ حقول الترقيد - استخدام القيمة المستخرجة
                'admission_reason': admission_reason or getattr(report, 'admission_reason', '') or '',
                # ✅ حقول العلاج الإشعاعي
                'radiation_therapy_type': getattr(report, 'radiation_therapy_type', '') or '',
                'radiation_therapy_session_number': getattr(report, 'radiation_therapy_session_number', '') or '',
                'radiation_therapy_remaining': getattr(report, 'radiation_therapy_remaining', '') or '',
                'radiation_therapy_recommendations': getattr(report, 'radiation_therapy_recommendations', '') or getattr(report, 'notes', '') or '',
                'radiation_therapy_return_date': getattr(report, 'radiation_therapy_return_date', '') or '',
                'radiation_therapy_return_reason': getattr(report, 'radiation_therapy_return_reason', '') or '',
                'radiation_therapy_final_notes': getattr(report, 'radiation_therapy_final_notes', '') or '',
                'radiation_therapy_completed': getattr(report, 'radiation_therapy_completed', False) or False,
                # ✅ المترجم - استخدام الاسم المحفوظ في التقرير
                'translator_name': translator_name,
                'is_edit': True  # علامة أن هذا تقرير معدل
            }
            
            # بث التقرير
            try:
                from services.broadcast_service import broadcast_new_report, format_report_message
                await broadcast_new_report(context.bot, broadcast_data)
                
                # ✅ عرض التقرير الكامل للمستخدم بعد التعديل
                try:
                    full_report = format_report_message(broadcast_data)
                    success_header = (
                        f"✅ **تم إعادة نشر التقرير بنجاح!**\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    )
                    full_message = success_header + full_report
                    
                    await query.edit_message_text(
                        full_message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as format_err:
                    logger.warning(f"⚠️ فشل عرض التقرير الكامل: {format_err}")
                    # fallback to simple message
                    await query.edit_message_text(
                        f"✅ **تم إعادة نشر التقرير بنجاح!**\n\n"
                        f"📋 **رقم التقرير:** #{report_id}\n"
                        f"👤 **المريض:** {patient.full_name if patient else 'غير معروف'}\n"
                        f"📅 **وقت النشر:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                        f"تم إرسال التقرير المعدل.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                
                logger.info(f"✅ تم إعادة نشر التقرير #{report_id}")
                
            except Exception as e:
                logger.error(f"❌ خطأ في إعادة النشر: {e}", exc_info=True)
                await query.edit_message_text(
                    f"❌ **حدث خطأ في إعادة النشر**\n\n"
                    f"يرجى المحاولة مرة أخرى.",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        # تنظيف البيانات
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"❌ خطأ في handle_republish: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ **حدث خطأ**\n\nيرجى المحاولة مرة أخرى.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

async def handle_field_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار الحقل المراد تعديله"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        query = update.callback_query
        await query.answer()
        
        logger.info(f"🔧 handle_field_selection: callback_data='{query.data}'")
        
        if query.data == "edit_cancel":
            await query.edit_message_text("❌ **تم إلغاء عملية التعديل**")
            return ConversationHandler.END
        
        if query.data == "edit_back":
            return await start_edit_reports_from_callback(query, context)
        
        if query.data == "edit_republish":
            return await handle_republish(update, context)
        
        # استخراج اسم الحقل
        field_name = query.data.split(':')[1]
        context.user_data['edit_field'] = field_name
        
        # أسماء الحقول بالعربي
        field_names = {
            'complaint_text': 'شكوى المريض',
            'doctor_decision': 'قرار الطبيب',
            'diagnosis': 'التشخيص الطبي',
            'treatment_plan': 'التوصيات / خطة العلاج',
            'medications': 'الأدوية / الفحوصات',
            'notes': 'الملاحظات / الفحوصات',
            'case_status': 'حالة الطوارئ',
            'followup_date': 'موعد العودة',
            'followup_reason': 'سبب العودة',
            'translator_name': 'المترجم',
            'room_number': 'رقم الغرفة والطابق',
            'radiology_type': 'نوع الأشعة والفحوصات',
            'radiology_delivery_date': 'تاريخ التسليم',
            'app_reschedule_reason': 'سبب تأجيل الموعد',
            'app_reschedule_return_date': 'موعد العودة الجديد',
            'app_reschedule_return_reason': 'سبب العودة',
            # ✅ حقول المسارات الخاصة
            'operation_details': 'تفاصيل العملية',
            'operation_name_en': 'اسم العملية بالإنجليزي',
            'therapy_details': 'تفاصيل جلسة العلاج الطبيعي',
            'device_details': 'تفاصيل الجهاز',
            'admission_reason': 'سبب الرقود',
            'admission_summary': 'ملخص الرقود',
            # ✅ حقول استشارة مع قرار عملية
            'decision': 'قرار الطبيب',
            'success_rate': 'نسبة نجاح العملية',
            'benefit_rate': 'نسبة الاستفادة',
            'tests': 'الفحوصات والأشعة',
            # ✅ حقول العلاج الإشعاعي
            'radiation_therapy_type': 'نوع الإشعاعي',
            'radiation_therapy_session_number': 'رقم الجلسة',
            'radiation_therapy_remaining': 'الجلسات المتبقية',
            'radiation_therapy_recommendations': 'ملاحظات / توصيات',
        }
        
        field_display = field_names.get(field_name, field_name)
        current_value = context.user_data['current_report_data'].get(field_name, "لا يوجد")
        
        # إذا كان الحقل هو المترجم، نعرض قائمة المترجمين
        if field_name == "translator_name":
            return await show_translator_selection_for_edit(query, context)
        
        # إذا كان الحقل هو التاريخ، نعرض التقويم الكامل مباشرة
        if field_name == "followup_date":
            text = f"📅 **تعديل {field_display}**\n\n"
            if current_value and current_value != "لا يوجد":
                followup_time = context.user_data['current_report_data'].get('followup_time', '')
                if followup_time:
                    time_12h = format_time_12h(followup_time)
                    text += f"**القيمة الحالية:** {current_value} - {time_12h}\n\n"
                else:
                    text += f"**القيمة الحالية:** {current_value}\n\n"
            else:
                text += "**القيمة الحالية:** لا يوجد موعد\n\n"
            text += "✅ **اختر التاريخ من التقويم أدناه:**\n"
            text += "_(لا يمكن إدخال التاريخ يدوياً)_\n"
            
            # عرض التقويم الكامل مباشرة
            now = datetime.now()
            keyboard = create_calendar_keyboard(now.year, now.month, "edit_followup", allow_future=True)
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="edit_back_to_fields")])
            keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="edit_cancel")])
            
            text += f"\n📆 **{MONTHS_AR[now.month]} {now.year}**"
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"✅ تم عرض حقل التعديل: {field_name} (تاريخ) - التقويم الكامل")
            return EDIT_DATE_CALENDAR
        else:
            text = f"✏️ **تعديل: {field_display}**\n\n"
            text += f"**القيمة الحالية:**\n```\n{current_value}\n```\n\n"
            text += f"📝 **أرسل القيمة الجديدة لـ ({field_display}):**"
            
            keyboard = [
                [InlineKeyboardButton("🔙 رجوع", callback_data="edit_back_to_fields")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="edit_cancel")]
            ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"✅ تم عرض حقل التعديل: {field_name}")
            return EDIT_VALUE
            
    except Exception as e:
        logger.error(f"❌ خطأ في handle_field_selection: {e}", exc_info=True)
        try:
            await query.edit_message_text(
                "❌ **حدث خطأ أثناء تحميل الحقل**\n\n"
                "يرجى المحاولة مرة أخرى.",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
        return ConversationHandler.END


def load_translator_names():
    """قراءة أسماء المترجمين"""
    try:
        from services.translators_service import get_all_translator_names
        names = get_all_translator_names()
        if names:
            return names
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"⚠️ فشل تحميل المترجمين: {e}")
    
    # قائمة احتياطية في حالة فشل التحميل - بنفس الترتيب المطلوب
    return ["معتز", "ادم", "هاشم", "مصطفى", "حسن", "نجم الدين", "محمد علي",
            "صبري", "عزي", "سعيد", "عصام", "زيد", "مهدي", "ادريس",
            "واصل", "عزالدين", "عبدالسلام", "يحيى", "ياسر"]


async def show_translator_selection_for_edit(query, context):
    """عرض قائمة المترجمين للتعديل"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        translator_names = load_translator_names()
        current_translator = context.user_data['current_report_data'].get('translator_name', 'غير محدد')
        
        text = f"👤 **تعديل المترجم**\n\n"
        text += f"**المترجم الحالي:** {current_translator}\n\n"
        text += "اختر المترجم الجديد من القائمة:"
        
        # تقسيم الأسماء إلى صفوف (3 أسماء لكل صف)
        keyboard = []
        row = []
        
        for i, name in enumerate(translator_names):
            row.append(InlineKeyboardButton(name, callback_data=f"edit_translator:{i}"))
            if len(row) == 3 or i == len(translator_names) - 1:
                keyboard.append(row)
                row = []
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="edit_back_to_fields")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="edit_cancel")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info(f"✅ تم عرض قائمة المترجمين للتعديل")
        return EDIT_TRANSLATOR
        
    except Exception as e:
        logger.error(f"❌ خطأ في show_translator_selection_for_edit: {e}", exc_info=True)
        await query.edit_message_text("❌ حدث خطأ أثناء تحميل قائمة المترجمين")
        return ConversationHandler.END


async def handle_translator_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار المترجم الجديد"""
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "edit_cancel":
            await query.edit_message_text("❌ **تم إلغاء عملية التعديل**")
            return ConversationHandler.END
        
        if query.data == "edit_back_to_fields":
            return await show_field_selection(query, context)
        
        # استخراج index المترجم
        parts = query.data.split(":")
        if len(parts) < 2:
            await query.edit_message_text("❌ خطأ في البيانات")
            return ConversationHandler.END
        
        translator_index = int(parts[1])
        translator_names = load_translator_names()
        
        if translator_index < 0 or translator_index >= len(translator_names):
            await query.edit_message_text("❌ اختيار غير صحيح")
            return ConversationHandler.END
        
        new_translator_name = translator_names[translator_index]
        
        # البحث عن المترجم في قاعدة البيانات
        report_id = context.user_data.get('edit_report_id')
        
        with SessionLocal() as s:
            # البحث عن المترجم أو إنشاؤه
            translator = s.query(Translator).filter_by(full_name=new_translator_name).first()
            if not translator:
                translator = Translator(full_name=new_translator_name)
                s.add(translator)
                s.commit()
            
            translator_id = translator.id
            
            # تحديث التقرير
            report = s.query(Report).filter_by(id=report_id).first()
            if report:
                report.translator_id = translator_id
                report.translator_name = new_translator_name  # Always update the name field as well
                s.commit()
                
                # تحديث البيانات المحفوظة
                context.user_data['current_report_data']['translator_name'] = new_translator_name
                context.user_data['current_report_data']['translator_id'] = translator_id
                
                logger.info(f"✅ تم تحديث المترجم للتقرير {report_id}: {new_translator_name}")
                
                await query.edit_message_text(
                    f"✅ **تم تعديل المترجم بنجاح**\n\n"
                    f"**المترجم الجديد:** {new_translator_name}",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # الانتظار قليلاً ثم العودة لقائمة الحقول
                import asyncio
                await asyncio.sleep(1)
                return await show_field_selection(query, context)
            else:
                await query.edit_message_text("❌ لم يتم العثور على التقرير")
                return ConversationHandler.END
                
    except Exception as e:
        logger.error(f"❌ خطأ في handle_translator_selection: {e}", exc_info=True)
        await query.edit_message_text("❌ حدث خطأ أثناء تحديث المترجم")
        return ConversationHandler.END


async def handle_callback_during_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأزرار أثناء انتظار القيمة الجديدة"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "edit_cancel":
        await query.edit_message_text("❌ **تم إلغاء عملية التعديل**")
        return ConversationHandler.END
    
    if query.data == "edit_back_to_fields":
        return await show_field_selection(query, context)
    
    return EDIT_VALUE

async def handle_text_during_date_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية أثناء انتظار اختيار التاريخ من التقويم - رفض النص وإعادة عرض التقويم"""
    message = update.message
    field_name = context.user_data.get('edit_field')
    current_value = context.user_data['current_report_data'].get(field_name, "لا يوجد")
    
    # إرسال رسالة تحذيرية
    await message.reply_text(
        "⚠️ **لا يمكن إدخال التاريخ يدوياً**\n\n"
        "✅ **يرجى استخدام التقويم أدناه لاختيار التاريخ**\n"
        "اضغط على التاريخ المطلوب من التقويم.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # إعادة عرض التقويم
    text = f"📅 **تعديل موعد العودة**\n\n"
    if current_value and current_value != "لا يوجد":
        followup_time = context.user_data['current_report_data'].get('followup_time', '')
        if followup_time:
            time_12h = format_time_12h(followup_time)
            text += f"**القيمة الحالية:** {current_value} - {time_12h}\n\n"
        else:
            text += f"**القيمة الحالية:** {current_value}\n\n"
    else:
        text += "**القيمة الحالية:** لا يوجد موعد\n\n"
    text += "✅ **اختر التاريخ من التقويم أدناه:**\n"
    text += "_(لا يمكن إدخال التاريخ يدوياً)_\n"
    
    # عرض التقويم الكامل
    now = datetime.now()
    keyboard = create_calendar_keyboard(now.year, now.month, "edit_followup", allow_future=True)
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="edit_back_to_fields")])
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="edit_cancel")])
    
    text += f"\n📆 **{MONTHS_AR[now.month]} {now.year}**"
    
    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return EDIT_DATE_CALENDAR

async def handle_date_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة التقويم لتحديد التاريخ"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "edit_cancel":
        await query.edit_message_text("❌ **تم إلغاء عملية التعديل**")
        return ConversationHandler.END
    
    if query.data == "edit_back_to_fields":
        return await show_field_selection(query, context)
    
    # معالجة اختيار التاريخ السريع
    if query.data.startswith("edit_followup:quick:"):
        date_str = query.data.split(":")[-1]
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        context.user_data['selected_date'] = selected_date
        
        # الانتقال لاختيار الوقت
        text = f"📅 **تم اختيار التاريخ:** {selected_date.strftime('%Y-%m-%d')}\n\n"
        text += "اختر الوقت:"
        
        # أزرار الأوقات السريعة
        keyboard = []
        time_buttons = []
        for hour in [9, 10, 11, 12, 13, 14, 15, 16, 17, 18]:
            time_str = f"{hour:02d}:00"
            time_display = f"{hour}:00" if hour < 12 else f"{hour-12}:00 مساءً" if hour > 12 else "12:00 ظهراً"
            time_buttons.append(InlineKeyboardButton(time_display, callback_data=f"edit_time:{time_str}"))
            if len(time_buttons) == 2:
                keyboard.append(time_buttons)
                time_buttons = []
        if time_buttons:
            keyboard.append(time_buttons)
        
        keyboard.append([InlineKeyboardButton("✏️ إدخال يدوي", callback_data="edit_time:manual")])
        keyboard.append([InlineKeyboardButton("⏭️ تخطي الوقت", callback_data="edit_time:skip")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="edit_back_to_fields")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="edit_cancel")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return EDIT_DATE_TIME
    
    # معالجة عرض التقويم
    elif query.data == "edit_followup:calendar":
        now = datetime.now()
        keyboard = create_calendar_keyboard(now.year, now.month, "edit_followup", allow_future=True)
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="edit_back_to_fields")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="edit_cancel")])
        
        text = "📅 **اختر التاريخ من التقويم:**\n\n"
        text += f"📆 {MONTHS_AR[now.month]} {now.year}"
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return EDIT_DATE_CALENDAR
    
    # معالجة التنقل في التقويم
    elif query.data.startswith("edit_followup:month:"):
        year_month = query.data.split(":")[-1]
        year, month = map(int, year_month.split("-"))
        keyboard = create_calendar_keyboard(year, month, "edit_followup", allow_future=True)
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="edit_back_to_fields")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="edit_cancel")])
        
        text = "📅 **اختر التاريخ من التقويم:**\n\n"
        text += f"📆 {MONTHS_AR[month]} {year}"
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return EDIT_DATE_CALENDAR
    
    # معالجة اختيار يوم من التقويم
    elif query.data.startswith("edit_followup:select:"):
        date_str = query.data.split(":")[-1]
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        context.user_data['selected_date'] = selected_date
        
        # الانتقال لاختيار الوقت
        text = f"📅 **تم اختيار التاريخ:** {selected_date.strftime('%Y-%m-%d')}\n\n"
        text += "اختر الوقت:"
        
        # أزرار الأوقات السريعة
        keyboard = []
        time_buttons = []
        for hour in [9, 10, 11, 12, 13, 14, 15, 16, 17, 18]:
            time_str = f"{hour:02d}:00"
            time_display = f"{hour}:00" if hour < 12 else f"{hour-12}:00 مساءً" if hour > 12 else "12:00 ظهراً"
            time_buttons.append(InlineKeyboardButton(time_display, callback_data=f"edit_time:{time_str}"))
            if len(time_buttons) == 2:
                keyboard.append(time_buttons)
                time_buttons = []
        if time_buttons:
            keyboard.append(time_buttons)
        
        keyboard.append([InlineKeyboardButton("✏️ إدخال يدوي", callback_data="edit_time:manual")])
        keyboard.append([InlineKeyboardButton("⏭️ تخطي الوقت", callback_data="edit_time:skip")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="edit_back_to_fields")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="edit_cancel")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return EDIT_DATE_TIME
    
    return EDIT_DATE_CALENDAR

async def handle_date_time_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار الوقت"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "edit_cancel":
        await query.edit_message_text("❌ **تم إلغاء عملية التعديل**")
        return ConversationHandler.END
    
    if query.data == "edit_back_to_fields":
        return await show_field_selection(query, context)
    
    selected_date = context.user_data.get('selected_date')
    if not selected_date:
        await query.answer("⚠️ لم يتم اختيار التاريخ", show_alert=True)
        return EDIT_DATE_CALENDAR
    
    # معالجة تخطي الوقت
    if query.data == "edit_time:skip":
        # حفظ التاريخ بدون وقت
        new_value = selected_date.strftime('%Y-%m-%d')
        context.user_data['new_value'] = new_value
        context.user_data['new_time'] = None
        
        # الانتقال لتأكيد التعديل
        await confirm_date_edit(query, context, selected_date, None)
        return CONFIRM_EDIT
    
    # معالجة إدخال الوقت يدوياً
    if query.data == "edit_time:manual":
        context.user_data['_waiting_for_time'] = True
        text = f"📅 **التاريخ المختار:** {selected_date.strftime('%Y-%m-%d')}\n\n"
        text += "أرسل الوقت بالصيغة:\n"
        text += "`HH:MM` (مثال: `14:30`)\n\n"
        text += "أو أرسل: `تخطي` لتخطي الوقت"
        
        keyboard = [
            [InlineKeyboardButton("🔙 رجوع", callback_data="edit_back_to_fields")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="edit_cancel")]
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return EDIT_DATE_TIME
    
    # معالجة اختيار وقت من الأزرار
    if query.data.startswith("edit_time:"):
        # استخراج الوقت بشكل صحيح (مثل edit_time:08:00 -> 08:00)
        time_str = query.data.replace("edit_time:", "", 1)
        if time_str != "manual" and time_str != "skip":
            context.user_data['new_time'] = time_str
            # حفظ القيمة الكاملة
            new_value = f"{selected_date.strftime('%Y-%m-%d')} {time_str}"
            context.user_data['new_value'] = new_value
            
            # الانتقال لتأكيد التعديل
            await confirm_date_edit(query, context, selected_date, time_str)
            return CONFIRM_EDIT
    
    return EDIT_DATE_TIME

async def confirm_date_edit(message_or_query, context, selected_date, selected_time):
    """تأكيد تعديل التاريخ"""
    field_name = context.user_data.get('edit_field')
    old_value = context.user_data['current_report_data'].get('followup_date', "لا يوجد")
    old_time = context.user_data['current_report_data'].get('followup_time', '')
    
    if old_value and old_value != "لا يوجد":
        old_display = f"{old_value}"
        if old_time:
            old_display += f" الساعة {old_time}"
    else:
        old_display = "لا يوجد"
    
    if selected_time:
        new_display = f"{selected_date.strftime('%Y-%m-%d')} الساعة {selected_time}"
    else:
        new_display = selected_date.strftime('%Y-%m-%d')
    
    # تنظيف القيم من الأحرف الخاصة بـ Markdown
    old_display_safe = escape_markdown(str(old_display) if old_display else "لا يوجد")
    new_display_safe = escape_markdown(str(new_display) if new_display else "")
    
    text = "📝 **تأكيد التعديل**\n\n"
    text += f"**الحقل:** موعد العودة\n\n"
    text += f"**القيمة القديمة:**\n{old_display_safe}\n\n"
    text += f"**القيمة الجديدة:**\n{new_display_safe}\n\n"
    text += "هل تريد نشر التعديل؟"
    
    keyboard = [
        [InlineKeyboardButton("📢 نشر التقرير", callback_data="edit_save_and_publish")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="edit_back_to_fields")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="edit_cancel")]
    ]
    
    # التحقق إذا كان query أو message
    if hasattr(message_or_query, 'edit_message_text'):
        await message_or_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await message_or_query.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    return CONFIRM_EDIT

async def handle_new_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة القيمة الجديدة"""
    new_value = update.message.text.strip()
    field_name = context.user_data.get('edit_field')
    
    # معالجة إدخال الوقت يدوياً
    if field_name == "followup_date" and context.user_data.get('_waiting_for_time'):
        selected_date = context.user_data.get('selected_date')
        if not selected_date:
            await update.message.reply_text("⚠️ **خطأ:** لم يتم اختيار التاريخ")
            return EDIT_DATE_CALENDAR
        
        if new_value.lower() == "تخطي" or new_value.lower() == "skip":
            # حفظ التاريخ بدون وقت
            context.user_data['new_value'] = selected_date.strftime('%Y-%m-%d')
            context.user_data['new_time'] = None
            context.user_data['_waiting_for_time'] = False
            
            await confirm_date_edit(update.message, context, selected_date, None)
            return CONFIRM_EDIT
        
        # التحقق من صيغة الوقت
        try:
            time_parts = new_value.split(':')
            if len(time_parts) != 2:
                raise ValueError
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError
            time_str = f"{hour:02d}:{minute:02d}"
            
            context.user_data['new_time'] = time_str
            context.user_data['new_value'] = f"{selected_date.strftime('%Y-%m-%d')} {time_str}"
            context.user_data['_waiting_for_time'] = False
            
            await confirm_date_edit(update.message, context, selected_date, time_str)
            return CONFIRM_EDIT
        except (ValueError, IndexError):
            await update.message.reply_text(
                "⚠️ **صيغة الوقت غير صحيحة**\n\n"
                "استخدم الصيغة: `HH:MM`\n"
                "مثال: `14:30` أو `09:00`\n\n"
                "أو أرسل: `تخطي` لتخطي الوقت",
                parse_mode=ParseMode.MARKDOWN
            )
            return EDIT_DATE_TIME
    
    # التحقق من صحة القيمة (للحقول الأخرى)
    if field_name == "followup_date" and new_value != "لا يوجد":
        try:
            datetime.strptime(new_value, '%Y-%m-%d %H:%M')
        except ValueError:
            await update.message.reply_text(
                "⚠️ **صيغة التاريخ والوقت غير صحيحة**\n\n"
                "استخدم الصيغة: `YYYY-MM-DD HH:MM`\n"
                "مثال: `2025-10-30 14:30`",
                parse_mode=ParseMode.MARKDOWN
            )
            return EDIT_VALUE
    
    # حفظ القيمة الجديدة
    context.user_data['new_value'] = new_value
    
    # أسماء الحقول بالعربي
    field_names = {
        'complaint_text': 'شكوى المريض',
        'doctor_decision': 'قرار الطبيب',
        'diagnosis': 'التشخيص الطبي',
        'treatment_plan': 'التوصيات / خطة العلاج',
        'notes': 'الفحوصات والأشعة',
        'medications': 'الأدوية',
        'followup_date': 'موعد العودة',
        'followup_reason': 'سبب العودة',
        'case_status': 'حالة الطوارئ',
        # ✅ حقول المسارات الخاصة
        'operation_details': 'تفاصيل العملية',
        'operation_name_en': 'اسم العملية بالإنجليزي',
        'therapy_details': 'تفاصيل جلسة العلاج الطبيعي',
        'device_details': 'تفاصيل الجهاز',
        'admission_reason': 'سبب الرقود',
        'admission_summary': 'ملخص الرقود',
        # ✅ حقول استشارة مع قرار عملية
        'decision': 'قرار الطبيب',
        'success_rate': 'نسبة نجاح العملية',
        'benefit_rate': 'نسبة الاستفادة',
        'tests': 'الفحوصات والأشعة',
        # ✅ حقول العلاج الإشعاعي
        'radiation_therapy_type': 'نوع الإشعاعي',
        'radiation_therapy_session_number': 'رقم الجلسة',
        'radiation_therapy_remaining': 'الجلسات المتبقية',
        'radiation_therapy_recommendations': 'ملاحظات / توصيات',
    }

    field_display = field_names.get(field_name, field_name.replace('_', ' '))
    old_value = context.user_data['current_report_data'].get(field_name, "لا يوجد")
    
    # تنظيف القيم من الأحرف الخاصة بـ Markdown
    old_value_safe = escape_markdown(str(old_value) if old_value else "لا يوجد")
    new_value_safe = escape_markdown(str(new_value) if new_value else "")
    
    # عرض الملخص
    text = "📝 **تأكيد التعديل**\n\n"
    text += f"**الحقل:** {field_display}\n\n"
    text += f"**القيمة القديمة:**\n{old_value_safe}\n\n"
    text += f"**القيمة الجديدة:**\n{new_value_safe}\n\n"
    text += "هل تريد نشر التعديل؟"
    
    keyboard = [
        [InlineKeyboardButton("📢 نشر التقرير", callback_data="edit_save_and_publish")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="edit_back_to_fields")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="edit_cancel")]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return CONFIRM_EDIT

async def save_edit_to_database(query, context):
    """حفظ التعديل في قاعدة البيانات (دالة مساعدة)"""
    import logging
    logger = logging.getLogger(__name__)
    
    report_id = context.user_data.get('edit_report_id')
    field_name = context.user_data.get('edit_field')
    new_value = context.user_data.get('new_value')
    
    with SessionLocal() as s:
        report = s.query(Report).filter_by(id=report_id).first()
        
        if not report:
            return False
        
        # تحديث الحقل
        if field_name == "followup_date":
            if new_value == "لا يوجد":
                report.followup_date = None
                report.followup_time = None
            else:
                # إذا كان التاريخ يحتوي على وقت
                if ' ' in new_value:
                    dt = datetime.strptime(new_value, '%Y-%m-%d %H:%M')
                    report.followup_date = dt
                    report.followup_time = dt.strftime('%H:%M')
                else:
                    # تاريخ فقط بدون وقت
                    report.followup_date = datetime.strptime(new_value, '%Y-%m-%d')
                    # حفظ الوقت إذا كان موجوداً في context
                    new_time = context.user_data.get('new_time')
                    if new_time:
                        report.followup_time = new_time
                    else:
                        report.followup_time = None
        elif field_name == "notes" and report.medical_action == "استشارة جديدة":
            # ✅ لحقل "استشارة جديدة": حفظ notes في medications أيضاً (لتوافق مع save_report_to_database)
            report.notes = new_value
            report.medications = new_value  # ✅ حفظ في medications لاسترجاع tests لاحقاً
            logger.info(f"✅ تم حفظ notes في medications أيضاً للتقرير #{report_id} (استشارة جديدة)")

        elif field_name == "notes" and report.medical_action == 'عملية':
            # ✅ حفظ notes وإعادة بناء doctor_decision لمسار العملية
            report.notes = new_value
            current_data = context.user_data.get('current_report_data', {})
            current_data['notes'] = new_value
            context.user_data['current_report_data'] = current_data
            operation_details = current_data.get('operation_details', 'لا يوجد')
            operation_name_en = current_data.get('operation_name_en', 'لا يوجد')
            new_decision = f"تفاصيل العملية: {operation_details}"
            if operation_name_en and operation_name_en != 'لا يوجد':
                new_decision += f"\nاسم العملية بالإنجليزي: {operation_name_en}"
            if new_value and new_value != 'لا يوجد':
                new_decision += f"\nملاحظات: {new_value}"
            report.doctor_decision = new_decision
            logger.info(f"✅ تم تحديث notes + doctor_decision لمسار العملية #{report_id}")

        elif field_name == "notes" and report.medical_action == 'ترقيد':
            # ✅ حفظ notes وإعادة بناء doctor_decision لمسار الترقيد
            report.notes = new_value
            current_data = context.user_data.get('current_report_data', {})
            current_data['notes'] = new_value
            context.user_data['current_report_data'] = current_data
            admission_reason = current_data.get('admission_reason', 'لا يوجد')
            new_decision = f"سبب الرقود: {admission_reason}"
            if new_value and new_value != 'لا يوجد':
                new_decision += f"\nملاحظات: {new_value}"
            report.doctor_decision = new_decision
            logger.info(f"✅ تم تحديث notes + doctor_decision لمسار الترقيد #{report_id}")

        # ✅ معالجة الحقول المخزنة في doctor_decision (باستثناء استشارة مع قرار عملية - لها معالج خاص)
        elif field_name in ['operation_details', 'operation_name_en', 'therapy_details', 'device_details', 'admission_reason', 'admission_summary'] and report.medical_action != 'استشارة مع قرار عملية':
            # استخراج القيم الحالية من current_report_data
            current_data = context.user_data.get('current_report_data', {})

            # تحديث القيمة المحددة
            current_data[field_name] = new_value
            context.user_data['current_report_data'] = current_data

            # إعادة بناء doctor_decision حسب نوع الإجراء
            medical_action = report.medical_action

            if medical_action == 'عملية':
                operation_details = current_data.get('operation_details', 'لا يوجد')
                operation_name_en = current_data.get('operation_name_en', 'لا يوجد')
                notes = current_data.get('notes', '')

                new_decision = f"تفاصيل العملية: {operation_details}"
                if operation_name_en and operation_name_en != 'لا يوجد':
                    new_decision += f"\nاسم العملية بالإنجليزي: {operation_name_en}"
                if notes and notes != 'لا يوجد':
                    new_decision += f"\nملاحظات: {notes}"
                report.doctor_decision = new_decision
                logger.info(f"✅ تم تحديث doctor_decision للعملية: {new_decision[:50]}...")

            elif medical_action in ['خروج من المستشفى', 'خروج']:
                admission_summary = current_data.get('admission_summary', 'لا يوجد')
                operation_details = current_data.get('operation_details', 'لا يوجد')
                operation_name_en = current_data.get('operation_name_en', 'لا يوجد')

                new_decision = f"ملخص الرقود: {admission_summary}"
                if operation_details and operation_details != 'لا يوجد':
                    new_decision += f"\nتفاصيل العملية: {operation_details}"
                if operation_name_en and operation_name_en != 'لا يوجد':
                    new_decision += f"\nاسم العملية بالإنجليزي: {operation_name_en}"
                report.doctor_decision = new_decision
                logger.info(f"✅ تم تحديث doctor_decision للخروج: {new_decision[:50]}...")

            elif medical_action in ['علاج طبيعي', 'علاج طبيعي وإعادة تأهيل']:
                therapy_details = current_data.get('therapy_details', new_value)
                report.doctor_decision = f"تفاصيل جلسة العلاج الطبيعي: {therapy_details}"
                logger.info(f"✅ تم تحديث doctor_decision للعلاج الطبيعي")

            elif medical_action == 'أجهزة تعويضية':
                device_details = current_data.get('device_details', new_value)
                report.doctor_decision = f"تفاصيل الجهاز: {device_details}"
                logger.info(f"✅ تم تحديث doctor_decision للأجهزة التعويضية")

            elif medical_action == 'ترقيد':
                admission_reason = current_data.get('admission_reason', new_value)
                notes = current_data.get('notes', '')

                new_decision = f"سبب الرقود: {admission_reason}"
                if notes and notes != 'لا يوجد':
                    new_decision += f"\nملاحظات: {notes}"
                report.doctor_decision = new_decision
                # أيضاً حفظ في complaint_text للتوافق
                if field_name == 'admission_reason':
                    report.complaint_text = admission_reason
                logger.info(f"✅ تم تحديث doctor_decision للترقيد")

        # ✅ معالجة حقول استشارة مع قرار عملية (شاملة diagnosis)
        elif field_name in ['diagnosis', 'decision', 'operation_name_en', 'success_rate', 'benefit_rate', 'tests'] and report.medical_action == 'استشارة مع قرار عملية':
            # تحديث القيمة في current_report_data
            current_data = context.user_data.get('current_report_data', {})
            current_data[field_name] = new_value
            context.user_data['current_report_data'] = current_data
            
            # إعادة بناء doctor_decision من الحقول الفرعية
            diagnosis_val = current_data.get('diagnosis', '') or (report.diagnosis or '')
            decision_val = current_data.get('decision', new_value if field_name == 'decision' else '')
            op_name = current_data.get('operation_name_en', new_value if field_name == 'operation_name_en' else '')
            s_rate = current_data.get('success_rate', new_value if field_name == 'success_rate' else '')
            b_rate = current_data.get('benefit_rate', new_value if field_name == 'benefit_rate' else '')
            tests_val = current_data.get('tests', new_value if field_name == 'tests' else '')
            
            # تنظيف القيم
            if diagnosis_val == 'لا يوجد': diagnosis_val = ''
            if decision_val == 'لا يوجد': decision_val = ''
            if op_name == 'لا يوجد': op_name = ''
            if s_rate == 'لا يوجد': s_rate = ''
            if b_rate == 'لا يوجد': b_rate = ''
            if tests_val == 'لا يوجد': tests_val = ''
            
            new_doctor_decision = f"التشخيص: {diagnosis_val}\n\nقرار الطبيب: {decision_val}"
            if op_name:
                new_doctor_decision += f"\n\nاسم العملية بالإنجليزي: {op_name}"
            if s_rate:
                new_doctor_decision += f"\n\nنسبة نجاح العملية: {s_rate}"
            if b_rate:
                new_doctor_decision += f"\n\nنسبة الاستفادة من العملية: {b_rate}"
            if tests_val:
                new_doctor_decision += f"\n\nالفحوصات المطلوبة: {tests_val}"
            
            report.doctor_decision = new_doctor_decision
            # تحديث الحقول المنفصلة إذا تم تعديلها
            if field_name == 'diagnosis':
                report.diagnosis = new_value
            logger.info(f"✅ تم تحديث doctor_decision لاستشارة مع قرار عملية: {field_name} = {new_value[:50]}...")

        # ✅ معالجة حقول العلاج الإشعاعي
        elif field_name in ['radiation_therapy_type', 'radiation_therapy_session_number', 'radiation_therapy_remaining', 'radiation_therapy_recommendations']:
            setattr(report, field_name, new_value)
            if field_name == 'radiation_therapy_recommendations':
                # حفظ في حقل notes أيضاً
                report.notes = new_value
            # تحديث doctor_decision أيضاً
            current_data = context.user_data.get('current_report_data', {})
            current_data[field_name] = new_value
            context.user_data['current_report_data'] = current_data
            
            rad_type = current_data.get('radiation_therapy_type', '') or getattr(report, 'radiation_therapy_type', '') or ''
            session_num = current_data.get('radiation_therapy_session_number', '') or getattr(report, 'radiation_therapy_session_number', '') or ''
            remaining = current_data.get('radiation_therapy_remaining', '') or getattr(report, 'radiation_therapy_remaining', '') or ''
            
            new_decision = f"نوع الإشعاعي: {rad_type}\n\n"
            new_decision += f"رقم الجلسة: {session_num}\n\n"
            new_decision += f"الجلسات المتبقية: {remaining}"
            report.doctor_decision = new_decision
            logger.info(f"✅ تم تحديث حقل العلاج الإشعاعي: {field_name} = {new_value}")

        elif field_name == 'followup_reason' and report.medical_action == 'جلسة إشعاعي':
            # حفظ سبب العودة في followup_reason و radiation_therapy_return_reason
            report.followup_reason = new_value
            report.radiation_therapy_return_reason = new_value
            logger.info(f"✅ تم تحديث followup_reason + radiation_therapy_return_reason = {new_value}")

        else:
            setattr(report, field_name, new_value)
        
        # تحديث تاريخ التعديل
        report.updated_at = datetime.now()
        
        s.commit()
        logger.info(f"✅ تم حفظ التعديل للتقرير #{report_id} - الحقل: {field_name}")
        return True

async def handle_confirm_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة تأكيد الحفظ"""
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    await query.answer()
    
    if query.data == "edit_cancel":
        await query.edit_message_text("❌ **تم إلغاء عملية التعديل**")
        return ConversationHandler.END
    
    if query.data == "edit_back_to_fields":
        return await show_field_selection(query, context)
    
    # حفظ ونشر التقرير
    if query.data == "edit_save_and_publish":
        # أولاً نحفظ التعديل
        await save_edit_to_database(query, context)
        # ثم ننشر التقرير
        return await handle_republish(update, context)
    
    if query.data == "edit_confirm_save":
        # حفظ التعديل في قاعدة البيانات
        report_id = context.user_data.get('edit_report_id')
        field_name = context.user_data.get('edit_field')
        new_value = context.user_data.get('new_value')
        
        with SessionLocal() as s:
            report = s.query(Report).filter_by(id=report_id).first()
            
            if not report:
                await query.edit_message_text("⚠️ **خطأ:** لم يتم العثور على التقرير")
                return ConversationHandler.END
            
            # حفظ القيمة القديمة
            old_value = getattr(report, field_name, "لا يوجد")
            if isinstance(old_value, datetime):
                old_value = old_value.strftime('%Y-%m-%d %H:%M')
            
            # تحديث الحقل
            if field_name == "followup_date":
                if new_value == "لا يوجد":
                    report.followup_date = None
                    report.followup_time = None
                else:
                    # إذا كان التاريخ يحتوي على وقت
                    if ' ' in new_value:
                        dt = datetime.strptime(new_value, '%Y-%m-%d %H:%M')
                        report.followup_date = dt
                        report.followup_time = dt.strftime('%H:%M')
                    else:
                        # تاريخ فقط بدون وقت
                        report.followup_date = datetime.strptime(new_value, '%Y-%m-%d')
                        # حفظ الوقت إذا كان موجوداً في context
                        new_time = context.user_data.get('new_time')
                        if new_time:
                            report.followup_time = new_time
                        else:
                            report.followup_time = None
            elif field_name == "notes" and report.medical_action == "استشارة جديدة":
                # ✅ لحقل "استشارة جديدة": حفظ notes في medications أيضاً (لتوافق مع save_report_to_database)
                report.notes = new_value
                report.medications = new_value  # ✅ حفظ في medications لاسترجاع tests لاحقاً
                logger.info(f"✅ تم حفظ notes في medications أيضاً للتقرير #{report_id} (استشارة جديدة)")
            else:
                setattr(report, field_name, new_value)
            
            # تحديث تاريخ التعديل
            report.updated_at = datetime.now()
            
            s.commit()
            
            # أسماء الحقول بالعربي
            field_names = {
                'complaint_text': 'شكوى المريض',
                'doctor_decision': 'قرار الطبيب',
                'diagnosis': 'التشخيص الطبي',
                'treatment_plan': 'التوصيات / خطة العلاج',
                'medications': 'الأدوية / الفحوصات',
                'notes': 'الملاحظات / الفحوصات',
                'case_status': 'حالة الطوارئ',
                'followup_date': 'موعد العودة',
                'followup_reason': 'سبب العودة'
            }
            
            field_display = field_names.get(field_name, field_name)
            
            # رسالة النجاح
            success_text = f"✅ **تم حفظ التعديل بنجاح**\n\n"
            success_text += f"📋 **رقم التقرير:** #{report_id}\n"
            success_text += f"✏️ **الحقل المعدل:** {field_display}\n"
            success_text += f"📅 **وقت التعديل:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            success_text += f"**القيمة الجديدة:**\n{new_value}"
            
            await query.edit_message_text(success_text, parse_mode=ParseMode.MARKDOWN)
        
        # تنظيف البيانات
        context.user_data.clear()
        
        return ConversationHandler.END
    
    return CONFIRM_EDIT

async def show_field_selection(query, context):
    """عرض قائمة الحقول مرة أخرى"""
    report_id = context.user_data.get('edit_report_id')
    
    with SessionLocal() as s:
        report = s.query(Report).filter_by(id=report_id).first()
        
        if not report:
            await query.edit_message_text("⚠️ **خطأ:** لم يتم العثور على التقرير")
            return ConversationHandler.END
        
        # تحديث بيانات التقرير من قاعدة البيانات (للحصول على آخر التعديلات)
        patient = s.query(Patient).filter_by(id=report.patient_id).first()
        hospital = s.query(Hospital).filter_by(id=report.hospital_id).first()
        department = s.query(Department).filter_by(id=report.department_id).first() if report.department_id else None
        doctor = s.query(Doctor).filter_by(id=report.doctor_id).first() if report.doctor_id else None
        translator = s.query(Translator).filter_by(id=report.translator_id).first() if report.translator_id else None
        
        # ✅ تحديث البيانات المحفوظة - تحديث شامل لجميع الحقول المحتملة
        current_data = context.user_data.get('current_report_data', {})
        current_data.update({
            'patient_name': patient.full_name if patient else "غير معروف",
            'hospital_name': hospital.name if hospital else "غير معروف",
            'department_name': department.name if department else "غير محدد",
            'doctor_name': doctor.full_name if doctor else "لم يتم التحديد",
            'medical_action': report.medical_action or "غير محدد",
            'complaint_text': report.complaint_text or "لا يوجد",
            'doctor_decision': report.doctor_decision or "لا يوجد",
            'diagnosis': report.diagnosis or "لا يوجد",
            'treatment_plan': report.treatment_plan or "لا يوجد",
            'medications': report.medications or "لا يوجد",
            'notes': report.notes or "لا يوجد",
            'case_status': report.case_status or "لا يوجد",
            'followup_date': report.followup_date.strftime('%Y-%m-%d') if report.followup_date else None,
            'followup_time': report.followup_time,
            'followup_reason': report.followup_reason or "لا يوجد",
            'room_number': getattr(report, 'room_number', None) or "لا يوجد",
            'radiology_type': getattr(report, 'radiology_type', None) or "لا يوجد",
            'radiology_delivery_date': getattr(report, 'radiology_delivery_date', None),
            'app_reschedule_reason': getattr(report, 'app_reschedule_reason', None) or "لا يوجد",
            'app_reschedule_return_date': getattr(report, 'app_reschedule_return_date', None),
            'app_reschedule_return_reason': getattr(report, 'app_reschedule_return_reason', None) or "لا يوجد",
            'translator_name': report.translator_name or (translator.full_name if translator else "غير محدد"),
            'translator_id': report.translator_id,
            # ✅ حقول العلاج الإشعاعي
            'radiation_therapy_type': getattr(report, 'radiation_therapy_type', None) or "لا يوجد",
            'radiation_therapy_session_number': getattr(report, 'radiation_therapy_session_number', None) or "لا يوجد",
            'radiation_therapy_remaining': getattr(report, 'radiation_therapy_remaining', None) or "لا يوجد",
            'radiation_therapy_recommendations': getattr(report, 'radiation_therapy_recommendations', None) or getattr(report, 'notes', None) or "",
            'radiation_therapy_return_reason': getattr(report, 'radiation_therapy_return_reason', None) or "لا يوجد",
        })
        
        # ✅ إعادة استخراج الحقول الخاصة من doctor_decision المحدث حسب نوع الإجراء
        dd_text = report.doctor_decision or ''
        
        if report.medical_action == 'استشارة مع قرار عملية':
            try:
                sections = dd_text.split('\n\n')
                for section in sections:
                    section = section.strip()
                    if section.startswith('التشخيص:'):
                        current_data['diagnosis'] = section.replace('التشخيص:', '', 1).strip() or "لا يوجد"
                    elif section.startswith('قرار الطبيب:'):
                        current_data['decision'] = section.replace('قرار الطبيب:', '', 1).strip() or "لا يوجد"
                    elif section.startswith('اسم العملية بالإنجليزي:'):
                        current_data['operation_name_en'] = section.replace('اسم العملية بالإنجليزي:', '', 1).strip() or "لا يوجد"
                    elif section.startswith('نسبة نجاح العملية:'):
                        current_data['success_rate'] = section.replace('نسبة نجاح العملية:', '', 1).strip() or "لا يوجد"
                    elif section.startswith('نسبة الاستفادة من العملية:'):
                        current_data['benefit_rate'] = section.replace('نسبة الاستفادة من العملية:', '', 1).strip() or "لا يوجد"
                    elif section.startswith('الفحوصات المطلوبة:'):
                        current_data['tests'] = section.replace('الفحوصات المطلوبة:', '', 1).strip() or "لا يوجد"
            except Exception:
                pass
        
        elif report.medical_action == 'عملية':
            try:
                if 'تفاصيل العملية:' in dd_text:
                    parts = dd_text.split('تفاصيل العملية:', 1)
                    if len(parts) > 1:
                        rest = parts[1]
                        if 'اسم العملية بالإنجليزي:' in rest:
                            current_data['operation_details'] = rest.split('اسم العملية بالإنجليزي:')[0].strip() or "لا يوجد"
                            rest2 = rest.split('اسم العملية بالإنجليزي:', 1)[1]
                            if 'ملاحظات:' in rest2:
                                current_data['operation_name_en'] = rest2.split('ملاحظات:')[0].strip() or "لا يوجد"
                                current_data['notes'] = rest2.split('ملاحظات:', 1)[1].strip() or "لا يوجد"
                            else:
                                current_data['operation_name_en'] = rest2.strip() or "لا يوجد"
                        else:
                            current_data['operation_details'] = rest.strip() or "لا يوجد"
                elif dd_text and dd_text.strip() and dd_text != "لا يوجد":
                    current_data['operation_details'] = dd_text.strip()
            except Exception:
                pass
        
        elif report.medical_action in ['خروج من المستشفى', 'خروج']:
            try:
                if 'ملخص الرقود:' in dd_text:
                    parts = dd_text.split('ملخص الرقود:', 1)
                    if len(parts) > 1:
                        rest = parts[1]
                        if 'تفاصيل العملية:' in rest:
                            current_data['admission_summary'] = rest.split('تفاصيل العملية:')[0].strip() or "لا يوجد"
                            rest2 = rest.split('تفاصيل العملية:', 1)[1]
                            if 'اسم العملية بالإنجليزي:' in rest2:
                                current_data['operation_details'] = rest2.split('اسم العملية بالإنجليزي:')[0].strip() or "لا يوجد"
                                current_data['operation_name_en'] = rest2.split('اسم العملية بالإنجليزي:', 1)[1].strip() or "لا يوجد"
                            else:
                                current_data['operation_details'] = rest2.strip() or "لا يوجد"
                        else:
                            current_data['admission_summary'] = rest.strip() or "لا يوجد"
                elif 'تفاصيل العملية:' in dd_text:
                    parts = dd_text.split('تفاصيل العملية:', 1)
                    if len(parts) > 1:
                        rest = parts[1]
                        if 'اسم العملية بالإنجليزي:' in rest:
                            current_data['operation_details'] = rest.split('اسم العملية بالإنجليزي:')[0].strip() or "لا يوجد"
                            current_data['operation_name_en'] = rest.split('اسم العملية بالإنجليزي:', 1)[1].strip() or "لا يوجد"
                        else:
                            current_data['operation_details'] = rest.strip() or "لا يوجد"
            except Exception:
                pass
        
        elif report.medical_action in ['علاج طبيعي', 'علاج طبيعي وإعادة تأهيل']:
            try:
                if 'تفاصيل جلسة العلاج الطبيعي:' in dd_text:
                    current_data['therapy_details'] = dd_text.split('تفاصيل جلسة العلاج الطبيعي:', 1)[1].strip() or "لا يوجد"
                elif 'تفاصيل الجلسة:' in dd_text:
                    current_data['therapy_details'] = dd_text.split('تفاصيل الجلسة:', 1)[1].strip() or "لا يوجد"
                elif dd_text and dd_text.strip() and dd_text != "لا يوجد":
                    current_data['therapy_details'] = dd_text.strip()
            except Exception:
                pass
        
        elif report.medical_action == 'أجهزة تعويضية':
            try:
                if 'تفاصيل الجهاز:' in dd_text:
                    current_data['device_details'] = dd_text.split('تفاصيل الجهاز:', 1)[1].strip() or "لا يوجد"
                elif dd_text and dd_text.strip() and dd_text != "لا يوجد":
                    current_data['device_details'] = dd_text.strip()
            except Exception:
                pass
        
        elif report.medical_action == 'ترقيد':
            try:
                if 'سبب الرقود:' in dd_text:
                    parts = dd_text.split('سبب الرقود:', 1)
                    if len(parts) > 1:
                        rest = parts[1]
                        if 'ملاحظات:' in rest:
                            current_data['admission_reason'] = rest.split('ملاحظات:')[0].strip() or "لا يوجد"
                            current_data['notes'] = rest.split('ملاحظات:', 1)[1].strip() or "لا يوجد"
                        else:
                            current_data['admission_reason'] = rest.strip() or "لا يوجد"
                elif dd_text and dd_text.strip() and dd_text != "لا يوجد":
                    current_data['admission_reason'] = dd_text.strip()
            except Exception:
                pass
            # fallback: استخدام complaint_text كـ admission_reason
            if current_data.get('admission_reason', 'لا يوجد') == 'لا يوجد':
                if report.complaint_text and report.complaint_text != "لا يوجد":
                    current_data['admission_reason'] = report.complaint_text
        
        context.user_data['current_report_data'] = current_data
        
        # عرض بيانات التقرير مرة أخرى
        medical_action = current_data.get('medical_action', report.medical_action or "غير محدد")
        
        # ✅ الحصول على الحقول المحددة لهذا النوع من الإجراء
        all_fields = get_editable_fields_by_action_type(medical_action)
        
        # ✅ بناء الأزرار - عرض فقط الحقول التي لها قيمة فعلية
        import logging
        logger = logging.getLogger(__name__)
        
        fields_with_values = []
        for field_name, field_display in all_fields:
            # ✅ التحقق من وجود قيمة فعلية للحقل
            if _has_field_value_in_report(report, current_data, field_name):
                fields_with_values.append((field_name, field_display))
                logger.info(f"✅ [EDIT_AFTER_PUBLISH] إضافة حقل '{field_name}' للقائمة (له قيمة)")
            else:
                logger.info(f"⏭️ [EDIT_AFTER_PUBLISH] تخطي حقل '{field_name}' (لا توجد قيمة)")
        
        # ✅ حماية: إذا كان نوع الإجراء مراجعة / عودة دورية، لا نضيف رقم الغرفة
        if _has_field_value_in_report(report, current_data, 'room_number'):
            has_room = any(f == 'room_number' for f, _ in fields_with_values)
            if not has_room:
                if medical_action and 'مراجعة / عودة دورية' in medical_action:
                    logger.warning(f"⚠️ [EDIT_AFTER_PUBLISH] تجاهل رقم الغرفة لمسار مراجعة / عودة دورية report_id={report_id}")
                else:
                    # إدراجه في موقع منطقي (مثلاً قبل followup_date إذا وجد، أو في النهاية)
                    room_entry = ('room_number', '🏥 رقم الغرفة والطابق')
                    inserted = False
                    for i, (fname, _) in enumerate(fields_with_values):
                        if fname == 'followup_date':
                            fields_with_values.insert(i, room_entry)
                            inserted = True
                            break
                    if not inserted:
                        fields_with_values.append(room_entry)
                    logger.info(f"✅ [EDIT_AFTER_PUBLISH] تم فرض إضافة 'room_number' لوجود قيمة له")
        
        # ✅ التحقق من وجود حقول مدخلة
        if not fields_with_values:
            await query.edit_message_text(
                "⚠️ **لا توجد حقول مدخلة للتعديل**\n\n"
                f"📋 **رقم التقرير:** #{report_id}\n"
                f"⚕️ **نوع الإجراء:** {medical_action}\n\n"
                "لم يتم إدخال أي بيانات في هذا التقرير.\n"
                "يرجى استخدام زر '🔙 رجوع' للرجوع إلى قائمة التقارير.",
                parse_mode=ParseMode.MARKDOWN
            )
            return SELECT_REPORT
        
        text = f"📋 **بيانات التقرير #{report_id}**\n\n"
        text += f"📅 **تاريخ التقرير:** {current_data.get('report_date', 'غير محدد')}\n"
        text += f"👤 **اسم المريض:** {current_data.get('patient_name', 'غير معروف')}\n"
        text += f"🏥 **المستشفى:** {current_data.get('hospital_name', 'غير معروف')}\n"
        text += f"🏷️ **القسم:** {current_data.get('department_name', 'غير محدد')}\n"
        text += f"👨‍⚕️ **الطبيب:** {current_data.get('doctor_name', 'لم يتم التحديد')}\n"
        text += f"⚕️ **نوع الإجراء:** {medical_action}\n\n"
        text += "اختر الحقل الذي تريد تعديله:\n"
        
        keyboard = []
        # ✅ عرض فقط الحقول التي لها قيمة
        for field_name, field_display in fields_with_values:
            current_value = current_data.get(field_name, "")
            
            # ✅ تنسيق القيمة للعرض
            if isinstance(current_value, (date, datetime)):
                display_value = current_value.strftime('%Y-%m-%d') if isinstance(current_value, date) else current_value.strftime('%Y-%m-%d %H:%M')
            elif current_value and len(str(current_value)) > 15:
                display_value = str(current_value)[:12] + "..."
            else:
                display_value = str(current_value) if current_value else ""
            
            button_text = f"{field_display}: {display_value}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"edit_field:{field_name}")])
        
        # إضافة زر إعادة النشر
        keyboard.append([InlineKeyboardButton("📢 إعادة نشر التقرير", callback_data="edit_republish")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="edit_back")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="edit_cancel")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SELECT_FIELD

async def start_edit_reports_from_callback(query, context):
    """إعادة عرض قائمة التقارير من callback"""
    import logging
    logger = logging.getLogger(__name__)
    
    with SessionLocal() as s:
        # ✅ استخدام معرف المستخدم الفعلي بدلاً من translator_id
        user_id = context.user_data.get('submitted_by_user_id')
        if not user_id and query.from_user:
            user_id = query.from_user.id
        
        # البحث عن تقارير اليوم فقط
        today = date.today()
        
        # ✅ إصلاح مشكلة التوقيت: توسيع النطاق ليشمل 24 ساعة الماضية + 12 ساعة قادمة
        now_utc = datetime.utcnow()
        today_start = now_utc - timedelta(hours=24)
        today_end = now_utc + timedelta(hours=12)
        
        logger.info(f"🔍 نطاق البحث (UTC - Expanded): من {today_start} إلى {today_end}")
        
        # ✅ البحث بمعرف المستخدم الذي أنشأ التقرير (نفس منطق start_edit_reports)
        translator = s.query(Translator).filter_by(tg_user_id=user_id).first()
        translator_id = translator.id if translator else None
        
        try:
            if translator_id:
                reports = s.query(Report).filter(
                    or_(
                        Report.submitted_by_user_id == user_id,  # التقارير الجديدة
                        and_(
                            Report.submitted_by_user_id.is_(None),  # التقارير القديمة فقط
                            Report.translator_id == translator_id  # المترجم يطابق المستخدم الحالي
                        )
                    ),
                    Report.report_date >= today_start,
                    Report.report_date <= today_end
                ).order_by(Report.report_date.desc()).all()
            else:
                reports = s.query(Report).filter(
                    Report.submitted_by_user_id == user_id,
                    Report.report_date >= today_start,
                    Report.report_date <= today_end
                ).order_by(Report.report_date.desc()).all()
                
            logger.info(f"✅ تم العثور على {len(reports)} تقرير للمستخدم {user_id} (translator_id: {translator_id})")
        except Exception as e:
            logger.warning(f"⚠️ Error using submitted_by_user_id, falling back to translator_id: {e}")
            if translator_id:
                reports = s.query(Report).filter(
                    Report.translator_id == translator_id,
                    Report.report_date >= today_start,
                    Report.report_date <= today_end
                ).order_by(Report.report_date.desc()).all()
            else:
                reports = []
        
        if not reports:
            await query.edit_message_text(
                f"📋 **لا توجد تقارير لليوم**\n\n"
                f"📅 **التاريخ:** {today.strftime('%Y-%m-%d')}"
            )
            return ConversationHandler.END
        
        text = "✏️ **تعديل التقارير - اليوم**\n\n"
        text += f"📅 **{today.strftime('%Y-%m-%d')}** ({len(reports)} تقرير)\n\n"
        text += "اختر التقرير الذي تريد تعديله:\n\n"
        
        keyboard = []
        for report in reports:
            patient = s.query(Patient).filter_by(id=report.patient_id).first()
            patient_name = patient.full_name if patient else "غير معروف"
            date_str = report.report_date.strftime('%Y-%m-%d %H:%M')
            button_text = f"#{report.id} | {patient_name} | {date_str}"
            keyboard.append([
                InlineKeyboardButton(
                    button_text, 
                    callback_data=f"edit_report:{report.id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="edit_cancel")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SELECT_REPORT

async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء عملية التعديل"""
    context.user_data.clear()
    await update.message.reply_text("❌ **تم إلغاء عملية التعديل**")
    return ConversationHandler.END

def register(app):
    """تسجيل معالج تعديل التقارير"""
    
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^✏️ تعديل التقارير$"), start_edit_reports)
        ],
        states={
            SELECT_REPORT: [
                CallbackQueryHandler(handle_report_selection, pattern="^edit_report:"),
                CallbackQueryHandler(handle_report_selection, pattern="^edit_cancel$")
            ],
            SELECT_FIELD: [
                CallbackQueryHandler(handle_field_selection, pattern="^edit_field:"),
                CallbackQueryHandler(handle_field_selection, pattern="^edit_republish$"),
                CallbackQueryHandler(handle_field_selection, pattern="^edit_back$"),
                CallbackQueryHandler(handle_field_selection, pattern="^edit_cancel$")
            ],
            EDIT_VALUE: [
                CallbackQueryHandler(handle_callback_during_edit),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_value)
            ],
            EDIT_DATE_CALENDAR: [
                CallbackQueryHandler(handle_date_calendar, pattern="^edit_followup:"),
                CallbackQueryHandler(handle_date_calendar, pattern="^edit_back_to_fields$"),
                CallbackQueryHandler(handle_date_calendar, pattern="^edit_cancel$"),
                # منع إدخال النص - يجب استخدام التقويم فقط وإعادة عرض التقويم
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    handle_text_during_date_calendar
                )
            ],
            EDIT_DATE_TIME: [
                CallbackQueryHandler(handle_date_time_selection, pattern="^edit_time:"),
                CallbackQueryHandler(handle_date_time_selection, pattern="^edit_back_to_fields$"),
                CallbackQueryHandler(handle_date_time_selection, pattern="^edit_cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_value)
            ],
            EDIT_TRANSLATOR: [
                CallbackQueryHandler(handle_translator_selection, pattern="^edit_translator:"),
                CallbackQueryHandler(handle_translator_selection, pattern="^edit_back_to_fields$"),
                CallbackQueryHandler(handle_translator_selection, pattern="^edit_cancel$"),
            ],
            CONFIRM_EDIT: [
                CallbackQueryHandler(handle_confirm_edit)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ إلغاء العملية الحالية$"), cancel_edit),
            CallbackQueryHandler(handle_report_selection, pattern="^edit_cancel$")
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,  # ✅ False لأن entry point هو MessageHandler
    )
    
    app.add_handler(conv_handler)
