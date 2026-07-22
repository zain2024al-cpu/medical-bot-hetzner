# ================================================
# bot/handlers/admin/admin_translators_management.py
# 🔹 إدارة المترجمين (أسماء المترجمين للاختيار عند إنشاء تقرير)
# ================================================

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode
import logging
import os
from db.session import SessionLocal
from db.models import User, TranslatorDirectory
from bot.shared_auth import is_admin
from bot.handlers.admin.decorators import require_admin

logger = logging.getLogger(__name__)

# مسار ملف المترجمين
TRANSLATOR_NAMES_FILE = "data/translator_names.txt"


# ================================================
# DB helpers — dual-write authority convergence
# ================================================

def _db_add_translator(name: str, telegram_id: int | None = None) -> bool:
    """
    Add translator to TranslatorDirectory (DB authority).
    translator_id is the given Telegram ID if provided, otherwise NULL.
    Returns True on success or if already exists, False on error.
    """
    try:
        with SessionLocal() as s:
            existing = s.query(TranslatorDirectory).filter(
                TranslatorDirectory.name == name
            ).first()
            if existing:
                logger.info("TD: translator already exists in DB: [%s]", name)
                return True
            s.add(TranslatorDirectory(translator_id=telegram_id, name=name))
            s.commit()
            logger.info("TD: added translator to DB: [%s] id=%s", name, telegram_id)
            return True
    except Exception as e:
        logger.error("TD: failed to add translator [%s]: %s", name, e)
        return False


def _find_translator_by_id(telegram_id: int):
    """يبحث عن مترجم بآيدي تيليجرام معيّن، لمنع تعارض المفتاح الأساسي."""
    try:
        with SessionLocal() as s:
            return s.query(TranslatorDirectory).filter(
                TranslatorDirectory.translator_id == telegram_id
            ).first()
    except Exception as e:
        logger.error("TD: failed to look up translator_id=%s: %s", telegram_id, e)
        return None


def _db_delete_translator(name: str) -> bool:
    """
    Remove translator from TranslatorDirectory by exact name.
    Safe: no FK cascade — historical reports retain their denormalized fields.
    Returns True if deleted or not found (idempotent), False on error.
    """
    try:
        with SessionLocal() as s:
            row = s.query(TranslatorDirectory).filter(
                TranslatorDirectory.name == name
            ).first()
            if row:
                s.delete(row)
                s.commit()
                logger.info("TD: deleted translator from DB: [%s]", name)
            else:
                logger.warning("TD: translator not found in DB for delete: [%s]", name)
            return True
    except Exception as e:
        logger.error("TD: failed to delete translator [%s]: %s", name, e)
        return False


def _db_rename_translator(old_name: str, new_name: str) -> bool:
    """
    Rename translator in TranslatorDirectory (old_name → new_name).
    If old_name not found, inserts new_name as a new entry (NULL translator_id).
    Returns True on success, False on error.
    """
    try:
        with SessionLocal() as s:
            row = s.query(TranslatorDirectory).filter(
                TranslatorDirectory.name == old_name
            ).first()
            if row:
                row.name = new_name
                s.commit()
                logger.info("TD: renamed translator in DB: [%s] -> [%s]", old_name, new_name)
            else:
                # old_name never existed in DB — insert new entry
                s.add(TranslatorDirectory(translator_id=None, name=new_name))
                s.commit()
                logger.warning(
                    "TD: old_name [%s] not found in DB during rename; inserted [%s] as new entry",
                    old_name, new_name
                )
            return True
    except Exception as e:
        logger.error("TD: failed to rename translator [%s] -> [%s]: %s", old_name, new_name, e)
        return False


def _db_add_translator_if_absent(name: str) -> bool:
    """
    Add translator to DB only if not already present (used by sync path).
    Returns True on success or already-exists, False on error.
    """
    return _db_add_translator(name)


def get_translator_names_from_file():
    """قراءة أسماء المترجمين من الملف (يدعم UTF-16 مع BOM أو UTF-8)"""
    try:
        if os.path.exists(TRANSLATOR_NAMES_FILE):
            with open(TRANSLATOR_NAMES_FILE, 'rb') as f:
                raw = f.read()
            if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
                text = raw.decode('utf-16')
            else:
                text = raw.decode('utf-8-sig')
            names = []
            for line in text.splitlines():
                line = line.strip()
                if line and not line.startswith('#'):
                    names.append(line)
            return names
    except Exception as e:
        logger.error(f"❌ خطأ في قراءة ملف المترجمين: {e}")
    return []


