# ================================================
# bot/handlers/user/user_reports_delete.py
# حذف التقارير المنشورة - للمستخدمين
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
from bot.keyboards import user_main_kb
from sqlalchemy import or_, and_
import logging
import os

logger = logging.getLogger(__name__)

# حالات المحادثة
SELECT_REPORT, CONFIRM_DELETE = range(2)

# إعدادات المجموعة
try:
    from config.settings import REPORTS_GROUP_ID
except (ImportError, AttributeError):
    REPORTS_GROUP_ID = os.getenv("REPORTS_GROUP_ID", "")


async def start_delete_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بداية عملية حذف التقارير"""
    try:
        if not update.message:
            logger.error("❌ start_delete_reports: لا توجد رسالة في update")
            return ConversationHandler.END
            
        user = update.effective_user
        if not user:
            logger.error("❌ start_delete_reports: لا يوجد مستخدم في update")
            await update.message.reply_text("❌ **خطأ:** لم يتم التعرف على المستخدم")
            return ConversationHandler.END
            
        logger.info(f"🗑️ start_delete_reports: بدء عملية حذف التقارير للمستخدم {user.id}")
        
        if not SessionLocal:
            logger.error("❌ SessionLocal غير متاح")
            await update.message.reply_text("❌ **خطأ:** قاعدة البيانات غير متاحة حالياً")
            return ConversationHandler.END
        
        with SessionLocal() as s:
            today = date.today()
            today_start = datetime.combine(today, datetime.min.time())
            today_end = datetime.combine(today, datetime.max.time())

            # ✅ البحث بمعرف المستخدم الذي أنشأ التقرير (submitted_by_user_id)
            # هذا الحقل يتم حفظه عند إنشاء التقرير بغض النظر عن اسم المترجم المختار
            # للتقارير القديمة: البحث عن translator_id الذي يطابق tg_user_id للمستخدم الحالي
            translator = s.query(Translator).filter_by(tg_user_id=user.id).first()
            translator_id = translator.id if translator else None
            
            logger.info(f"🔍 البحث عن تقارير للحذف (اليوم):")
            logger.info(f"   - Telegram user.id: {user.id}")
            logger.info(f"   - translator found: {translator.full_name if translator else 'None'}")
            logger.info(f"   - translator_id: {translator_id}")

            # ✅ البحث عن التقارير:
            # 1. submitted_by_user_id == user.id (للتقارير الجديدة - الأفضل)
            # 2. translator_id == translator_id AND submitted_by_user_id IS NULL (للتقارير القديمة فقط)
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

            if not reports:
                await update.message.reply_text(
                    "📋 **لا توجد تقارير لليوم**\n\n"
                    "لم يتم العثور على أي تقارير قمت بنشرها اليوم.\n"
                    "استخدم زر '📝 إضافة تقرير جديد' لإضافة تقرير.",
                    reply_markup=user_main_kb(),
                    parse_mode=ParseMode.MARKDOWN
                )
                return ConversationHandler.END

            # حفظ معرف المستخدم للتحقق لاحقاً
            context.user_data['submitted_by_user_id'] = user.id

            # إنشاء قائمة بالتقارير
            text = "🗑️ **حذف التقارير**\n\n"
            text += f"عرض آخر {len(reports)} تقرير قمت بنشره:\n\n"
            text += "⚠️ **تحذير:** سيتم حذف التقرير من المجموعة وقاعدة البيانات.\n\n"
            text += "اختر التقرير الذي تريد حذفه من القائمة أدناه 👇\n"
            
            keyboard = []
            for report in reports:
                # جلب بيانات المريض
                patient = s.query(Patient).filter_by(id=report.patient_id).first()
                patient_name = patient.full_name if patient else "غير معروف"
                
                # جلب بيانات المستشفى
                hospital = s.query(Hospital).filter_by(id=report.hospital_id).first()
                hospital_name = hospital.name if hospital else "غير معروف"
                
                # تنسيق الوقت
                time_str = ""
                if report.report_date:
                    time_str = report.report_date.strftime("%H:%M")
                
                # نص الزر - مختصر
                button_text = f"#{report.id} {patient_name} ({time_str})"
                if len(button_text) > 50:
                    button_text = button_text[:47] + "..."
                
                keyboard.append([
                    InlineKeyboardButton(
                        button_text,
                        callback_data=f"delete_report:{report.id}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="delete_cancel")])
            
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            
            return SELECT_REPORT
            
    except Exception as e:
        logger.error(f"❌ خطأ في start_delete_reports: {e}", exc_info=True)
        error_message = "❌ **حدث خطأ**\n\nيرجى المحاولة مرة أخرى."
        try:
            if update.message:
                await update.message.reply_text(error_message, parse_mode=ParseMode.MARKDOWN)
            elif update.callback_query:
                await update.callback_query.message.reply_text(error_message, parse_mode=ParseMode.MARKDOWN)
        except Exception as send_error:
            logger.error(f"❌ خطأ في إرسال رسالة الخطأ: {send_error}")
        return ConversationHandler.END


async def handle_report_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار التقرير للحذف"""
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "delete_cancel":
            await query.edit_message_text(
                "❌ **تم إلغاء عملية الحذف**\n\n"
                "يمكنك البدء من جديد من القائمة الرئيسية.",
                parse_mode=ParseMode.MARKDOWN
            )
            await query.message.reply_text(
                "📋 اختر العملية المطلوبة:",
                reply_markup=user_main_kb()
            )
            return ConversationHandler.END
        
        # استخراج رقم التقرير
        report_id = int(query.data.split(':')[1])
        context.user_data['delete_report_id'] = report_id
        logger.info(f"🗑️ تم اختيار التقرير رقم {report_id} للحذف")
        
        with SessionLocal() as s:
            report = s.query(Report).filter_by(id=report_id).first()
            
            if not report:
                await query.edit_message_text("⚠️ **خطأ:** لم يتم العثور على التقرير")
                return ConversationHandler.END
            
            # ✅ التحقق من أن المستخدم هو من أنشأ التقرير
            # السماح بالحذف إذا كان submitted_by_user_id مطابقاً أو None (للتقارير القديمة)
            current_user_id = context.user_data.get('submitted_by_user_id')
            if not current_user_id and query.from_user:
                current_user_id = query.from_user.id
                context.user_data['submitted_by_user_id'] = current_user_id
            
            # التحقق: إذا كان submitted_by_user_id موجوداً في التقرير، يجب أن يطابق المستخدم الحالي
            # إذا كان None (تقرير قديم)، نتحقق من translator_id
            # ✅ قاعدة واحدة ترفض افتراضياً — انظر can_modify_report في
            # shared_auth.py. الفحص السابق كان يمرّ لمن لا صفَّ له في users.
            from bot.shared_auth import can_modify_report
            if not can_modify_report(report, current_user_id, s):
                await query.edit_message_text("⚠️ **خطأ:** لا يمكنك حذف هذا التقرير")
                return ConversationHandler.END
            
            # جلب بيانات التقرير الكاملة
            patient = s.query(Patient).filter_by(id=report.patient_id).first()
            hospital = s.query(Hospital).filter_by(id=report.hospital_id).first()
            department = s.query(Department).filter_by(id=report.department_id).first() if report.department_id else None
            doctor = s.query(Doctor).filter_by(id=report.doctor_id).first() if report.doctor_id else None
            
            # بناء نص التأكيد
            text = "⚠️ **تأكيد الحذف**\n\n"
            text += "هل أنت متأكد من حذف هذا التقرير؟\n\n"
            text += f"📋 **رقم التقرير:** {report_id}\n"
            text += f"👤 **المريض:** {patient.full_name if patient else 'غير معروف'}\n"
            text += f"🏥 **المستشفى:** {hospital.name if hospital else 'غير معروف'}\n"
            if department:
                text += f"🏷️ **القسم:** {department.name}\n"
            if doctor:
                text += f"👨‍⚕️ **الطبيب:** {doctor.full_name}\n"
            text += f"⚕️ **نوع الإجراء:** {report.medical_action or 'غير محدد'}\n"
            if report.report_date:
                text += f"📅 **التاريخ:** {report.report_date.strftime('%Y-%m-%d %H:%M')}\n"
            text += "\n⚠️ **تحذير:**\n"
            text += "• سيتم حذف التقرير من قاعدة البيانات\n"
            text += "• سيتم حذف الرسالة من المجموعة\n"
            text += "• لا يمكن التراجع عن هذه العملية\n"
            
            keyboard = [
                [InlineKeyboardButton("✅ تأكيد الحذف", callback_data="delete_confirm")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="delete_back")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="delete_cancel")]
            ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            
            return CONFIRM_DELETE
            
    except Exception as e:
        logger.error(f"❌ خطأ في handle_report_selection: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ **حدث خطأ**\n\nيرجى المحاولة مرة أخرى.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END


async def handle_confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة تأكيد الحذف"""
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "delete_cancel":
            await query.edit_message_text(
                "❌ **تم إلغاء عملية الحذف**\n\n"
                "يمكنك البدء من جديد من القائمة الرئيسية.",
                parse_mode=ParseMode.MARKDOWN
            )
            await query.message.reply_text(
                "📋 اختر العملية المطلوبة:",
                reply_markup=user_main_kb()
            )
            return ConversationHandler.END
        
        if query.data == "delete_back":
            # إعادة عرض قائمة التقارير
            user = update.effective_user
            with SessionLocal() as s:
                today = date.today()
                today_start = datetime.combine(today, datetime.min.time())
                today_end = datetime.combine(today, datetime.max.time())
                
                # ✅ البحث بمعرف المستخدم الذي أنشأ التقرير (نفس منطق start_delete_reports)
                translator = s.query(Translator).filter_by(tg_user_id=user.id).first()
                translator_id = translator.id if translator else None
                
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
                    reports = s.query(Report).filter(
                        Report.submitted_by_user_id == user.id,
                        Report.report_date >= today_start,
                        Report.report_date <= today_end
                    ).order_by(Report.report_date.desc()).all()
                
                if not reports:
                    await query.edit_message_text(
                        "📋 **لا توجد تقارير لليوم**\n\n"
                        f"📅 **التاريخ:** {today.strftime('%Y-%m-%d')}\n\n"
                        "لم تقم بإضافة أي تقارير اليوم.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return ConversationHandler.END
                
                text = "🗑️ **حذف التقارير - اليوم**\n\n"
                text += f"📅 **{today.strftime('%Y-%m-%d')}** ({len(reports)} تقرير)\n\n"
                text += "⚠️ **تحذير:** سيتم حذف التقرير من المجموعة وقاعدة البيانات.\n\n"
                text += "اختر التقرير الذي تريد حذفه:\n\n"
                
                keyboard = []
                for report in reports:
                    patient = s.query(Patient).filter_by(id=report.patient_id).first()
                    patient_name = patient.full_name if patient else "غير معروف"
                    hospital = s.query(Hospital).filter_by(id=report.hospital_id).first()
                    hospital_name = hospital.name if hospital else "غير معروف"
                    
                    button_text = f"📋 {patient_name} - {hospital_name}"
                    if len(button_text) > 50:
                        button_text = button_text[:47] + "..."
                    
                    keyboard.append([
                        InlineKeyboardButton(
                            button_text,
                            callback_data=f"delete_report:{report.id}"
                        )
                    ])
                    
                    text += f"📋 **{patient_name}**\n"
                    text += f"🏥 {hospital_name}\n"
                    text += f"⚕️ {report.medical_action or 'غير محدد'}\n\n"
                
                keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="delete_cancel")])
                
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )
                
                return SELECT_REPORT
        
        if query.data == "delete_confirm":
            report_id = context.user_data.get('delete_report_id')
            
            if not report_id:
                await query.edit_message_text("⚠️ **خطأ:** لم يتم تحديد التقرير")
                return ConversationHandler.END
            
            with SessionLocal() as s:
                report = s.query(Report).filter_by(id=report_id).first()
                
                if not report:
                    await query.edit_message_text("⚠️ **خطأ:** لم يتم العثور على التقرير")
                    return ConversationHandler.END
                
                # ✅ التحقق من أن المستخدم هو من أنشأ التقرير
                current_user_id = context.user_data.get('submitted_by_user_id')
                if not current_user_id and query.from_user:
                    current_user_id = query.from_user.id
                    context.user_data['submitted_by_user_id'] = current_user_id
                
                # التحقق: إذا كان submitted_by_user_id موجوداً في التقرير، يجب أن يطابق المستخدم الحالي
                # إذا كان None (تقرير قديم)، نتحقق من translator_id
                # ✅ قاعدة واحدة ترفض افتراضياً — انظر can_modify_report في
                # shared_auth.py. الفحص السابق كان يمرّ لمن لا صفَّ له في users.
                from bot.shared_auth import can_modify_report
                if not can_modify_report(report, current_user_id, s):
                    await query.edit_message_text("⚠️ **خطأ:** لا يمكنك حذف هذا التقرير")
                    return ConversationHandler.END
                
                # حفظ معرف الرسالة قبل الحذف (إذا كان موجوداً)
                group_message_id = getattr(report, 'group_message_id', None)
                
                # حذف التقرير من قاعدة البيانات
                s.delete(report)
                s.commit()

                logger.info(f"✅ تم حذف التقرير {report_id} من قاعدة البيانات")

                # ✅ تنظيف السجل المعلَّق المرتبط — وإلا بقي **يتيماً** في شاشة
                # "التقارير المعلقة" بـ«نوع الفحص: —» بلا أي طريقة لإغلاقه
                # (لا يمكن رفع مرفق لتقرير محذوف، فيبقى للأبد).
                try:
                    from services.pending_reports_service import drop_pending_for_report
                    drop_pending_for_report(report_id)
                except Exception:
                    logger.debug("تم تجاهل استثناء في تنظيف السجل المعلَّق", exc_info=True)


                # محاولة حذف الرسالة من المجموعة
                if group_message_id and REPORTS_GROUP_ID:
                    try:
                        await context.bot.delete_message(
                            chat_id=REPORTS_GROUP_ID,
                            message_id=group_message_id
                        )
                        logger.info(f"✅ تم حذف الرسالة {group_message_id} من المجموعة {REPORTS_GROUP_ID}")
                    except Exception as e:
                        logger.warning(f"⚠️ فشل حذف الرسالة من المجموعة: {e}")
                        # لا نوقف العملية إذا فشل حذف الرسالة
                
                # جلب بيانات المريض للرسالة النهائية
                patient = s.query(Patient).filter_by(id=report.patient_id).first() if report.patient_id else None
                patient_name = patient.full_name if patient else "غير معروف"
                
                await query.edit_message_text(
                    f"✅ **تم حذف التقرير بنجاح**\n\n"
                    f"📋 **رقم التقرير:** {report_id}\n"
                    f"👤 **المريض:** {patient_name}\n\n"
                    f"يمكنك الآن إضافة تقرير جديد باستخدام زر '📝 إضافة تقرير جديد'.",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                return ConversationHandler.END
                
    except Exception as e:
        logger.error(f"❌ خطأ في handle_confirm_delete: {e}", exc_info=True)
        try:
            await query.edit_message_text(
                "❌ **حدث خطأ أثناء الحذف**\n\nيرجى المحاولة مرة أخرى.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            logger.debug("تم تجاهل استثناء في handle_confirm_delete", exc_info=True)
        return ConversationHandler.END


async def cancel_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء عملية الحذف"""
    try:
        if update.message:
            await update.message.reply_text(
                "❌ **تم إلغاء عملية الحذف**\n\n"
                "يمكنك البدء من جديد من القائمة الرئيسية.",
                reply_markup=user_main_kb(),
                parse_mode=ParseMode.MARKDOWN
            )
        elif update.callback_query:
            await update.callback_query.answer("تم الإلغاء")
            await update.callback_query.edit_message_text(
                "❌ **تم إلغاء عملية الحذف**\n\n"
                "يمكنك البدء من جديد من القائمة الرئيسية.",
                parse_mode=ParseMode.MARKDOWN
            )
            await update.callback_query.message.reply_text(
                "📋 اختر العملية المطلوبة:",
                reply_markup=user_main_kb()
            )
    except Exception:
        logger.debug("تم تجاهل استثناء في cancel_delete", exc_info=True)
    
    # تنظيف البيانات
    context.user_data.pop('delete_report_id', None)
    context.user_data.pop('submitted_by_user_id', None)
    
    return ConversationHandler.END


def register(app):
    """تسجيل handler حذف التقارير"""
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🗑️ حذف التقارير$"), start_delete_reports)
        ],
        states={
            SELECT_REPORT: [
                CallbackQueryHandler(handle_report_selection, pattern="^delete_report:"),
                CallbackQueryHandler(cancel_delete, pattern="^delete_cancel$")
            ],
            CONFIRM_DELETE: [
                CallbackQueryHandler(handle_confirm_delete, pattern="^delete_confirm$"),
                CallbackQueryHandler(handle_report_selection, pattern="^delete_back$"),
                CallbackQueryHandler(cancel_delete, pattern="^delete_cancel$")
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ إلغاء العملية الحالية$"), cancel_delete),
            CallbackQueryHandler(cancel_delete, pattern="^delete_cancel$")
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,  # ✅ False لأن entry point هو MessageHandler
    )
    
    app.add_handler(conv_handler)
