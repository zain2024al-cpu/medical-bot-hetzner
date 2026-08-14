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
# ✅ التسلسل المشترك (chemo / targeted / immuno) — بلا TreatmentPlan
# وبلا "عدد كلي" إطلاقاً (بطلب المستخدم صراحةً — الغرض الأصلي من الخطة
# كان التقدّم/العدّ التلقائي، وكلاهما أُلغيا في جلستين سابقتين، فلم يعد
# للعدد الكلي أي فائدة فعلية):
#   "رقم الجلسة/الدورة الحالية؟" (يدوي، كل تقرير من الصفر بلا تذكّر ولا
#   خطة محفوظة) → [الكيماوي فقط: رقم الجلسة ضمن الدورة] → الشكوى →
#   الملاحظات → تاريخ العودة → سبب العودة → المترجم/البوابة/النشر
# لقطة نصية فقط تُحفَظ في Report.treatment_plan_summary (نفس صيغة نص
# غسيل الكلى بالضبط)، بلا أي صف TreatmentPlan جديد.
#
# غسيل الكلى (dialysis) نفس الفلسفة تماماً، وسابق لها بهذا التبسيط —
# ولا شكوى مريض ولا قرار طبيب ولا رفع مرفقات لها (بناءً على طلب المستخدم):
#   رقم الجلسة الحالية (يدوي) → تاريخ الجلسة القادمة (تقويم فقط — بلا
#   وقت وبلا سبب) → المترجم/البوابة/النشر
#
# ⚠️ شاشة "✏️ تعديل الخطة" (`_show_plan_display` وما بعدها) ومعالِجات
# `CHEMO_CYCLES_*` (نمط الدورات القديم) أصبحت غير قابلة للوصول من إنشاء
# تقرير جديد بعد إزالة TreatmentPlan لهذه الأنواع الثلاثة — بقيت الدوال/
# الحالات مسجَّلة كرمز خامل (خطط قديمة محفوظة في قاعدة البيانات تبقى
# كما هي، غير قابلة للتعديل عبر هذه الشاشة). حذفها الفعلي مهمة منفصلة
# مستقبلية (نفس نمط تنظيف الكود الميت الموثَّق في MAINTENANCE_LOG.md).

