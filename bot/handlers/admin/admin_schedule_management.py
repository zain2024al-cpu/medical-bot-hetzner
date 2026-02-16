# ================================================
# bot/handlers/admin/admin_schedule_management.py
# 🔹 إدارة جدول المترجمين الجديد
# ================================================

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters, CommandHandler
from telegram.constants import ParseMode
import os
import logging
from datetime import datetime, date
from db.session import SessionLocal
from db.models import (
    ScheduleImage, TranslatorSchedule, DailyReportTracking, 
    TranslatorNotification, Translator, DailySchedule
)
from bot.shared_auth import is_admin
from bot.keyboards import admin_main_kb

logger = logging.getLogger(__name__)

# حالات المحادثة
UPLOAD_SCHEDULE, CONFIRM_SCHEDULE, VIEW_SCHEDULE = range(3)

async def start_schedule_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إدارة الجدول"""
    user = update.effective_user
    
    # التحقق من أن المستخدم أدمن
    if not is_admin(user.id):
        await update.message.reply_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
        return ConversationHandler.END

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 رفع جدول جديد", callback_data="upload_schedule")],
        [InlineKeyboardButton("📋 عرض الجدول الحالي", callback_data="view_schedule")],
        [InlineKeyboardButton("📊 تتبع التقارير اليومية", callback_data="track_reports")],
        [InlineKeyboardButton("🔔 إرسال تنبيهات", callback_data="send_notifications")],
        [InlineKeyboardButton("📝 أسماء المرضى", callback_data="manage_patients")],
        [InlineKeyboardButton("🏥 إدارة المستشفيات", callback_data="manage_hospitals")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ])

    await update.message.reply_text(
        "📅 **إدارة جدول المترجمين**\n\n"
        "اختر العملية المطلوبة:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_schedule_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار العملية"""
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    
    if choice == "upload_schedule":
        await query.edit_message_text(
            "📤 **رفع جدول جديد**\n\n"
            "أرسل صورة الجدول الآن:",
            parse_mode=ParseMode.MARKDOWN
        )
        return UPLOAD_SCHEDULE
    
    elif choice == "view_schedule":
        return await view_current_schedule(update, context)
    
    elif choice == "track_reports":
        return await track_daily_reports(update, context)
    
    elif choice == "send_notifications":
        return await send_notifications_menu(update, context)
    
    elif choice == "manage_patients":
        # استخدام معالج إدارة الأسماء الجديد الذي تم إنشاؤه في نهاية الملف
        return await handle_manage_patients(update, context)
    
    elif choice == "manage_hospitals":
        # إدارة المستشفيات
        return await handle_manage_hospitals(update, context)
    
    elif choice == "back_to_main":
        await query.edit_message_text(
            "🔙 العودة للقائمة الرئيسية",
            reply_markup=admin_main_kb()
        )
        return ConversationHandler.END

async def upload_schedule_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رفع صورة الجدول"""
    if not update.message.photo:
        await update.message.reply_text("⚠️ يرجى إرسال صورة الجدول.\n\n❌ أو اكتب 'إلغاء' لإنهاء العملية")
        return UPLOAD_SCHEDULE
    
    # حفظ الصورة
    photo = update.message.photo[-1]  # أعلى دقة
    file = await context.bot.get_file(photo.file_id)
    
    # إنشاء مجلد للصور إذا لم يكن موجوداً
    os.makedirs("uploads/schedules", exist_ok=True)
    
    # اسم الملف
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"schedule_{timestamp}.jpg"
    file_path = f"uploads/schedules/{filename}"
    
    # تحميل الصورة
    await file.download_to_drive(file_path)
    
    # حفظ في قاعدة البيانات
    with SessionLocal() as s:
        schedule_image = ScheduleImage(
            file_id=photo.file_id,
            file_path=file_path,
            uploader_id=update.effective_user.id
        )
        s.add(schedule_image)
        s.commit()
        s.refresh(schedule_image)
        
        context.user_data["schedule_image_id"] = schedule_image.id
        context.user_data["file_path"] = file_path
        context.user_data["photo_file_id"] = photo.file_id
    
    # تأكيد الرفع
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأكيد وحفظ الجدول", callback_data="confirm_schedule")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_upload")]
    ])
    
    await update.message.reply_text(
        f"✅ **تم رفع الجدول بنجاح!**\n\n"
        f"📁 اسم الملف: {filename}\n"
        f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"هل تريد حفظ الجدول في النظام؟",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return CONFIRM_SCHEDULE

async def confirm_schedule_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد حفظ الجدول"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm_schedule":
        # حفظ الجدول في DailySchedule لجعله متاحاً للمستخدمين
        file_path = context.user_data.get("file_path")
        if file_path:
            with SessionLocal() as s:
                ds = DailySchedule(
                    date=datetime.now(),  # استخدام التوقيت المحلي بدلاً من UTC
                    photo_path=file_path,
                    photo_file_id=context.user_data.get("photo_file_id"),
                    uploaded_by=update.effective_user.id
                )
                s.add(ds)
                s.commit()
                logger.info(f"تم حفظ الجدول في DailySchedule: {file_path}")
            
            # بث الجدول لجميع المستخدمين
            try:
                from services.broadcast_service import broadcast_schedule
                
                # إعداد بيانات الجدول
                days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
                now = datetime.now()
                day_name = days_ar.get(now.weekday(), '')
                
                schedule_data = {
                    'date': now.strftime('%Y-%m-%d'),
                    'day_name': day_name,
                    'upload_time': now.strftime('%H:%M')
                }
                
                photo_source = context.user_data.get("photo_file_id") or file_path
                use_file_id = bool(context.user_data.get("photo_file_id"))
                await broadcast_schedule(context.bot, photo_source, schedule_data, use_file_id=use_file_id)
                logger.info("تم بث الجدول لجميع المستخدمين")
            except Exception as e:
                logger.error(f"خطأ في بث الجدول: {e}")
        
        # رسالة التأكيد
        await query.edit_message_text(
            "✅ **تم حفظ الجدول بنجاح!**\n\n"
            "📋 الجدول متاح الآن للمترجمين\n"
            "📊 سيتم تتبع التقارير تلقائياً\n"
            "📢 تم إرسال الجدول لجميع المستخدمين\n\n"
            "💡 **ملاحظة:** يمكنك الآن إضافة تفاصيل المترجمين يدوياً أو استخدام OCR لاستخراج البيانات تلقائياً.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # إضافة سجل تتبع للمترجمين (مثال)
        await create_daily_tracking_records(update, context)
        
    else:  # cancel_upload
        await query.edit_message_text("❌ تم إلغاء رفع الجدول.")
    
    return ConversationHandler.END

async def create_daily_tracking_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إنشاء سجلات تتبع يومية للمترجمين"""
    try:
        # هذا مثال - يمكن تحسينه لاستخراج أسماء المترجمين من الجدول
        sample_translators = [
            "اكرم محمد العزي يحيى المروني",
            "مطهر محمد محمد شمس الدين الحكيم", 
            "محمد علي يحيى احمد القاسمي",
            "ایمان اسماعیل محمد حسن راويه",
            "موسى محمد علي مسعد احمد الظفاري"
        ]
        
        today = date.today()
        
        with SessionLocal() as s:
            # إنشاء الجداول إذا لم تكن موجودة
            try:
                from db.models import Base
                Base.metadata.create_all(bind=s.bind)
            except Exception as e:
                logger.warning(f"تحذير في إنشاء الجداول: {e}")
            
            for translator_name in sample_translators:
                try:
                    # التحقق من وجود سجل اليوم
                    existing = s.query(DailyReportTracking).filter_by(
                        date=today,
                        translator_name=translator_name
                    ).first()
                    
                    if not existing:
                        tracking = DailyReportTracking(
                            date=today,
                            translator_name=translator_name,
                            expected_reports=1,  # افتراضياً تقرير واحد لكل مترجم
                            actual_reports=0
                        )
                        s.add(tracking)
                except Exception as e:
                    logger.warning(f"خطأ في إنشاء سجل للمترجم {translator_name}: {e}")
                    continue
            
            s.commit()
            logger.info("تم إنشاء سجلات التتبع بنجاح")
            
    except Exception as e:
        logger.error(f"خطأ في إنشاء سجلات التتبع: {e}")

