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

            # إرسال إشعار للمستخدم المقبول
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="✅ تم قبولك! يمكنك الآن استخدام النظام."
                )
            except Exception:
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
    query = update.callback_query
    await query.answer()

    action = query.data.replace("settings:", "")

    if action in ["enable_group", "disable_group"]:
        new_value = "true" if action == "enable_group" else "false"

        # في بيئة الإنتاج، يجب تحديث متغير البيئة أو ملف التكوين
        # هنا سنعرض رسالة توضيحية
        status_text = "✅ مفعل" if new_value == "true" else "❌ معطل"

        await query.edit_message_text(
            f"⚙️ **تم تحديث الإعدادات**\n\n"
            f"البث للمجموعة: {status_text}\n\n"
            f"💡 **ملاحظة:** لتطبيق التغيير، أعد تشغيل البوت مع المتغير:\n"
            f"`USE_GROUP_BROADCAST={new_value}`",
            reply_markup=reports_group_management_kb(),
            parse_mode="Markdown"
        )


# 🧩 تسجيل الهاندلرز الخاصة بلوحة التحكم
def register(app):
    app.add_handler(CommandHandler("admin", admin_start))
    app.add_handler(CommandHandler("cancel", cancel_all))  # ✅ أمر إعادة التعيين
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ مساعدة$"), admin_start))
    # ✅ لا نحتاج لإضافة معالج لزر "👥 إدارة المستخدمين" هنا
    # لأن ConversationHandler في admin_users_management.py يتعامل معه مباشرة
    app.add_handler(CallbackQueryHandler(handle_user_approval, pattern="^(approve|reject):"))
    app.add_handler(CallbackQueryHandler(handle_back_to_main, pattern="^back_to_main$"))
    app.add_handler(CallbackQueryHandler(handle_admin_buttons, pattern="^admin:"))
    app.add_handler(CallbackQueryHandler(handle_group_settings, pattern="^settings:"))
