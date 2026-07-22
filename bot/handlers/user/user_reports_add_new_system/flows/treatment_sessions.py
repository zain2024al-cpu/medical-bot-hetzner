# =============================
# flows/treatment_sessions.py
# مسارات "💉 جلسات العلاج": العلاج الكيماوي / الموجه / المناعي / غسيل الكلى
# =============================
#
# جميع هذه المسارات تعتمد على محرك خطط العلاج العام
# (services/treatment_plan_service.py). العلاج الإشعاعي مستثنى من هذا
# الملف — لا يزال في flows/radiation_therapy.py، معدَّلاً ليستخدم نفس
# المحرك لكن مع الحفاظ على أعمدة Report القديمة لعدم كسر بطاقة تقريره.
#
# التسلسل المشترك (targeted / immuno / dialysis):
#   [لا خطة نشطة] → "كم عدد الجلسات الكلي؟" → إنشاء الخطة (جلسة 1)
#   [خطة نشطة]    → تقدُّم تلقائي (+1) → عرض "الجلسة الحالية: N من X"
#                    + [✅ متابعة] [✏️ تعديل الخطة]
#   ← ثم: الملاحظات → تاريخ العودة → سبب العودة → المترجم/البوابة/النشر
#
# العلاج الكيماوي إضافياً: يسأل أولاً (أول مرة فقط) "حسب الجلسات" أو
# "حسب الدورات"، وفي حال الدورات: عدد الدورات، ثم هل نفسه لكل الدورات
# (نعم → عدد موحّد) أو (لا → إدخال تسلسلي لكل دورة).

import json
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from ..states import (
    TREATMENT_PLAN_SETUP, TREATMENT_PLAN_EDIT_VALUE, TREATMENT_PLAN_EDIT_REASON,
    TREATMENT_PLAN_DISPLAY, TREATMENT_PLAN_MANUAL_SESSION,
    TREATMENT_COMPLAINT, TREATMENT_NOTES, TREATMENT_FOLLOWUP_DATE,
    TREATMENT_FOLLOWUP_REASON, TREATMENT_TRANSLATOR,
    CHEMO_MODE_CHOICE, CHEMO_CYCLES_TOTAL, CHEMO_CYCLES_UNIFORM_CHOICE,
    CHEMO_CYCLES_UNIFORM_COUNT, CHEMO_CYCLES_CUSTOM_ENTRY,
)
from ..utils import _nav_buttons
from ...user_reports_add_helpers import validate_text_input
from .shared import show_translator_selection
from .new_consult import _render_followup_calendar
from services.treatment_plan_service import (
    get_active_plan, create_plan, advance_plan, edit_plan, format_progress_text,
)

logger = logging.getLogger(__name__)

TREATMENT_MEDICAL_ACTION = {
    "chemo": "العلاج الكيماوي",
    "targeted": "العلاج الموجه",
    "immuno": "العلاج المناعي",
    "dialysis": "جلسات غسيل الكلى",
}


def _actor(update: Update):
    """معرّف واسم المستخدم الحالي (لتسجيله كمنشئ/معدِّل الخطة)."""
    u = update.effective_user
    if not u:
        return None, None
    return u.id, (u.full_name or u.username or str(u.id))


# ═══════════════════════════════════════════════════════════════════
# نقاط الدخول (targeted / immuno / dialysis) — نمط "جلسات" بسيط
# ═══════════════════════════════════════════════════════════════════
async def _start_simple_session_flow(message, context, treatment_key: str):
    data = context.user_data.setdefault("report_tmp", {})
    data["medical_action"] = TREATMENT_MEDICAL_ACTION[treatment_key]
    data["current_flow"] = f"treatment_{treatment_key}"
    data["_treatment_key"] = treatment_key
    data.pop("_tp_editing_plan_id", None)

    patient_id = data.get("patient_id")
    plan = get_active_plan(patient_id, treatment_key) if patient_id else None
    if plan:
        advanced = advance_plan(plan["id"])
        return await _show_plan_display(message, context, advanced)

    await message.reply_text(
        f"💉 **{TREATMENT_MEDICAL_ACTION[treatment_key]}**\n\n"
        "📊 **كم عدد الجلسات الكلي؟**\n\n"
        "أدخل رقماً (مثال: 12):",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown",
    )
    return TREATMENT_PLAN_SETUP


async def start_targeted_flow(message, context):
    return await _start_simple_session_flow(message, context, "targeted")


