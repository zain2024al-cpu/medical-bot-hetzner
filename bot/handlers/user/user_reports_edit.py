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
from datetime import datetime, date
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
    """
    test_cases = [
        ('استشارة جديدة', 6),  # 6 حقول
        ('استشارة مع قرار عملية', 6),  # 6 حقول
        ('استشارة أخيرة', 3),  # 3 حقول
        ('طوارئ', 6),  # 6 حقول
        ('متابعة في الرقود', 6),  # 6 حقول
        ('مراجعة / عودة دورية', 5),  # 5 حقول (بدون رقم غرفة)
        ('عملية', 5),  # 5 حقول
        ('علاج طبيعي وإعادة تأهيل', 5),  # 5 حقول
        ('ترقيد', 6),  # 6 حقول
        ('خروج من المستشفى', 4),  # 4 حقول
        ('نوع غير معروف', 3),  # 3 حقول افتراضية
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
            ('doctor_decision', '📝 قرار الطبيب'),
            ('notes', '⚕️ اسم العملية'),
            ('treatment_plan', '📊 نسبة النجاح'),
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
    elif action_clean == 'متابعة في الرقود':
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
    # ===========================================
    elif action_clean == 'عملية':
        return [
            ('complaint_text', '⚕️ تفاصيل العملية'),
            ('notes', '📝 اسم العملية بالانجليزي'),
            ('doctor_decision', '📋 ملاحظات العملية'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 8. علاج طبيعي وإعادة تأهيل - التركيز على العلاج
    # ===========================================
    elif action_clean == 'علاج طبيعي وإعادة تأهيل':
        return [
            ('complaint_text', '🏃 تفاصيل العلاج الطبيعي'),
            ('doctor_decision', '📝 تقييم الطبيب'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 9. ترقيد - التركيز على أسباب الرقود
    # ===========================================
    elif action_clean == 'ترقيد':
        return [
            ('complaint_text', '🛏️ سبب الرقود'),
            ('diagnosis', '🔬 التشخيص'),
            ('doctor_decision', '📝 قرار الطبيب'),
            ('room_number', '🏥 رقم الغرفة'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 10. خروج من المستشفى - التركيز على الخروج
    # ===========================================
    elif action_clean == 'خروج من المستشفى' or action_clean == 'خروج':
        return [
            ('complaint_text', '📋 ملخص حالة المريض'),
            ('diagnosis', '🔬 التشخيص النهائي'),
            ('doctor_decision', '⚕️ قرار الطبيب والتوصيات'),
            ('treatment_plan', '💊 خطة العلاج بعد الخروج'),
            ('notes', '📝 ملاحظات إضافية'),
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
    # ===========================================
    elif action_clean == 'علاج طبيعي':
        return [
            ('complaint_text', '🏃 تفاصيل الجلسة'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
            ('translator_name', '👤 المترجم'),
        ]

    # ===========================================
    # 14. أجهزة تعويضية - التركيز على الجهاز
    # ===========================================
    elif action_clean == 'أجهزة تعويضية':
        return [
            ('complaint_text', '🦾 تفاصيل الجهاز'),
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
            today_start = datetime.combine(today, datetime.min.time())
            today_end = datetime.combine(today, datetime.max.time())

            # ✅ البحث بمعرف المستخدم الذي أنشأ التقرير (submitted_by_user_id)
            # هذا الحقل يتم حفظه عند إنشاء التقرير بغض النظر عن اسم المترجم المختار
            # للتقارير القديمة: البحث عن translator_id الذي يطابق tg_user_id للمستخدم الحالي
            translator = s.query(Translator).filter_by(tg_user_id=user.id).first()
            translator_id = translator.id if translator else None
            
            logger.info(f"🔍 البحث عن تقارير للمستخدم:")
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
            
            # حفظ البيانات الحالية
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
                'medications': report.medications or "لا يوجد",
                'notes': report.notes or "لا يوجد",
                'case_status': report.case_status or "لا يوجد",
                'followup_date': report.followup_date.strftime('%Y-%m-%d') if report.followup_date else None,
                'followup_time': report.followup_time,
                'followup_reason': report.followup_reason or "لا يوجد",
                'report_date': report.report_date.strftime('%Y-%m-%d %H:%M'),
                'translator_name': translator.full_name if translator else "غير محدد",
                'translator_id': report.translator_id,
                # حقول إضافية
                'room_number': getattr(report, 'room_number', None) or "لا يوجد",
                'radiology_type': getattr(report, 'radiology_type', None) or "لا يوجد",
                'radiology_delivery_date': getattr(report, 'radiology_delivery_date', None),
                'app_reschedule_reason': getattr(report, 'app_reschedule_reason', None) or "لا يوجد",
                'app_reschedule_return_date': getattr(report, 'app_reschedule_return_date', None),
                'app_reschedule_return_reason': getattr(report, 'app_reschedule_return_reason', None) or "لا يوجد",
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
            text += "اختر الحقل الذي تريد تعديله:\n"
            
            # بناء الأزرار - جميع حقول هذا النوع من الإجراء (حتى الفارغة)
            keyboard = []
            all_fields = get_editable_fields_by_action_type(medical_action)
            
            for field_name, field_display in all_fields:
                current_value = context.user_data['current_report_data'].get(field_name, "")
                
                # عرض جميع الحقول مع قيمتها الحالية
                if not current_value or str(current_value).strip() == "" or current_value == "لا يوجد":
                    display_value = "⚠️ فارغ"
                elif len(str(current_value)) > 15:
                    display_value = str(current_value)[:12] + "..."
                else:
                    display_value = str(current_value)
                
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
            translator = s.query(Translator).filter_by(id=report.translator_id).first() if report.translator_id else None
            
            # تجهيز بيانات البث - جميع الحقول
            followup_display = 'لا يوجد'
            if report.followup_date:
                followup_display = report.followup_date.strftime('%Y-%m-%d')
                if report.followup_time:
                    time_12h = format_time_12h(report.followup_time)
                    followup_display += f" - {time_12h}"
            
            broadcast_data = {
                'report_id': report_id,
                'report_date': report.report_date.strftime('%Y-%m-%d %H:%M') if report.report_date else datetime.now().strftime('%Y-%m-%d %H:%M'),
                'patient_name': patient.full_name if patient else 'غير معروف',
                'hospital_name': hospital.name if hospital else 'غير معروف',
                'department_name': department.name if department else 'غير محدد',
                'doctor_name': doctor.full_name if doctor else 'لم يتم التحديد',
                'medical_action': report.medical_action or 'غير محدد',
                # جميع الحقول النصية
                'complaint_text': report.complaint_text or '',
                'diagnosis': report.diagnosis or '',
                'doctor_decision': report.doctor_decision or '',
                'decision': report.doctor_decision or '',  # نسخة للتوافق
                'treatment_plan': report.treatment_plan or '',
                'notes': report.notes or '',
                'medications': report.medications or '',
                'case_status': report.case_status or '',
                # موعد العودة
                'followup_date': followup_display,
                'followup_time': report.followup_time or '',
                'followup_reason': report.followup_reason or 'لا يوجد',
                # حقول خاصة
                'room_number': getattr(report, 'room_number', '') or '',
                'operation_name_en': getattr(report, 'operation_name_en', '') or '',
                'success_rate': getattr(report, 'success_rate', '') or '',
                'benefit_rate': getattr(report, 'benefit_rate', '') or '',
                # حقول تأجيل الموعد
                'app_reschedule_reason': getattr(report, 'app_reschedule_reason', '') or '',
                'app_reschedule_return_date': getattr(report, 'app_reschedule_return_date', '') or '',
                'app_reschedule_return_reason': getattr(report, 'app_reschedule_return_reason', '') or '',
                # حقول الأشعة
                'radiology_type': getattr(report, 'radiology_type', '') or '',
                'radiology_delivery_date': getattr(report, 'radiology_delivery_date', '') or '',
                # المترجم
                'translator_name': translator.full_name if translator else 'غير محدد',
                'is_edit': True  # علامة أن هذا تقرير معدل
            }
            
            # بث التقرير
            try:
                from services.broadcast_service import broadcast_new_report
                await broadcast_new_report(context.bot, broadcast_data)
                
                await query.edit_message_text(
                    f"✅ **تم إعادة نشر التقرير بنجاح!**\n\n"
                    f"📋 **رقم التقرير:** #{report_id}\n"
                    f"👤 **المريض:** {patient.full_name if patient else 'غير معروف'}\n"
                    f"📅 **وقت النشر:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"تم إرسال التقرير المعدل لجميع المستخدمين.",
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
            "واصل", "عزالدين", "عبدالسلام", "يحيى العنسي", "ياسر"]


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
        time_str = query.data.split(":")[-1]
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
    
    text = "📝 **تأكيد التعديل**\n\n"
    text += f"**الحقل:** موعد العودة\n\n"
    text += f"**القيمة القديمة:**\n{old_display}\n\n"
    text += f"**القيمة الجديدة:**\n{new_display}\n\n"
    text += "هل تريد حفظ ونشر التعديل؟"
    
    keyboard = [
        [InlineKeyboardButton("📢 حفظ ونشر", callback_data="edit_save_and_publish")],
        [InlineKeyboardButton("💾 حفظ فقط", callback_data="edit_confirm_save")],
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
        'followup_date': 'موعد العودة',
        'followup_reason': 'سبب العودة'
    }
    
    field_display = field_names.get(field_name, field_name)
    old_value = context.user_data['current_report_data'].get(field_name, "لا يوجد")
    
    # عرض الملخص
    text = "📝 **تأكيد التعديل**\n\n"
    text += f"**الحقل:** {field_display}\n\n"
    text += f"**القيمة القديمة:**\n{old_value}\n\n"
    text += f"**القيمة الجديدة:**\n{new_value}\n\n"
    text += "هل تريد حفظ ونشر التعديل؟"
    
    keyboard = [
        [InlineKeyboardButton("📢 حفظ ونشر", callback_data="edit_save_and_publish")],
        [InlineKeyboardButton("💾 حفظ فقط", callback_data="edit_confirm_save")],
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
        
        # تحديث البيانات المحفوظة
        context.user_data['current_report_data'].update({
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
            'translator_name': translator.full_name if translator else "غير محدد",
            'translator_id': report.translator_id,
        })
        
        # عرض بيانات التقرير مرة أخرى
        medical_action = context.user_data['current_report_data']['medical_action']
        
        # ✅ الحصول على الحقول المحددة لهذا النوع من الإجراء
        all_fields = get_editable_fields_by_action_type(medical_action)
        
        text = f"📋 **بيانات التقرير #{report_id}**\n\n"
        text += f"📅 **تاريخ التقرير:** {context.user_data['current_report_data']['report_date']}\n"
        text += f"👤 **اسم المريض:** {context.user_data['current_report_data']['patient_name']}\n"
        text += f"🏥 **المستشفى:** {context.user_data['current_report_data']['hospital_name']}\n"
        text += f"🏷️ **القسم:** {context.user_data['current_report_data']['department_name']}\n"
        text += f"👨‍⚕️ **الطبيب:** {context.user_data['current_report_data']['doctor_name']}\n"
        text += f"⚕️ **نوع الإجراء:** {medical_action}\n\n"
        text += "اختر الحقل الذي تريد تعديله:\n"
        
        # بناء الأزرار - جميع حقول هذا النوع من الإجراء (حتى الفارغة)
        keyboard = []
        for field_name, field_display in all_fields:
            current_value = context.user_data['current_report_data'].get(field_name, "")
            
            # عرض جميع الحقول مع قيمتها الحالية
            if not current_value or str(current_value).strip() == "" or current_value == "لا يوجد":
                display_value = "⚠️ فارغ"
            elif len(str(current_value)) > 15:
                display_value = str(current_value)[:12] + "..."
            else:
                display_value = str(current_value)
            
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
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
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
                # منع إدخال النص - يجب استخدام التقويم فقط
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, 
                    lambda u, c: u.message.reply_text(
                        "⚠️ **لا يمكن إدخال التاريخ يدوياً**\n\n"
                        "✅ **يرجى استخدام التقويم أعلاه لاختيار التاريخ**\n"
                        "اضغط على التاريخ المطلوب من التقويم.",
                        parse_mode=ParseMode.MARKDOWN
                    )
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
