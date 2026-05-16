# =============================
# hospital_handlers.py
# معالجات اختيار المستشفى
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging

from .states import STATE_SELECT_HOSPITAL, STATE_SELECT_DEPARTMENT
from .navigation import nav_push
from .ui_primitives import paginate, pagination_buttons, screen_header, smart_rows
from .selector_context import SelectorContext

logger = logging.getLogger(__name__)

def _get_usage_counts() -> dict:
    """
    يجلب عدد التقارير لكل مستشفى من جدول Report.
    يُعيد dict: {hospital_name_lower: count}
    """
    try:
        from db.session import SessionLocal
        from db.models import Report
        from sqlalchemy import func
        with SessionLocal() as s:
            rows = (
                s.query(Report.hospital_name, func.count(Report.id))
                .filter(Report.hospital_name.isnot(None), Report.hospital_name != "")
                .group_by(Report.hospital_name)
                .all()
            )
        return {name.strip().lower(): cnt for name, cnt in rows}
    except Exception as e:
        logger.warning(f"⚠️ Could not fetch usage counts: {e}")
        return {}


def get_hospitals_list() -> list:
    """
    جلب المستشفيات مرتبةً حسب الاستخدام (الأكثر استخداماً أولاً).
    المصدر: Hospital table مع ترتيب من Report.hospital_name.
    Fallback للأبجدية إذا لم تتوفر إحصاءات.
    """
    db_hospitals = []

    try:
        from db.session import SessionLocal
        from db.models import Hospital
        with SessionLocal() as s:
            hospitals = s.query(Hospital).all()
            if hospitals:
                from services.hospitals_service import _INVALID_HOSPITAL_NAMES
                db_hospitals = [
                    h.name for h in hospitals
                    if h.name and h.name.strip() not in _INVALID_HOSPITAL_NAMES
                ]
    except Exception as e:
        logger.warning(f"⚠️ Could not load hospitals from database: {e}", exc_info=True)

    if not db_hospitals:
        try:
            from services.hospitals_service import get_all_hospitals
            json_hospitals = get_all_hospitals() or []
            logger.warning(f"⚠️ Hospitals DB empty — JSON fallback ({len(json_hospitals)})")
            return list(json_hospitals)
        except Exception as e:
            logger.error(f"❌ Failed to load hospitals from JSON fallback: {e}", exc_info=True)
            return []

    # إزالة التكرار
    seen = set()
    unique = []
    for name in db_hospitals:
        key = name.strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(name)

    # ترتيب حسب الاستخدام (تنازلياً) ثم أبجدياً كفاصل
    usage = _get_usage_counts()
    unique.sort(key=lambda n: (-usage.get(n.strip().lower(), 0), n))

    logger.info(f"✅ Hospitals sorted by usage: {len(unique)} total")
    return unique

def _build_hospitals_keyboard(page=0, search_query="", context=None):
    """بناء لوحة مفاتيح المستشفيات مع بحث"""
    all_hospitals = get_hospitals_list()

    if search_query:
        search_lower = search_query.lower()
        hospitals_list = [h for h in all_hospitals if search_lower in h.lower()]
    else:
        hospitals_list = list(all_hospitals)

    total = len(hospitals_list)
    page_items, page, total_pages = paginate(hospitals_list, page, per_page=8)

    if context:
        context.user_data.setdefault("report_tmp", {})["hospitals_list"] = hospitals_list
        context.user_data["report_tmp"]["hospitals_page"] = page
        SelectorContext.save_hospital(context, page=page, search=search_query)

    start_idx = page * 8
    indexed = list(enumerate(page_items))

    def make_btn(item):
        i, name = item
        display = f"🏥 {name}"
        return InlineKeyboardButton(display, callback_data=f"hospital_idx:{start_idx + i}")

    keyboard = smart_rows(
        [{"name": name, "_i": i} for i, name in indexed],
        lambda item: InlineKeyboardButton(
            f"🏥 {item['name']}",
            callback_data=f"hospital_idx:{start_idx + item['_i']}"
        )
    )

    nav_row = pagination_buttons(page, total_pages, "hosp_page")
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="go_to_patient_selection"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    context_line = f"🔍 نتائج: **{search_query}**" if search_query else ""
    text = screen_header(
        icon="🏥", title="اختيار المستشفى",
        step=3, total_steps=6,
        count=total, count_label="مستشفى",
        page=page, total_pages=total_pages,
        context_line=context_line,
    )
    return text, InlineKeyboardMarkup(keyboard), search_query


async def render_hospital_selection(message, context, query=None,
                                    page: int = 0, search: str = ""):
    """عرض شاشة اختيار المستشفى.
    - query  : إذا مُمرَّر يُعدَّل الرسالة الحالية (للرجوع). وإلا ترسل رسالة جديدة.
    - page/search: استعادة السياق المحفوظ عند الرجوع.
    """
    text, keyboard, resolved_search = _build_hospitals_keyboard(page, search, context)
    context.user_data.setdefault("report_tmp", {})["hospitals_search"] = resolved_search
    if query:
        try:
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
            return
        except Exception:
            pass
    await message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def show_hospitals_menu(message, context, page=None, search_query=None, query=None,
                              restore=False):
    """Navigation wrapper - يحدث state ثم يستدعي rendering.
    restore=True: يستعيد السياق المحفوظ (للرجوع).
    restore=False: يبدأ من page=0 (عند الوصول الطبيعي).
    """
    nav_push(context, STATE_SELECT_HOSPITAL)
    context.user_data['_conversation_state'] = STATE_SELECT_HOSPITAL
    if restore:
        ctx = SelectorContext.load_hospital(context)
        _page = ctx.page
        _search = ctx.search
    else:
        _page = page if page is not None else 0
        _search = search_query if search_query is not None else ""
    await render_hospital_selection(message, context, query=query,
                                    page=_page, search=_search)


async def handle_hospital_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار المستشفى"""
    
    query = update.callback_query
    await query.answer()

    if query.data.startswith("hospital_idx:"):
        hospital_index = int(query.data.split(":", 1)[1])
        hospitals_list = context.user_data.get("report_tmp", {}).get("hospitals_list", [])

        if not hospitals_list:
            # Snapshot wiped (PM2 restart) — re-render so user picks from a fresh list.
            # Do NOT rebuild-and-resolve: resolving a stale index into a rebuilt list is
            # drift injection — the order may have changed since the button was rendered.
            logger.warning(
                "hospitals_list snapshot missing for user %s — re-rendering hospital selection",
                getattr(query.from_user, "id", "?"),
            )
            await query.answer()
            await render_hospital_selection(query.message, context)
            return STATE_SELECT_HOSPITAL

        if 0 <= hospital_index < len(hospitals_list):
            choice = hospitals_list[hospital_index]
            logger.info(f"✅ Selected hospital at index {hospital_index}: {choice}")
        else:
            logger.error(f"❌ Invalid hospital index: {hospital_index}, list length: {len(hospitals_list)}")
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