async def start_immuno_flow(message, context):
    return await _start_simple_session_flow(message, context, "immuno")


async def start_dialysis_flow(message, context):
    return await _start_simple_session_flow(message, context, "dialysis")


# ═══════════════════════════════════════════════════════════════════
# نقطة الدخول: العلاج الكيماوي (اختيار جلسات/دورات أول مرة فقط)
# ═══════════════════════════════════════════════════════════════════
async def start_chemo_flow(message, context):
    data = context.user_data.setdefault("report_tmp", {})
    data["medical_action"] = TREATMENT_MEDICAL_ACTION["chemo"]
    data["current_flow"] = "treatment_chemo"
    data["_treatment_key"] = "chemo"
    data.pop("_tp_editing_plan_id", None)

    patient_id = data.get("patient_id")
    plan = get_active_plan(patient_id, "chemo") if patient_id else None
    if plan:
        advanced = advance_plan(plan["id"])
        return await _show_plan_display(message, context, advanced)

    await message.reply_text(
        "💉 **العلاج الكيماوي**\n\n"
        "🔄 **كيف تريد متابعة الخطة العلاجية؟**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 حسب الجلسات", callback_data="chemo_mode:sessions")],
            [InlineKeyboardButton("🔄 حسب الدورات العلاجية (Cycles)", callback_data="chemo_mode:cycles")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
             InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")],
        ]),
        parse_mode="Markdown",
    )
    return CHEMO_MODE_CHOICE


async def handle_chemo_mode_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mode = query.data.split(":", 1)[1]
    data = context.user_data.setdefault("report_tmp", {})

    if mode == "sessions":
        data["_chemo_mode"] = "sessions"
        await query.edit_message_text(
            "📝 **حسب الجلسات**\n\n📊 **كم عدد الجلسات الكلي؟**\n\nأدخل رقماً (مثال: 12):",
            parse_mode="Markdown",
        )
        return TREATMENT_PLAN_SETUP

    data["_chemo_mode"] = "cycles"
    await query.edit_message_text(
        "🔄 **حسب الدورات العلاجية**\n\n📊 **كم عدد الدورات العلاجية؟**\n\nمثال: 6",
        parse_mode="Markdown",
    )
    return CHEMO_CYCLES_TOTAL


async def handle_chemo_cycles_total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text(
            "⚠️ يرجى إدخال رقم صحيح أكبر من صفر (عدد الدورات):",
            reply_markup=_nav_buttons(show_back=True),
        )
        return CHEMO_CYCLES_TOTAL

    data = context.user_data.setdefault("report_tmp", {})
    data["_chemo_total_cycles"] = int(text)

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "❓ **هل جميع الدورات تحتوي على نفس عدد الجلسات؟**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ نعم", callback_data="chemo_uniform:yes"),
             InlineKeyboardButton("✏️ لا", callback_data="chemo_uniform:no")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
             InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")],
        ]),
        parse_mode="Markdown",
    )
    return CHEMO_CYCLES_UNIFORM_CHOICE


async def handle_chemo_cycles_uniform_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]
    data = context.user_data.setdefault("report_tmp", {})

    if choice == "yes":
        await query.edit_message_text(
            "✅ **نعم — نفس العدد لكل الدورات**\n\n"
            "📊 **كم عدد الجلسات في كل دورة؟**\n\nمثال: 3",
            parse_mode="Markdown",
        )
        return CHEMO_CYCLES_UNIFORM_COUNT

    # custom: تسلسلي لكل دورة
    data["_chemo_custom_list"] = []
    data["_chemo_custom_index"] = 1
    total = data.get("_chemo_total_cycles", 1)
    await query.edit_message_text(
        f"✏️ **إدخال مستقل لكل دورة**\n\n"
        f"📊 **كم عدد الجلسات في الدورة رقم 1 من {total}؟**",
        parse_mode="Markdown",
    )
    return CHEMO_CYCLES_CUSTOM_ENTRY


async def handle_chemo_cycles_uniform_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text(
            "⚠️ يرجى إدخال رقم صحيح أكبر من صفر (عدد الجلسات في كل دورة):",
            reply_markup=_nav_buttons(show_back=True),
        )
        return CHEMO_CYCLES_UNIFORM_COUNT

    data = context.user_data.setdefault("report_tmp", {})
    sessions_per_cycle = int(text)
    total_cycles = data.get("_chemo_total_cycles", 1)

    await update.message.reply_text("✅ تم الحفظ")
    plan = await _commit_chemo_plan(
        update, context, mode="cycles_uniform",
        total_cycles=total_cycles, sessions_per_cycle=sessions_per_cycle,
    )
    return await _show_plan_display(update.message, context, plan)


