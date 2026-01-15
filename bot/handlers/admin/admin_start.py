# ================================================
# bot/handlers/admin/admin_start.py
# 🔹 لوحة تحكم الأدمن + نظام الموافقة على المستخدمين
# ================================================

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from bot.shared_auth import is_admin
from bot.keyboards import admin_main_kb, admin_main_inline_kb, reports_group_management_kb, admin_main_inline_kb_with_group
from db.session import SessionLocal
from db.models import Translator
from datetime import datetime


# 🟣 أمر /admin لفتح لوحة تحكم الأدمن
async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
    
    # مسح أي حالة عالقة
    if context.user_data:
        context.user_data.clear()
    
    await update.message.reply_text(
        f"👑 أهلاً {user.first_name}! لوحة التحكم جاهزة.",
        reply_markup=admin_main_kb()
    )


# 🔄 أمر /cancel لإعادة تعيين كل شيء
async def cancel_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إعادة تعيين كل الحالات والبيانات المعلقة"""
    from telegram.ext import ConversationHandler
    
    # مسح بيانات المستخدم
    if context.user_data:
        context.user_data.clear()
    
    # مسح بيانات المحادثة
    if hasattr(context, 'chat_data') and context.chat_data:
        context.chat_data.clear()
    
    user = update.effective_user
    
    if is_admin(user.id):
        await update.message.reply_text(
            "✅ **تم إعادة تعيين كل الحالات**\n\n"
            "يمكنك الآن استخدام أي زر من جديد.",
            reply_markup=admin_main_kb(),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "✅ تم إعادة تعيين الحالة.\n"
            "اضغط /start للبدء من جديد."
        )
    
    return ConversationHandler.END


# ✅ دالة لمعالجة زر القبول / الرفض للمستخدمين الجدد
async def handle_user_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    action, user_id_str = data.split(":")
    user_id = int(user_id_str)

    with SessionLocal() as s:
        translator = s.query(Translator).filter_by(tg_user_id=user_id).first()
        if not translator:
            await query.edit_message_text("❌ لم يتم العثور على المستخدم في قاعدة البيانات.")
            return

        if action == "approve":
            translator.is_approved = True
            translator.updated_at = datetime.now()
            # حفظ في SQLite
            s.commit()
            await query.edit_message_text(f"✅ تم قبول المستخدم: {translator.full_name}")

            # إرسال إشعار للمستخدم المقبول مع القائمة الرئيسية
            try:
                from bot.keyboards import user_main_kb
                from datetime import datetime
                import hashlib
                
                # الحصول على رسالة ترحيبية
                now = datetime.now()
                days_ar = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
                months_ar = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                            "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
                day_name = days_ar[now.weekday()]
                month_name = months_ar[now.month - 1]
                
                hour = now.hour
                minute = now.strftime("%M")
                if 5 <= hour < 12:
                    greeting = "صباح الخير"
                else:
                    greeting = "مساء الخير"
                
                date_str = f"{day_name}، {now.day} {month_name} {now.year}"
                time_str = f"{hour}:{minute}"
                
                welcome_message = f"""╔════════════════════╗
  🌟 {greeting} {translator.full_name}
╚════════════════════╝

✅ **تم قبولك بنجاح!**

يمكنك الآن استخدام النظام بالكامل.

📅 {date_str}
⏰ {time_str}

━━━━━━━━━━━━━━━━━━━━

