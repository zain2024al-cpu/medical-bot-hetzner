# =============================
# flows/oncology_multiselect.py
# اختيار متعدد لجلسات الأورام (كيماوي/مناعي/موجّه/إشعاعي معاً في تقرير واحد)
# =============================
#
# شاشة "🎗️ جلسات الأورام" أصبحت اختيارية متعددة (checkbox) بدل زر واحد.
# - اختيار نوع واحد فقط → يُفوَّض مباشرة لدالة البدء الأصلية لذلك النوع
#   (start_chemo_flow/start_immuno_flow/start_targeted_flow/
#   start_radiation_therapy_flow) بلا أي تغيير في سلوكها.
# - اختيار نوعين أو أكثر → "طابور" يعالج كل نوع بدوره: إن كانت له خطة
#   نشطة يتقدَّم تلقائياً (+1)، وإلا يُسأل عن الإعداد الأول (الكيماوي:
#   دورات، البقية: عدد الجلسات الكلي ثم رقم الجلسة الحالية) — كل نوع
#   بخطته المستقلة تماماً في TreatmentPlan (فلترة/إحصاء دقيقة لاحقاً بلا
#   أي تغيير في قاعدة البيانات). بعد كل نوع: سؤال اختياري عن طريقة
#   الإعطاء (عيادة يومية/رقود). بعد انتهاء الطابور: دمج كل الملخصات في
#   تقرير واحد (current_flow="treatment_combined") ثم المتابعة بنفس
#   خطوات "جلسات العلاج" المشتركة (شكوى → ملاحظات → موعد العودة → مترجم).

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from ..states import (
    ONCOLOGY_QUEUE_TOTAL, ONCOLOGY_QUEUE_CURRENT,
    ONCOLOGY_DELIVERY_MODE, ONCOLOGY_DELIVERY_DAYS,
    CHEMO_CYCLES_TOTAL, TREATMENT_COMPLAINT,
)
from ..utils import _nav_buttons
from services.treatment_plan_service import get_active_plan, advance_plan, create_plan, format_progress_text
from .treatment_sessions import start_chemo_flow, start_immuno_flow, start_targeted_flow, _prompt_complaint
from .radiation_therapy import start_radiation_therapy_flow

logger = logging.getLogger(__name__)

# (مفتاح, أيقونة, تسمية قصيرة للملخص, تسمية كاملة لنوع الإجراء المدمج)
ONCOLOGY_TYPES = [
    ("chemo",     "💉", "الكيماوي",  "العلاج الكيماوي"),
    ("immuno",    "🧬", "المناعي",   "العلاج المناعي"),
    ("targeted",  "🎯", "الموجّه",   "العلاج الموجه"),
    ("radiation", "☢️", "الإشعاعي",  "جلسة إشعاعي"),
]
_BY_KEY = {k: (icon, short, full) for k, icon, short, full in ONCOLOGY_TYPES}

_SINGLE_START_FUNCS = {
    "chemo": start_chemo_flow,
    "immuno": start_immuno_flow,
    "targeted": start_targeted_flow,
    "radiation": start_radiation_therapy_flow,
}

_QUEUE_TOTAL_PROMPTS = {
    "chemo":     "💉 **الكيماوي**\n\n📊 **كم عدد الجلسات الكلي؟**\n\nأدخل رقماً (مثال: 6):",
    "immuno":    "🧬 **المناعي**\n\n📊 **كم عدد الجلسات الكلي؟**\n\nأدخل رقماً (مثال: 12):",
    "targeted":  "🎯 **الموجّه**\n\n📊 **كم عدد الجلسات الكلي؟**\n\nأدخل رقماً (مثال: 8):",
    "radiation": "☢️ **الإشعاعي**\n\n📊 **كم عدد الجلسات الكلي؟**\n\nأدخل رقماً (مثال: 30):",
}


def _icon(key):
    return _BY_KEY[key][0]


def _short_label(key):
    return _BY_KEY[key][1]


def _full_label(key):
    return _BY_KEY[key][2]


def _actor(update: Update):
    u = update.effective_user
    if not u:
        return None, None
    return u.id, (u.full_name or u.username or str(u.id))


# ═══════════════════════════════════════════════════════════════════
# شاشة الاختيار المتعدد (checkbox) — تبقى ضمن حالة R_ACTION_TYPE
# ═══════════════════════════════════════════════════════════════════
_SCREEN_TEXT = "⚕️ **🎗️ جلسات الأورام**\n\nاختر نوعاً واحداً أو أكثر، ثم اضغط «➡️ التالي»:"


def _build_multiselect_keyboard(selected):
    keyboard = []
    row = []
    for key, icon, short, _full in ONCOLOGY_TYPES:
        mark = "✅" if key in selected else "⬜"
        row.append(InlineKeyboardButton(f"{mark} {icon} {short}", callback_data=f"onc_toggle:{key}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("➡️ التالي", callback_data="onc_next")])
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع للقائمة", callback_data="action_cat:main"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel"),
    ])
    return InlineKeyboardMarkup(keyboard)