async def handle_chemo_cycles_custom_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text(
            "⚠️ يرجى إدخال رقم صحيح أكبر من صفر (عدد الجلسات لهذه الدورة):",
            reply_markup=_nav_buttons(show_back=True),
        )
        return CHEMO_CYCLES_CUSTOM_ENTRY

    data = context.user_data.setdefault("report_tmp", {})
    data.setdefault("_chemo_custom_list", []).append(int(text))
    current_index = data.get("_chemo_custom_index", 1)
    total = data.get("_chemo_total_cycles", 1)

    if current_index < total:
        data["_chemo_custom_index"] = current_index + 1
        await update.message.reply_text(
            f"✅ تم الحفظ\n\n"
            f"📊 **كم عدد الجلسات في الدورة رقم {current_index + 1} من {total}؟**",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown",
        )
        return CHEMO_CYCLES_CUSTOM_ENTRY

    await update.message.reply_text("✅ تم الحفظ")
    plan = await _commit_chemo_plan(
        update, context, mode="cycles_custom",
        total_cycles=total, custom_cycle_sessions=data["_chemo_custom_list"],
    )
    return await _show_plan_display(update.message, context, plan)


async def _commit_chemo_plan(update, context, mode, total_cycles=None, sessions_per_cycle=None, custom_cycle_sessions=None):
    """ينشئ خطة جديدة أو يعدّل خطة قائمة (حسب _tp_editing_plan_id) بنتائج
    أسئلة الدورات، وينظّف مفاتيح الإعداد المؤقتة."""
    data = context.user_data.setdefault("report_tmp", {})
    patient_id = data.get("patient_id")
    actor_id, actor_name = _actor(update)
    editing_id = data.get("_tp_editing_plan_id")

    if editing_id:
        plan = edit_plan(
            editing_id,
            {"total_cycles": total_cycles, "sessions_per_cycle": sessions_per_cycle,
             "custom_cycle_sessions": custom_cycle_sessions},
            changed_by=actor_id, changed_by_name=actor_name,
            reason=data.pop("_tp_edit_reason", None),
        )
    else:
        plan = create_plan(
            patient_id=patient_id, treatment_key="chemo", mode=mode,
            total_cycles=total_cycles, sessions_per_cycle=sessions_per_cycle,
            custom_cycle_sessions=custom_cycle_sessions,
            created_by=actor_id, created_by_name=actor_name,
        )

    for k in ("_chemo_mode", "_chemo_total_cycles", "_chemo_custom_list",
              "_chemo_custom_index", "_tp_editing_plan_id"):
        data.pop(k, None)
    return plan


