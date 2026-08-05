# =============================
# flows/transplant.py
# 🫁 معاملة الزراعة — نوع إجراء يظهر حصراً في قسم "🏙️ الرعاية الصحية -
# تشناي" (context.user_data["report_city"] == "chennai")، مخفي تماماً
# عن قائمة نوع الإجراء الاعتيادية (انظر action_type_handlers.py).
#
# معاملة إدارية/قانونية مرتبطة بزراعة عضو — لا خطة علاجية ولا مريض طبي
# بالمعنى المعتاد المستخدَم في بقية أنواع الإجراءات.
#
# التسلسل: نوع الزراعة (كبد/كلى، اختيار واحد) → الجهة (اختيار متعدد:
# المحكمة/المحامي/مكتب التنسيق) → تفاصيل المعاملة (نص حر) → تاريخ العودة
# → سبب العودة → المترجم → نشر. الخطوات الأربع الأخيرة تُعاد استخدامها
# حرفياً من الآلية العامة المشتركة بكل أنواع الإجراءات (نفس ما تفعله
# flows/treatment_sessions.py).

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from ..states import (
    TRANSPLANT_TYPE, TRANSPLANT_PARTY, TRANSPLANT_DETAILS,
    TRANSPLANT_FOLLOWUP_DATE, TRANSPLANT_FOLLOWUP_REASON, TRANSPLANT_TRANSLATOR,
)
from ..utils import _nav_buttons
from ...user_reports_add_helpers import validate_text_input
from .shared import show_translator_selection
from .new_consult import _render_followup_calendar

logger = logging.getLogger(__name__)

MEDICAL_ACTION_LABEL = "معاملة الزراعة"

# (مفتاح, تسمية العرض)
TRANSPLANT_TYPES = [
    ("liver",  "زراعة كبد"),
    ("kidney", "زراعة كلى"),
]

# (مفتاح, أيقونة, تسمية)
TRANSPLANT_PARTIES = [
    ("court",         "⚖️", "المحكمة"),
    ("lawyer",        "👨‍⚖️", "المحامي"),
    ("coordination",  "🏢", "مكتب التنسيق"),
]
_PARTY_BY_KEY = {k: (icon, label) for k, icon, label in TRANSPLANT_PARTIES}


# ═══════════════════════════════════════════════════════════════════
# Step 1: نوع الزراعة (اختيار واحد)
# ═══════════════════════════════════════════════════════════════════
def _type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"transplant_type:{key}")
         for key, label in TRANSPLANT_TYPES],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")],
    ])


async def start_transplant_flow(message, context):
    data = context.user_data.setdefault("report_tmp", {})
    data["medical_action"] = MEDICAL_ACTION_LABEL
    data["current_flow"] = "transplant"

    await message.reply_text(
        f"🫁 **{MEDICAL_ACTION_LABEL}**\n\n"
        "اختر نوع الزراعة:",
        reply_markup=_type_keyboard(),
        parse_mode="Markdown",
    )
    return TRANSPLANT_TYPE


async def handle_transplant_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split(":", 1)[1]
    label = dict(TRANSPLANT_TYPES).get(key, key)

    data = context.user_data.setdefault("report_tmp", {})
    data["transplant_type"] = label
    data["_transplant_parties_selected"] = []

    try:
        await query.edit_message_text(f"✅ تم اختيار: {label}")
    except Exception:
        logger.debug("تم تجاهل استثناء في handle_transplant_type_choice", exc_info=True)
    await _prompt_party(query.message, context)
    return TRANSPLANT_PARTY


# ═══════════════════════════════════════════════════════════════════
# Step 2: الجهة (اختيار متعدد — ١ أو ٢ أو الكل)
# ═══════════════════════════════════════════════════════════════════
_PARTY_SCREEN_TEXT = "🏢 **الجهة**\n\nاختر جهة واحدة أو أكثر، ثم اضغط «➡️ التالي»:"


def _party_keyboard(selected: set) -> InlineKeyboardMarkup:
    keyboard = []
    row = []
    for key, icon, label in TRANSPLANT_PARTIES:
        mark = "✅" if key in selected else "⬜"
        row.append(InlineKeyboardButton(f"{mark} {icon} {label}", callback_data=f"transplant_party:{key}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("➡️ التالي", callback_data="transplant_party_next")])
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel"),
    ])
    return InlineKeyboardMarkup(keyboard)