👇 اختر العملية المطلوبة:"""
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=welcome_message,
                    reply_markup=user_main_kb(),
                    parse_mode="Markdown"
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"❌ خطأ في إرسال القائمة بعد الموافقة: {e}", exc_info=True)
                # إرسال رسالة بسيطة كـ fallback
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="✅ تم قبولك! اضغط /start للبدء."
                    )
                except:
                    pass

        elif action == "reject":
            # حذف من SQLite
            user_name = translator.full_name
            s.delete(translator)
            s.commit()
            await query.edit_message_text(f"🚫 تم رفض المستخدم: {user_name}")

            # إرسال إشعار للمستخدم المرفوض
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ تم رفض طلبك. يرجى التواصل مع الإدارة لمزيد من التفاصيل."
                )
            except Exception:
                pass


# دالة معالجة العودة للقائمة الرئيسية
async def handle_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر العودة للقائمة الرئيسية"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    if not is_admin(user.id):
        await query.edit_message_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
        return
    
    # لا يمكن استخدام edit_message_text مع ReplyKeyboardMarkup
    # لذلك نرسل رسالة جديدة
    await query.message.reply_text(
        f"👑 أهلاً {user.first_name}! لوحة التحكم جاهزة.",
        reply_markup=admin_main_kb()
    )
    # محاولة حذف الرسالة القديمة
    try:
        await query.message.delete()
    except:
        pass


async def handle_admin_buttons(update, context):
    """معالجة أزرار الأدمن العامة"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not is_admin(user.id):
        await query.edit_message_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
        return

    data = query.data

    if data == "admin:refresh":
        # تحديث الصفحة الرئيسية
        await query.edit_message_text(
            f"👑 **لوحة تحكم الأدمن**\n\nأهلاً {user.first_name}!\nاختر العملية المطلوبة:",
            reply_markup=admin_main_inline_kb_with_group(),
            parse_mode="Markdown"
        )

    elif data == "admin:manage_group":
        # إدارة مجموعة التقارير
        await query.edit_message_text(
            "🏥 **إدارة مجموعة التقارير**\n\n"
            "اختر العملية المطلوبة لإدارة مجموعة التقارير:",
            reply_markup=reports_group_management_kb(),
            parse_mode="Markdown"
        )

    elif data.startswith("group:"):
        # معالجات مجموعة التقارير
        await handle_group_management(update, context)

    elif data.startswith("admin:"):
        # أزرار أخرى - يمكن إضافة معالجات إضافية هنا
        await query.edit_message_text(
            f"⚠️ هذه الخاصية قيد التطوير: {data}",
            reply_markup=admin_main_inline_kb()
        )