async def view_current_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الجدول الحالي"""
    query = update.callback_query
    await query.answer()
    
    try:
        with SessionLocal() as s:
            # البحث عن آخر جدول تم رفعه في DailySchedule
            daily_schedule = s.query(DailySchedule).order_by(DailySchedule.date.desc()).first()
            
            if not daily_schedule:
                await query.edit_message_text(
                    "⚠️ **لا يوجد جدول متاح حالياً**\n\n"
                    "لم يتم رفع أي جدول بعد.\n"
                    "استخدم 'رفع جدول جديد' لرفع جدول.",
                    parse_mode=ParseMode.MARKDOWN
                )
            elif (
                not daily_schedule.photo_file_id
                and (not daily_schedule.photo_path or not os.path.exists(daily_schedule.photo_path))
            ):
                await query.edit_message_text(
                    "⚠️ **خطأ في الملف**\n\n"
                    "لا يوجد مرجع للصورة في السحابة أو على الخادم.\n"
                    "يرجى رفع جدول جديد.",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                # معلومات الجدول
                days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
                schedule_date = daily_schedule.date or datetime.utcnow()
                day_name = days_ar.get(schedule_date.weekday(), '')
                date_str = schedule_date.strftime('%Y-%m-%d')
                time_str = daily_schedule.created_at.strftime('%H:%M') if daily_schedule.created_at else "غير محدد"
                
                # عرض الجدول
                await query.edit_message_text("📋 **الجدول الحالي:**")
                
                # إرسال الصورة
                if daily_schedule.photo_file_id:
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=daily_schedule.photo_file_id,
                        caption=f"📅 **جدول اليوم**\n\n"
                                f"📆 التاريخ: {date_str} ({day_name})\n"
                                f"🕐 آخر تحديث: {time_str}\n"
                                f"👤 رافع الجدول: Admin ID {daily_schedule.uploaded_by}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    with open(daily_schedule.photo_path, 'rb') as photo_file:
                        await context.bot.send_photo(
                            chat_id=query.message.chat_id,
                            photo=photo_file,
                            caption=f"📅 **جدول اليوم**\n\n"
                                    f"📆 التاريخ: {date_str} ({day_name})\n"
                                    f"🕐 آخر تحديث: {time_str}\n"
                                    f"👤 رافع الجدول: Admin ID {daily_schedule.uploaded_by}",
                            parse_mode=ParseMode.MARKDOWN
                        )
                
                # عرض إحصائيات التتبع
                try:
                    today = date.today()
                    tracking_records = s.query(DailyReportTracking).filter_by(date=today).all()
                    
                    if tracking_records:
                        stats_text = "📊 **إحصائيات التتبع اليومية:**\n\n"
                        for record in tracking_records:
                            status = "✅" if record.is_completed else "⏳"
                            stats_text += f"{status} **{record.translator_name}**\n"
                            stats_text += f"   📝 التقارير: {record.actual_reports}/{record.expected_reports}\n\n"
                        
                        await context.bot.send_message(
                            chat_id=query.message.chat_id,
                            text=stats_text,
                            parse_mode=ParseMode.MARKDOWN
                        )
                except Exception as e:
                    logger.warning(f"خطأ في عرض إحصائيات التتبع: {e}")
                
    except Exception as e:
        logger.error(f"خطأ في عرض الجدول: {e}")
        import traceback
        traceback.print_exc()
        await query.edit_message_text(
            f"❌ **حدث خطأ في عرض الجدول**\n\n{str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    return ConversationHandler.END

async def track_daily_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تتبع التقارير اليومية"""
    query = update.callback_query
    await query.answer()
    
    today = date.today()
    
    with SessionLocal() as s:
        # جلب سجلات التتبع
        tracking_records = s.query(DailyReportTracking).filter_by(date=today).all()
        
        if not tracking_records:
            await query.edit_message_text("⚠️ لا توجد سجلات تتبع لهذا اليوم.")
            return
        
        # عرض الإحصائيات
        completed = sum(1 for r in tracking_records if r.is_completed)
        total = len(tracking_records)
        
        stats_text = f"📊 **تقرير التتبع اليومي**\n\n"
        stats_text += f"📅 التاريخ: {today.strftime('%Y-%m-%d')}\n"
        stats_text += f"✅ مكتمل: {completed}/{total}\n"
        stats_text += f"⏳ متبقي: {total - completed}\n\n"
        
        # تفاصيل كل مترجم
        for record in tracking_records:
            status = "✅" if record.is_completed else "⏳"
            stats_text += f"{status} **{record.translator_name}**\n"
            stats_text += f"   📝 التقارير: {record.actual_reports}/{record.expected_reports}\n"
            if record.reminder_sent:
                stats_text += f"   🔔 تم إرسال تذكير\n"
            stats_text += "\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 تحديث الإحصائيات", callback_data="refresh_tracking")],
            [InlineKeyboardButton("🔔 إرسال تذكيرات", callback_data="send_reminders")],
            [InlineKeyboardButton("🔙 العودة", callback_data="back_to_schedule")]
        ])
        
        await query.edit_message_text(
            stats_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

async def send_notifications_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """قائمة إرسال التنبيهات"""
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔔 تذكير للمترجمين المتأخرين", callback_data="remind_late")],
        [InlineKeyboardButton("📢 إشعار عام للمترجمين", callback_data="general_notification")],
        [InlineKeyboardButton("📊 تقرير يومي للمترجمين", callback_data="daily_report")],
        [InlineKeyboardButton("🔙 العودة", callback_data="back_to_schedule")]
    ])
    
    await query.edit_message_text(
        "🔔 **إرسال التنبيهات**\n\n"
        "اختر نوع التنبيه:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def send_reminders_to_late_translators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال تذكيرات للمترجمين المتأخرين"""
    query = update.callback_query
    await query.answer()
    
    today = date.today()
    
    with SessionLocal() as s:
        # البحث عن المترجمين المتأخرين
        late_translators = s.query(DailyReportTracking).filter(
            DailyReportTracking.date == today,
            DailyReportTracking.is_completed == False,
            DailyReportTracking.reminder_sent == False
        ).all()
        
        if not late_translators:
            await query.edit_message_text("✅ جميع المترجمين مكتملون أو تم إرسال التذكيرات لهم.")
            return
        
        sent_count = 0
        for record in late_translators:
            # البحث عن المترجم في النظام
            translator = s.query(Translator).filter_by(full_name=record.translator_name).first()
            
            if translator:
                # إرسال التذكير (هنا يمكن إضافة منطق إرسال رسالة)
                notification = TranslatorNotification(
                    translator_name=record.translator_name,
                    notification_type="reminder",
                    message=f"تذكير: لم يتم رفع التقارير المطلوبة لليوم {today.strftime('%Y-%m-%d')}",
                    is_sent=True,
                    sent_at=datetime.now()
                )
                s.add(notification)
                
                # تحديث سجل التتبع
                record.reminder_sent = True
                sent_count += 1
        
        s.commit()
        
        await query.edit_message_text(
            f"✅ **تم إرسال {sent_count} تذكير للمترجمين المتأخرين**\n\n"
            f"📅 التاريخ: {today.strftime('%Y-%m-%d')}",
            parse_mode=ParseMode.MARKDOWN
        )

async def cancel_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء رفع الجدول"""
    context.user_data.clear()
    await update.callback_query.edit_message_text("❌ تم إلغاء رفع الجدول.")
    return ConversationHandler.END

async def back_to_schedule_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة لقائمة إدارة الجدول"""
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 رفع جدول جديد", callback_data="upload_schedule")],
        [InlineKeyboardButton("📋 عرض الجدول الحالي", callback_data="view_schedule")],
        [InlineKeyboardButton("📊 تتبع التقارير اليومية", callback_data="track_reports")],
        [InlineKeyboardButton("🔔 إرسال تنبيهات", callback_data="send_notifications")],
        [InlineKeyboardButton("📝 أسماء المرضى", callback_data="manage_patients")],
        [InlineKeyboardButton("🏥 إدارة المستشفيات", callback_data="manage_hospitals")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ])

    await query.edit_message_text(
        "📅 **إدارة جدول المترجمين**\n\n"
        "اختر العملية المطلوبة:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def start_daily_patients_from_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فتح إدارة أسماء المرضى اليومية من داخل إدارة الجدول"""
    query = update.callback_query
    await query.answer()
    
    today = date.today()
    
    # عرض القائمة الرئيسية لإدارة أسماء المرضى
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة أسماء مرضى اليوم", callback_data="dp_add_from_schedule")],
        [InlineKeyboardButton("👀 عرض أسماء مرضى اليوم", callback_data="dp_view_from_schedule")],
        [InlineKeyboardButton("🗑️ حذف جميع أسماء اليوم", callback_data="dp_delete_from_schedule")],
        [InlineKeyboardButton("🔙 العودة لإدارة الجدول", callback_data="back_to_schedule")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ])
    
    text = "🧍‍♂️ **إدارة أسماء المرضى اليومية**\n\n"
    text += f"📅 **التاريخ:** {today.strftime('%Y-%m-%d')}\n\n"
    text += "اختر العملية المطلوبة:"
    
    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # حفظ معلومة أننا جئنا من إدارة الجدول
    context.user_data['from_schedule'] = True
    
    return ConversationHandler.END

