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
SCHEDULE_MENU, UPLOAD_SCHEDULE, CONFIRM_SCHEDULE, VIEW_SCHEDULE = range(4)

async def start_schedule_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إدارة الجدول"""
    import logging
    logger = logging.getLogger(__name__)
    
    user = update.effective_user
    
    logger.info("=" * 80)
    logger.info(f"✅ start_schedule_management called! Update ID: {update.update_id}")
    
    if not update.message:
        logger.error("❌ No message in update!")
        return ConversationHandler.END
    
    user = update.effective_user
    
    logger.info(f"✅ User ID: {user.id if user else 'None'}")
    logger.info(f"✅ Message text: '{update.message.text if update.message else 'None'}'")
    
    # التحقق من أن المستخدم أدمن
    if not is_admin(user.id):
        logger.warning(f"❌ User {user.id if user else 'None'} is not admin")
        await update.message.reply_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
        return ConversationHandler.END
    
    logger.info("✅ Starting schedule management conversation")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 رفع جدول جديد", callback_data="upload_schedule")],
        [InlineKeyboardButton("📋 عرض الجدول الحالي", callback_data="view_schedule")],
        [InlineKeyboardButton("📊 تتبع التقارير اليومية", callback_data="track_reports")],
        [InlineKeyboardButton("🔔 إرسال تنبيهات", callback_data="send_notifications")],
        [InlineKeyboardButton("📝 أسماء المرضى", callback_data="manage_patients")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ])

    try:
        await update.message.reply_text(
            "📅 **إدارة جدول المترجمين**\n\n"
            "اختر العملية المطلوبة:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info(f"✅ Message sent successfully. Returning SCHEDULE_MENU: {SCHEDULE_MENU}")
        logger.info("=" * 80)
        return SCHEDULE_MENU
    except Exception as e:
        logger.error(f"❌ Error sending message: {e}", exc_info=True)
        logger.info("=" * 80)
        return ConversationHandler.END

async def handle_schedule_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار العملية"""
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    logger.info(f"✅ handle_schedule_choice called with choice: '{choice}'")
    logger.info(f"✅ Current state: {context.user_data.get('_conversation_state', 'None')}")
    
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
    
    elif choice == "back_to_main":
        await query.edit_message_text(
            "🔙 العودة للقائمة الرئيسية",
            reply_markup=admin_main_kb()
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    # إذا لم يكن هناك تطابق، العودة للقائمة
    return SCHEDULE_MENU

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
                    date=datetime.utcnow(),
                    photo_path=file_path,
                    photo_file_id=context.user_data.get("photo_file_id"),
                    uploaded_by=update.effective_user.id
                )
                s.add(ds)
                s.commit()
                print(f"✅ تم حفظ الجدول في DailySchedule: {file_path}")
            
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
                print("✅ تم بث الجدول لجميع المستخدمين")
            except Exception as e:
                print(f"⚠️ خطأ في بث الجدول: {e}")
        
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
                print(f"⚠️ تحذير في إنشاء الجداول: {e}")
            
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
                    print(f"⚠️ خطأ في إنشاء سجل للمترجم {translator_name}: {e}")
                    continue
            
            s.commit()
            print("✅ تم إنشاء سجلات التتبع بنجاح")
            
    except Exception as e:
        print(f"❌ خطأ في إنشاء سجلات التتبع: {e}")