def build_oncology_multiselect_screen(context):
    """يُستدعى من action_type_handlers.py عند فتح '🎗️ جلسات الأورام'."""
    data = context.user_data.setdefault("report_tmp", {})
    data["_onc_selected"] = []
    return _SCREEN_TEXT, _build_multiselect_keyboard(set())


async def handle_onc_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split(":", 1)[1]
    data = context.user_data.setdefault("report_tmp", {})
    selected = list(data.get("_onc_selected") or [])
    if key in selected:
        selected.remove(key)
    else:
        selected.append(key)
    data["_onc_selected"] = selected
    from ..states import R_ACTION_TYPE
    try:
        await query.edit_message_text(_SCREEN_TEXT, reply_markup=_build_multiselect_keyboard(set(selected)), parse_mode="Markdown")
    except Exception:
        logger.debug("تم تجاهل استثناء في handle_onc_toggle", exc_info=True)
    return R_ACTION_TYPE


async def handle_onc_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from ..states import R_ACTION_TYPE
    query = update.callback_query
    await query.answer()
    data = context.user_data.setdefault("report_tmp", {})
    selected = list(data.get("_onc_selected") or [])

    if not selected:
        await query.answer("⚠️ اختر نوعاً واحداً على الأقل", show_alert=True)
        return R_ACTION_TYPE

    if len(selected) == 1:
        key = selected[0]
        data.pop("_onc_selected", None)
        try:
            await query.edit_message_text(f"تم اختيار نوع الإجراء\n\nالنوع:\n{_full_label(key)}")
        except Exception:
            logger.debug("تم تجاهل استثناء في handle_onc_next", exc_info=True)
        result = await _SINGLE_START_FUNCS[key](query.message, context)
        return result

    data["_onc_selected_snapshot"] = list(selected)
    data["_onc_queue"] = list(selected)
    data["_onc_summaries"] = {}
    data.pop("_onc_selected", None)
    try:
        await query.edit_message_text("✅ تم اختيار: " + " + ".join(_short_label(k) for k in selected))
    except Exception:
        logger.debug("تم تجاهل استثناء في handle_onc_next", exc_info=True)
    return await _process_next_in_queue(query.message, context)


# ═══════════════════════════════════════════════════════════════════
# الطابور: معالجة كل نوع مُختار بدوره
# ═══════════════════════════════════════════════════════════════════
async def _process_next_in_queue(message, context):
    data = context.user_data.setdefault("report_tmp", {})
    queue = data.get("_onc_queue") or []
    if not queue:
        return await _finish_queue(message, context)

    key = queue[0]
    data["_onc_current_type"] = key
    patient_id = data.get("patient_id")
    plan = get_active_plan(patient_id, key) if patient_id else None
    if plan:
        advanced = advance_plan(plan["id"])
        summary = format_progress_text(advanced)
        data.setdefault("_onc_summaries", {})[key] = summary
        await message.reply_text(f"{_icon(key)} **{_short_label(key)}**\n{summary}", parse_mode="Markdown")
        return await _ask_delivery_mode(message, context)

    # ✅ الكيماوي لم يعد استثناءً: كان يتفرّع هنا لأسئلة الدورات، وصار يمرّ
    # بنفس مسار بقية الأنواع (عدد الجلسات الكلي ← رقم الجلسة الحالية) —
    # مطابقةً لتبسيط start_chemo_flow. لولا ذلك لاختلف النوع نفسه بين
    # الاختيار المفرد والاختيار المُدمج.
    data["_treatment_key"] = key
    await message.reply_text(
        _QUEUE_TOTAL_PROMPTS[key], reply_markup=_nav_buttons(show_back=True), parse_mode="Markdown",
    )
    return ONCOLOGY_QUEUE_TOTAL


async def chemo_committed_in_queue(message, context, plan: dict):
    """يُستدعى من treatment_sessions.py بعد إنشاء خطة كيماوي وهو في وضع
    الطابور (بدل _show_plan_display العادية)."""
    data = context.user_data.setdefault("report_tmp", {})
    summary = format_progress_text(plan)
    data.setdefault("_onc_summaries", {})["chemo"] = summary
    data["_onc_current_type"] = "chemo"
    await message.reply_text(f"💉 **الكيماوي**\n{summary}", parse_mode="Markdown")
    return await _ask_delivery_mode(message, context)


async def handle_oncology_queue_total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text(
            "⚠️ يرجى إدخال رقم صحيح أكبر من صفر (عدد الجلسات الكلي):",
            reply_markup=_nav_buttons(show_back=True),
        )
        return ONCOLOGY_QUEUE_TOTAL

    data = context.user_data.setdefault("report_tmp", {})
    data["_onc_pending_total"] = int(text)
    await update.message.reply_text(
        "✅ تم الحفظ\n\n🔢 **رقم الجلسة الحالية؟**\n\n(إن كانت هذه أول جلسة أدخل 1)",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown",
    )
    return ONCOLOGY_QUEUE_CURRENT