def save_translator_names_to_file(names):
    """حفظ أسماء المترجمين في الملف"""
    try:
        os.makedirs(os.path.dirname(TRANSLATOR_NAMES_FILE), exist_ok=True)
        with open(TRANSLATOR_NAMES_FILE, 'w', encoding='utf-8') as f:
            f.write("# أسماء المترجمين\n")
            for name in names:
                f.write(f"{name}\n")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في حفظ ملف المترجمين: {e}")
        return False


# ================================================
# إدارة المترجمين
# ================================================

async def handle_manage_translators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة المترجمين"""
    query = update.callback_query
    await query.answer()
    
    # التحقق من صلاحيات الأدمن
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
        return ConversationHandler.END
    
    # قراءة المترجمين من الملف
    names = get_translator_names_from_file()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة مترجم جديد", callback_data="add_translator")],
        [InlineKeyboardButton("📋 عرض جميع المترجمين", callback_data="view_translators")],
        [InlineKeyboardButton("✏️ تعديل مترجم", callback_data="edit_translator")],
        [InlineKeyboardButton("🗑️ حذف مترجم", callback_data="delete_translator")],
        [InlineKeyboardButton("🔄 مزامنة من المستخدمين", callback_data="sync_translators")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_schedule")]
    ])
    
    await query.edit_message_text(
        f"👥 **إدارة المترجمين**\n\n"
        f"📊 **عدد المترجمين:** {len(names)}\n\n"
        f"اختر العملية:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


@require_admin
async def handle_view_translators(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    """عرض جميع المترجمين مع صفحات"""
    query = update.callback_query
    await query.answer()
    
    # استخراج رقم الصفحة من callback_data إذا موجود
    if query.data.startswith("view_translators_page:"):
        page = int(query.data.split(":")[1])
    
    names = get_translator_names_from_file()
    
    if not names:
        text = "📋 **قائمة المترجمين**\n\n⚠️ لا يوجد مترجمين مسجلين\n\nاستخدم '➕ إضافة مترجم جديد' أو '🔄 مزامنة من المستخدمين'"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]
        ])
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # ترتيب المترجمين أبجدياً
        names_sorted = sorted(names, key=lambda x: x.strip())
        
        # إعدادات الصفحات
        items_per_page = 20
        total = len(names_sorted)
        total_pages = max(1, (total + items_per_page - 1) // items_per_page)
        page = max(0, min(page, total_pages - 1))
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, total)
        
        text = f"📋 **قائمة المترجمين**\n\n"
        text += f"📊 **العدد:** {total}\n"
        text += f"📄 **الصفحة:** {page + 1} من {total_pages}\n\n"
        
        for i in range(start_idx, end_idx):
            text += f"{i + 1}. 👤 {names_sorted[i]}\n"
        
        # أزرار التنقل
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"view_translators_page:{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️ التالي", callback_data=f"view_translators_page:{page + 1}"))
        
        keyboard = []
        if nav_buttons:
            keyboard.append(nav_buttons)
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )


@require_admin
async def handle_add_translator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إضافة مترجم جديد"""
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_translator_input")]
    ])

    await query.edit_message_text(
        "➕ **إضافة مترجم جديد**\n\n"
        "📝 اكتب اسم المترجم:\n"
        "مثال: أحمد محمد",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return "ADD_TRANSLATOR_NAME"


@require_admin
async def handle_translator_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم المترجم الجديد"""
    name = update.message.text.strip()
    
    if not name or len(name) < 2:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_translator_input")]
        ])
        await update.message.reply_text(
            "⚠️ **خطأ:** الاسم قصير جداً\n\n"
            "يرجى إدخال اسم صحيح:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return "ADD_TRANSLATOR_NAME"
    
    # قراءة الأسماء الحالية
    names = get_translator_names_from_file()
    
    # التحقق من التكرار
    if name in names:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]])
        await update.message.reply_text(
            f"⚠️ **المترجم موجود مسبقاً:** {name}",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    
    # حفظ الاسم مؤقتاً، والانتقال لخطوة إدخال آيدي التيليجرام
    context.user_data['add_translator_pending_name'] = name

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭️ تخطي (بدون آيدي)", callback_data="add_translator_skip_id")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_translator_input")]
    ])

    await update.message.reply_text(
        f"👤 **الاسم:** {name}\n\n"
        "🔢 أدخل رقم آيدي التيليجرام الخاص بالمترجم:\n"
        "(أو اضغط 'تخطي' لإضافته بدون آيدي الآن)",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    return "ADD_TRANSLATOR_ID"


async def _finalize_add_translator(reply_target, context, name: str, telegram_id: int | None, edit: bool):
    """يكمل إضافة المترجم إلى القاعدة والملف، برد إما بـ edit_message_text أو reply_text."""
    names = get_translator_names_from_file()

    if name in names:
        text = f"⚠️ **المترجم موجود مسبقاً:** {name}"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]])
        if edit:
            await reply_target.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        else:
            await reply_target.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    names.append(name)

    db_ok = _db_add_translator(name, telegram_id=telegram_id)
    if not db_ok:
        logger.error("TD: DB write failed for add [%s] id=%s — aborting file write", name, telegram_id)
        text = "❌ **خطأ في الحفظ في قاعدة البيانات**\n\nلم يتم الحفظ."
        if edit:
            await reply_target.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
        else:
            await reply_target.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    file_ok = save_translator_names_to_file(names)
    if not file_ok:
        logger.warning("TD: file write failed after DB success for add [%s] — DB is authoritative", name)

    logger.info("TD add complete: [%s]  id=%s  db=%s  file=%s", name, telegram_id, db_ok, file_ok)

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]])
    id_line = f"\n🆔 **الآيدي:** {telegram_id}" if telegram_id else ""
    text = (
        f"✅ **تم إضافة المترجم بنجاح:** {name}{id_line}\n\n"
        f"👥 سيظهر المترجم عند إنشاء تقرير جديد"
    )

    if edit:
        await reply_target.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        await reply_target.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    return ConversationHandler.END


@require_admin
async def handle_translator_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال آيدي التيليجرام للمترجم الجديد"""
    text = update.message.text.strip()

    name = context.user_data.get('add_translator_pending_name')
    if not name:
        await update.message.reply_text("❌ **خطأ:** لم يتم العثور على اسم المترجم.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭️ تخطي (بدون آيدي)", callback_data="add_translator_skip_id")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_translator_input")]
    ])

    if not text.isdigit():
        await update.message.reply_text(
            "⚠️ **خطأ:** الآيدي يجب أن يكون أرقاماً فقط\n\n"
            "أدخل رقم آيدي التيليجرام، أو اضغط 'تخطي':",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return "ADD_TRANSLATOR_ID"

    telegram_id = int(text)

    conflict = _find_translator_by_id(telegram_id)
    if conflict:
        await update.message.reply_text(
            f"⚠️ **هذا الآيدي مستخدَم بالفعل للمترجم:** {conflict.name}\n\n"
            "أدخل آيدي آخر، أو اضغط 'تخطي' لإضافته بدون آيدي:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return "ADD_TRANSLATOR_ID"

    context.user_data.pop('add_translator_pending_name', None)
    return await _finalize_add_translator(update.message, context, name, telegram_id, edit=False)


@require_admin
async def handle_add_translator_skip_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تخطي إدخال الآيدي — إضافة المترجم بدون آيدي تيليجرام"""
    query = update.callback_query
    await query.answer()

    name = context.user_data.pop('add_translator_pending_name', None)
    if not name:
        await query.edit_message_text("❌ **خطأ:** لم يتم العثور على اسم المترجم.", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    return await _finalize_add_translator(query, context, name, None, edit=True)


@require_admin
async def handle_delete_translator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """واجهة حذف مترجم"""
    query = update.callback_query
    await query.answer()
    
    names = get_translator_names_from_file()
    
    if not names:
        await query.edit_message_text(
            "⚠️ **لا يوجد مترجمين لحذفهم**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]]),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # ترتيب أبجدي
    names_sorted = sorted(names, key=lambda x: x.strip())
    
    # حفظ الأسماء في context
    context.user_data['delete_translator_names_list'] = names_sorted
    
    # استخراج رقم الصفحة
    page = 0
    if query.data.startswith("delete_trans_page:"):
        page = int(query.data.split(":")[1])
    
    # إعدادات الصفحات
    items_per_page = 10
    total = len(names_sorted)
    total_pages = max(1, (total + items_per_page - 1) // items_per_page)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total)
    
    # عرض المترجمين مع أزرار حذف
    keyboard = []
    for i in range(start_idx, end_idx):
        display_name = names_sorted[i][:25] + "..." if len(names_sorted[i]) > 25 else names_sorted[i]
        keyboard.append([InlineKeyboardButton(
            f"🗑️ {display_name}",
            callback_data=f"confirm_delete_trans:{i}"  # index فقط
        )])
    
    # أزرار التنقل
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"delete_trans_page:{page - 1}"))
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("➡️ التالي", callback_data=f"delete_trans_page:{page + 1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")])
    
    await query.edit_message_text(
        f"🗑️ **حذف مترجم**\n\n"
        f"📊 **العدد:** {total}\n"
        f"📄 **الصفحة:** {page + 1} من {total_pages}\n\n"
        f"اختر المترجم المراد حذفه:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


@require_admin
async def handle_confirm_delete_translator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد حذف مترجم"""
    query = update.callback_query
    await query.answer()
    
    # استخراج البيانات
    parts = query.data.split(':')
    if len(parts) < 2 or not parts[1].isdigit():
        await query.edit_message_text("❌ خطأ: طلب حذف غير صالح.")
        return
    
    index = int(parts[1])
    
    # استخراج الاسم من context
    names_list = context.user_data.get('delete_translator_names_list', [])
    if index >= len(names_list):
        await query.edit_message_text(
            "❌ **خطأ:** الفهرس غير صالح",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]]),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    name_to_delete = names_list[index]
    
    # قراءة الأسماء من الملف
    names = get_translator_names_from_file()
    
    # حذف الاسم — DB first (authority), then file (backup)
    if name_to_delete in names:
        names.remove(name_to_delete)

        db_ok = _db_delete_translator(name_to_delete)
        if not db_ok:
            logger.error("TD: DB write failed for delete [%s] — aborting file write", name_to_delete)
            await query.edit_message_text(
                "❌ **خطأ في الحذف من قاعدة البيانات**\n\nلم يتم الحذف.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]]),
                parse_mode=ParseMode.MARKDOWN
            )
            return

        file_ok = save_translator_names_to_file(names)
        if not file_ok:
            logger.warning("TD: file write failed after DB success for delete [%s] — DB is authoritative", name_to_delete)

        logger.info("TD delete complete: [%s]  db=%s  file=%s", name_to_delete, db_ok, file_ok)

        await query.edit_message_text(
            f"✅ **تم حذف المترجم:** {name_to_delete}\n\n"
            f"📊 **عدد المترجمين المتبقين:** {len(names)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]]),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await query.edit_message_text(
            "⚠️ **المترجم غير موجود**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]]),
            parse_mode=ParseMode.MARKDOWN
        )


