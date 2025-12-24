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

# حالات المحادثة
SELECT_REPORT, SELECT_FIELD, EDIT_VALUE, CONFIRM_EDIT, EDIT_DATE_CALENDAR, EDIT_DATE_TIME = range(6)

def medical_action_to_flow_type(medical_action):
    """تحويل medical_action إلى flow_type"""
    if not medical_action:
        return "new_consult"
    
    action_lower = medical_action.lower().strip()
    
    # خريطة التحويل
    action_to_flow = {
        "استشارة جديدة": "new_consult",
        "متابعة في الرقود": "followup",
        "مراجعة / عودة دورية": "followup",
        "استشارة مع قرار عملية": "surgery_consult",
        "طوارئ": "emergency",
        "عملية": "operation",
        "استشارة أخيرة": "final_consult",
        "ترقيد": "admission",
        "خروج من المستشفى": "discharge",
        "علاج طبيعي": "rehab_physical",
        "أجهزة تعويضية": "rehab_device",
        "أشعة وفحوصات": "radiology",
    }
    
    # البحث المباشر
    if medical_action in action_to_flow:
        return action_to_flow[medical_action]
    
    # البحث الجزئي
    for action_key, flow_type in action_to_flow.items():
        if action_key in medical_action or medical_action in action_key:
            return flow_type
    
    # البحث في النص الإنجليزي
    if "new consult" in action_lower or "new_consult" in action_lower:
        return "new_consult"
    elif "followup" in action_lower or "follow-up" in action_lower:
        return "followup"
    elif "surgery" in action_lower and "consult" in action_lower:
        return "surgery_consult"
    elif "emergency" in action_lower:
        return "emergency"
    elif "operation" in action_lower:
        return "operation"
    elif "final consult" in action_lower or "final_consult" in action_lower:
        return "final_consult"
    elif "admission" in action_lower:
        return "admission"
    elif "discharge" in action_lower:
        return "discharge"
    elif "rehab" in action_lower and "physical" in action_lower:
        return "rehab_physical"
    elif "rehab" in action_lower and "device" in action_lower:
        return "rehab_device"
    elif "radiology" in action_lower:
        return "radiology"
    
    # افتراضي
    return "new_consult"

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