# ═══════════════════════════════════════════════════════════════════
# إعداد الخطة أول مرة (نمط "جلسات" بسيط) — مشترك لكل الأنماط البسيطة
# ═══════════════════════════════════════════════════════════════════
async def handle_treatment_plan_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يُستقبَل فيه رقم الجلسات الكلي — إما إنشاء أول مرة أو تعديل خطة قائمة."""
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text(
            "⚠️ يرجى إدخال رقم صحيح أكبر من صفر (عدد الجلسات الكلي):",
            reply_markup=_nav_buttons(show_back=True),
        )
        return TREATMENT_PLAN_SETUP

    data = context.user_data.setdefault("report_tmp", {})
    total_sessions = int(text)
    treatment_key = data.get("_treatment_key", "chemo")
    patient_id = data.get("patient_id")
    actor_id, actor_name = _actor(update)
    editing_id = data.get("_tp_editing_plan_id")

    await update.message.reply_text("✅ تم الحفظ")

    if editing_id:
        plan = edit_plan(
            editing_id, {"total_sessions": total_sessions},
            changed_by=actor_id, changed_by_name=actor_name,
            reason=data.pop("_tp_edit_reason", None),
        )
        data.pop("_tp_editing_plan_id", None)
    else:
        plan = create_plan(
            patient_id=patient_id, treatment_key=treatment_key, mode="sessions",
            total_sessions=total_sessions, created_by=actor_id, created_by_name=actor_name,
        )

    data.pop("_chemo_mode", None)
    return await _show_plan_display(update.message, context, plan)


# ═══════════════════════════════════════════════════════════════════
# عرض التقدُّم + أزرار متابعة/تعديل
# ═══════════════════════════════════════════════════════════════════
async def _show_plan_display(message, context, plan: dict):
    data = context.user_data.setdefault("report_tmp", {})
    data["_tp_plan_id"] = plan.get("id")
    summary = format_progress_text(plan)
    data["treatment_plan_summary"] = summary
    context.user_data['_conversation_state'] = TREATMENT_PLAN_DISPLAY

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ متابعة", callback_data="tp_display:continue"),
         InlineKeyboardButton("✏️ تعديل الخطة", callback_data="tp_display:edit")],
        [InlineKeyboardButton("🔢 إدخال رقم الجلسة الحالية", callback_data="tp_display:manual")],
    ])
    await message.reply_text(f"{summary}", reply_markup=keyboard, parse_mode="Markdown")
    return TREATMENT_PLAN_DISPLAY


async def handle_treatment_plan_display_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]
    data = context.user_data.setdefault("report_tmp", {})

    if choice == "continue":
        await query.edit_message_text(f"{data.get('treatment_plan_summary', '')}", parse_mode="Markdown")
        await _prompt_complaint(query.message, context)
        context.user_data['_conversation_state'] = TREATMENT_COMPLAINT
        return TREATMENT_COMPLAINT

    if choice == "manual":
        # ✅ إدخال يدوي لرقم الجلسة الحالية — لمرضى بدأوا الجلسات فعلياً قبل
        # إنشاء الخطة في هذا النظام، فيحتاج المترجم مطابقة العدّاد مباشرة
        # بدل الاعتماد فقط على "متابعة" (+1) أو "تعديل الخطة" (العدد الكلي).
        await query.edit_message_text(
            "🔢 **إدخال رقم الجلسة الحالية**\n\n"
            "أدخل رقم الجلسة الحالية (مثال: 5):",
            parse_mode="Markdown",
        )
        return TREATMENT_PLAN_MANUAL_SESSION

    # edit
    plan_id = data.get("_tp_plan_id")
    data["_tp_editing_plan_id"] = plan_id
    treatment_key = data.get("_treatment_key")

    with_plan = get_active_plan(data.get("patient_id"), treatment_key) if data.get("patient_id") else None
    mode = (with_plan or {}).get("mode", "sessions")

    if mode == "sessions":
        await query.edit_message_text(
            "✏️ **تعديل الخطة**\n\n📊 **العدد الكلي الجديد للجلسات؟**",
            parse_mode="Markdown",
        )
        return TREATMENT_PLAN_EDIT_VALUE

    # cycles_uniform / cycles_custom -> إعادة أسئلة الدورات كاملة
    await query.edit_message_text(
        "✏️ **تعديل الخطة**\n\n📊 **كم عدد الدورات العلاجية الجديد؟**",
        parse_mode="Markdown",
    )
    return CHEMO_CYCLES_TOTAL


async def handle_treatment_plan_manual_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدخال يدوي لرقم الجلسة الحالية — يعدّل current_session مباشرة (بلا
    المرور بأسئلة العدد الكلي)، مع تسجيل التغيير في سجل تدقيق الخطة."""
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text(
            "⚠️ يرجى إدخال رقم صحيح أكبر من صفر (رقم الجلسة الحالية):",
            reply_markup=_nav_buttons(show_back=True),
        )
        return TREATMENT_PLAN_MANUAL_SESSION

    data = context.user_data.setdefault("report_tmp", {})
    plan_id = data.get("_tp_plan_id")
    actor_id, actor_name = _actor(update)

    plan = edit_plan(
        plan_id, {"current_session": int(text)},
        changed_by=actor_id, changed_by_name=actor_name,
        reason="تصحيح يدوي لرقم الجلسة الحالية",
    )

    await update.message.reply_text("✅ تم الحفظ")
    return await _show_plan_display(update.message, context, plan)


async def handle_treatment_plan_edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text(
            "⚠️ يرجى إدخال رقم صحيح أكبر من صفر:",
            reply_markup=_nav_buttons(show_back=True),
        )
        return TREATMENT_PLAN_EDIT_VALUE

    data = context.user_data.setdefault("report_tmp", {})
    data["_tp_pending_total_sessions"] = int(text)

    await update.message.reply_text(
        "✅ تم الحفظ\n\n"
        "✍️ **سبب التعديل** (اختياري)\n\n"
        "اكتب السبب، أو اضغط الزر أدناه للتخطي:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭️ بدون سبب", callback_data="tp_edit_reason_skip")],
        ]),
        parse_mode="Markdown",
    )
    return TREATMENT_PLAN_EDIT_REASON


