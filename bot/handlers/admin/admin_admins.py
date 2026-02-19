# ================================================
# bot/handlers/admin/admin_admins.py
# 👑 إدارة الأدمنين - إضافة وحذف الأدمنين
# ================================================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from bot.shared_auth import is_admin
from bot.keyboards import admin_main_kb
from config.settings import ADMIN_IDS
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

# States
AA_START, AA_ADD_INPUT, AA_REMOVE_SELECT, AA_CONFIRM_REMOVE = range(4)

async def start_admin_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إدارة الأدمنين"""
    user = update.effective_user

    if not is_admin(user.id):
        if update.message:
            await update.message.reply_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
        elif update.callback_query:
            try:
                await update.callback_query.answer("🚫 هذه الخاصية مخصصة للإدمن فقط.", show_alert=True)
            except Exception:
                pass
        return ConversationHandler.END

    # لوحة إدارة الأدمنين
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة أدمن", callback_data="aa:add")],
        [InlineKeyboardButton("🗑️ حذف أدمن", callback_data="aa:remove")],
        [InlineKeyboardButton("📋 عرض الأدمنين", callback_data="aa:list")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="aa:back")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="aa:cancel")]
    ])

    # معالجة callback query إذا كان موجوداً
    if update.callback_query:
        query = update.callback_query
        try:
            await query.answer()
        except Exception:
            pass
        try:
            await query.edit_message_text(
                "👑 **إدارة الأدمنين**\n\n"
                "اختر العملية المطلوبة:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        except Exception:
            # إذا فشل التعديل، أرسل رسالة جديدة
            try:
                if query.message:
                    await query.message.reply_text(
                        "👑 **إدارة الأدمنين**\n\n"
                        "اختر العملية المطلوبة:",
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )
            except Exception:
                pass
    elif update.message:
        await update.message.reply_text(
            "👑 **إدارة الأدمنين**\n\n"
            "اختر العملية المطلوبة:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    return AA_START

async def handle_admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أزرار إدارة الأدمنين"""
    query = update.callback_query
    await query.answer()

    data = query.data.replace("aa:", "")

    if data == "add":
        await query.edit_message_text(
            "👑 **إضافة أدمن جديد**\n\n"
            "أرسل معرف التليجرام (ID) للشخص الذي تريد إضافته كأدمن:\n\n"
            "💡 **كيفية الحصول على ID:**\n"
            "1. أرسل /id للبوت @userinfobot\n"
            "2. أو في أي محادثة مع البوت، اضغط على الرابط الخاص بالمستخدم\n\n"
            "⚠️ **تحذير:** تأكد من صحة المعرف قبل الإضافة.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ إلغاء", callback_data="aa:cancel")]
            ])
        )
        return AA_ADD_INPUT

    elif data == "remove":
        if len(ADMIN_IDS) <= 1:
            await query.edit_message_text(
                "⚠️ **تحذير**\n\n"
                "لا يمكن حذف جميع الأدمنين!\n"
                "يجب أن يبقى أدمن واحد على الأقل.\n\n"
                "👑 إدارة الأدمنين:",
                reply_markup=_admin_management_kb(),
                parse_mode="Markdown"
            )
            return AA_START

        # عرض قائمة الأدمنين للحذف
        admin_list = []
        for i, admin_id in enumerate(ADMIN_IDS, 1):
            admin_list.append([InlineKeyboardButton(f"🗑️ {admin_id}", callback_data=f"remove_admin:{admin_id}")])

        admin_list.append([InlineKeyboardButton("🔙 رجوع", callback_data="aa:back")])
        admin_list.append([InlineKeyboardButton("❌ إلغاء", callback_data="aa:cancel")])

        await query.edit_message_text(
            "🗑️ **حذف أدمن**\n\n"
            "اختر الأدمن الذي تريد حذفه:",
            reply_markup=InlineKeyboardMarkup(admin_list),
            parse_mode="Markdown"
        )
        return AA_REMOVE_SELECT

    elif data == "list":
        admin_text = "👑 **قائمة الأدمنين الحاليين**\n\n"
        for i, admin_id in enumerate(ADMIN_IDS, 1):
            admin_text += f"{i}. `{admin_id}`\n"

        admin_text += f"\n📊 **المجموع:** {len(ADMIN_IDS)} أدمن"
        admin_text += f"\n\n📅 **آخر تحديث:** {datetime.now().strftime('%H:%M:%S')}"

        await query.edit_message_text(
            admin_text,
            reply_markup=_admin_management_kb(),
            parse_mode="Markdown"
        )
        return AA_START

    elif data == "back":
        # لا يمكن استخدام edit_message_text مع ReplyKeyboardMarkup
        # لذلك نرسل رسالة جديدة
        await query.message.reply_text(
            "👑 لوحة التحكم جاهزة.",
            reply_markup=admin_main_kb()
        )
        # محاولة حذف الرسالة القديمة
        try:
            await query.message.delete()
        except:
            pass
        return ConversationHandler.END
    
    elif data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ تم إلغاء العملية")
        return ConversationHandler.END

    elif data.startswith("remove_admin:"):
        admin_id_to_remove = int(data.split(":")[1])

        # التأكيد قبل الحذف
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚠️ نعم، احذف", callback_data=f"confirm_remove:{admin_id_to_remove}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="aa:cancel")]
        ])

        await query.edit_message_text(
            f"⚠️ **تأكيد الحذف**\n\n"
            f"هل أنت متأكد من حذف الأدمن:\n"
            f"`{admin_id_to_remove}`\n\n"
            f"⚠️ **تحذير:** هذا الإجراء لا يمكن التراجع عنه!",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        return AA_CONFIRM_REMOVE

async def handle_add_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال معرف الأدمن الجديد"""
    user_id_str = update.message.text.strip()

    try:
        new_admin_id = int(user_id_str)
    except ValueError:
        await update.message.reply_text(
            "❌ **خطأ في المعرف**\n\n"
            "المعرف يجب أن يكون رقماً صحيحاً.\n\n"
            "أعد إدخال المعرف:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ إلغاء", callback_data="aa:cancel")]
            ])
        )
        return AA_ADD_INPUT

    # التحقق من أن المعرف ليس أدمن بالفعل
    if new_admin_id in ADMIN_IDS:
        await update.message.reply_text(
            f"⚠️ **المعرف موجود بالفعل**\n\n"
            f"`{new_admin_id}` هو أدمن بالفعل.\n\n"
            "👑 إدارة الأدمنين:",
            reply_markup=_admin_management_kb(),
            parse_mode="Markdown"
        )
        return AA_START

    # إضافة الأدمن الجديد
    ADMIN_IDS.append(new_admin_id)

    # حفظ في ملف البيئة (إذا أمكن)
    try:
        _save_admin_ids_to_env()
    except Exception as e:
        logger.warning(f"فشل حفظ الأدمنين في ملف البيئة: {e}")

    await update.message.reply_text(
        f"✅ **تم إضافة الأدمن بنجاح**\n\n"
        f"👤 المعرف: `{new_admin_id}`\n"
        f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"🎉 تم منح صلاحيات الأدمن لهذا المستخدم!\n\n"
        f"👑 إدارة الأدمنين:",
        reply_markup=_admin_management_kb(),
        parse_mode="Markdown"
    )
    return AA_START

async def handle_confirm_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد حذف الأدمن"""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("confirm_remove:"):
        return AA_START

    admin_id_to_remove = int(data.split(":")[1])

    # التحقق من أنه لا يحذف نفسه
    current_user_id = update.effective_user.id
    if admin_id_to_remove == current_user_id:
        await query.edit_message_text(
            "⚠️ **لا يمكنك حذف نفسك**\n\n"
            "👑 إدارة الأدمنين:",
            reply_markup=_admin_management_kb(),
            parse_mode="Markdown"
        )
        return AA_START

    # التحقق من أن هناك أكثر من أدمن واحد
    if len(ADMIN_IDS) <= 1:
        await query.edit_message_text(
            "⚠️ **لا يمكن حذف آخر أدمن**\n\n"
            "👑 إدارة الأدمنين:",
            reply_markup=_admin_management_kb(),
            parse_mode="Markdown"
        )
        return AA_START

    # حذف الأدمن
    if admin_id_to_remove in ADMIN_IDS:
        ADMIN_IDS.remove(admin_id_to_remove)

        # حفظ في ملف البيئة
        try:
            _save_admin_ids_to_env()
        except Exception as e:
            logger.warning(f"فشل حفظ الأدمنين في ملف البيئة: {e}")

        await query.edit_message_text(
            f"🗑️ **تم حذف الأدمن**\n\n"
            f"👤 المعرف: `{admin_id_to_remove}`\n"
            f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"⚠️ تم إزالة صلاحيات الأدمن من هذا المستخدم.\n\n"
            f"👑 إدارة الأدمنين:",
            reply_markup=_admin_management_kb(),
            parse_mode="Markdown"
        )
    else:
        await query.edit_message_text(
            "❌ **الأدمن غير موجود**\n\n"
            "👑 إدارة الأدمنين:",
            reply_markup=_admin_management_kb(),
            parse_mode="Markdown"
        )

    return AA_START

def _admin_management_kb():
    """لوحة إدارة الأدمنين"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة أدمن", callback_data="aa:add")],
        [InlineKeyboardButton("🗑️ حذف أدمن", callback_data="aa:remove")],
        [InlineKeyboardButton("📋 عرض الأدمنين", callback_data="aa:list")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="aa:back")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="aa:cancel")]
    ])

def _get_config_env_path():
    """الحصول على المسار المطلق لملف config.env"""
    # المسار المطلق بناءً على مجلد المشروع الجذري
    # bot/handlers/admin/admin_admins.py -> نرجع 3 مستويات للجذر
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(base_dir, '..', '..', '..')
    project_root = os.path.normpath(project_root)
    return os.path.join(project_root, 'config.env')

def _save_admin_ids_to_env():
    """حفظ معرفات الأدمنين في ملف البيئة"""
    config_path = _get_config_env_path()
    try:
        # قراءة ملف البيئة
        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # البحث عن سطر ADMIN_IDS وتحديثه
        updated = False
        for i, line in enumerate(lines):
            if line.startswith('ADMIN_IDS='):
                admin_ids_str = ','.join(map(str, ADMIN_IDS))
                lines[i] = f'ADMIN_IDS={admin_ids_str}\n'
                updated = True
                break

        # إذا لم يوجد السطر، أضفه
        if not updated:
            admin_ids_str = ','.join(map(str, ADMIN_IDS))
            lines.append(f'\nADMIN_IDS={admin_ids_str}\n')

        # كتابة الملف
        with open(config_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        logger.info(f"✅ تم حفظ معرفات الأدمنين في ملف البيئة: {config_path}")
        logger.info(f"✅ ADMIN_IDS = {ADMIN_IDS}")

    except Exception as e:
        logger.error(f"❌ فشل حفظ معرفات الأدمنين في {config_path}: {e}")
        raise

async def _aa_entry_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    نقطة دخول ذكية: عند ضغط زر aa: خارج المحادثة النشطة
    يعيد فتح قائمة إدارة الأدمنين ثم يعالج الزر مباشرة
    """
    query = update.callback_query
    if not query:
        return ConversationHandler.END

    user = update.effective_user
    if not is_admin(user.id):
        try:
            await query.answer("🚫 هذه الخاصية مخصصة للإدمن فقط.", show_alert=True)
        except Exception:
            pass
        return ConversationHandler.END

    # معالجة الزر مباشرة بدلاً من إعادة عرض القائمة
    return await handle_admin_actions(update, context)


def register(app):
    """تسجيل المعالجات"""
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^👑 إدارة الأدمنين$"), start_admin_management),
            # ✅ entry point من لوحة التحكم الرئيسية
            CallbackQueryHandler(start_admin_management, pattern=r"^admin:manage_admins$"),
            # ✅ entry points لأزرار aa: - حتى لو انتهت المحادثة السابقة تعمل الأزرار
            CallbackQueryHandler(_aa_entry_from_button, pattern=r"^aa:"),
        ],
        states={
            AA_START: [
                CallbackQueryHandler(handle_admin_actions, pattern=r"^aa:"),
                CallbackQueryHandler(handle_admin_actions, pattern=r"^remove_admin:"),
            ],
            AA_ADD_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_admin_input),
                CallbackQueryHandler(handle_admin_actions, pattern=r"^aa:"),
            ],
            AA_REMOVE_SELECT: [
                CallbackQueryHandler(handle_admin_actions, pattern=r"^(aa:|remove_admin:)"),
                CallbackQueryHandler(handle_confirm_remove_admin, pattern=r"^confirm_remove:"),
            ],
            AA_CONFIRM_REMOVE: [
                CallbackQueryHandler(handle_confirm_remove_admin, pattern=r"^confirm_remove:"),
                CallbackQueryHandler(handle_admin_actions, pattern=r"^aa:"),
            ]
        },
        fallbacks=[
            CallbackQueryHandler(handle_admin_actions, pattern=r"^aa:"),
            CallbackQueryHandler(handle_admin_actions, pattern=r"^remove_admin:"),
            CallbackQueryHandler(handle_confirm_remove_admin, pattern=r"^confirm_remove:"),
        ],
        name="admin_management_conv",
        per_chat=True,
        per_user=True,
        allow_reentry=True  # ✅ السماح بإعادة الدخول
    )
    app.add_handler(conv)