async def _prompt_party(message_or_query, context):
    data = context.user_data.get("report_tmp", {})
    selected = set(data.get("_transplant_parties_selected") or [])
    kb = _party_keyboard(selected)
    if hasattr(message_or_query, "edit_message_text"):
        try:
            await message_or_query.edit_message_text(_PARTY_SCREEN_TEXT, reply_markup=kb, parse_mode="Markdown")
            return
        except Exception:
            logger.debug("تم تجاهل استثناء في _prompt_party", exc_info=True)
    await message_or_query.reply_text(_PARTY_SCREEN_TEXT, reply_markup=kb, parse_mode="Markdown")


async def handle_transplant_party_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split(":", 1)[1]

    data = context.user_data.setdefault("report_tmp", {})
    selected = list(data.get("_transplant_parties_selected") or [])
    if key in selected:
        selected.remove(key)
    else:
        selected.append(key)
    data["_transplant_parties_selected"] = selected

    try:
        await query.edit_message_text(
            _PARTY_SCREEN_TEXT, reply_markup=_party_keyboard(set(selected)), parse_mode="Markdown"
        )
    except Exception:
        logger.debug("تم تجاهل استثناء في handle_transplant_party_toggle", exc_info=True)
    return TRANSPLANT_PARTY


async def handle_transplant_party_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = context.user_data.setdefault("report_tmp", {})
    selected = list(data.get("_transplant_parties_selected") or [])

    if not selected:
        await query.answer("⚠️ اختر جهة واحدة على الأقل", show_alert=True)
        return TRANSPLANT_PARTY

    labels = [_PARTY_BY_KEY[k][1] for k in selected if k in _PARTY_BY_KEY]
    data["transplant_parties"] = "، ".join(labels)
    data.pop("_transplant_parties_selected", None)

    try:
        await query.edit_message_text(f"✅ تم اختيار: {data['transplant_parties']}")
    except Exception:
        logger.debug("تم تجاهل استثناء في handle_transplant_party_next", exc_info=True)
    await _prompt_details(query.message, context)
    return TRANSPLANT_DETAILS


# ═══════════════════════════════════════════════════════════════════
# Step 3: تفاصيل المعاملة (نص حر يدوي)
# ═══════════════════════════════════════════════════════════════════
async def _prompt_details(message_or_query, context):
    text = (
        "📝 **تفاصيل المعاملة**\n\n"
        "يرجى إدخال تفاصيل المعاملة:"
    )
    kb = _nav_buttons(show_back=True)
    if hasattr(message_or_query, "edit_message_text"):
        try:
            await message_or_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return
        except Exception:
            logger.debug("تم تجاهل استثناء في _prompt_details", exc_info=True)
    await message_or_query.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def handle_transplant_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['_conversation_state'] = TRANSPLANT_DETAILS
    text = update.message.text.strip()

    valid, msg = validate_text_input(text, min_length=3)
    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\nيرجى إدخال تفاصيل المعاملة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown",
        )
        return TRANSPLANT_DETAILS

    context.user_data.setdefault("report_tmp", {})["transplant_details"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await _render_followup_calendar(update.message, context)
    context.user_data['_conversation_state'] = TRANSPLANT_FOLLOWUP_DATE
    return TRANSPLANT_FOLLOWUP_DATE


# ═══════════════════════════════════════════════════════════════════
# Step 5: سبب العودة (تاريخ العودة يستخدم الآلية العامة المشتركة، بلا
# دالة مخصَّصة هنا — انظر _followup_date_state_handlers في
# conversation_handler.py)
# ═══════════════════════════════════════════════════════════════════
async def handle_transplant_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['_conversation_state'] = TRANSPLANT_FOLLOWUP_REASON
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)
    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\nيرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown",
        )
        return TRANSPLANT_FOLLOWUP_REASON

    data = context.user_data.setdefault("report_tmp", {})
    data["followup_reason"] = text
    flow_type = data.get("current_flow", "transplant")

    await update.message.reply_text("✅ تم الحفظ")
    gate_result = await show_translator_selection(update.message, context, flow_type)
    if gate_result == "MEDICAL_REPORT_ASK":
        return gate_result
    return TRANSPLANT_TRANSLATOR


__all__ = [
    'start_transplant_flow', 'handle_transplant_type_choice',
    'handle_transplant_party_toggle', 'handle_transplant_party_next',
    'handle_transplant_details', 'handle_transplant_followup_reason',
    'MEDICAL_ACTION_LABEL', 'TRANSPLANT_TYPES', 'TRANSPLANT_PARTIES',
]