# ================================================
# إدارة أسماء المرضى (نظام الملف)
# ================================================

async def handle_manage_patients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة أسماء المرضى من قاعدة البيانات الموحدة"""
    query = update.callback_query
    await query.answer()
    
    # استخدام الخدمة الموحدة
    try:
        from services.patients_service import get_patients_count
        count = get_patients_count()
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل عدد المرضى: {e}")
        count = 0
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة اسم جديد", callback_data="add_patient_name")],
        [InlineKeyboardButton("📋 عرض جميع الأسماء", callback_data="view_patient_names")],
        [InlineKeyboardButton("✏️ تعديل اسم", callback_data="edit_patient_name")],
        [InlineKeyboardButton("🗑️ حذف اسم", callback_data="delete_patient_name")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_schedule")]
    ])
    
    await query.edit_message_text(
        f"📝 **إدارة أسماء المرضى**\n\n"
        f"📊 **عدد الأسماء:** {count}\n\n"
        f"اختر العملية:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END

async def handle_view_patient_names(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض أسماء المرضى مع التصفح بالصفحات"""
    query = update.callback_query
    await query.answer()
    
    # استخراج رقم الصفحة من callback_data
    page = 0
    if query.data.startswith("sched_patient_page:"):
        try:
            page = int(query.data.split(":")[1])
        except:
            page = 0
    
    ITEMS_PER_PAGE = 10
    
    # استخدام الخدمة الموحدة
    try:
        from services.patients_service import get_patients_paginated
        patients, total_count, total_pages = get_patients_paginated(page=page, per_page=ITEMS_PER_PAGE)
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل المرضى: {e}")
        patients, total_count, total_pages = [], 0, 0
    
    if not patients:
        text = "📋 **قائمة أسماء المرضى**\n\n⚠️ لا توجد أسماء مسجلة"
    else:
        start_num = page * ITEMS_PER_PAGE + 1
        text = f"📋 **قائمة أسماء المرضى**\n\n"
        text += f"📊 **العدد الكلي:** {total_count}\n"
        text += f"📄 **الصفحة:** {page + 1} من {total_pages}\n\n"
        
        for i, patient in enumerate(patients, start_num):
            text += f"{i}. {patient['name']}\n"
    
    # أزرار التنقل
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"sched_patient_page:{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data=f"sched_patient_page:{page + 1}"))
    
    keyboard = []
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_add_patient_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إضافة اسم مريض جديد"""
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_patient_input")]
    ])

    await query.edit_message_text(
        "➕ **إضافة اسم مريض جديد**\n\n"
        "📝 اكتب الاسم الكامل للمريض:\n"
        "مثال: أحمد محمد",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return "ADD_PATIENT_NAME"

async def handle_cancel_patient_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    await handle_manage_patients(update, context)
    return ConversationHandler.END

async def handle_patient_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم المريض الجديد - يستخدم الخدمة الموحدة"""
    name = update.message.text.strip()
    
    if not name or len(name) < 2:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_patient_input")]
        ])
        await update.message.reply_text(
            "⚠️ **خطأ:** الاسم قصير جداً\n\n"
            "يرجى إدخال اسم صحيح:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return "ADD_PATIENT_NAME"
    
    # إضافة الاسم باستخدام الخدمة الموحدة
    try:
        from services.patients_service import add_patient, get_patient_by_name
        
        # التحقق من عدم التكرار
        existing = get_patient_by_name(name)
        if existing:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")]])
            await update.message.reply_text(
                f"⚠️ **الاسم موجود مسبقاً:** {name}",
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        patient_id = add_patient(name)
        
        if patient_id:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")]])
            await update.message.reply_text(
                f"✅ **تم إضافة الاسم:** {name}\n\n"
                f"📝 يمكنك إضافة المزيد أو الرجوع للقائمة",
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                f"❌ **خطأ في الإضافة**",
                parse_mode=ParseMode.MARKDOWN
            )
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error adding patient: {e}")
        await update.message.reply_text(
            f"❌ **خطأ في الحفظ:** {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

async def handle_delete_patient_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """واجهة حذف اسم مريض مع التصفح بالصفحات"""
    query = update.callback_query
    await query.answer()
    
    # استخراج رقم الصفحة
    page = 0
    if query.data.startswith("delete_patient_page:"):
        try:
            page = int(query.data.split(":")[1])
        except:
            page = 0
    
    ITEMS_PER_PAGE = 8
    
    # استخدام الخدمة الموحدة
    try:
        from services.patients_service import get_patients_paginated
        patients, total_count, total_pages = get_patients_paginated(page=page, per_page=ITEMS_PER_PAGE)
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل المرضى: {e}")
        patients, total_count, total_pages = [], 0, 0
    
    if not patients:
        await query.edit_message_text(
            "⚠️ **لا توجد أسماء لحذفها**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")]]),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # عرض الأسماء مع أزرار حذف
    keyboard = []
    for patient in patients:
        # حفظ الأسماء في context للوصول إليها لاحقاً
        context.user_data.setdefault('patient_names_cache', {})[patient['id']] = patient['name']
        keyboard.append([InlineKeyboardButton(
            f"🗑️ {patient['name']}",
            callback_data=f"del_patient:{patient['id']}"  # تقصير callback_data
        )])
    
    # أزرار التنقل
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"delete_patient_page:{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data=f"delete_patient_page:{page + 1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")])
    
    await query.edit_message_text(
        f"🗑️ **حذف اسم مريض**\n\n"
        f"📊 **العدد:** {total_count} | 📄 الصفحة: {page + 1}/{total_pages}\n\n"
        f"اختر الاسم المراد حذفه:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد حذف اسم مريض - يستخدم الخدمة الموحدة"""
    query = update.callback_query
    await query.answer()
    
    # استخراج البيانات (del_patient:id)
    parts = query.data.split(':')
    if len(parts) < 2 or not parts[1].isdigit():
        logger.warning(f"Received invalid delete confirmation: {query.data}")
        await query.edit_message_text("❌ خطأ: طلب حذف غير صالح.")
        return ConversationHandler.END
    
    patient_id = int(parts[1])
    # جلب الاسم من الكاش أو من قاعدة البيانات
    name_to_delete = context.user_data.get('patient_names_cache', {}).get(patient_id, '')
    if not name_to_delete:
        try:
            from services.patients_service import get_patient_by_id
            patient = get_patient_by_id(patient_id)
            if patient:
                name_to_delete = patient.get('name', f'مريض #{patient_id}')
        except:
            name_to_delete = f'مريض #{patient_id}'
    
    # حذف المريض باستخدام الخدمة الموحدة
    try:
        from services.patients_service import delete_patient, get_patients_count
        
        success = delete_patient(patient_id)
        
        if success:
            remaining_count = get_patients_count()
            await query.edit_message_text(
                f"✅ **تم حذف الاسم:** {name_to_delete}\n\n"
                f"📊 **عدد الأسماء المتبقية:** {remaining_count}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")]]),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.edit_message_text(
                f"❌ **فشل حذف الاسم:** {name_to_delete}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")]]),
                parse_mode=ParseMode.MARKDOWN
            )
    except Exception as e:
        logger.error(f"Error deleting patient: {e}")
        await query.edit_message_text(
            f"❌ **خطأ في الحذف:** {str(e)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")]]),
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_edit_patient_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """واجهة تعديل اسم مريض مع التصفح بالصفحات"""
    query = update.callback_query
    await query.answer()
    
    # استخراج رقم الصفحة
    page = 0
    if query.data.startswith("edit_patient_page:"):
        try:
            page = int(query.data.split(":")[1])
        except:
            page = 0
    
    ITEMS_PER_PAGE = 8
    
    # استخدام الخدمة الموحدة
    try:
        from services.patients_service import get_patients_paginated
        patients, total_count, total_pages = get_patients_paginated(page=page, per_page=ITEMS_PER_PAGE)
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل المرضى: {e}")
        patients, total_count, total_pages = [], 0, 0
    
    if not patients:
        await query.edit_message_text(
            "⚠️ **لا توجد أسماء لتعديلها**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")]]),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # عرض الأسماء مع أزرار تعديل
    keyboard = []
    for patient in patients:
        # حفظ الأسماء في context للوصول إليها لاحقاً
        context.user_data.setdefault('patient_names_cache', {})[patient['id']] = patient['name']
        keyboard.append([InlineKeyboardButton(
            f"✏️ {patient['name']}",
            callback_data=f"edit_patient:{patient['id']}"  # تقصير callback_data
        )])
    
    # أزرار التنقل
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"edit_patient_page:{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data=f"edit_patient_page:{page + 1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")])
    
    await query.edit_message_text(
        f"✏️ **تعديل اسم مريض**\n\n"
        f"📊 **العدد:** {total_count} | 📄 الصفحة: {page + 1}/{total_pages}\n\n"
        f"اختر الاسم المراد تعديله:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_select_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار اسم للتعديل - يستخدم ID بدل الindex"""
    query = update.callback_query
    await query.answer()
    
    # استخراج البيانات (edit_patient:id)
    parts = query.data.split(':')
    if len(parts) < 2 or not parts[1].isdigit():
        await query.edit_message_text("❌ خطأ في البيانات")
        return ConversationHandler.END
    
    patient_id = int(parts[1])
    # جلب الاسم من الكاش أو من قاعدة البيانات
    old_name = context.user_data.get('patient_names_cache', {}).get(patient_id, '')
    if not old_name:
        try:
            from services.patients_service import get_patient_by_id
            patient = get_patient_by_id(patient_id)
            if patient:
                old_name = patient.get('name', f'مريض #{patient_id}')
        except:
            old_name = f'مريض #{patient_id}'
    
    # حفظ في context
    context.user_data['edit_patient_id'] = patient_id
    context.user_data['edit_patient_old_name'] = old_name
    
    await query.edit_message_text(
        f"✏️ **تعديل اسم المريض**\n\n"
        f"📝 **الاسم الحالي:** {old_name}\n\n"
        f"اكتب الاسم الجديد:",
        parse_mode=ParseMode.MARKDOWN
    )
    
    return "EDIT_NAME_INPUT"

async def handle_edit_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال الاسم الجديد للتعديل - يستخدم الخدمة الموحدة"""
    new_name = update.message.text.strip()
    
    if not new_name or len(new_name) < 2:
        await update.message.reply_text(
            "⚠️ **خطأ:** الاسم قصير جداً\n\n"
            "يرجى إدخال اسم صحيح:",
            parse_mode=ParseMode.MARKDOWN
        )
        return "EDIT_NAME_INPUT"
    
    # الحصول على البيانات المحفوظة
    patient_id = context.user_data.get('edit_patient_id')
    old_name = context.user_data.get('edit_patient_old_name')
    
    if patient_id is None or old_name is None:
        await update.message.reply_text("❌ **خطأ:** لم يتم اختيار اسم للتعديل", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    
    # تعديل الاسم باستخدام الخدمة الموحدة
    try:
        from services.patients_service import update_patient
        
        success = update_patient(patient_id, new_name)
        
        # مسح البيانات المحفوظة
        context.user_data.pop('edit_patient_id', None)
        context.user_data.pop('edit_patient_old_name', None)
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")]])
        
        if success:
            await update.message.reply_text(
                f"✅ **تم تعديل الاسم بنجاح**\n\n"
                f"📝 **من:** {old_name}\n"
                f"📝 **إلى:** {new_name}",
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                f"❌ **فشل تعديل الاسم**",
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error updating patient: {e}")
        await update.message.reply_text(
            f"❌ **خطأ في الحفظ:** {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END


# ================================================
# إدارة المستشفيات
# ================================================

HOSPITALS_PER_PAGE = 10

async def handle_manage_hospitals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة المستشفيات"""
    query = update.callback_query
    await query.answer()
    
    from services.hospitals_service import get_all_hospitals
    hospitals = get_all_hospitals()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 عرض جميع المستشفيات", callback_data="view_hospitals:0")],
        [InlineKeyboardButton("➕ إضافة مستشفى جديد", callback_data="add_hospital")],
        [InlineKeyboardButton("✏️ تعديل مستشفى", callback_data="edit_hospital:0")],
        [InlineKeyboardButton("🗑️ حذف مستشفى", callback_data="delete_hospital:0")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_schedule")]
    ])
    
    await query.edit_message_text(
        f"🏥 **إدارة المستشفيات**\n\n"
        f"📊 **عدد المستشفيات:** {len(hospitals)}\n\n"
        f"اختر العملية:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END


async def handle_view_hospitals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المستشفيات مع صفحات"""
    query = update.callback_query
    await query.answer()
    
    # استخراج رقم الصفحة
    page = 0
    if ":" in query.data:
        try:
            page = int(query.data.split(":")[1])
        except:
            page = 0
    
    from services.hospitals_service import get_all_hospitals
    hospitals = get_all_hospitals()
    
    if not hospitals:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]])
        await query.edit_message_text(
            "📋 **قائمة المستشفيات**\n\n⚠️ لا توجد مستشفيات مسجلة",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # حساب الصفحات
    total_pages = (len(hospitals) + HOSPITALS_PER_PAGE - 1) // HOSPITALS_PER_PAGE
    start_idx = page * HOSPITALS_PER_PAGE
    end_idx = min(start_idx + HOSPITALS_PER_PAGE, len(hospitals))
    
    # بناء النص
    text = f"📋 **قائمة المستشفيات** (صفحة {page + 1}/{total_pages})\n\n"
    text += f"📊 **الإجمالي:** {len(hospitals)} مستشفى\n\n"
    
    for i, hospital in enumerate(hospitals[start_idx:end_idx], start_idx + 1):
        text += f"{i}. {hospital}\n"
    
    # أزرار التنقل
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"view_hospitals:{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data=f"view_hospitals:{page+1}"))
    
    keyboard = []
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_add_hospital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إضافة مستشفى جديد"""
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_hospital_input")]
    ])

    await query.edit_message_text(
        "➕ **إضافة مستشفى جديد**\n\n"
        "🏥 اكتب اسم المستشفى بالإنجليزي:\n"
        "مثال: Apollo Hospital, Bangalore",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return "ADD_HOSPITAL"

async def handle_cancel_hospital_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    await handle_manage_hospitals(update, context)
    return ConversationHandler.END


async def handle_hospital_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم المستشفى الجديد"""
    name = update.message.text.strip()
    
    if not name or len(name) < 3:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_hospital_input")]
        ])
        await update.message.reply_text(
            "⚠️ **خطأ:** الاسم قصير جداً\n\n"
            "يرجى إدخال اسم صحيح:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return "ADD_HOSPITAL"
    
    from services.hospitals_service import add_hospital, get_all_hospitals
    
    # التحقق من عدم التكرار
    existing = get_all_hospitals()
    if name.lower().strip() in [h.lower().strip() for h in existing]:
        await update.message.reply_text(
            f"⚠️ **المستشفى موجود بالفعل:** {name}",
            parse_mode=ParseMode.MARKDOWN
        )
        return "ADD_HOSPITAL"
    
    # إضافة المستشفى
    if add_hospital(name):
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]])
        await update.message.reply_text(
            f"✅ **تم إضافة المستشفى:** {name}",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ **خطأ في الحفظ**",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END


async def handle_delete_hospital_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة المستشفيات للحذف"""
    query = update.callback_query
    await query.answer()
    
    # استخراج رقم الصفحة
    page = 0
    if ":" in query.data:
        try:
            page = int(query.data.split(":")[1])
        except:
            page = 0
    
    from services.hospitals_service import get_all_hospitals
    hospitals = get_all_hospitals()
    
    if not hospitals:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]])
        await query.edit_message_text(
            "⚠️ **لا توجد مستشفيات للحذف**",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # حساب الصفحات
    total_pages = (len(hospitals) + HOSPITALS_PER_PAGE - 1) // HOSPITALS_PER_PAGE
    start_idx = page * HOSPITALS_PER_PAGE
    end_idx = min(start_idx + HOSPITALS_PER_PAGE, len(hospitals))
    
    # أزرار الحذف
    keyboard = []
    for i, hospital in enumerate(hospitals[start_idx:end_idx], start_idx):
        short_name = hospital[:30] + "..." if len(hospital) > 30 else hospital
        keyboard.append([InlineKeyboardButton(
            f"🗑️ {short_name}",
            callback_data=f"confirm_del_hosp:{i}"
        )])
    
    # أزرار التنقل
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"delete_hospital:{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"delete_hospital:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")])
    
    await query.edit_message_text(
        f"🗑️ **حذف مستشفى** (صفحة {page + 1}/{total_pages})\n\n"
        f"اختر المستشفى المراد حذفه:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_confirm_delete_hospital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد حذف مستشفى"""
    query = update.callback_query
    await query.answer()
    
    # استخراج index المستشفى
    try:
        idx = int(query.data.split(":")[1])
    except:
        await query.edit_message_text("❌ خطأ في البيانات")
        return
    
    from services.hospitals_service import get_all_hospitals
    hospitals = get_all_hospitals()
    
    if idx >= len(hospitals):
        await query.edit_message_text("❌ المستشفى غير موجود")
        return
    
    hospital_name = hospitals[idx]
    
    # حفظ في context للتأكيد
    context.user_data['delete_hospital_name'] = hospital_name
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ نعم، احذف", callback_data="do_delete_hospital")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="manage_hospitals")]
    ])
    
    await query.edit_message_text(
        f"⚠️ **تأكيد الحذف**\n\n"
        f"هل أنت متأكد من حذف:\n\n"
        f"🏥 **{hospital_name}**",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_do_delete_hospital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ حذف المستشفى"""
    query = update.callback_query
    await query.answer()
    
    hospital_name = context.user_data.get('delete_hospital_name')
    if not hospital_name:
        await query.edit_message_text("❌ خطأ: لم يتم تحديد المستشفى")
        return
    
    from services.hospitals_service import delete_hospital
    
    if delete_hospital(hospital_name):
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]])
        await query.edit_message_text(
            f"✅ **تم حذف المستشفى:** {hospital_name}",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]])
        await query.edit_message_text(
            f"❌ **فشل حذف المستشفى:** {hospital_name}",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    
    context.user_data.pop('delete_hospital_name', None)


async def handle_edit_hospital_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة المستشفيات للتعديل"""
    query = update.callback_query
    await query.answer()
    
    # استخراج رقم الصفحة
    page = 0
    if ":" in query.data:
        try:
            page = int(query.data.split(":")[1])
        except:
            page = 0
    
    from services.hospitals_service import get_all_hospitals
    hospitals = get_all_hospitals()
    
    if not hospitals:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]])
        await query.edit_message_text(
            "⚠️ **لا توجد مستشفيات للتعديل**",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # حساب الصفحات
    total_pages = (len(hospitals) + HOSPITALS_PER_PAGE - 1) // HOSPITALS_PER_PAGE
    start_idx = page * HOSPITALS_PER_PAGE
    end_idx = min(start_idx + HOSPITALS_PER_PAGE, len(hospitals))
    
    # أزرار التعديل
    keyboard = []
    for i, hospital in enumerate(hospitals[start_idx:end_idx], start_idx):
        short_name = hospital[:30] + "..." if len(hospital) > 30 else hospital
        keyboard.append([InlineKeyboardButton(
            f"✏️ {short_name}",
            callback_data=f"select_edit_hosp:{i}"
        )])
    
    # أزرار التنقل
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"edit_hospital:{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"edit_hospital:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")])
    
    await query.edit_message_text(
        f"✏️ **تعديل مستشفى** (صفحة {page + 1}/{total_pages})\n\n"
        f"اختر المستشفى المراد تعديله:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def handle_select_edit_hospital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار مستشفى للتعديل"""
    query = update.callback_query
    await query.answer()
    
    # استخراج index المستشفى
    try:
        idx = int(query.data.split(":")[1])
    except:
        await query.edit_message_text("❌ خطأ في البيانات")
        return
    
    from services.hospitals_service import get_all_hospitals
    hospitals = get_all_hospitals()
    
    if idx >= len(hospitals):
        await query.edit_message_text("❌ المستشفى غير موجود")
        return
    
    hospital_name = hospitals[idx]
    
    # حفظ في context
    context.user_data['edit_hospital_name'] = hospital_name
    
    await query.edit_message_text(
        f"✏️ **تعديل المستشفى**\n\n"
        f"📍 **الاسم الحالي:**\n{hospital_name}\n\n"
        f"اكتب الاسم الجديد:",
        parse_mode=ParseMode.MARKDOWN
    )
    return "EDIT_HOSPITAL"


async def handle_hospital_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال الاسم الجديد للمستشفى"""
    new_name = update.message.text.strip()
    old_name = context.user_data.get('edit_hospital_name')
    
    if not old_name:
        await update.message.reply_text("❌ خطأ: لم يتم تحديد المستشفى")
        return ConversationHandler.END
    
    if not new_name or len(new_name) < 3:
        await update.message.reply_text(
            "⚠️ **خطأ:** الاسم قصير جداً\n\n"
            "يرجى إدخال اسم صحيح:",
            parse_mode=ParseMode.MARKDOWN
        )
        return "EDIT_HOSPITAL"
    
    from services.hospitals_service import update_hospital
    
    if update_hospital(old_name, new_name):
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]])
        await update.message.reply_text(
            f"✅ **تم تعديل المستشفى**\n\n"
            f"📝 **من:** {old_name}\n"
            f"📝 **إلى:** {new_name}",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]])
        await update.message.reply_text(
            f"❌ **فشل تعديل المستشفى**",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    
    context.user_data.pop('edit_hospital_name', None)
    return ConversationHandler.END


def register(app):
    """تسجيل الهاندلرز"""
    
    # معالج callback منفصل لزر الرجوع من أسماء المرضى (خارج ConversationHandler)
    app.add_handler(CallbackQueryHandler(
        back_to_schedule_menu, 
        pattern="^back_to_schedule$"
    ))
    
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📅 إدارة الجدول$"), start_schedule_management),
            CallbackQueryHandler(handle_schedule_choice, pattern="^upload_schedule$|^view_schedule$|^track_reports$|^send_notifications$|^daily_patients$|^back_to_main$")
        ],
        states={
            UPLOAD_SCHEDULE: [
                MessageHandler(filters.PHOTO, upload_schedule_image),
                CallbackQueryHandler(cancel_upload, pattern="^cancel_upload$"),
            ],
            CONFIRM_SCHEDULE: [
                CallbackQueryHandler(confirm_schedule_save, pattern="^confirm_schedule$|^cancel_upload$"),
            ],
            VIEW_SCHEDULE: [
                CallbackQueryHandler(back_to_schedule_menu, pattern="^back_to_schedule$"),
            ]
        },
        fallbacks=[
            CallbackQueryHandler(send_reminders_to_late_translators, pattern="^remind_late$"),
            CallbackQueryHandler(send_notifications_menu, pattern="^general_notification$|^daily_report$"),
            CallbackQueryHandler(track_daily_reports, pattern="^refresh_tracking$|^send_reminders$"),
            CallbackQueryHandler(start_daily_patients_from_schedule, pattern="^daily_patients$"),
            MessageHandler(filters.Regex("^إلغاء$|^الغاء$|^cancel$"), cancel_upload)
        ],
        name="admin_schedule_management_conv",
        per_chat=True,
        per_user=True,
        per_message=False,
    )
    
    # دالة wrapper لإضافة اسم (لحل مشكلة async)
    async def start_add_patient_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await handle_add_patient_name(update, context)
    
    # ConversationHandler لإدارة الأسماء (إضافة وتعديل)
    patient_names_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_select_edit, pattern="^edit_patient:\\d+$"),
            CallbackQueryHandler(start_add_patient_name, pattern="^add_patient_name$")
        ],
        states={
            "EDIT_NAME_INPUT": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_name_input)
            ],
            "ADD_PATIENT_NAME": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_patient_name_input)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(handle_manage_patients, pattern="^manage_patients$"),
            CallbackQueryHandler(handle_cancel_patient_input, pattern="^cancel_patient_input$")
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
        name="patient_names_conv"
    )
    
    # إضافة معالجات لأزرار إدارة الأسماء
    app.add_handler(patient_names_conv)  # تسجيل ConversationHandler أولاً
    app.add_handler(CallbackQueryHandler(handle_manage_patients, pattern="^manage_patients$"))
    # عرض المرضى مع التصفح بالصفحات
    app.add_handler(CallbackQueryHandler(handle_view_patient_names, pattern="^view_patient_names$"))
    app.add_handler(CallbackQueryHandler(handle_view_patient_names, pattern="^sched_patient_page:\\d+$"))
    # حذف المرضى مع التصفح
    app.add_handler(CallbackQueryHandler(handle_delete_patient_name, pattern="^delete_patient_name$"))
    app.add_handler(CallbackQueryHandler(handle_delete_patient_name, pattern="^delete_patient_page:\\d+$"))
    app.add_handler(CallbackQueryHandler(handle_confirm_delete, pattern="^del_patient:\\d+$"))
    # تعديل المرضى مع التصفح
    app.add_handler(CallbackQueryHandler(handle_edit_patient_name, pattern="^edit_patient_name$"))
    app.add_handler(CallbackQueryHandler(handle_edit_patient_name, pattern="^edit_patient_page:\\d+$"))
    app.add_handler(CallbackQueryHandler(handle_select_edit, pattern="^edit_patient:\\d+$"))
    
    # ================================================
    # إضافة معالجات إدارة المستشفيات
    # ================================================
    
    # دالة wrapper لإضافة مستشفى
    async def start_add_hospital(update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await handle_add_hospital(update, context)
    
    # دالة wrapper لتعديل مستشفى
    async def start_edit_hospital(update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await handle_select_edit_hospital(update, context)
    
    # ConversationHandler لإدارة المستشفيات (إضافة وتعديل)
    hospitals_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_hospital, pattern="^add_hospital$"),
            CallbackQueryHandler(start_edit_hospital, pattern="^select_edit_hosp:"),
        ],
        states={
            "ADD_HOSPITAL": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_hospital_name_input)
            ],
            "EDIT_HOSPITAL": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_hospital_edit_input)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(handle_manage_hospitals, pattern="^manage_hospitals$"),
            CallbackQueryHandler(handle_cancel_hospital_input, pattern="^cancel_hospital_input$")
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
        name="hospitals_conv"
    )
    
    app.add_handler(hospitals_conv)  # تسجيل ConversationHandler للمستشفيات
    app.add_handler(CallbackQueryHandler(handle_manage_hospitals, pattern="^manage_hospitals$"))
    app.add_handler(CallbackQueryHandler(handle_view_hospitals, pattern="^view_hospitals:\\d+$"))
    app.add_handler(CallbackQueryHandler(handle_delete_hospital_menu, pattern="^delete_hospital:\\d+$"))
    app.add_handler(CallbackQueryHandler(handle_confirm_delete_hospital, pattern="^confirm_del_hosp:\\d+$"))
    app.add_handler(CallbackQueryHandler(handle_do_delete_hospital, pattern="^do_delete_hospital$"))
    app.add_handler(CallbackQueryHandler(handle_edit_hospital_menu, pattern="^edit_hospital:\\d+$"))
    
    app.add_handler(conv)