async def view_current_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الجدول الحالي - جدول اليوم"""
    query = update.callback_query
    await query.answer()
    
    try:
        with SessionLocal() as s:
            # ✅ البحث عن جدول اليوم (وليس آخر جدول)
            today = date.today()
            from sqlalchemy import func, cast, Date
            
            # ✅ البحث عن جدول اليوم فقط - مقارنة التاريخ فقط (بدون الوقت)
            daily_schedule = s.query(DailySchedule).filter(
                func.date(DailySchedule.date) == today
            ).first()
            
            if not daily_schedule:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 العودة", callback_data="back_to_schedule")]
                ])
                await query.edit_message_text(
                    f"⚠️ **لا يوجد جدول متاح لليوم**\n\n"
                    f"📅 **تاريخ اليوم:** {today.strftime('%Y-%m-%d')}\n\n"
                    f"لم يتم رفع جدول لليوم بعد.\n"
                    f"استخدم 'رفع جدول جديد' لرفع جدول.",
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN
                )
                return SCHEDULE_MENU
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
                # ✅ تحويل إلى date object للمقارنة
                if isinstance(schedule_date, datetime):
                    schedule_date_obj = schedule_date.date()
                else:
                    schedule_date_obj = schedule_date
                day_name = days_ar.get(schedule_date.weekday() if isinstance(schedule_date, datetime) else schedule_date_obj.weekday(), '')
                date_str = schedule_date_obj.strftime('%Y-%m-%d') if hasattr(schedule_date_obj, 'strftime') else str(schedule_date_obj)
                time_str = daily_schedule.created_at.strftime('%H:%M') if daily_schedule.created_at else "غير محدد"
                
                # ✅ التحقق من أن الجدول هو لليوم
                is_today = (schedule_date_obj == today)
                schedule_label = "📅 **جدول اليوم**" if is_today else f"📅 **جدول {date_str}**"
                
                # عرض الجدول
                await query.edit_message_text("📋 **الجدول الحالي:**")
                
                # إرسال الصورة
                if daily_schedule.photo_file_id:
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=daily_schedule.photo_file_id,
                        caption=f"{schedule_label}\n\n"
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
                            caption=f"{schedule_label}\n\n"
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
                    print(f"⚠️ خطأ في عرض إحصائيات التتبع: {e}")
                
    except Exception as e:
        print(f"❌ خطأ في عرض الجدول: {e}")
        import traceback
        traceback.print_exc()
        await query.edit_message_text(
            f"❌ **حدث خطأ في عرض الجدول**\n\n{str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # إضافة زر للعودة
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 العودة", callback_data="back_to_schedule")]
    ])
    await query.message.reply_text(
        "🔙 العودة لقائمة إدارة الجدول",
        reply_markup=keyboard
    )
    return SCHEDULE_MENU

async def track_daily_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تتبع التقارير اليومية"""
    query = update.callback_query
    await query.answer()
    
    today = date.today()
    
    with SessionLocal() as s:
        # محاولة إضافة العمود translator_id إذا لم يكن موجوداً
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(s.bind)
            columns = [col['name'] for col in inspector.get_columns('daily_report_tracking')]
            
            if 'translator_id' not in columns:
                logger.info("🔧 Adding translator_id column to daily_report_tracking table...")
                try:
                    s.execute(text("ALTER TABLE daily_report_tracking ADD COLUMN translator_id INTEGER"))
                    s.commit()
                    logger.info("✅ Successfully added translator_id column")
                except Exception as alter_error:
                    logger.warning(f"⚠️ Could not add column (may already exist): {alter_error}")
                    s.rollback()
        except Exception as inspect_error:
            logger.warning(f"⚠️ Could not inspect table: {inspect_error}")
        
        # جلب سجلات التتبع
        try:
            tracking_records = s.query(DailyReportTracking).filter_by(date=today).all()
        except Exception as e:
            logger.error(f"❌ Error querying DailyReportTracking: {e}", exc_info=True)
            # إذا فشل، جرب query محدود بدون translator_id
            try:
                tracking_records = s.query(
                    DailyReportTracking.id,
                    DailyReportTracking.translator_name,
                    DailyReportTracking.date,
                    DailyReportTracking.expected_reports,
                    DailyReportTracking.actual_reports,
                    DailyReportTracking.is_completed,
                    DailyReportTracking.reminder_sent,
                    DailyReportTracking.created_at
                ).filter_by(date=today).all()
            except Exception as e2:
                logger.error(f"❌ Error in fallback query: {e2}", exc_info=True)
                await query.edit_message_text(
                    "❌ **خطأ في قاعدة البيانات**\n\n"
                    "يرجى التحقق من قاعدة البيانات أو التواصل مع المطور.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
        
        if not tracking_records:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 العودة", callback_data="back_to_schedule")]
            ])
            await query.edit_message_text(
                "⚠️ لا توجد سجلات تتبع لهذا اليوم.",
                reply_markup=keyboard
            )
            return SCHEDULE_MENU
        
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
            # استخدام translator_name إذا كان متوفراً، وإلا استخدام "غير محدد"
            translator_name = getattr(record, 'translator_name', None) or 'غير محدد'
            stats_text += f"{status} **{translator_name}**\n"
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
        return SCHEDULE_MENU

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
    return SCHEDULE_MENU

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
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 العودة", callback_data="back_to_schedule")]
            ])
            await query.edit_message_text(
                "✅ جميع المترجمين مكتملون أو تم إرسال التذكيرات لهم.",
                reply_markup=keyboard
            )
            return SCHEDULE_MENU
        
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
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 العودة", callback_data="back_to_schedule")]
        ])
        await query.edit_message_text(
            f"✅ **تم إرسال {sent_count} تذكير للمترجمين المتأخرين**\n\n"
            f"📅 التاريخ: {today.strftime('%Y-%m-%d')}",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return SCHEDULE_MENU

async def cancel_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء رفع الجدول"""
    context.user_data.clear()
    await update.callback_query.edit_message_text("❌ تم إلغاء رفع الجدول.")
    return ConversationHandler.END

async def back_to_schedule_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة لقائمة إدارة الجدول"""
    import logging
    logger = logging.getLogger(__name__)
    
    query = update.callback_query
    if query:
        await query.answer()
    
    logger.info(f"✅ back_to_schedule_menu called")
    logger.info(f"✅ Current state before: {context.user_data.get('_conversation_state', 'None')}")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 رفع جدول جديد", callback_data="upload_schedule")],
        [InlineKeyboardButton("📋 عرض الجدول الحالي", callback_data="view_schedule")],
        [InlineKeyboardButton("📊 تتبع التقارير اليومية", callback_data="track_reports")],
        [InlineKeyboardButton("🔔 إرسال تنبيهات", callback_data="send_notifications")],
        [InlineKeyboardButton("📝 أسماء المرضى", callback_data="manage_patients")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ])

    try:
        if query:
            await query.edit_message_text(
                "📅 **إدارة جدول المترجمين**\n\n"
                "اختر العملية المطلوبة:",
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                "📅 **إدارة جدول المترجمين**\n\n"
                "اختر العملية المطلوبة:",
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        logger.info(f"✅ Message sent successfully. Returning SCHEDULE_MENU: {SCHEDULE_MENU}")
        return SCHEDULE_MENU
    except Exception as e:
        logger.error(f"❌ Error in back_to_schedule_menu: {e}", exc_info=True)
        return SCHEDULE_MENU

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
    """إدارة أسماء المرضى من قاعدة البيانات"""
    query = update.callback_query
    await query.answer()
    
    # قراءة الأسماء من قاعدة البيانات (مع fallback للملف)
    try:
        from db.patient_names_loader import get_patient_names_from_database_or_file
        names = get_patient_names_from_database_or_file(prefer_database=True)
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل أسماء المرضى: {e}")
        # Fallback: قراءة من الملف
        try:
            with open('data/patient_names.txt', 'r', encoding='utf-8') as f:
                content = f.read()
            names = []
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    names.append(line)
        except FileNotFoundError:
            names = []
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة اسم جديد", callback_data="add_patient_name")],
        [InlineKeyboardButton("📋 عرض جميع الأسماء", callback_data="view_patient_names")],
        [InlineKeyboardButton("✏️ تعديل اسم", callback_data="edit_patient_name")],
        [InlineKeyboardButton("🗑️ حذف اسم", callback_data="delete_patient_name")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_schedule")]
    ])
    
    await query.edit_message_text(
        f"📝 **إدارة أسماء المرضى**\n\n"
        f"📊 **عدد الأسماء:** {len(names)}\n\n"
        f"اختر العملية:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return SCHEDULE_MENU

async def handle_view_patient_names(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض أسماء المرضى من قاعدة البيانات"""
    query = update.callback_query
    await query.answer()
    
    # قراءة الأسماء من قاعدة البيانات (مع fallback للملف)
    try:
        from db.patient_names_loader import get_patient_names_from_database_or_file
        names = get_patient_names_from_database_or_file(prefer_database=True)
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل أسماء المرضى: {e}")
        # Fallback: قراءة من الملف
        try:
            with open('data/patient_names.txt', 'r', encoding='utf-8') as f:
                content = f.read()
            names = []
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    names.append(line)
        except FileNotFoundError:
            names = []
    
    if not names:
        text = "📋 **قائمة أسماء المرضى**\n\n⚠️ لا توجد أسماء مسجلة"
    else:
        text = f"📋 **قائمة أسماء المرضى**\n\n📊 **العدد:** {len(names)}\n\n"
        for i, name in enumerate(names[:30], 1):  # أول 30 اسم
            text += f"{i}. {name}\n"
        
        if len(names) > 30:
            text += f"\n... و {len(names) - 30} اسم آخر"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")]
    ])
    
    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_add_patient_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إضافة اسم مريض جديد"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info(f"✅ handle_add_patient_name called! Update ID: {update.update_id}")
    
    query = update.callback_query
    if query:
        await query.answer()
        try:
            await query.edit_message_text(
                "➕ **إضافة اسم مريض جديد**\n\n"
                "📝 اكتب الاسم الكامل للمريض:\n"
                "مثال: أحمد محمد",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"✅ Message edited successfully. Returning ADD_PATIENT_NAME")
            # حفظ state في context.user_data للتحقق لاحقاً
            context.user_data['_conversation_state'] = "ADD_PATIENT_NAME"
            logger.info("=" * 80)
            return "ADD_PATIENT_NAME"
        except Exception as e:
            logger.error(f"❌ Error editing message: {e}", exc_info=True)
            try:
                await query.message.reply_text(
                    "➕ **إضافة اسم مريض جديد**\n\n"
                    "📝 اكتب الاسم الكامل للمريض:\n"
                    "مثال: أحمد محمد",
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.info(f"✅ Message sent via reply. Returning ADD_PATIENT_NAME")
                # حفظ state في context.user_data للتحقق لاحقاً
                context.user_data['_conversation_state'] = "ADD_PATIENT_NAME"
                logger.info("=" * 80)
                return "ADD_PATIENT_NAME"
            except Exception as e2:
                logger.error(f"❌ Error sending message: {e2}", exc_info=True)
                logger.info("=" * 80)
                return ConversationHandler.END
    
    logger.error("❌ No callback query in update!")
    logger.info("=" * 80)
    return ConversationHandler.END

async def handle_patient_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم المريض الجديد"""
    import logging
    import os
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info(f"✅ handle_patient_name_input called! Update ID: {update.update_id}")
    logger.info(f"📝 Current conversation state: {context.user_data.get('_conversation_state', 'None')}")
    
    if not update.message:
        logger.error("❌ No message in update!")
        return ConversationHandler.END
    
    name = update.message.text.strip()
    logger.info(f"✅ Received name: '{name}'")
    
    if not name or len(name) < 2:
        logger.warning(f"⚠️ Name too short: '{name}'")
        await update.message.reply_text(
            "⚠️ **خطأ:** الاسم قصير جداً\n\n"
            "يرجى إدخال اسم صحيح (حرفين على الأقل):",
            parse_mode=ParseMode.MARKDOWN
        )
        return "ADD_PATIENT_NAME"
    
    # إضافة الاسم للملف
    try:
        # الحصول على المسار المطلق للملف
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        data_dir = os.path.join(base_dir, 'data')
        file_path = os.path.join(data_dir, 'patient_names.txt')
        
        logger.info(f"📁 File path: {file_path}")
        logger.info(f"📁 Base dir: {base_dir}")
        logger.info(f"📁 Data dir: {data_dir}")
        
        # التأكد من وجود المجلد
        os.makedirs(data_dir, exist_ok=True)
        logger.info(f"✅ Data directory created/verified: {data_dir}")
        
        # قراءة الملف أولاً للتحقق من عدم وجود الاسم مسبقاً
        existing_names = []
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            existing_names.append(line)
                logger.info(f"📋 Loaded {len(existing_names)} existing names from file")
            else:
                logger.info(f"📋 File doesn't exist yet, will create new file")
        except Exception as e:
            logger.error(f"❌ Error reading file: {e}", exc_info=True)
        
        # التحقق من عدم وجود الاسم مسبقاً
        if name in existing_names:
            logger.warning(f"⚠️ Name '{name}' already exists")
            await update.message.reply_text(
                f"⚠️ **الاسم موجود مسبقاً:** {name}\n\n"
                f"يرجى إدخال اسم آخر:",
                parse_mode=ParseMode.MARKDOWN
            )
            return "ADD_PATIENT_NAME"
        
        # إضافة الاسم
        with open(file_path, 'a', encoding='utf-8') as f:
            # إذا كان الملف فارغاً أو جديداً، لا نضيف newline في البداية
            if existing_names or os.path.getsize(file_path) > 0:
                f.write(f"\n{name}")
            else:
                f.write(name)
        logger.info(f"✅ Name '{name}' added to file successfully at: {file_path}")
        
        # التحقق من أن الملف تم حفظه
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            logger.info(f"✅ File exists and size is: {file_size} bytes")
        else:
            logger.error(f"❌ File was not created at: {file_path}")
    except Exception as e:
        logger.error(f"❌ Error saving name to file: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ **خطأ في الحفظ:** {str(e)}\n\n"
            f"يرجى المحاولة مرة أخرى:",
            parse_mode=ParseMode.MARKDOWN
        )
        return "ADD_PATIENT_NAME"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة اسم آخر", callback_data="add_patient_name")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")]
    ])
    
    await update.message.reply_text(
        f"✅ **تم إضافة الاسم بنجاح:** {name}\n\n"
        f"📝 يمكنك إضافة المزيد أو الرجوع للقائمة",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    logger.info(f"✅ Success message sent. Ending conversation.")
    # تنظيف state
    context.user_data.pop('_conversation_state', None)
    logger.info("=" * 80)
    return ConversationHandler.END

async def handle_delete_patient_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """واجهة حذف اسم مريض"""
    query = update.callback_query
    await query.answer()
    
    # قراءة الملف
    try:
        with open('data/patient_names.txt', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        await query.edit_message_text(
            "⚠️ **لا توجد أسماء لحذفها**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")]]),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # استخراج الأسماء
    names = []
    for line in content.split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            names.append(line)
    
    if not names:
        await query.edit_message_text(
            "⚠️ **لا توجد أسماء لحذفها**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")]]),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # عرض الأسماء مع أزرار حذف (أول 10 فقط لتجنب مشاكل الكيبورد الكبير)
    keyboard = []
    for i, name in enumerate(names[:10]):
        keyboard.append([InlineKeyboardButton(
            f"🗑️ {name}",
            callback_data=f"confirm_delete:{i}:{name}"
        )])
    
    if len(names) > 10:
        keyboard.append([InlineKeyboardButton(
            f"⚠️ عرض {len(names) - 10} اسم آخر...",
            callback_data="delete_page_2"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")])
    
    await query.edit_message_text(
        f"🗑️ **حذف اسم مريض**\n\n"
        f"📊 **العدد:** {len(names)}\n\n"
        f"اختر الاسم المراد حذفه:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد حذف اسم مريض"""
    query = update.callback_query
    await query.answer()
    
    # استخراج البيانات
    parts = query.data.split(':', 2)
    # تحقق مما إذا كان parts[1] رقمياً قبل التحويل
    if len(parts) < 2 or not parts[1].isdigit():
        # إذا لم يكن رقمياً، قم بمعالجة الخطأ أو تجاهله
        logger.warning(f"Received non-digit index for delete confirmation: {query.data}")
        await query.edit_message_text("❌ خطأ: طلب حذف غير صالح.")
        return ConversationHandler.END
    index = int(parts[1])
    name_to_delete = parts[2]
    
    # قراءة الملف
    try:
        with open('data/patient_names.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        await query.edit_message_text("❌ **خطأ في القراءة**", parse_mode=ParseMode.MARKDOWN)
        return
    
    # حذف الاسم
    new_lines = []
    names = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            names.append(stripped)
        else:
            new_lines.append(line)
    
    # حذف الاسم من القائمة
    if index < len(names) and names[index] == name_to_delete:
        names.pop(index)
    
    # إعادة بناء الملف
    for name in names:
        new_lines.append(name + '\n')
    
    # حفظ الملف
    try:
        with open('data/patient_names.txt', 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        await query.edit_message_text(
            f"✅ **تم حذف الاسم:** {name_to_delete}\n\n"
            f"📊 **عدد الأسماء المتبقية:** {len(names)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")]]),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        await query.edit_message_text(
            f"❌ **خطأ في الحفظ:** {str(e)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")]]),
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_edit_patient_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """واجهة تعديل اسم مريض"""
    query = update.callback_query
    await query.answer()
    
    # قراءة الملف
    try:
        with open('data/patient_names.txt', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        await query.edit_message_text(
            "⚠️ **لا توجد أسماء لتعديلها**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")]]),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # استخراج الأسماء
    names = []
    for line in content.split('\n'):
        line = line.strip()
        if line and not line.startswith('#'):
            names.append(line)
    
    if not names:
        await query.edit_message_text(
            "⚠️ **لا توجد أسماء لتعديلها**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")]]),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # عرض الأسماء مع أزرار تعديل (أول 10 فقط)
    keyboard = []
    for i, name in enumerate(names[:10]):
        keyboard.append([InlineKeyboardButton(
            f"✏️ {name}",
            callback_data=f"select_edit:{i}:{name}"
        )])
    
    if len(names) > 10:
        keyboard.append([InlineKeyboardButton(
            f"⚠️ عرض {len(names) - 10} اسم آخر...",
            callback_data="edit_page_2"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")])
    
    await query.edit_message_text(
        f"✏️ **تعديل اسم مريض**\n\n"
        f"📊 **العدد:** {len(names)}\n\n"
        f"اختر الاسم المراد تعديله:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_select_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار اسم للتعديل"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info(f"✅ handle_select_edit called! Update ID: {update.update_id}")
    
    query = update.callback_query
    if not query:
        logger.error("❌ No callback query in update!")
        return ConversationHandler.END
    
    await query.answer()
    
    # استخراج البيانات
    try:
        parts = query.data.split(':', 2)
        if len(parts) < 3:
            logger.error(f"❌ Invalid callback data: {query.data}")
            await query.edit_message_text("❌ **خطأ:** بيانات غير صحيحة", parse_mode=ParseMode.MARKDOWN)
            return ConversationHandler.END
        
        index = int(parts[1])
        old_name = parts[2]
        
        logger.info(f"✅ Editing name at index {index}: '{old_name}'")
        
        # حفظ في context
        context.user_data['edit_patient_index'] = index
        context.user_data['edit_patient_old_name'] = old_name
        
        try:
            await query.edit_message_text(
                f"✏️ **تعديل اسم المريض**\n\n"
                f"📝 **الاسم الحالي:** {old_name}\n\n"
                f"اكتب الاسم الجديد:",
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"✅ Message edited successfully. Returning EDIT_NAME_INPUT")
            logger.info("=" * 80)
            return "EDIT_NAME_INPUT"
        except Exception as e:
            logger.error(f"❌ Error editing message: {e}", exc_info=True)
            try:
                await query.message.reply_text(
                    f"✏️ **تعديل اسم المريض**\n\n"
                    f"📝 **الاسم الحالي:** {old_name}\n\n"
                    f"اكتب الاسم الجديد:",
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.info(f"✅ Message sent via reply. Returning EDIT_NAME_INPUT")
                logger.info("=" * 80)
                return "EDIT_NAME_INPUT"
            except Exception as e2:
                logger.error(f"❌ Error sending message: {e2}", exc_info=True)
                logger.info("=" * 80)
                return ConversationHandler.END
    except ValueError as e:
        logger.error(f"❌ Error parsing callback data: {e}")
        await query.edit_message_text("❌ **خطأ:** بيانات غير صحيحة", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

async def handle_edit_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال الاسم الجديد للتعديل"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info(f"✅ handle_edit_name_input called! Update ID: {update.update_id}")
    
    if not update.message:
        logger.error("❌ No message in update!")
        return ConversationHandler.END
    
    new_name = update.message.text.strip()
    logger.info(f"✅ Received new name: '{new_name}'")
    
    if not new_name or len(new_name) < 2:
        logger.warning(f"⚠️ Name too short: '{new_name}'")
        await update.message.reply_text(
            "⚠️ **خطأ:** الاسم قصير جداً\n\n"
            "يرجى إدخال اسم صحيح (حرفين على الأقل):",
            parse_mode=ParseMode.MARKDOWN
        )
        return "EDIT_NAME_INPUT"
    
    # الحصول على البيانات المحفوظة
    index = context.user_data.get('edit_patient_index')
    old_name = context.user_data.get('edit_patient_old_name')
    
    logger.info(f"✅ Editing name at index {index}: '{old_name}' -> '{new_name}'")
    
    if index is None or old_name is None:
        logger.error("❌ Missing edit data in context")
        await update.message.reply_text("❌ **خطأ:** لم يتم اختيار اسم للتعديل", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    
    # تعديل الاسم في الملف
    try:
        # قراءة الملف
        with open('data/patient_names.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        logger.error("❌ File not found")
        await update.message.reply_text("❌ **خطأ في القراءة**", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    
    # تعديل الاسم
    new_lines = []
    names = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            names.append(stripped)
        else:
            new_lines.append(line)
    
    # تعديل الاسم في القائمة
    if index < len(names) and names[index] == old_name:
        names[index] = new_name
        logger.info(f"✅ Name updated in list at index {index}")
    else:
        logger.warning(f"⚠️ Name not found at index {index} or name mismatch")
        # محاولة البحث عن الاسم في القائمة
        try:
            actual_index = names.index(old_name)
            names[actual_index] = new_name
            logger.info(f"✅ Name found and updated at actual index {actual_index}")
        except ValueError:
            logger.error(f"❌ Name '{old_name}' not found in list")
            await update.message.reply_text(
                f"❌ **خطأ:** لم يتم العثور على الاسم '{old_name}'",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
    
    # إعادة بناء الملف
    for name in names:
        new_lines.append(name + '\n')
    
    # حفظ الملف
    try:
        with open('data/patient_names.txt', 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        logger.info(f"✅ File saved successfully")
    except Exception as e:
        logger.error(f"❌ Error saving file: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ **خطأ في الحفظ:** {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    
    # مسح البيانات المحفوظة
    context.user_data.pop('edit_patient_index', None)
    context.user_data.pop('edit_patient_old_name', None)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ تعديل اسم آخر", callback_data="edit_patient_name")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")]
    ])
    
    await update.message.reply_text(
        f"✅ **تم تعديل الاسم بنجاح**\n\n"
        f"📝 **من:** {old_name}\n"
        f"📝 **إلى:** {new_name}",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    logger.info(f"✅ Success message sent. Ending conversation.")
    logger.info("=" * 80)
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
            # ✅ استخدام pattern مرن جداً - يطابق أي نص يحتوي على "إدارة الجدول"
            MessageHandler(
                filters.ChatType.PRIVATE & 
                filters.TEXT & 
                ~filters.COMMAND & 
                filters.Regex(r".*إدارة.*الجدول.*"),
                start_schedule_management
            ),
            # ✅ pattern بديل بدون ChatType للتوافق
            MessageHandler(
                filters.TEXT & 
                ~filters.COMMAND & 
                filters.Regex(r".*إدارة.*الجدول.*"),
                start_schedule_management
            ),
        ],
        states={
            SCHEDULE_MENU: [
                CallbackQueryHandler(handle_schedule_choice, pattern="^upload_schedule$|^view_schedule$|^track_reports$|^send_notifications$|^daily_patients$|^back_to_main$"),
            ],
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
            CallbackQueryHandler(back_to_schedule_menu, pattern="^back_to_schedule$"),
            CallbackQueryHandler(send_reminders_to_late_translators, pattern="^remind_late$"),
            CallbackQueryHandler(send_notifications_menu, pattern="^general_notification$|^daily_report$"),
            CallbackQueryHandler(track_daily_reports, pattern="^refresh_tracking$|^send_reminders$"),
            CallbackQueryHandler(start_daily_patients_from_schedule, pattern="^daily_patients$"),
            CallbackQueryHandler(handle_schedule_choice, pattern="^upload_schedule$|^view_schedule$|^track_reports$|^send_notifications$|^manage_patients$|^back_to_main$"),
            MessageHandler(filters.Regex("^إلغاء$|^الغاء$|^cancel$"), cancel_upload)
        ],
        name="admin_schedule_management_conv",
        per_chat=True,
        per_user=True,
        per_message=False,  # ✅ تعطيل per_message للسماح بمعالجة الرسائل بشكل صحيح
        allow_reentry=True,  # ✅ السماح بإعادة الدخول للقائمة الرئيسية
    )
    
    # دالة wrapper لإضافة اسم (لحل مشكلة async)
    async def start_add_patient_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.info(f"✅ start_add_patient_name called! Update ID: {update.update_id}")
        return await handle_add_patient_name(update, context)
    
    # ConversationHandler لإدارة الأسماء (إضافة وتعديل)
    patient_names_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_select_edit, pattern="^select_edit:"),
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
            MessageHandler(filters.Regex("^إلغاء$|^الغاء$|^cancel$"), handle_manage_patients)
        ],
        per_chat=True,
        per_user=True,
        per_message=False,  # ✅ تعطيل per_message للسماح بمعالجة الرسائل بشكل صحيح
        name="patient_names_conv",
        allow_reentry=True  # ✅ السماح بإعادة الدخول
    )
    
    # إضافة معالجات لأزرار إدارة الأسماء
    # ✅ تسجيل ConversationHandler في group=0 لضمان الأولوية (قبل universal fallback في group=99)
    app.add_handler(patient_names_conv, group=0)
    app.add_handler(CallbackQueryHandler(handle_manage_patients, pattern="^manage_patients$"), group=1)
    app.add_handler(CallbackQueryHandler(handle_view_patient_names, pattern="^view_patient_names$"), group=1)
    app.add_handler(CallbackQueryHandler(handle_delete_patient_name, pattern="^delete_patient_name$"), group=1)
    app.add_handler(CallbackQueryHandler(handle_confirm_delete, pattern="^confirm_delete:\\d+:.*"), group=1)
    app.add_handler(CallbackQueryHandler(handle_edit_patient_name, pattern="^edit_patient_name$"), group=1)
    
    # ✅ تسجيل ConversationHandler الرئيسي في group=0 لضمان الأولوية
    app.add_handler(conv, group=0)