async def handle_oncology_queue_current(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text(
            "⚠️ يرجى إدخال رقم صحيح أكبر من صفر (رقم الجلسة الحالية):",
            reply_markup=_nav_buttons(show_back=True),
        )
        return ONCOLOGY_QUEUE_CURRENT

    data = context.user_data.setdefault("report_tmp", {})
    key = data.get("_onc_current_type")
    total = data.pop("_onc_pending_total", None)
    current = int(text)
    actor_id, actor_name = _actor(update)

    plan = create_plan(
        patient_id=data.get("patient_id"), treatment_key=key, mode="sessions",
        total_sessions=total, current_session=current,
        created_by=actor_id, created_by_name=actor_name,
    )

    if key == "radiation":
        remaining = max(0, (total or 0) - current)
        data["radiation_therapy_session_number"] = str(current)
        data["radiation_therapy_remaining"] = str(remaining)
        data.setdefault("radiation_therapy_type", "غير محدد")

    await update.message.reply_text("✅ تم الحفظ")
    summary = format_progress_text(plan)
    data.setdefault("_onc_summaries", {})[key] = summary
    await update.message.reply_text(f"{_icon(key)} **{_short_label(key)}**\n{summary}", parse_mode="Markdown")
    return await _ask_delivery_mode(update.message, context)


# ═══════════════════════════════════════════════════════════════════
# طريقة الإعطاء (عيادة يومية / رقود) — سؤال اختياري بعد كل نوع
# ═══════════════════════════════════════════════════════════════════
async def _ask_delivery_mode(message, context):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 عيادة يومية", callback_data="onc_delivery:outpatient"),
         InlineKeyboardButton("🛏️ رقود", callback_data="onc_delivery:admission")],
    ])
    await message.reply_text("🏥 **طريقة الإعطاء هذه المرة؟**", reply_markup=keyboard, parse_mode="Markdown")
    return ONCOLOGY_DELIVERY_MODE


async def handle_oncology_delivery_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]

    if choice == "outpatient":
        try:
            await query.edit_message_text("🏠 عيادة يومية")
        except Exception:
            logger.debug("تم تجاهل استثناء في handle_oncology_delivery_mode", exc_info=True)
        return await _advance_queue_after_delivery(query.message, context)

    try:
        await query.edit_message_text(
            "🛏️ رقود — كم عدد الأيام المتوقعة؟",
            reply_markup=_nav_buttons(show_back=True),
        )
    except Exception:
        logger.debug("تم تجاهل استثناء في handle_oncology_delivery_mode", exc_info=True)
    return ONCOLOGY_DELIVERY_DAYS


async def handle_oncology_delivery_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("⚠️ يرجى إدخال رقم صحيح أكبر من صفر (عدد أيام الرقود المتوقعة):")
        return ONCOLOGY_DELIVERY_DAYS

    data = context.user_data.setdefault("report_tmp", {})
    key = data.get("_onc_current_type")
    summaries = data.setdefault("_onc_summaries", {})
    if key in summaries:
        summaries[key] = summaries[key] + f"\n🛏️ رقود ({text} أيام متوقعة)"

    await update.message.reply_text("✅ تم الحفظ")
    return await _advance_queue_after_delivery(update.message, context)


async def _advance_queue_after_delivery(message, context):
    data = context.user_data.setdefault("report_tmp", {})
    queue = data.get("_onc_queue") or []
    key = data.get("_onc_current_type")
    if queue and queue[0] == key:
        queue.pop(0)
        data["_onc_queue"] = queue
    return await _process_next_in_queue(message, context)


# ═══════════════════════════════════════════════════════════════════
# انتهاء الطابور — دمج الملخصات ومتابعة المسار المشترك
# ═══════════════════════════════════════════════════════════════════
async def _finish_queue(message, context):
    data = context.user_data.setdefault("report_tmp", {})
    order = data.get("_onc_selected_snapshot") or list(data.get("_onc_summaries", {}).keys())
    summaries = data.get("_onc_summaries", {})
    present = [k for k in order if k in summaries]

    combined_action = " + ".join(_full_label(k) for k in present)
    header = "🎗️ **العلاج:** " + " + ".join(_short_label(k) for k in present)
    blocks = [f"{_icon(k)} **{_short_label(k)}**\n{summaries[k]}" for k in present]

    data["medical_action"] = combined_action
    data["current_flow"] = "treatment_combined"
    data["_treatment_key"] = "combined"
    data["treatment_plan_summary"] = header + "\n\n" + "\n\n".join(blocks)

    for k in ("_onc_selected", "_onc_selected_snapshot", "_onc_queue", "_onc_summaries",
              "_onc_current_type", "_onc_pending_total"):
        data.pop(k, None)

    await _prompt_complaint(message, context)
    context.user_data['_conversation_state'] = TREATMENT_COMPLAINT
    return TREATMENT_COMPLAINT


__all__ = [
    'build_oncology_multiselect_screen', 'handle_onc_toggle', 'handle_onc_next',
    'chemo_committed_in_queue',
    'handle_oncology_queue_total', 'handle_oncology_queue_current',
    'handle_oncology_delivery_mode', 'handle_oncology_delivery_days',
]
