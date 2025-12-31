# =============================
# hospital_handlers.py
# معالجات اختيار المستشفى
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging

from .states import STATE_SELECT_HOSPITAL, STATE_SELECT_DEPARTMENT
from .navigation import nav_push
from ..user_reports_add_helpers import PREDEFINED_HOSPITALS

logger = logging.getLogger(__name__)

# ✅ دالة لجلب المستشفيات من قاعدة البيانات مع دمج القائمة المحددة مسبقاً
def get_hospitals_list():
    """جلب المستشفيات من قاعدة البيانات أولاً، ثم دمجها مع القائمة المحددة مسبقاً"""
    db_hospitals = []
    all_hospitals_set = set()
    
    # ✅ 1. جلب المستشفيات من قاعدة البيانات
    try:
        from db.session import SessionLocal
        from db.models import Hospital
        
        with SessionLocal() as s:
            hospitals = s.query(Hospital).order_by(Hospital.name).all()
            if hospitals:
                # ✅ فلترة: فقط المستشفيات الإنجليزية (إزالة العربية)
                db_hospitals = [
                    h.name for h in hospitals 
                    if h.name and not any('\u0600' <= char <= '\u06FF' for char in h.name)
                ]
                all_hospitals_set.update(db_hospitals)
                logger.info(f"✅ Loaded {len(db_hospitals)} English hospitals from database")
    except Exception as e:
        logger.warning(f"⚠️ Could not load hospitals from database: {e}", exc_info=True)
    
    # ✅ 2. دمج القائمة المحددة مسبقاً (إضافة فقط المستشفيات غير الموجودة)
    for predefined_hospital in PREDEFINED_HOSPITALS:
        if predefined_hospital and predefined_hospital not in all_hospitals_set:
            all_hospitals_set.add(predefined_hospital)
    
    # ✅ 3. ترتيب القائمة النهائية
    final_list = list(all_hospitals_set)
    
    # ترتيب: المستشفيات من قاعدة البيانات أولاً، ثم القائمة المحددة مسبقاً
    final_sorted = sorted(final_list, key=lambda x: (
        0 if x in db_hospitals else 1,  # قاعدة البيانات أولاً
        x.lower()  # ثم الترتيب الأبجدي
    ))
    
    logger.info(f"✅ Total hospitals: {len(final_sorted)} (DB: {len(db_hospitals)}, Predefined: {len(PREDEFINED_HOSPITALS)})")
    return final_sorted


def _sort_hospitals_custom(hospitals_list):
    """
    تم تعطيل الترتيب التلقائي - الآن يتم الاحتفاظ بالترتيب من ملف doctors_unified.json
    الترتيب المخصص من المستخدم محفوظ في ملف البيانات
    """
    # إرجاع القائمة كما هي بدون ترتيب
    return list(hospitals_list)

def _sort_hospitals_custom_OLD_DISABLED(hospitals_list):
    """ترتيب المستشفيات حسب الأولوية: Manipal -> Aster -> Bangalore -> البقية - معطل"""
    def get_sort_key(hospital):
        hospital_lower = hospital.lower()
        
        # 1. مستشفيات Manipal أولاً
        if 'manipal' in hospital_lower:
            return (0, hospital)
        
        # 2. مستشفيات Aster ثانياً
        if 'aster' in hospital_lower:
            return (1, hospital)
        
        # 3. مستشفيات Bangalore ثالثاً
        if 'bangalore' in hospital_lower or 'bengaluru' in hospital_lower:
            return (2, hospital)
        
        # 4. البقية
        return (3, hospital)
    
    return sorted(hospitals_list, key=get_sort_key)


def _build_hospitals_keyboard(page=0, search_query="", context=None):
    """بناء لوحة مفاتيح المستشفيات مع بحث"""
    items_per_page = 8

    # ✅ جلب المستشفيات من قاعدة البيانات أولاً
    all_hospitals = get_hospitals_list()
    
    # تصفية المستشفيات إذا كان هناك بحث
    if search_query:
        search_lower = search_query.lower()
        hospitals_list = [
            h for h in all_hospitals if search_lower in h.lower()]
    else:
        hospitals_list = list(all_hospitals)

    total = len(hospitals_list)
    total_pages = max(1, (total + items_per_page - 1) // items_per_page)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total)

    keyboard = []

    # حفظ قائمة المستشفيات في user_data للوصول إليها لاحقاً
    if context:
        context.user_data.setdefault("report_tmp", {})["hospitals_list"] = hospitals_list
        context.user_data["report_tmp"]["hospitals_page"] = page

    # عرض المستشفيات (سطر واحد لكل مستشفى)
    for i in range(start_idx, end_idx):
        hospital_index = i
        keyboard.append([InlineKeyboardButton(
            f"🏥 {hospitals_list[i]}",
            callback_data=f"hospital_idx:{hospital_index}"
        )])

    # أزرار التنقل
    nav_buttons = []
    if total_pages > 1:
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("⬅️ السابق", callback_data=f"hosp_page:{page - 1}"))
        nav_buttons.append(
            InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton("➡️ التالي", callback_data=f"hosp_page:{page + 1}"))
        if nav_buttons:
            keyboard.append(nav_buttons)

    # أزرار التنقل - استخدام زر الرجوع العادي
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="go_to_patient_selection"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = (
        f"🏥 **اختيار المستشفى** (الخطوة 3 من 5)\n\n"
        f"📋 **العدد:** {total} مستشفى"
    )
    if search_query:
        text += f"\n🔍 **البحث:** {search_query}"
    text += f"\n📄 **الصفحة:** {page + 1} من {total_pages}\n\nاختر المستشفى:"

    return text, InlineKeyboardMarkup(keyboard), search_query