@require_admin
async def handle_edit_translator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """واجهة تعديل مترجم"""
    query = update.callback_query
    await query.answer()
    
    names = get_translator_names_from_file()
    
    if not names:
        await query.edit_message_text(
            "⚠️ **لا يوجد مترجمين لتعديلهم**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]]),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # ترتيب أبجدي
    names_sorted = sorted(names, key=lambda x: x.strip())
    
    # حفظ الأسماء في context
    context.user_data['edit_translator_names_list'] = names_sorted
    
    # استخراج رقم الصفحة
    page = 0
    if query.data.startswith("edit_trans_page:"):
        page = int(query.data.split(":")[1])
    
    # إعدادات الصفحات
    items_per_page = 10
    total = len(names_sorted)
    total_pages = max(1, (total + items_per_page - 1) // items_per_page)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total)
    
    # عرض المترجمين مع أزرار تعديل
    keyboard = []
    for i in range(start_idx, end_idx):
        display_name = names_sorted[i][:25] + "..." if len(names_sorted[i]) > 25 else names_sorted[i]
        keyboard.append([InlineKeyboardButton(
            f"✏️ {display_name}",
            callback_data=f"select_edit_trans:{i}"  # index فقط
        )])
    
    # أزرار التنقل
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"edit_trans_page:{page - 1}"))
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("➡️ التالي", callback_data=f"edit_trans_page:{page + 1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")])
    
    await query.edit_message_text(
        f"✏️ **تعديل مترجم**\n\n"
        f"📊 **العدد:** {total}\n"
        f"📄 **الصفحة:** {page + 1} من {total_pages}\n\n"
        f"اختر المترجم المراد تعديله:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


@require_admin
async def handle_select_edit_translator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار مترجم للتعديل"""
    query = update.callback_query
    await query.answer()
    
    # استخراج البيانات
    parts = query.data.split(':')
    if len(parts) < 2 or not parts[1].isdigit():
        await query.edit_message_text("❌ خطأ: طلب تعديل غير صالح.")
        return ConversationHandler.END
    
    index = int(parts[1])
    
    # استخراج الاسم من context
    names_list = context.user_data.get('edit_translator_names_list', [])
    if index >= len(names_list):
        await query.edit_message_text(
            "❌ **خطأ:** الفهرس غير صالح",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]]),
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    
    old_name = names_list[index]
    
    # حفظ في context
    context.user_data['edit_translator_index'] = index
    context.user_data['edit_translator_old_name'] = old_name
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_translator_input")]
    ])

    await query.edit_message_text(
        f"✏️ **تعديل اسم المترجم**\n\n"
        f"👤 **الاسم الحالي:** {old_name}\n\n"
        f"اكتب الاسم الجديد:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    return "EDIT_TRANSLATOR_INPUT"


@require_admin
async def handle_edit_translator_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال الاسم الجديد للمترجم"""
    new_name = update.message.text.strip()
    
    if not new_name or len(new_name) < 2:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_translator_input")]
        ])
        await update.message.reply_text(
            "⚠️ **خطأ:** الاسم قصير جداً\n\n"
            "يرجى إدخال اسم صحيح:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return "EDIT_TRANSLATOR_INPUT"
    
    # الحصول على البيانات المحفوظة
    index = context.user_data.get('edit_translator_index')
    old_name = context.user_data.get('edit_translator_old_name')
    
    if index is None or old_name is None:
        await update.message.reply_text("❌ **خطأ:** لم يتم اختيار مترجم للتعديل", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    
    # قراءة الأسماء
    names = get_translator_names_from_file()
    
    # تعديل الاسم — DB first (authority), then file (backup)
    if index < len(names) and names[index] == old_name:
        names[index] = new_name

        db_ok = _db_rename_translator(old_name, new_name)
        if not db_ok:
            logger.error("TD: DB write failed for rename [%s]->[%s] — aborting file write", old_name, new_name)
            await update.message.reply_text(
                "❌ **خطأ في التعديل في قاعدة البيانات**\n\nلم يتم التعديل.",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END

        file_ok = save_translator_names_to_file(names)
        if not file_ok:
            logger.warning(
                "TD: file write failed after DB success for rename [%s]->[%s] — DB is authoritative",
                old_name, new_name
            )

        logger.info("TD rename complete: [%s]->[%s]  db=%s  file=%s", old_name, new_name, db_ok, file_ok)

        # مسح البيانات المحفوظة
        context.user_data.pop('edit_translator_index', None)
        context.user_data.pop('edit_translator_old_name', None)

        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]])

        await update.message.reply_text(
            f"✅ **تم تعديل اسم المترجم بنجاح**\n\n"
            f"👤 **من:** {old_name}\n"
            f"👤 **إلى:** {new_name}",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            "⚠️ **المترجم غير موجود**",
            parse_mode=ParseMode.MARKDOWN
        )
    
    return ConversationHandler.END