import calendar
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from ..states import (
    TREATMENT_PLAN_SETUP, TREATMENT_PLAN_EDIT_VALUE, TREATMENT_PLAN_EDIT_REASON,
    TREATMENT_PLAN_DISPLAY, TREATMENT_PLAN_MANUAL_SESSION,
    TREATMENT_COMPLAINT, TREATMENT_NOTES, TREATMENT_FOLLOWUP_DATE,
    TREATMENT_FOLLOWUP_REASON, TREATMENT_TRANSLATOR,
    CHEMO_CYCLES_TOTAL, CHEMO_CYCLES_UNIFORM_CHOICE,
    CHEMO_CYCLES_UNIFORM_COUNT, CHEMO_CYCLES_CUSTOM_ENTRY,
    TREATMENT_DIALYSIS_SESSION, TREATMENT_DIALYSIS_NEXT_DATE,
    TREATMENT_CHEMO_SESSION_NUMBER,
)
from ..utils import _nav_buttons, MONTH_NAMES_AR, WEEKDAYS_AR
from ...user_reports_add_helpers import validate_text_input
from .shared import show_translator_selection
from .new_consult import _render_followup_calendar
from services.treatment_plan_service import (
    get_active_plan, create_plan, edit_plan, format_progress_text,
    unit_labels,
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
def _build_manual_session_summary(treatment_key: str, current: int) -> str:
    """لقطة نصية لرقم الجلسة/الدورة الحالية — بلا أي TreatmentPlan محفوظة،
    إدخال يدوي بحت في كل تقرير (بطلب المستخدم صراحةً: إلغاء سؤال العدد
    الكلي والتتبّع/التقدّم التلقائي للكيماوي/الموجّه/المناعي). نفس صيغة
    النص المستخدمة أصلاً لغسيل الكلى بالضبط — التعديل بعد النشر
    (`_apply_session_number_edit`/`_current_session_number_display` في
    user_reports_edit.py) يطابق هذه الصيغة عبر تعبير نمطي مشترك."""
    _, the, _pl = unit_labels(treatment_key)
    return f"📋 **{TREATMENT_MEDICAL_ACTION[treatment_key]}**\n\nرقم {the} الحالية: {current}"


async def _start_simple_session_flow(message, context, treatment_key: str):
    """✅ لا خطة محفوظة (TreatmentPlan) ولا سؤال عن العدد الكلي — بطلب
    المستخدم صراحةً لإلغاء الحفظ/التتبّع التلقائي. إدخال يدوي بحت لرقم
    الجلسة/الدورة الحالية في كل تقرير، بنفس نمط غسيل الكلى تماماً."""
    data = context.user_data.setdefault("report_tmp", {})
    data["medical_action"] = TREATMENT_MEDICAL_ACTION[treatment_key]
    data["current_flow"] = f"treatment_{treatment_key}"
    data["_treatment_key"] = treatment_key
    data.pop("_tp_editing_plan_id", None)

    # وحدة العدّ تُشتق من نوع العلاج: الكيماوي «دورة»، وغيره «جلسة».
    _one, the, _pl = unit_labels(treatment_key)
    await message.reply_text(
        f"💉 **{TREATMENT_MEDICAL_ACTION[treatment_key]}**\n\n"
        f"🔢 **رقم {the} الحالية؟**\n\n"
        "أدخل رقماً (مثال: 3):",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown",
    )
    return TREATMENT_PLAN_SETUP


async def start_targeted_flow(message, context):
    return await _start_simple_session_flow(message, context, "targeted")


async def start_immuno_flow(message, context):
    return await _start_simple_session_flow(message, context, "immuno")


async def start_dialysis_flow(message, context):
    """
    غسيل الكلى: بلا TreatmentPlan وبلا "عدد جلسات كلي" وبلا شكوى/قرار طبيب
    — ينتقل مباشرة لرقم الجلسة الحالية (إدخال يدوي، بلا تذكّر أو خطة
    محفوظة)، ثم تاريخ الجلسة القادمة فقط.
    """
    data = context.user_data.setdefault("report_tmp", {})
    data["medical_action"] = TREATMENT_MEDICAL_ACTION["dialysis"]
    data["current_flow"] = "treatment_dialysis"
    data["_treatment_key"] = "dialysis"
    data.pop("_tp_editing_plan_id", None)

    await _prompt_dialysis_session(message, context)
    context.user_data['_conversation_state'] = TREATMENT_DIALYSIS_SESSION
    return TREATMENT_DIALYSIS_SESSION


# ═══════════════════════════════════════════════════════════════════
# نقطة الدخول: العلاج الكيماوي — نفس منطق المناعي/الموجّه
# ═══════════════════════════════════════════════════════════════════
async def start_chemo_flow(message, context):
    """
    ✅ إدخال يدوي بحت لرقم الدورة الحالية، بلا خطة محفوظة وبلا سؤال عن
    العدد الكلي (بطلب المستخدم صراحةً) — تماماً كالمناعي والموجّه.

    ⚠️ سابقاً: كان يسأل عن عدد الدورات الكلي ← هل عددها موحّد؟ ← وإن لا،
    **إدخال يدوي لكل دورة على حدة** (6 دورات = 8 خطوات لتقرير واحد) —
    أُزيل بطلب المستخدم لأنه مُتعب بلا مقابل. ثم لاحقاً حتى سؤال "العدد
    الكلي" نفسه أُزيل تماماً (لا TreatmentPlan إطلاقاً لهذا النوع بعد
    الآن)، فأصبحت شاشة "✏️ تعديل الخطة" (`_show_plan_display` وما بعدها،
    ومعها معالِجات `CHEMO_CYCLES_*`) غير قابلة للوصول من إنشاء تقرير
    جديد — بقيت مسجَّلة كرمز خامل بلا أثر عملي، لا حاجة لإزالتها ما لم
    تُطلَب صراحةً (خطط قديمة محفوظة في قاعدة البيانات تبقى كما هي، غير
    قابلة للتعديل عبر هذه الشاشة بعد الآن).
    """
    return await _start_simple_session_flow(message, context, "chemo")


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
            reply_markup=_nav_buttons(show_back=True),
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
        reply_markup=_nav_buttons(show_back=True),
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
    if data.get("_onc_queue") is not None:
        from .oncology_multiselect import chemo_committed_in_queue
        return await chemo_committed_in_queue(update.message, context, plan)
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
    if data.get("_onc_queue") is not None:
        from .oncology_multiselect import chemo_committed_in_queue
        return await chemo_committed_in_queue(update.message, context, plan)
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
    """✅ يستقبل رقم الجلسة/الدورة الحالية مباشرة (لا عدد كلي، بلا خطة
    محفوظة) — بطلب المستخدم صراحةً. لقطة نصية فقط في treatment_plan_summary،
    بنفس نمط غسيل الكلى (انظر _build_manual_session_summary أعلاه)."""
    text = update.message.text.strip()
    data = context.user_data.setdefault("report_tmp", {})
    treatment_key = data.get("_treatment_key", "chemo")
    _unit = unit_labels(treatment_key)[1]
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text(
            f"⚠️ يرجى إدخال رقم صحيح أكبر من صفر (رقم {_unit} الحالية):",
            reply_markup=_nav_buttons(show_back=True),
        )
        return TREATMENT_PLAN_SETUP

    current = int(text)
    data["treatment_plan_summary"] = _build_manual_session_summary(treatment_key, current)

    await update.message.reply_text("✅ تم الحفظ")

    if treatment_key == "chemo":
        await _prompt_chemo_session_number(update.message, context)
        context.user_data['_conversation_state'] = TREATMENT_CHEMO_SESSION_NUMBER
        return TREATMENT_CHEMO_SESSION_NUMBER

    # ✅ استيراد محلي عمداً (لا في أعلى الملف) لتفادي استيراد دائري —
    # oncology_multiselect.py يستورد من هذا الملف على مستوى الوحدة.
    # سؤال طريقة الإعطاء (عيادة يومية/رقود) كان مقصوراً على الزر المدمج
    # "🎗️ جلسات الأورام" عند اختيار نوعين أو أكثر فقط — لا يظهر إطلاقاً
    # عند اختيار نوع واحد فقط من نفس الشاشة أو عبر الأزرار المفردة (خلل
    # حقيقي مُبلَّغ عنه). موحَّد الآن لجميع مسارات الدخول.
    from .oncology_multiselect import _ask_delivery_mode
    return await _ask_delivery_mode(update.message, context)


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
        [InlineKeyboardButton(
            f"🔢 إدخال رقم {unit_labels(data.get('_treatment_key'))[1]} الحالية",
            callback_data="tp_display:manual")],
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
        # ✅ الكيماوي فقط: رقم الجلسة ضمن الدورة الحالية — كل دورة تحتوي
        # عدة جلسات، ورقم الدورة نفسها (current_session) لا يميّز بينها.
        # targeted/immuno/dialysis ليس لها هذا المفهوم فتتخطّاه مباشرة.
        if data.get("_treatment_key") == "chemo":
            await _prompt_chemo_session_number(query.message, context)
            context.user_data['_conversation_state'] = TREATMENT_CHEMO_SESSION_NUMBER
            return TREATMENT_CHEMO_SESSION_NUMBER
        await _prompt_complaint(query.message, context)
        context.user_data['_conversation_state'] = TREATMENT_COMPLAINT
        return TREATMENT_COMPLAINT

    if choice == "manual":
        # ✅ إدخال يدوي لرقم الجلسة الحالية — لمرضى بدأوا الجلسات فعلياً قبل
        # إنشاء الخطة في هذا النظام، فيحتاج المترجم مطابقة العدّاد مباشرة
        # بدل الاعتماد فقط على "متابعة" (+1) أو "تعديل الخطة" (العدد الكلي).
        _the = unit_labels(data.get("_treatment_key"))[1]
        await query.edit_message_text(
            f"🔢 **إدخال رقم {_the} الحالية**\n\n"
            f"أدخل رقم {_the} الحالية (مثال: 5):",
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
            f"✏️ **تعديل الخطة**\n\n"
            f"📊 **العدد الكلي الجديد لل{unit_labels(treatment_key)[2]}؟**",
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
# الكيماوي فقط: رقم الجلسة ضمن الدورة الحالية (يدوي، بلا تتبّع/عدّ كلي)
# ═══════════════════════════════════════════════════════════════════
async def _prompt_chemo_session_number(message, context):
    await message.reply_text(
        "🔢 **رقم الجلسة ضمن الدورة الحالية**\n\n"
        "أدخل رقم هذه الجلسة (مثال: 2):",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown",
    )


async def handle_chemo_session_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رقم الجلسة ضمن الدورة الحالية — إدخال يدوي بحت في كل تقرير، بلا خطة
    محفوظة أو عدّ كلي لجلسات كل دورة (بطلب المستخدم صراحةً)."""
    context.user_data['_conversation_state'] = TREATMENT_CHEMO_SESSION_NUMBER
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text(
            "⚠️ يرجى إدخال رقم صحيح أكبر من صفر (رقم الجلسة ضمن الدورة):",
            reply_markup=_nav_buttons(show_back=True),
        )
        return TREATMENT_CHEMO_SESSION_NUMBER

    data = context.user_data.setdefault("report_tmp", {})
    data["chemo_session_number"] = int(text)

    await update.message.reply_text("✅ تم الحفظ")
    # ✅ استيراد محلي عمداً — انظر نفس الملاحظة في handle_treatment_plan_setup
    # أعلاه (توحيد سؤال طريقة الإعطاء بين الأزرار المفردة والزر المدمج).
    from .oncology_multiselect import _ask_delivery_mode
    return await _ask_delivery_mode(update.message, context)


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
    """ملاحظات الطبيب — targeted/immuno/chemo فقط (غسيل الكلى لا يمر بهذه
    الخطوة إطلاقاً، انظر start_dialysis_flow)."""
    text = (
        "📝 **ملاحظات الطبيب**\n\n"
        "يرجى إدخال أي ملاحظات إضافية، أو اضغط الزر أدناه إذا لا توجد ملاحظات:"
    )
    await message.reply_text(text, reply_markup=_notes_keyboard(), parse_mode="Markdown")


async def _after_notes(message_or_query, context):
    """ما بعد الملاحظات (targeted/immuno/chemo فقط) → تاريخ العودة."""
    await _render_followup_calendar(message_or_query, context)
    context.user_data['_conversation_state'] = TREATMENT_FOLLOWUP_DATE
    return TREATMENT_FOLLOWUP_DATE


async def handle_treatment_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['_conversation_state'] = TREATMENT_NOTES
    text = update.message.text.strip()
    if text.lower() in ['لا يوجد', 'لا', 'no', 'none']:
        text = "لا يوجد"
    context.user_data.setdefault("report_tmp", {})["notes"] = text

    await update.message.reply_text("✅ تم الحفظ")
    return await _after_notes(update.message, context)


async def handle_treatment_notes_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.setdefault("report_tmp", {})["notes"] = "لا يوجد"
    return await _after_notes(query, context)


# ═══════════════════════════════════════════════════════════════════
# غسيل الكلى فقط: رقم الجلسة الحالية (يدوي) → تاريخ الجلسة القادمة فقط
# (بلا وقت وبلا سبب — بناءً على طلب المستخدم صراحةً) → المترجم مباشرة
# ═══════════════════════════════════════════════════════════════════
async def _prompt_dialysis_session(message_or_query, context):
    text = (
        "🔢 **رقم الجلسة الحالية**\n\n"
        "أدخل رقم الجلسة الحالية (مثال: 5):"
    )
    kb = _nav_buttons(show_back=True)
    if hasattr(message_or_query, "edit_message_text"):
        try:
            await message_or_query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
            return
        except Exception:
            logger.debug("تم تجاهل استثناء في _prompt_dialysis_session", exc_info=True)
    await message_or_query.reply_text(text, reply_markup=kb, parse_mode="Markdown")


async def handle_treatment_dialysis_session_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رقم الجلسة الحالية — إدخال يدوي بحت في كل تقرير، بلا خطة محفوظة
    وبلا تذكّر أو اقتراح (بناءً على طلب المستخدم صراحةً)."""
    context.user_data['_conversation_state'] = TREATMENT_DIALYSIS_SESSION
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text(
            "⚠️ يرجى إدخال رقم صحيح أكبر من صفر (رقم الجلسة الحالية):",
            reply_markup=_nav_buttons(show_back=True),
        )
        return TREATMENT_DIALYSIS_SESSION

    data = context.user_data.setdefault("report_tmp", {})
    data["treatment_plan_summary"] = f"🩸 **جلسات غسيل الكلى**\n\nرقم الجلسة الحالية: {int(text)}"

    await update.message.reply_text("✅ تم الحفظ")
    await _render_dialysis_next_date_calendar(update.message, context)
    context.user_data['_conversation_state'] = TREATMENT_DIALYSIS_NEXT_DATE
    return TREATMENT_DIALYSIS_NEXT_DATE


def _build_dialysis_next_date_markup(year: int, month: int):
    """تقويم تاريخ الجلسة القادمة — نسخة مبسّطة عن تقويم تاريخ العودة العام
    في new_consult.py (بلا خطوة وقت وبلا سبب بعدها)، بـ callback_data
    مستقلة تماماً (dlx_cal_*) حتى لا تتداخل مع أي حالة أخرى."""
    cal = calendar.Calendar(firstweekday=calendar.SATURDAY)
    weeks = cal.monthdayscalendar(year, month)
    today = datetime.now().date()

    keyboard = [
        [
            InlineKeyboardButton("⬅️", callback_data=f"dlx_cal_prev:{year}-{month:02d}"),
            InlineKeyboardButton(f"{MONTH_NAMES_AR.get(month, month)} {year}", callback_data="noop"),
            InlineKeyboardButton("➡️", callback_data=f"dlx_cal_next:{year}-{month:02d}"),
        ],
        [InlineKeyboardButton(day, callback_data="noop") for day in WEEKDAYS_AR],
    ]

    for week in weeks:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="noop"))
                continue
            date_str = f"{year}-{month:02d}-{day:02d}"
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            if date_obj < today:
                row.append(InlineKeyboardButton(" ", callback_data="noop"))
            else:
                mark = "📍" if date_obj == today else ""
                row.append(InlineKeyboardButton(f"{mark}{day:02d}", callback_data=f"dlx_cal_day:{date_str}"))
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel"),
    ])

    text = f"📅 **تاريخ الجلسة القادمة**\n\n{MONTH_NAMES_AR.get(month, str(month))} {year}\n\nاختر التاريخ من التقويم:"
    return text, InlineKeyboardMarkup(keyboard)