def get_editable_fields_by_action_type(medical_action):
    """تحديد الحقول القابلة للتعديل حسب نوع الإجراء"""
    if not medical_action:
        # إذا لم يكن هناك نوع إجراء محدد، نعرض الحقول الأساسية
        return [
            ('complaint_text', '💬 شكوى المريض'),
            ('doctor_decision', '📝 قرار الطبيب'),
            ('diagnosis', '🔬 التشخيص الطبي'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
        ]
    
    action_lower = medical_action.lower().strip()
    
    # استشارة جديدة
    if 'استشارة جديدة' in medical_action or 'new consult' in action_lower:
        return [
            ('complaint_text', '💬 شكوى المريض'),
            ('diagnosis', '🔬 التشخيص الطبي'),
            ('doctor_decision', '📝 قرار الطبيب'),
            ('notes', '🧪 الفحوصات والأشعة'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
        ]
    
    # استشارة مع قرار عملية
    elif 'استشارة مع قرار عملية' in medical_action or 'surgery consult' in action_lower:
        return [
            ('diagnosis', '🔬 التشخيص'),
            ('doctor_decision', '📝 قرار الطبيب وتفاصيل العملية'),
            ('notes', '📋 اسم العملية بالإنجليزي'),
            ('treatment_plan', '📊 نسبة نجاح العملية'),
            ('medications', '🧪 الفحوصات والأشعة'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
        ]
    
    # استشارة أخيرة
    elif 'استشارة أخيرة' in medical_action or 'final consult' in action_lower:
        return [
            ('diagnosis', '🔬 التشخيص'),
            ('doctor_decision', '📝 قرار الطبيب'),
            ('treatment_plan', '📋 التوصيات'),
        ]
    
    # طوارئ
    elif 'طوارئ' in medical_action or 'emergency' in action_lower:
        return [
            ('complaint_text', '💬 شكوى المريض'),
            ('diagnosis', '🔬 التشخيص الطبي'),
            ('doctor_decision', '📝 قرار الطبيب وماذا تم للحالة'),
            ('case_status', '🚨 حالة الطوارئ (خروج/ترقيد/عملية)'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
        ]
    
    # متابعة في الرقود
    elif 'متابعة في الرقود' in medical_action or 'followup' in action_lower:
        return [
            ('complaint_text', '💬 شكوى المريض'),
            ('diagnosis', '🔬 التشخيص الطبي'),
            ('doctor_decision', '📝 قرار الطبيب'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
        ]
    
    # عملية
    elif 'عملية' in medical_action or 'operation' in action_lower:
        return [
            ('complaint_text', '⚕️ تفاصيل العملية بالعربي'),
            ('notes', '🔤 اسم العملية بالإنجليزي'),
            ('doctor_decision', '📝 ملاحظات'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
        ]
    
    # علاج طبيعي وإعادة تأهيل
    elif 'علاج طبيعي' in medical_action or 'rehab' in action_lower:
        return [
            ('complaint_text', '🏃 تفاصيل العلاج الطبيعي'),
            ('notes', '🦾 تفاصيل الأجهزة التعويضية'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
        ]
    
    # ترقيد
    elif 'ترقيد' in medical_action or 'admission' in action_lower:
        return [
            ('complaint_text', '🛏️ سبب الرقود'),
            ('notes', '🚪 رقم الغرفة'),
            ('doctor_decision', '📝 ملاحظات'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
        ]
    
    # خروج من المستشفى
    elif 'خروج' in medical_action or 'discharge' in action_lower:
        return [
            ('diagnosis', '🔬 التشخيص النهائي'),
            ('doctor_decision', '📝 قرار الطبيب'),
            ('treatment_plan', '💊 الأدوية الموصى بها'),
            ('notes', '📋 التعليمات'),
        ]
    
    # الحقول الافتراضية
    else:
        return [
            ('complaint_text', '💬 شكوى المريض'),
            ('doctor_decision', '📝 قرار الطبيب'),
            ('diagnosis', '🔬 التشخيص الطبي'),
            ('followup_date', '📅 موعد العودة'),
            ('followup_reason', '✍️ سبب العودة'),
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
            # البحث عن المترجم
            translator = s.query(Translator).filter_by(tg_user_id=user.id).first()
            
            if not translator:
                await update.message.reply_text(
                    "⚠️ **لم يتم العثور على بيانات المترجم**\n\n"
                    "يرجى التواصل مع الإدارة لتسجيل بياناتك.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return ConversationHandler.END
            
            # البحث عن تقارير اليوم فقط
            today = date.today()
            today_start = datetime.combine(today, datetime.min.time())
            today_end = datetime.combine(today, datetime.max.time())

            reports = s.query(Report).filter(
                Report.translator_id == translator.id,
                Report.report_date >= today_start,
                Report.report_date <= today_end
            ).order_by(Report.report_date.desc()).all()

            if not reports:
                await update.message.reply_text(
                    "📋 **لا توجد تقارير لليوم**\n\n"
                    f"📅 **التاريخ:** {today.strftime('%Y-%m-%d')}\n\n"
                    "لم تقم بإضافة أي تقارير اليوم.\n"
                    "استخدم زر '📝 إضافة تقرير جديد' لإضافة تقرير.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return ConversationHandler.END

            # حفظ اسم المترجم
            context.user_data['translator_name'] = translator.full_name
            context.user_data['translator_id'] = translator.id

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

def parse_report_to_report_tmp(report, flow_type):
    """تحويل بيانات التقرير من قاعدة البيانات إلى report_tmp"""
    import re
    from datetime import datetime
    
    report_tmp = {
        "patient_name": None,
        "hospital_name": None,
        "department_name": None,
        "doctor_name": None,
        "report_date": report.report_date,
        "medical_action": report.medical_action,
        "current_flow": flow_type,
        "translator_id": report.translator_id,
    }
    
    # جلب البيانات الأساسية
    with SessionLocal() as s:
        patient = s.query(Patient).filter_by(id=report.patient_id).first()
        hospital = s.query(Hospital).filter_by(id=report.hospital_id).first()
        department = s.query(Department).filter_by(id=report.department_id).first() if report.department_id else None
        doctor = s.query(Doctor).filter_by(id=report.doctor_id).first() if report.doctor_id else None
        
        report_tmp["patient_name"] = patient.full_name if patient else ""
        report_tmp["hospital_name"] = hospital.name if hospital else ""
        report_tmp["department_name"] = department.name if department else ""
        report_tmp["doctor_name"] = doctor.full_name if doctor else ""
    
    # تحليل الحقول حسب flow_type
    if flow_type in ["new_consult", "followup", "emergency"]:
        report_tmp["complaint"] = report.complaint_text or ""
        
        # تحليل doctor_decision لفصل التشخيص والقرار
        decision_text = report.doctor_decision or ""
        if "التشخيص:" in decision_text:
            parts = decision_text.split("التشخيص:")
            if len(parts) > 1:
                diagnosis_part = parts[1].split("قرار الطبيب:")[0].strip()
                report_tmp["diagnosis"] = diagnosis_part
                if "قرار الطبيب:" in decision_text:
                    decision_part = decision_text.split("قرار الطبيب:")[1].strip()
                    report_tmp["decision"] = decision_part
        else:
            report_tmp["diagnosis"] = ""
            report_tmp["decision"] = decision_text
        
        if flow_type == "new_consult":
            # استخراج الفحوصات
            if "الفحوصات المطلوبة:" in decision_text:
                tests_part = decision_text.split("الفحوصات المطلوبة:")[1].strip()
                report_tmp["tests"] = tests_part
            else:
                report_tmp["tests"] = ""
        
        if flow_type == "emergency":
            # استخراج وضع الحالة
            if "وضع الحالة:" in decision_text:
                status_part = decision_text.split("وضع الحالة:")[1].strip()
                report_tmp["status"] = status_part
            else:
                report_tmp["status"] = ""
    
    elif flow_type == "surgery_consult":
        decision_text = report.doctor_decision or ""
        
        # استخراج التشخيص
        if "التشخيص:" in decision_text:
            report_tmp["diagnosis"] = decision_text.split("التشخيص:")[1].split("قرار الطبيب:")[0].strip()
        else:
            report_tmp["diagnosis"] = ""
        
        # استخراج قرار الطبيب
        if "قرار الطبيب:" in decision_text:
            decision_part = decision_text.split("قرار الطبيب:")[1]
            if "اسم العملية" in decision_part:
                decision_part = decision_part.split("اسم العملية")[0].strip()
            report_tmp["decision"] = decision_part.strip()
        else:
            report_tmp["decision"] = ""
        
        # استخراج اسم العملية
        if "اسم العملية بالإنجليزي:" in decision_text:
            report_tmp["operation_name_en"] = decision_text.split("اسم العملية بالإنجليزي:")[1].split("نسبة نجاح")[0].strip()
        else:
            report_tmp["operation_name_en"] = ""
        
        # استخراج نسبة النجاح
        if "نسبة نجاح العملية:" in decision_text:
            report_tmp["success_rate"] = decision_text.split("نسبة نجاح العملية:")[1].split("نسبة الاستفادة")[0].strip()
        else:
            report_tmp["success_rate"] = ""
        
        # استخراج نسبة الاستفادة
        if "نسبة الاستفادة من العملية:" in decision_text:
            report_tmp["benefit_rate"] = decision_text.split("نسبة الاستفادة من العملية:")[1].split("الفحوصات")[0].strip()
        else:
            report_tmp["benefit_rate"] = ""
        
        # استخراج الفحوصات
        if "الفحوصات المطلوبة:" in decision_text:
            report_tmp["tests"] = decision_text.split("الفحوصات المطلوبة:")[1].strip()
        else:
            report_tmp["tests"] = ""
    
    elif flow_type == "operation":
        decision_text = report.doctor_decision or ""
        
        # استخراج تفاصيل العملية
        if "تفاصيل العملية:" in decision_text:
            report_tmp["operation_details"] = decision_text.split("تفاصيل العملية:")[1].split("اسم العملية")[0].strip()
        else:
            report_tmp["operation_details"] = ""
        
        # استخراج اسم العملية
        if "اسم العملية بالإنجليزي:" in decision_text:
            report_tmp["operation_name_en"] = decision_text.split("اسم العملية بالإنجليزي:")[1].split("ملاحظات")[0].strip()
        else:
            report_tmp["operation_name_en"] = ""
        
        # استخراج الملاحظات
        if "ملاحظات:" in decision_text:
            report_tmp["notes"] = decision_text.split("ملاحظات:")[1].strip()
        else:
            report_tmp["notes"] = ""
    
    elif flow_type == "final_consult":
        decision_text = report.doctor_decision or ""
        
        # استخراج التشخيص النهائي
        if "التشخيص النهائي:" in decision_text:
            report_tmp["diagnosis"] = decision_text.split("التشخيص النهائي:")[1].split("قرار الطبيب")[0].strip()
        else:
            report_tmp["diagnosis"] = ""
        
        # استخراج قرار الطبيب
        if "قرار الطبيب:" in decision_text:
            report_tmp["decision"] = decision_text.split("قرار الطبيب:")[1].split("التوصيات")[0].strip()
        else:
            report_tmp["decision"] = ""
        
        # استخراج التوصيات
        if "التوصيات الطبية:" in decision_text:
            report_tmp["recommendations"] = decision_text.split("التوصيات الطبية:")[1].strip()
        else:
            report_tmp["recommendations"] = ""
    
    elif flow_type == "admission":
        decision_text = report.doctor_decision or ""
        
        # استخراج سبب الرقود
        if "سبب الرقود:" in decision_text:
            report_tmp["admission_reason"] = decision_text.split("سبب الرقود:")[1].split("رقم الغرفة")[0].strip()
        else:
            report_tmp["admission_reason"] = ""
        
        # استخراج رقم الغرفة
        if "رقم الغرفة:" in decision_text:
            report_tmp["room_number"] = decision_text.split("رقم الغرفة:")[1].split("ملاحظات")[0].strip()
        else:
            report_tmp["room_number"] = ""
        
        # استخراج الملاحظات
        if "ملاحظات:" in decision_text:
            report_tmp["notes"] = decision_text.split("ملاحظات:")[1].strip()
        else:
            report_tmp["notes"] = ""
    
    elif flow_type == "discharge":
        decision_text = report.doctor_decision or ""
        
        # محاولة تحديد نوع الخروج
        if "ملخص الرقود:" in decision_text:
            report_tmp["discharge_type"] = "admission"
            report_tmp["admission_summary"] = decision_text.split("ملخص الرقود:")[1].strip()
        elif "تفاصيل العملية:" in decision_text:
            report_tmp["discharge_type"] = "operation"
            report_tmp["operation_details"] = decision_text.split("تفاصيل العملية:")[1].split("اسم العملية")[0].strip()
            if "اسم العملية بالإنجليزي:" in decision_text:
                report_tmp["operation_name_en"] = decision_text.split("اسم العملية بالإنجليزي:")[1].strip()
        else:
            report_tmp["discharge_type"] = "admission"
    
    elif flow_type == "rehab_physical":
        decision_text = report.doctor_decision or ""
        if "تفاصيل الجلسة:" in decision_text:
            report_tmp["therapy_details"] = decision_text.split("تفاصيل الجلسة:")[1].strip()
        else:
            report_tmp["therapy_details"] = ""
    
    elif flow_type == "rehab_device":
        decision_text = report.doctor_decision or ""
        if "تفاصيل الجهاز:" in decision_text:
            report_tmp["device_details"] = decision_text.split("تفاصيل الجهاز:")[1].strip()
        else:
            report_tmp["device_details"] = ""
    
    elif flow_type == "radiology":
        decision_text = report.doctor_decision or ""
        if "نوع الأشعة والفحوصات:" in decision_text:
            report_tmp["radiology_type"] = decision_text.split("نوع الأشعة والفحوصات:")[1].strip()
        else:
            report_tmp["radiology_type"] = ""
    
    # تاريخ العودة وسبب العودة (مشترك)
    report_tmp["followup_date"] = report.followup_date
    report_tmp["followup_reason"] = report.followup_reason or ""
    
    # استخراج وقت العودة من followup_date إذا كان موجوداً
    if report.followup_date:
        report_tmp["followup_time"] = report.followup_date.strftime("%H:%M") if hasattr(report.followup_date, 'strftime') else ""
    else:
        report_tmp["followup_time"] = ""
    
    return report_tmp

async def handle_report_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار التقرير - إعادة المستخدم إلى نفس الخطوات"""
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
            
            # التحقق من أن التقرير يخص المترجم
            if report.translator_id != context.user_data.get('translator_id'):
                await query.edit_message_text("⚠️ **خطأ:** لا يمكنك تعديل هذا التقرير")
                return ConversationHandler.END
            
            # تحديد flow_type من medical_action
            flow_type = medical_action_to_flow_type(report.medical_action)
            logger.info(f"✅ Flow type determined: {flow_type} from medical_action: {report.medical_action}")
            
            # تحويل بيانات التقرير إلى report_tmp
            report_tmp = parse_report_to_report_tmp(report, flow_type)
            context.user_data['report_tmp'] = report_tmp
            context.user_data['report_tmp']['is_edit_mode'] = True
            context.user_data['report_tmp']['edit_report_id'] = report_id
            
            # إنشاء current_report_data من بيانات التقرير (للتوافق مع الكود القديم)
            patient = s.query(Patient).filter_by(id=report.patient_id).first()
            hospital = s.query(Hospital).filter_by(id=report.hospital_id).first()
            department = s.query(Department).filter_by(id=report.department_id).first() if report.department_id else None
            doctor = s.query(Doctor).filter_by(id=report.doctor_id).first() if report.doctor_id else None
            
            context.user_data['current_report_data'] = {
                'report_id': report_id,
                'report_date': report.report_date.strftime('%Y-%m-%d %H:%M') if report.report_date else '',
                'patient_name': patient.full_name if patient else '',
                'hospital_name': hospital.name if hospital else '',
                'department_name': department.name if department else '',
                'doctor_name': doctor.full_name if doctor else '',
                'medical_action': report.medical_action or '',
                'complaint_text': report.complaint_text or '',
                'doctor_decision': report.doctor_decision or '',
                'diagnosis': report.diagnosis or '',
                'treatment_plan': report.treatment_plan or '',
                'medications': report.medications or '',
                'notes': report.notes or '',
                'case_status': report.case_status or '',
                'followup_date': report.followup_date.strftime('%Y-%m-%d') if report.followup_date else '',
                'followup_time': report.followup_time or '',
                'followup_reason': report.followup_reason or '',
            }
            
            logger.info(f"✅ تم تحميل بيانات التقرير في report_tmp: {list(report_tmp.keys())}")
            logger.info(f"✅ تم إنشاء current_report_data: {list(context.user_data['current_report_data'].keys())}")
            
            # استيراد دالة start_report من user_reports_add_new_system
            from bot.handlers.user.user_reports_add_new_system import start_report
            
            # إعادة المستخدم إلى نفس الخطوات
            await query.edit_message_text(
                f"✏️ **تعديل التقرير #{report_id}**\n\n"
                f"📋 **نوع الإجراء:** {report.medical_action}\n"
                f"🔄 **جارٍ إعادة تحميل التقرير...**",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # بدء نفس التدفق
            # نحتاج إلى إعادة المستخدم إلى الخطوة المناسبة حسب flow_type
            # سنستخدم start_report ولكن مع report_tmp محمّل مسبقاً
            
            # إرسال رسالة جديدة لبدء التدفق
            await query.message.reply_text(
                "✏️ **تعديل التقرير**\n\n"
                "تم تحميل بيانات التقرير. سيتم إعادة عرض الخطوات للتعديل.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # بدء التدفق من البداية (لكن مع البيانات المحمّلة)
            # سنستخدم ConversationHandler الموجود في user_reports_add_new_system
            # لكن نحتاج إلى إعادة توجيه المستخدم إلى الخطوة المناسبة
            
            # للآن، سنعرض الملخص النهائي مباشرة مع إمكانية التعديل
            from bot.handlers.user.user_reports_add_new_system import show_final_summary
            
            await show_final_summary(query.message, context, flow_type)
            
            # إرجاع state التأكيد المناسب
            from bot.handlers.user.user_reports_add_new_system import get_confirm_state
            confirm_state = get_confirm_state(flow_type)
            context.user_data['_conversation_state'] = confirm_state
            
            logger.info(f"✅ تم تحميل التقرير وإعادة عرضه للتحرير - flow_type: {flow_type}")
            return confirm_state
            
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
            'followup_reason': 'سبب العودة'
        }
        
        field_display = field_names.get(field_name, field_name)
        
        # الحصول على القيمة الحالية من current_report_data أو report_tmp
        current_report_data = context.user_data.get('current_report_data', {})
        report_tmp = context.user_data.get('report_tmp', {})
        
        if field_name in current_report_data:
            current_value = current_report_data.get(field_name, "لا يوجد")
        else:
            # محاولة الحصول من report_tmp
            # تحويل field_name إلى field_key في report_tmp
            field_key_mapping = {
                "complaint_text": "complaint",
                "doctor_decision": "decision",
                "diagnosis": "diagnosis",
                "treatment_plan": "treatment_plan",
                "medications": "medications",
                "notes": "notes",
                "case_status": "status",
                "followup_date": "followup_date",
                "followup_reason": "followup_reason",
            }
            field_key = field_key_mapping.get(field_name, field_name)
            current_value = report_tmp.get(field_key, "لا يوجد")
        
        # إذا كان الحقل هو التاريخ، نعرض التقويم
        if field_name == "followup_date":
            text = f"📅 **تعديل {field_display}**\n\n"
            if current_value and current_value != "لا يوجد":
                followup_time = current_report_data.get('followup_time', '') or report_tmp.get('followup_time', '')
                if followup_time:
                    text += f"**القيمة الحالية:** {current_value} الساعة {followup_time}\n\n"
                else:
                    text += f"**القيمة الحالية:** {current_value}\n\n"
            else:
                text += "**القيمة الحالية:** لا يوجد موعد\n\n"
            text += "اختر التاريخ من التقويم:"
            
            # عرض التقويم
            keyboard = create_quick_date_buttons("edit_followup")
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="edit_back_to_fields")])
            keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="edit_cancel")])
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"✅ تم عرض حقل التعديل: {field_name} (تاريخ)")
            return EDIT_DATE_CALENDAR
        else:
            text = f"✏️ **تعديل {field_display}**\n\n"
            text += f"**القيمة الحالية:**\n{current_value}\n\n"
            text += "أرسل القيمة الجديدة:"
            
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
    text += "هل تريد حفظ التعديل؟"
    
    keyboard = [
        [InlineKeyboardButton("✅ تأكيد الحفظ", callback_data="edit_confirm_save")],
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
    text += "هل تريد حفظ التعديل؟"
    
    keyboard = [
        [InlineKeyboardButton("✅ تأكيد الحفظ", callback_data="edit_confirm_save")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="edit_back_to_fields")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="edit_cancel")]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return CONFIRM_EDIT

async def handle_confirm_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة تأكيد الحفظ"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "edit_cancel":
        await query.edit_message_text("❌ **تم إلغاء عملية التعديل**")
        return ConversationHandler.END
    
    if query.data == "edit_back_to_fields":
        return await show_field_selection(query, context)
    
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
        
        # عرض بيانات التقرير مرة أخرى
        medical_action = context.user_data['current_report_data']['medical_action']
        editable_fields = get_editable_fields_by_action_type(medical_action)
        
        text = f"📋 **بيانات التقرير #{report_id}**\n\n"
        text += f"📅 **تاريخ التقرير:** {context.user_data['current_report_data']['report_date']}\n"
        text += f"👤 **اسم المريض:** {context.user_data['current_report_data']['patient_name']}\n"
        text += f"🏥 **المستشفى:** {context.user_data['current_report_data']['hospital_name']}\n"
        text += f"🏷️ **القسم:** {context.user_data['current_report_data']['department_name']}\n"
        text += f"👨‍⚕️ **الطبيب:** {context.user_data['current_report_data']['doctor_name']}\n"
        text += f"⚕️ **نوع الإجراء:** {medical_action}\n\n"
        text += "اختر الحقل الذي تريد تعديله:"
        
        # بناء الأزرار حسب نوع الإجراء
        keyboard = []
        for field_name, field_display in editable_fields:
            keyboard.append([InlineKeyboardButton(field_display, callback_data=f"edit_field:{field_name}")])
        
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
    with SessionLocal() as s:
        translator_id = context.user_data.get('translator_id')
        
        # البحث عن تقارير اليوم فقط
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        reports = s.query(Report).filter(
            Report.translator_id == translator_id,
            Report.report_date >= today_start,
            Report.report_date <= today_end
        ).order_by(Report.report_date.desc()).all()
        
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

async def handle_edit_from_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر 'مراجعة وتعديل التقرير' من الملخص"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        query = update.callback_query
        if not query:
            logger.error("❌ handle_edit_from_summary: No query found")
            return ConversationHandler.END
        
        await query.answer()
        
        # استخراج flow_type من callback_data
        parts = query.data.split(":")
        flow_type = parts[1] if len(parts) > 1 else None
        
        # الحصول على flow_type من report_tmp إذا لم يكن في callback_data
        data = context.user_data.get("report_tmp", {})
        if not flow_type:
            flow_type = data.get("current_flow")
        
        logger.info(f"✏️ Edit button clicked - flow_type: {flow_type}")
        
        # استخدام handle_edit_before_save من user_reports_add_new_system
        from bot.handlers.user.user_reports_add_new_system import handle_edit_before_save
        result = await handle_edit_before_save(query, context, flow_type)
        
        # handle_edit_before_save يرجع state، لكن نحن في ConversationHandler مختلف
        # لذلك سنعود إلى SELECT_FIELD state الخاص بـ user_reports_edit
        return SELECT_FIELD
        
    except Exception as e:
        logger.error(f"❌ خطأ في handle_edit_from_summary: {e}", exc_info=True)
        try:
            if query:
                await query.answer("⚠️ حدث خطأ أثناء فتح المراجعة", show_alert=True)
        except:
            pass
        return ConversationHandler.END

async def handle_publish_from_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر 'نشر التقرير' من الملخص"""
    from bot.handlers.user.user_reports_add_new_system import handle_final_confirm
    return await handle_final_confirm(update, context)

async def handle_back_to_summary_from_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر 'رجوع للملخص' من شاشة المراجعة"""
    from bot.handlers.user.user_reports_add_new_system import handle_final_confirm
    return await handle_final_confirm(update, context)

async def handle_cancel_from_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر 'إلغاء' من الملخص"""
    from bot.handlers.user.user_reports_add_new_system import handle_cancel_navigation
    return await handle_cancel_navigation(update, context)

def map_field_key_to_db_field(field_key):
    """تحويل field_key من report_tmp إلى اسم الحقل في قاعدة البيانات"""
    field_mapping = {
        "complaint": "complaint_text",
        "diagnosis": "diagnosis",
        "decision": "doctor_decision",
        "tests": "notes",
        "status": "case_status",
        "followup_date": "followup_date",
        "followup_reason": "followup_reason",
        "treatment_plan": "treatment_plan",
        "medications": "medications",
        "notes": "notes",
        "case_status": "case_status",
        # الحقول الأساسية
        "patient_name": "patient_name",  # سيتم التعامل معها بشكل خاص
        "hospital_name": "hospital_name",  # سيتم التعامل معها بشكل خاص
        "department_name": "department_name",  # سيتم التعامل معها بشكل خاص
        "doctor_name": "doctor_name",  # سيتم التعامل معها بشكل خاص
        "report_date": "report_date",  # سيتم التعامل معها بشكل خاص
    }
    return field_mapping.get(field_key, field_key)

async def handle_edit_field_from_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار حقل من قائمة التعديل (من show_edit_fields_menu)"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        query = update.callback_query
        if not query:
            return ConversationHandler.END
        
        await query.answer()
        
        # callback_data format: "edit_field:{flow_type}:{field_key}"
        parts = query.data.split(":")
        if len(parts) < 3:
            await query.edit_message_text("❌ خطأ في البيانات")
            return ConversationHandler.END
        
        flow_type = parts[1]
        field_key = parts[2]  # مثل "complaint", "diagnosis", "decision"
        
        logger.info(f"✏️ handle_edit_field_from_menu: flow_type={flow_type}, field_key={field_key}")
        
        # تحويل field_key إلى اسم الحقل في قاعدة البيانات
        db_field_name = map_field_key_to_db_field(field_key)
        
        # حفظ معلومات التعديل
        context.user_data["edit_field_key"] = field_key
        context.user_data["edit_flow_type"] = flow_type
        context.user_data["edit_field"] = db_field_name
        
        # الحصول على القيمة الحالية من report_tmp أو current_report_data
        report_tmp = context.user_data.get("report_tmp", {})
        current_report_data = context.user_data.get("current_report_data", {})
        
        # محاولة الحصول على القيمة من report_tmp أولاً، ثم من current_report_data
        if field_key in report_tmp:
            current_value = report_tmp.get(field_key)
        else:
            # تحويل field_key إلى db_field_name للحصول على القيمة من current_report_data
            db_field_name = map_field_key_to_db_field(field_key)
            current_value = current_report_data.get(db_field_name, "غير محدد")
        
        # إذا كان الحقل من الحقول الأساسية (patient_name, hospital_name, etc.)
        # نحتاج إلى معالجة خاصة
        if field_key in ["patient_name", "hospital_name", "department_name", "doctor_name", "report_date"]:
            await query.edit_message_text(
                f"⚠️ **لا يمكن تعديل هذا الحقل من هنا**\n\n"
                f"الحقل '{field_key}' يحتاج إلى تعديل من خلال واجهة خاصة.\n\n"
                f"يرجى استخدام زر '🔙 رجوع' للرجوع إلى قائمة الحقول.",
                parse_mode="Markdown"
            )
            return SELECT_FIELD
        
        # إذا كان الحقل هو التاريخ، نعرض التقويم
        if field_key == "followup_date":
            # استخدام handle_field_selection مع callback_data معدّل
            # إنشاء callback_data جديد بالصيغة المتوقعة
            query.data = f"edit_field:{db_field_name}"
            return await handle_field_selection(update, context)
        
        # للحقول النصية الأخرى
        # عرض واجهة التعديل
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
        
        field_display = field_names.get(db_field_name, db_field_name)
        
        # تنسيق القيمة الحالية للعرض
        if isinstance(current_value, datetime):
            current_value_display = current_value.strftime('%Y-%m-%d %H:%M')
        elif current_value and current_value != "غير محدد":
            current_value_display = str(current_value)
        else:
            current_value_display = "لا يوجد"
        
        text = f"✏️ **تعديل {field_display}**\n\n"
        text += f"**القيمة الحالية:**\n{current_value_display}\n\n"
        text += "أرسل القيمة الجديدة:"
        
        keyboard = [
            [InlineKeyboardButton("🔙 رجوع", callback_data=f"review:{flow_type}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ]
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info(f"✅ تم عرض حقل التعديل: {field_key} -> {db_field_name}")
        return EDIT_VALUE
        
    except Exception as e:
        logger.error(f"❌ خطأ في handle_edit_field_from_menu: {e}", exc_info=True)
        try:
            if query:
                await query.answer("⚠️ حدث خطأ", show_alert=True)
                await query.edit_message_text(
                    "❌ **حدث خطأ أثناء تحميل الحقل**\n\n"
                    "يرجى المحاولة مرة أخرى.",
                    parse_mode=ParseMode.MARKDOWN
                )
        except:
            pass
        return ConversationHandler.END

async def handle_review_from_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر 'رجوع' من قائمة الحقول (العودة إلى الملخص)"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        query = update.callback_query
        if not query:
            return ConversationHandler.END
        
        await query.answer()
        
        # callback_data format: "review:{flow_type}"
        parts = query.data.split(":")
        flow_type = parts[1] if len(parts) > 1 else None
        
        if not flow_type:
            data = context.user_data.get("report_tmp", {})
            flow_type = data.get("current_flow")
        
        logger.info(f"🔙 Back to summary - flow_type: {flow_type}")
        
        # إعادة عرض الملخص
        from bot.handlers.user.user_reports_add_new_system import show_final_summary
        await show_final_summary(query.message, context, flow_type)
        
        # إرجاع CONFIRM_EDIT state (أو يمكن إرجاع state آخر مناسب)
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"❌ خطأ في handle_review_from_menu: {e}", exc_info=True)
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
                CallbackQueryHandler(handle_date_calendar, pattern="^edit_cancel$")
            ],
            EDIT_DATE_TIME: [
                CallbackQueryHandler(handle_date_time_selection, pattern="^edit_time:"),
                CallbackQueryHandler(handle_date_time_selection, pattern="^edit_back_to_fields$"),
                CallbackQueryHandler(handle_date_time_selection, pattern="^edit_cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_value)
            ],
            CONFIRM_EDIT: [
                CallbackQueryHandler(handle_confirm_edit)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ إلغاء العملية الحالية$"), cancel_edit),
            CallbackQueryHandler(handle_report_selection, pattern="^edit_cancel$"),
            # معالجة callbacks من show_final_summary (عند التعديل من الملخص)
            CallbackQueryHandler(handle_edit_from_summary, pattern="^edit:"),
            CallbackQueryHandler(handle_publish_from_summary, pattern="^publish:"),
            CallbackQueryHandler(handle_back_to_summary_from_edit, pattern="^back_to_summary:"),
            CallbackQueryHandler(handle_cancel_from_summary, pattern="^nav:cancel"),
            # معالجة callbacks من show_edit_fields_menu (عند التعديل من قائمة الحقول)
            CallbackQueryHandler(handle_edit_field_from_menu, pattern="^edit_field:"),
            CallbackQueryHandler(handle_review_from_menu, pattern="^review:")
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )
    
    app.add_handler(conv_handler)