async def render_hospital_selection(message, context):
    """عرض شاشة اختيار المستشفى - rendering فقط"""
    text, keyboard, search = _build_hospitals_keyboard(0, "", context)
    context.user_data["report_tmp"]["hospitals_search"] = search
    await message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def show_hospitals_menu(message, context, page=0, search_query=""):
    """Navigation wrapper - يحدث state ثم يستدعي rendering"""
    nav_push(context, STATE_SELECT_HOSPITAL)
    context.user_data['_conversation_state'] = STATE_SELECT_HOSPITAL
    await render_hospital_selection(message, context)


async def handle_hospital_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار المستشفى"""
    
    query = update.callback_query
    await query.answer()

    if query.data.startswith("hospital_idx:"):
        hospital_index = int(query.data.split(":", 1)[1])
        hospitals_list = context.user_data.get("report_tmp", {}).get("hospitals_list", [])
        
        if not hospitals_list:
            logger.warning(f"⚠️ hospitals_list is empty, rebuilding it. Index: {hospital_index}")
            hospitals_list = get_hospitals_list()
            context.user_data.setdefault("report_tmp", {})["hospitals_list"] = hospitals_list
            logger.info(f"✅ Rebuilt hospitals_list with {len(hospitals_list)} hospitals")
        
        if 0 <= hospital_index < len(hospitals_list):
            choice = hospitals_list[hospital_index]
            logger.info(f"✅ Selected hospital at index {hospital_index}: {choice}")
        else:
            logger.error(f"❌ Invalid hospital index: {hospital_index}, list length: {len(hospitals_list)}")
            hospitals_list = get_hospitals_list()
            context.user_data.setdefault("report_tmp", {})["hospitals_list"] = hospitals_list
            if 0 <= hospital_index < len(hospitals_list):
                choice = hospitals_list[hospital_index]
                logger.info(f"✅ Selected hospital after rebuild at index {hospital_index}: {choice}")
            else:
                logger.error(f"❌ Still invalid index after rebuild: {hospital_index}")
                await query.answer("❌ خطأ في اختيار المستشفى. يرجى المحاولة مرة أخرى.", show_alert=True)
                return STATE_SELECT_HOSPITAL
    else:
        choice = query.data.split(":", 1)[1]
        logger.info(f"✅ Selected hospital from callback data: {choice}")

    context.user_data["report_tmp"]["hospital_name"] = choice
    context.user_data["report_tmp"].pop("hospitals_search", None)
    context.user_data["report_tmp"].pop("hospitals_search_mode", None)
    context.user_data["report_tmp"].pop("hospitals_list", None)
    
    context.user_data['last_valid_state'] = 'department_selection'
    context.user_data['_conversation_state'] = STATE_SELECT_DEPARTMENT

    try:
        await query.edit_message_text(
            f"✅ **تم اختيار المستشفى**\n\n"
            f"🏥 **المستشفى:**\n"
            f"{choice}"
        )
    except Exception as e:
        logger.warning(f"⚠️ Could not edit message, sending new one: {e}")
        await query.message.reply_text(
            f"✅ **تم اختيار المستشفى**\n\n"
            f"🏥 **المستشفى:**\n"
            f"{choice}"
        )
    
    from .department_handlers import show_departments_menu
    await show_departments_menu(query.message, context)
    return STATE_SELECT_DEPARTMENT


async def handle_hospital_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل بين صفحات المستشفيات"""
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 1)[1])
    search = context.user_data.get("report_tmp", {}).get("hospitals_search", "")
    text, keyboard, search = _build_hospitals_keyboard(page, search, context)
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    return STATE_SELECT_HOSPITAL


async def handle_hospital_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج البحث في المستشفيات"""
    if update.message:
        search_mode = context.user_data.get("report_tmp", {}).get("hospitals_search_mode", False)
        if search_mode:
            search_query = update.message.text.strip()
            context.user_data["report_tmp"]["hospitals_search"] = search_query
            context.user_data["report_tmp"]["hospitals_search_mode"] = False
            text, keyboard, _ = _build_hospitals_keyboard(0, search_query, context)
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
            return STATE_SELECT_HOSPITAL
        else:
            return STATE_SELECT_HOSPITAL