async def _apply_pending_edit(update_or_query, context, reason):
    data = context.user_data.setdefault("report_tmp", {})
    plan_id = data.pop("_tp_editing_plan_id", None)
    total_sessions = data.pop("_tp_pending_total_sessions", None)
    actor_id, actor_name = _actor(update_or_query)
    plan = edit_plan(plan_id, {"total_sessions": total_sessions},
                      changed_by=actor_id, changed_by_name=actor_name, reason=reason)
    return plan


async def handle_treatment_plan_edit_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    plan = await _apply_pending_edit(update, context, reason)
    return await _show_plan_display(update.message, context, plan)


async def handle_treatment_plan_edit_reason_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = await _apply_pending_edit(update, context, None)
    return await _show_plan_display(query.message, context, plan)


# ═══════════════════════════════════════════════════════════════════
# شكوى المريض → ملاحظات الطبيب → التقويم المشترك → سبب العودة → المترجم
# ═══════════════════════════════════════════════════════════════════
async def _prompt_complaint(message, context):
    await message.reply_text(
        "🗣️ **شكوى المريض**\n\n"
        "يرجى إدخال شكوى المريض:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown",
    )


async def handle_treatment_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['_conversation_state'] = TREATMENT_COMPLAINT
    text = update.message.text.strip()

    valid, msg = validate_text_input(text, min_length=3)
    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\nيرجى إدخال شكوى المريض:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown",
        )
        return TREATMENT_COMPLAINT

    context.user_data.setdefault("report_tmp", {})["complaint"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await _prompt_notes(update.message, context)
    context.user_data['_conversation_state'] = TREATMENT_NOTES
    return TREATMENT_NOTES


def _notes_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭️ لا توجد ملاحظات", callback_data="treatment_notes_skip")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
         InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")],
    ])


async def _prompt_notes(message, context):
    await message.reply_text(
        "📝 **ملاحظات الطبيب**\n\n"
        "يرجى إدخال أي ملاحظات إضافية، أو اضغط الزر أدناه إذا لا توجد ملاحظات:",
        reply_markup=_notes_keyboard(),
        parse_mode="Markdown",
    )


async def handle_treatment_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['_conversation_state'] = TREATMENT_NOTES
    text = update.message.text.strip()
    if text.lower() in ['لا يوجد', 'لا', 'no', 'none']:
        text = "لا يوجد"
    context.user_data.setdefault("report_tmp", {})["notes"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await _render_followup_calendar(update.message, context)
    context.user_data['_conversation_state'] = TREATMENT_FOLLOWUP_DATE
    return TREATMENT_FOLLOWUP_DATE


async def handle_treatment_notes_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.setdefault("report_tmp", {})["notes"] = "لا يوجد"
    await _render_followup_calendar(query, context)
    context.user_data['_conversation_state'] = TREATMENT_FOLLOWUP_DATE
    return TREATMENT_FOLLOWUP_DATE


async def handle_treatment_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['_conversation_state'] = TREATMENT_FOLLOWUP_REASON
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)
    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\nيرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown",
        )
        return TREATMENT_FOLLOWUP_REASON

    data = context.user_data.setdefault("report_tmp", {})
    data["followup_reason"] = text
    flow_type = data.get("current_flow", "treatment_chemo")

    await update.message.reply_text("✅ تم الحفظ")
    gate_result = await show_translator_selection(update.message, context, flow_type)
    if gate_result == "MEDICAL_REPORT_ASK":
        return gate_result
    return TREATMENT_TRANSLATOR


__all__ = [
    'start_targeted_flow', 'start_immuno_flow', 'start_dialysis_flow', 'start_chemo_flow',
    'handle_chemo_mode_choice', 'handle_chemo_cycles_total', 'handle_chemo_cycles_uniform_choice',
    'handle_chemo_cycles_uniform_count', 'handle_chemo_cycles_custom_entry',
    'handle_treatment_plan_setup', 'handle_treatment_plan_display_choice',
    'handle_treatment_plan_edit_value', 'handle_treatment_plan_edit_reason',
    'handle_treatment_plan_edit_reason_skip', 'handle_treatment_plan_manual_session',
    'handle_treatment_complaint',
    'handle_treatment_notes', 'handle_treatment_notes_skip', 'handle_treatment_followup_reason',
    'TREATMENT_MEDICAL_ACTION',
]
