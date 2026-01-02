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
from db.models import User
from bot.shared_auth import is_admin

logger = logging.getLogger(__name__)

# مسار ملف المترجمين
TRANSLATOR_NAMES_FILE = "data/translator_names.txt"


def get_translator_names_from_file():
    """قراءة أسماء المترجمين من الملف"""
    try:
        if os.path.exists(TRANSLATOR_NAMES_FILE):
            with open(TRANSLATOR_NAMES_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            names = []
            for line in lines:
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


async def handle_add_translator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إضافة مترجم جديد"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "➕ **إضافة مترجم جديد**\n\n"
        "📝 اكتب اسم المترجم:\n"
        "مثال: أحمد محمد",
        parse_mode=ParseMode.MARKDOWN
    )
    return "ADD_TRANSLATOR_NAME"


async def handle_translator_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم المترجم الجديد"""
    name = update.message.text.strip()
    
    if not name or len(name) < 2:
        await update.message.reply_text(
            "⚠️ **خطأ:** الاسم قصير جداً\n\n"
            "يرجى إدخال اسم صحيح:",
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
    
    # إضافة الاسم
    names.append(name)
    
    if save_translator_names_to_file(names):
        logger.info(f"✅ تم إضافة المترجم '{name}'")
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]])
        
        await update.message.reply_text(
            f"✅ **تم إضافة المترجم بنجاح:** {name}\n\n"
            f"👥 سيظهر المترجم عند إنشاء تقرير جديد",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            "❌ **خطأ في الحفظ**",
            parse_mode=ParseMode.MARKDOWN
        )
    
    return ConversationHandler.END


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
    
    # حذف الاسم
    if name_to_delete in names:
        names.remove(name_to_delete)
        
        if save_translator_names_to_file(names):
            logger.info(f"✅ تم حذف المترجم '{name_to_delete}'")
            
            await query.edit_message_text(
                f"✅ **تم حذف المترجم:** {name_to_delete}\n\n"
                f"📊 **عدد المترجمين المتبقين:** {len(names)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]]),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await query.edit_message_text(
                "❌ **خطأ في الحفظ**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]]),
                parse_mode=ParseMode.MARKDOWN
            )
    else:
        await query.edit_message_text(
            "⚠️ **المترجم غير موجود**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_translators")]]),
            parse_mode=ParseMode.MARKDOWN
        )


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
    
    await query.edit_message_text(
        f"✏️ **تعديل اسم المترجم**\n\n"
        f"👤 **الاسم الحالي:** {old_name}\n\n"
        f"اكتب الاسم الجديد:",
        parse_mode=ParseMode.MARKDOWN
    )
    
    return "EDIT_TRANSLATOR_INPUT"


async def handle_edit_translator_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال الاسم الجديد للمترجم"""
    new_name = update.message.text.strip()
    
    if not new_name or len(new_name) < 2:
        await update.message.reply_text(
            "⚠️ **خطأ:** الاسم قصير جداً\n\n"
            "يرجى إدخال اسم صحيح:",
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
    
    # تعديل الاسم
    if index < len(names) and names[index] == old_name:
        names[index] = new_name
        
        if save_translator_names_to_file(names):
            logger.info(f"✅ تم تعديل اسم المترجم من '{old_name}' إلى '{new_name}'")
            
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
                "❌ **خطأ في الحفظ**",
                parse_mode=ParseMode.MARKDOWN
            )
    else:
        await update.message.reply_text(
            "⚠️ **المترجم غير موجود**",
            parse_mode=ParseMode.MARKDOWN
        )
    
    return ConversationHandler.END


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
                        current_names.add(first_name)
                        added_count += 1
        
        # حفظ الأسماء
        names_list = sorted(list(current_names))
        save_translator_names_to_file(names_list)
        
        logger.info(f"✅ تم مزامنة {added_count} مترجم جديد")
        
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
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_translator_input)
            ],
            "ADD_TRANSLATOR_NAME": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_translator_name_input)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(handle_manage_translators, pattern="^manage_translators$")
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
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