async def _render_dialysis_next_date_calendar(message_or_query, context, year=None, month=None):
    data = context.user_data.setdefault("report_tmp", {})
    if year is None or month is None:
        now = datetime.now()
        year = data.get("followup_calendar_year", now.year)
        month = data.get("followup_calendar_month", now.month)

    text, markup = _build_dialysis_next_date_markup(year, month)
    data["followup_calendar_year"] = year
    data["followup_calendar_month"] = month

    if hasattr(message_or_query, "edit_message_text"):
        await message_or_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await message_or_query.reply_text(text, reply_markup=markup, parse_mode="Markdown")


async def handle_dialysis_next_date_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التنقل بين الشهور في تقويم تاريخ الجلسة القادمة."""
    query = update.callback_query
    await query.answer()
    action, ym = query.data.split(":", 1)
    year, month = (int(x) for x in ym.split("-"))
    if action == "dlx_cal_prev":
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    else:
        month += 1
        if month == 13:
            month, year = 1, year + 1
    await _render_dialysis_next_date_calendar(query, context, year, month)
    return TREATMENT_DIALYSIS_NEXT_DATE


async def handle_dialysis_next_date_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار تاريخ الجلسة القادمة من التقويم → المترجم مباشرة (بلا وقت
    وبلا سبب — بناءً على طلب المستخدم صراحةً)."""
    query = update.callback_query
    await query.answer()
    date_str = query.data.split(":", 1)[1]
    date_value = datetime.strptime(date_str, "%Y-%m-%d").date()

    data = context.user_data.setdefault("report_tmp", {})
    data["followup_date"] = date_value
    data["followup_time"] = None

    days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
    day_name = days_ar.get(date_value.weekday(), '')
    await query.edit_message_text(
        f"✅ **تم اختيار تاريخ الجلسة القادمة**\n\n"
        f"📅 {date_value.strftime('%d')} {MONTH_NAMES_AR.get(date_value.month, date_value.month)} "
        f"{date_value.year} ({day_name})",
        parse_mode="Markdown",
    )

    flow_type = data.get("current_flow", "treatment_dialysis")
    gate_result = await show_translator_selection(query.message, context, flow_type)
    if gate_result == "MEDICAL_REPORT_ASK":
        return gate_result
    return TREATMENT_TRANSLATOR


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
    'handle_chemo_cycles_total', 'handle_chemo_cycles_uniform_choice',
    'handle_chemo_cycles_uniform_count', 'handle_chemo_cycles_custom_entry',
    'handle_treatment_plan_setup', 'handle_treatment_plan_display_choice',
    'handle_treatment_plan_edit_value', 'handle_treatment_plan_edit_reason',
    'handle_treatment_plan_edit_reason_skip', 'handle_treatment_plan_manual_session',
    'handle_chemo_session_number',
    'handle_treatment_complaint',
    'handle_treatment_notes', 'handle_treatment_notes_skip', 'handle_treatment_followup_reason',
    'handle_treatment_dialysis_session_number',
    'handle_dialysis_next_date_nav', 'handle_dialysis_next_date_day',
    'TREATMENT_MEDICAL_ACTION',
]