@require_admin
async def handle_sync_translators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مزامنة المترجمين من قاعدة البيانات (المستخدمين المعتمدين)"""
    query = update.callback_query
    await query.answer()
    
    try:
        # قراءة الأسماء الحالية من الملف
        current_names = set(get_translator_names_from_file())
        
        # جلب المستخدمين المعتمدين من قاعدة البيانات
        added_count = 0
        with SessionLocal() as s:
            users = s.query(User).filter(
                User.is_approved == True,
                User.full_name.isnot(None)
            ).all()
            
            for user in users:
                # استخراج الاسم الأول أو الاسم الكامل المختصر
                full_name = user.full_name.strip()
                if full_name and full_name not in current_names:
                    # إضافة الاسم الأول فقط لتسهيل الاختيار
                    first_name = full_name.split()[0] if full_name else None
                    if first_name and first_name not in current_names:
                        # DB write first (authority); file write follows after loop
                        db_ok = _db_add_translator_if_absent(first_name)
                        if not db_ok:
                            logger.error(
                                "TD: DB write failed during sync for [%s] — skipping this entry",
                                first_name
                            )
                            continue
                        current_names.add(first_name)
                        added_count += 1

        # حفظ الأسماء — file write after all DB writes succeed
        names_list = sorted(list(current_names))
        file_ok = save_translator_names_to_file(names_list)
        if not file_ok:
            logger.warning("TD: file write failed after sync DB writes — DB is authoritative, %d entries added", added_count)

        logger.info("TD sync complete: added=%d  total=%d  file=%s", added_count, len(names_list), file_ok)
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]])
        
        await query.edit_message_text(
            f"✅ **تمت المزامنة بنجاح**\n\n"
            f"➕ **مترجمين جدد:** {added_count}\n"
            f"📊 **إجمالي المترجمين:** {len(names_list)}",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"❌ خطأ في مزامنة المترجمين: {e}")
        await query.edit_message_text(
            f"❌ **خطأ في المزامنة:** {str(e)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]]),
            parse_mode=ParseMode.MARKDOWN
        )


@require_admin
async def handle_cancel_translator_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء عملية إضافة/تعديل مترجم"""
    query = update.callback_query
    await query.answer()

    # مسح البيانات المؤقتة
    context.user_data.pop('edit_translator_index', None)
    context.user_data.pop('edit_translator_old_name', None)
    context.user_data.pop('edit_translator_names_list', None)

    names = get_translator_names_from_file()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة مترجم جديد", callback_data="add_translator")],
        [InlineKeyboardButton("📋 عرض جميع المترجمين", callback_data="view_translators")],
        [InlineKeyboardButton("✏️ تعديل مترجم", callback_data="edit_translator")],
        [InlineKeyboardButton("🗑️ حذف مترجم", callback_data="delete_translator")],
        [InlineKeyboardButton("🔄 مزامنة من القائمة الثابتة", callback_data="sync_translators")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_schedule")]
    ])

    await query.edit_message_text(
        f"❌ **تم إلغاء العملية**\n\n"
        f"👥 **إدارة المترجمين**\n"
        f"📊 **عدد المترجمين:** {len(names)}\n\n"
        f"اختر العملية:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END


def register(app):
    """تسجيل الهاندلرز"""

    # ConversationHandler لإدارة المترجمين (إضافة وتعديل)
    translators_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_select_edit_translator, pattern="^select_edit_trans:"),
            CallbackQueryHandler(handle_add_translator, pattern="^add_translator$")
        ],
        states={
            "EDIT_TRANSLATOR_INPUT": [
                CallbackQueryHandler(handle_cancel_translator_input, pattern="^cancel_translator_input$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_translator_input)
            ],
            "ADD_TRANSLATOR_NAME": [
                CallbackQueryHandler(handle_cancel_translator_input, pattern="^cancel_translator_input$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translator_name_input)
            ],
            "ADD_TRANSLATOR_ID": [
                CallbackQueryHandler(handle_add_translator_skip_id, pattern="^add_translator_skip_id$"),
                CallbackQueryHandler(handle_cancel_translator_input, pattern="^cancel_translator_input$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translator_id_input)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(handle_cancel_translator_input, pattern="^cancel_translator_input$"),
            CallbackQueryHandler(handle_manage_translators, pattern="^manage_translators$")
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=True,
        name="translators_conv"
    )
    
    # تسجيل الهاندلرز
    app.add_handler(translators_conv)
    app.add_handler(CallbackQueryHandler(handle_manage_translators, pattern="^manage_translators$"))
    app.add_handler(CallbackQueryHandler(handle_view_translators, pattern="^view_translators$"))
    app.add_handler(CallbackQueryHandler(handle_view_translators, pattern="^view_translators_page:"))  # صفحات المترجمين
    app.add_handler(CallbackQueryHandler(handle_delete_translator, pattern="^delete_translator$"))
    app.add_handler(CallbackQueryHandler(handle_delete_translator, pattern="^delete_trans_page:"))  # صفحات الحذف
    app.add_handler(CallbackQueryHandler(handle_confirm_delete_translator, pattern="^confirm_delete_trans:\\d+$"))  # index فقط
    app.add_handler(CallbackQueryHandler(handle_edit_translator, pattern="^edit_translator$"))
    app.add_handler(CallbackQueryHandler(handle_edit_translator, pattern="^edit_trans_page:"))  # صفحات التعديل
    app.add_handler(CallbackQueryHandler(handle_sync_translators, pattern="^sync_translators$"))