async def handle_group_management(update, context):
    """معالجة إدارة مجموعة التقارير"""
    query = update.callback_query
    await query.answer()

    data = query.data.replace("group:", "")

    if data == "setup":
        # إعداد المجموعة
        from services.broadcast_service import setup_reports_group
        import os

        group_id = os.getenv("REPORTS_GROUP_ID", "")
        invite_link = os.getenv("GROUP_INVITE_LINK", "")

        if not group_id:
            await query.edit_message_text(
                "❌ **خطأ في الإعداد**\n\n"
                "لم يتم تحديد معرف مجموعة التقارير في متغيرات البيئة.\n\n"
                "أضف `REPORTS_GROUP_ID` في ملف `.env`",
                reply_markup=reports_group_management_kb()
            )
            return

        try:
            await setup_reports_group(context.bot, invite_link)
            await query.edit_message_text(
                "✅ **تم إعداد المجموعة بنجاح**\n\n"
                "🏥 تم إرسال رسالة تعريفية للمجموعة\n"
                "🔗 تم إرسال دعوات للمستخدمين (إذا كان هناك رابط دعوة)\n\n"
                f"📋 **معرف المجموعة:** `{group_id}`",
                reply_markup=reports_group_management_kb(),
                parse_mode="Markdown"
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ **فشل إعداد المجموعة**\n\nخطأ: {str(e)}",
                reply_markup=reports_group_management_kb()
            )

    elif data == "invite":
        # إرسال دعوات
        import os
        invite_link = os.getenv("GROUP_INVITE_LINK", "")

        if not invite_link:
            await query.edit_message_text(
                "❌ **لا يوجد رابط دعوة**\n\n"
                "أضف `GROUP_INVITE_LINK` في ملف `.env` لإرسال الدعوات",
                reply_markup=reports_group_management_kb()
            )
            return

        from services.broadcast_service import send_group_invitations
        try:
            await send_group_invitations(context.bot, invite_link)
            await query.edit_message_text(
                "✅ **تم إرسال الدعوات بنجاح**\n\n"
                "📬 تم إرسال دعوات الانضمام لجميع المستخدمين النشطين",
                reply_markup=reports_group_management_kb()
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ **فشل إرسال الدعوات**\n\nخطأ: {str(e)}",
                reply_markup=reports_group_management_kb()
            )

    elif data == "status":
        # حالة المجموعة
        import os
        group_id = os.getenv("REPORTS_GROUP_ID", "")
        use_group = os.getenv("USE_GROUP_BROADCAST", "true").lower() == "true"

        status_text = f"""
🏥 **حالة مجموعة التقارير**

📊 **الإعدادات الحالية:**
• البث للمجموعة: {"✅ مفعل" if use_group else "❌ معطل"}
• معرف المجموعة: {group_id if group_id else "غير محدد"}
• رابط الدعوة: {"موجود" if os.getenv("GROUP_INVITE_LINK") else "غير موجود"}

📈 **إحصائيات الأداء:**
"""

        # إضافة إحصائيات الأداء إذا كانت متوفرة
        try:
            from services.performance_utils import get_performance_stats
            stats = get_performance_stats()
            status_text += f"""
• إجمالي الطلبات: {stats.get('total_requests', 0)}
• معدل الأخطاء: {stats.get('error_rate', 0):.1f}%
• متوسط زمن الاستجابة: {stats.get('avg_response_time', 0):.2f}s
• الذاكرة المستخدمة: {stats.get('current_memory_mb', 0):.1f}MB"""
        except:
            status_text += "\n• إحصائيات الأداء: غير متوفرة"

        await query.edit_message_text(
            status_text,
            reply_markup=reports_group_management_kb(),
            parse_mode="Markdown"
        )

    elif data == "settings":
        # إعدادات البث
        import os
        current_setting = os.getenv("USE_GROUP_BROADCAST", "true")

        keyboard = [
            [InlineKeyboardButton("✅ تفعيل البث للمجموعة", callback_data="settings:enable_group")],
            [InlineKeyboardButton("❌ إلغاء تفعيل البث للمجموعة", callback_data="settings:disable_group")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="group:back")]
        ]

        await query.edit_message_text(
            f"⚙️ **إعدادات البث**\n\n"
            f"الحالة الحالية: {'✅ مفعل' if current_setting.lower() == 'true' else '❌ معطل'}\n\n"
            f"اختر الإعداد المطلوب:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )


async def handle_group_settings(update, context):
    """معالجة إعدادات المجموعة"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        query = update.callback_query
        if not query:
            logger.error("❌ handle_group_settings: No callback_query found")
            return
        
        await query.answer()
        
        logger.info(f"🔧 handle_group_settings: callback_data = {query.data}")
        
        action = query.data.replace("settings:", "")
        logger.info(f"🔧 handle_group_settings: action = {action}")

        if action in ["enable_group", "disable_group"]:
            # ✅ استخدام broadcast_control لتغيير الحالة فعلياً
            from bot.broadcast_control import is_broadcast_enabled, set_broadcast_enabled
            
            # الحالة قبل التغيير
            old_state = is_broadcast_enabled()
            logger.info(f"🔧 handle_group_settings: الحالة قبل التغيير = {old_state}")
            
            if action == "enable_group":
                # تفعيل البث
                set_broadcast_enabled(True)
                status_text = "✅ مفعل"
                logger.info("🔧 handle_group_settings: تم تفعيل البث")
            else:  # disable_group
                # إيقاف البث
                set_broadcast_enabled(False)
                status_text = "❌ معطل"
                logger.info("🔧 handle_group_settings: تم إيقاف البث")
            
            # التحقق من الحالة الجديدة
            final_state = is_broadcast_enabled()
            logger.info(f"🔧 handle_group_settings: الحالة بعد التغيير = {final_state}")
            
            await query.edit_message_text(
                f"⚙️ **تم تحديث الإعدادات**\n\n"
                f"البث للمجموعة: {status_text}\n\n"
                f"📊 **الحالة الحالية:** {'✅ مفعل' if final_state else '❌ معطل'}\n\n"
                f"💡 التغيير فعال فوراً - لا حاجة لإعادة تشغيل البوت",
                reply_markup=reports_group_management_kb(),
                parse_mode="Markdown"
            )
            logger.info("✅ handle_group_settings: تم تحديث الرسالة بنجاح")
        else:
            logger.warning(f"⚠️ handle_group_settings: action غير معروف: {action}")
            
    except Exception as e:
        logger.error(f"❌ خطأ في handle_group_settings: {e}", exc_info=True)
        try:
            if query:
                await query.answer(f"❌ حدث خطأ: {str(e)[:50]}", show_alert=True)
        except:
            pass


# ✅ معالج زر إيقاف/تفعيل إرسال التقارير من لوحة المفاتيح
async def handle_toggle_broadcast_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر إيقاف/تفعيل إرسال التقارير من لوحة المفاتيح الرئيسية"""
    import logging
    logger = logging.getLogger(__name__)
    
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
        return
    
    try:
        from bot.broadcast_control import is_broadcast_enabled, set_broadcast_enabled
        
        # الحالة الحالية
        current_state = is_broadcast_enabled()
        logger.info(f"🔧 handle_toggle_broadcast_button: الحالة الحالية = {current_state}")
        
        # تبديل الحالة
        new_state = not current_state
        set_broadcast_enabled(new_state)
        
        # التحقق من الحالة الجديدة
        final_state = is_broadcast_enabled()
        logger.info(f"🔧 handle_toggle_broadcast_button: الحالة الجديدة = {final_state}")
        
        # تحديث لوحة المفاتيح
        status_text = "🟢 تم تفعيل إرسال التقارير للمجموعة" if final_state else "🔴 تم إيقاف إرسال التقارير للمجموعة"
        
        await update.message.reply_text(
            f"{status_text}\n\n"
            f"📊 **الحالة الحالية:** {'✅ مفعل' if final_state else '❌ معطل'}\n\n"
            f"💡 التغيير فعال فوراً - لا حاجة لإعادة تشغيل البوت",
            reply_markup=admin_main_kb(),
            parse_mode="Markdown"
        )
        logger.info("✅ handle_toggle_broadcast_button: تم التحديث بنجاح")
        
    except Exception as e:
        logger.error(f"❌ خطأ في handle_toggle_broadcast_button: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ حدث خطأ: {str(e)[:100]}",
            reply_markup=admin_main_kb()
        )


# 🧩 تسجيل الهاندلرز الخاصة بلوحة التحكم
def register(app):
    app.add_handler(CommandHandler("admin", admin_start))
    app.add_handler(CommandHandler("cancel", cancel_all))  # ✅ أمر إعادة التعيين
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ مساعدة$"), admin_start))
    # ✅ معالج زر إيقاف/تفعيل إرسال التقارير من لوحة المفاتيح
    app.add_handler(MessageHandler(filters.Regex(r"^(🟢 تفعيل إرسال التقارير|🔴 إيقاف إرسال التقارير)$"), handle_toggle_broadcast_button))
    # ✅ لا نحتاج لإضافة معالج لزر "👥 إدارة المستخدمين" هنا
    # لأن ConversationHandler في admin_users_management.py يتعامل معه مباشرة
    app.add_handler(CallbackQueryHandler(handle_user_approval, pattern="^(approve|reject):"))
    app.add_handler(CallbackQueryHandler(handle_back_to_main, pattern="^back_to_main$"))
    app.add_handler(CallbackQueryHandler(handle_admin_buttons, pattern="^admin:"))
    app.add_handler(CallbackQueryHandler(handle_group_settings, pattern="^settings:"))
