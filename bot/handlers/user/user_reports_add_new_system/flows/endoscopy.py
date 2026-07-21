# =============================
# flows/endoscopy.py
# مسار المناظير - ENDOSCOPY FLOW
# =============================
#
# تسلسل الإدخال (بعد اختيار المريض/المستشفى/القسم/الطبيب/التاريخ ونوع الإجراء):
#   1. شكوى المريض (نص حر)
#   2. نوع المنظار (3 أزرار: Colonoscopy / Upper GI Endoscopy / Endoscopy & Colonoscopy)
#   3. نتيجة المنظار / خطة الطبيب (نص حر)
#   4. الإجراءات التي تمت أثناء المنظار (اختيار متعدد + "أخرى" → نص)
#   5. الملاحظات (اختياري)
#   ── ثم الذيل المشترك القياسي (نفس بقية المسارات) ──
#   6. تاريخ العودة (التقويم الموحّد) + الوقت
#   7. سبب العودة
#   8. بوابة التقرير الطبي (نعم / لم يجهز بعد / لا) + المرفقات
#   9. اختيار المترجم → التأكيد → النشر
#
# ملاحظات التصميم:
# - تاريخ/سبب العودة يعيدان استخدام معالجات التقويم/الوقت المشتركة في
#   new_consult (المُوجَّهة عبر current_flow="endoscopy")، فلا تكرار.
# - حقول المنظار (endoscopy_type/result/procedures) تُخزَّن في report_tmp
#   وتُحفظ في db عبر shared.py (بلا شرط flow_type، لأن هذه المفاتيح لا
#   يضبطها أي مسار آخر).

import json
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from ..states import (
    ENDOSCOPY_COMPLAINT, ENDOSCOPY_TYPE, ENDOSCOPY_RESULT,
    ENDOSCOPY_PROCEDURES, ENDOSCOPY_PROCEDURES_OTHER, ENDOSCOPY_NOTES,
    ENDOSCOPY_FOLLOWUP_DATE, ENDOSCOPY_FOLLOWUP_REASON, ENDOSCOPY_TRANSLATOR,
)
from ..utils import _nav_buttons
from ...user_reports_add_helpers import validate_text_input
from .shared import show_translator_selection
from .new_consult import _render_followup_calendar

logger = logging.getLogger(__name__)

MEDICAL_ACTION = "المناظير"
FLOW_KEY = "endoscopy"

# ── نوع المنظار: رمز ثابت + تسمية العرض (مصطلحات طبية إنجليزية معتمدة) ──
ENDOSCOPY_TYPES = [
    ("upper_gi",     "Upper GI Endoscopy"),
    ("colonoscopy",  "Colonoscopy"),
    ("both",         "Upper GI Endoscopy & Colonoscopy"),
    ("ercp",         "ERCP (Endoscopic Retrograde Cholangiopancreatography)"),
    ("bronchoscopy", "Bronchoscopy"),
    ("cystoscopy",   "Cystoscopy"),
    ("hysteroscopy", "Hysteroscopy"),
    ("laryngoscopy", "Laryngoscopy"),
    ("sigmoidoscopy", "Sigmoidoscopy"),
    ("enteroscopy",  "Enteroscopy"),
    ("eus",          "EUS (Endoscopic Ultrasound)"),
]
_TYPE_LABEL = {code: label for code, label in ENDOSCOPY_TYPES}

# ── الإجراءات التي تمت أثناء المنظار: رمز ثابت + تسمية ثنائية اللغة ──
ENDOSCOPY_PROCEDURE_OPTIONS = [
    ("biopsy",          "أخذ خزعة (Biopsy)"),
    ("polypectomy",     "إزالة بوليب (Polypectomy)"),
    ("band_ligation",   "ربط بواسير (Hemorrhoid Band Ligation)"),
    ("hemorrhoidectomy", "إزالة بواسير (Hemorrhoidectomy)"),
    ("dilatation",      "توسيع تضيق (Dilatation)"),
    ("hemostasis",      "إيقاف نزيف (Hemostasis)"),
    ("foreign_body",    "إزالة جسم غريب (Foreign Body Removal)"),
    ("other",           "أخرى"),
]
_PROC_LABEL = {code: label for code, label in ENDOSCOPY_PROCEDURE_OPTIONS}

# نص عند عدم اختيار أي إجراء (منظار تشخيصي فقط) — يُكتب تلقائياً.
_DIAGNOSTIC_ONLY_LABEL = "منظار تشخيصي — لم يُجرَ أي إجراء"


# ═══════════════════════════════════════════════════════════════════
# 1) بدء المسار → شكوى المريض
# ═══════════════════════════════════════════════════════════════════
async def start_endoscopy_flow(message, context):
    """بدء مسار المناظير — الحقل 1: شكوى المريض."""
    data = context.user_data.setdefault("report_tmp", {})
    data["medical_action"] = MEDICAL_ACTION
    data["current_flow"] = FLOW_KEY
    context.user_data['_conversation_state'] = ENDOSCOPY_COMPLAINT

    await message.reply_text(
        "🔬 **المناظير**\n\n"
        "📝 **شكوى المريض**\n\n"
        "يرجى إدخال شكوى المريض:",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown",
    )
    return ENDOSCOPY_COMPLAINT


async def handle_endoscopy_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 1: شكوى المريض (نص حر) → نوع المنظار."""
    context.user_data['_conversation_state'] = ENDOSCOPY_COMPLAINT
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)
    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\nيرجى إدخال شكوى المريض:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown",
        )
        return ENDOSCOPY_COMPLAINT

    data = context.user_data.setdefault("report_tmp", {})
    data["complaint_text"] = text
    data["current_flow"] = FLOW_KEY
    data["medical_action"] = MEDICAL_ACTION

    await update.message.reply_text("✅ تم الحفظ")
    await _show_endoscopy_type(update.message, context)
    context.user_data['_conversation_state'] = ENDOSCOPY_TYPE
    return ENDOSCOPY_TYPE


# ═══════════════════════════════════════════════════════════════════
# 2) نوع المنظار (اختيار من 3)
# ═══════════════════════════════════════════════════════════════════
async def _show_endoscopy_type(message, context):
    rows = [[InlineKeyboardButton(label, callback_data=f"endo_type:{code}")]
            for code, label in ENDOSCOPY_TYPES]
    rows.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel"),
    ])
    await message.reply_text(
        "🔬 **نوع المنظار**\n\nاختر نوع المنظار:",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode="Markdown",
    )


async def handle_endoscopy_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 2: نوع المنظار → نتيجة/خطة."""
    query = update.callback_query
    await query.answer()
    code = query.data.split(":", 1)[1]
    label = _TYPE_LABEL.get(code)
    if not label:
        await query.answer("نوع غير صحيح", show_alert=True)
        return ENDOSCOPY_TYPE

    data = context.user_data.setdefault("report_tmp", {})
    data["endoscopy_type"] = label

    await query.edit_message_text(f"✅ **نوع المنظار:** {label}", parse_mode="Markdown")
    await query.message.reply_text(
        "📋 **نتيجة المنظار / خطة الطبيب**\n\n"
        "اكتب النتيجة أو خطة الطبيب (مثال: المنظار طبيعي، يحتاج عملية، أخذ خزعة، "
        "مراجعة بعد أسبوع، علاج دوائي...):",
        reply_markup=_nav_buttons(show_back=True),
        parse_mode="Markdown",
    )
    context.user_data['_conversation_state'] = ENDOSCOPY_RESULT
    return ENDOSCOPY_RESULT


# ═══════════════════════════════════════════════════════════════════
# 3) نتيجة المنظار / خطة الطبيب (نص حر)
# ═══════════════════════════════════════════════════════════════════
async def handle_endoscopy_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحقل 3: نتيجة/خطة → الإجراءات التي تمت."""
    context.user_data['_conversation_state'] = ENDOSCOPY_RESULT
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)
    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\nيرجى إدخال نتيجة المنظار / خطة الطبيب:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown",
        )
        return ENDOSCOPY_RESULT

    data = context.user_data.setdefault("report_tmp", {})
    data["endoscopy_result"] = text
    data.setdefault("_endoscopy_selected", [])

    await update.message.reply_text("✅ تم الحفظ")
    await _show_procedures(update.message, context)
    context.user_data['_conversation_state'] = ENDOSCOPY_PROCEDURES
    return ENDOSCOPY_PROCEDURES


# ═══════════════════════════════════════════════════════════════════
# 4) الإجراءات التي تمت أثناء المنظار (اختيار متعدد)
# ═══════════════════════════════════════════════════════════════════
def _build_procedures_keyboard(selected: list) -> InlineKeyboardMarkup:
    rows = []
    for code, label in ENDOSCOPY_PROCEDURE_OPTIONS:
        mark = "✅" if code in selected else "☐"
        rows.append([InlineKeyboardButton(f"{mark} {label}", callback_data=f"endo_proc:{code}")])
    rows.append([InlineKeyboardButton("✅ متابعة", callback_data="endo_proc_done")])
    rows.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel"),
    ])
    return InlineKeyboardMarkup(rows)


async def _show_procedures(message, context, edit_query=None):
    selected = context.user_data.setdefault("report_tmp", {}).setdefault("_endoscopy_selected", [])
    text = (
        "🔧 **الإجراءات التي تمت أثناء المنظار**\n\n"
        "اختر كل ما تم (يمكن اختيار أكثر من إجراء)، ثم اضغط **✅ متابعة**.\n"
        "إن لم يُجرَ أي إجراء، اضغط **✅ متابعة** مباشرة (منظار تشخيصي)."
    )
    markup = _build_procedures_keyboard(selected)
    if edit_query is not None:
        await edit_query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await message.reply_text(text, reply_markup=markup, parse_mode="Markdown")


async def handle_endoscopy_procedure_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تبديل اختيار إجراء (checkbox)."""
    query = update.callback_query
    await query.answer()
    code = query.data.split(":", 1)[1]
    if code not in _PROC_LABEL:
        return ENDOSCOPY_PROCEDURES

    data = context.user_data.setdefault("report_tmp", {})
    selected = data.setdefault("_endoscopy_selected", [])
    if code in selected:
        selected.remove(code)
    else:
        selected.append(code)

    await _show_procedures(query.message, context, edit_query=query)
    return ENDOSCOPY_PROCEDURES


async def handle_endoscopy_procedures_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إنهاء اختيار الإجراءات → (نص 'أخرى' إن اختير) أو → الملاحظات."""
    query = update.callback_query
    await query.answer()
    data = context.user_data.setdefault("report_tmp", {})
    selected = data.setdefault("_endoscopy_selected", [])

    if "other" in selected:
        await query.edit_message_text(
            "✍️ **إجراء آخر**\n\nاكتب الإجراء الذي تم (أو الإجراءات الإضافية):",
            parse_mode="Markdown",
        )
        context.user_data['_conversation_state'] = ENDOSCOPY_PROCEDURES_OTHER
        return ENDOSCOPY_PROCEDURES_OTHER

    _finalize_procedures(data, other_text=None)
    await query.edit_message_text("✅ تم حفظ الإجراءات", parse_mode="Markdown")
    await _prompt_notes(query.message, context)
    context.user_data['_conversation_state'] = ENDOSCOPY_NOTES
    return ENDOSCOPY_NOTES


async def handle_endoscopy_procedures_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نص إجراء 'أخرى' → الملاحظات."""
    context.user_data['_conversation_state'] = ENDOSCOPY_PROCEDURES_OTHER
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=2)
    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\nاكتب الإجراء الذي تم:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown",
        )
        return ENDOSCOPY_PROCEDURES_OTHER

    data = context.user_data.setdefault("report_tmp", {})
    _finalize_procedures(data, other_text=text)

    await update.message.reply_text("✅ تم الحفظ")
    await _prompt_notes(update.message, context)
    context.user_data['_conversation_state'] = ENDOSCOPY_NOTES
    return ENDOSCOPY_NOTES


def _finalize_procedures(data: dict, other_text):
    """يبني endoscopy_procedures كـ JSON من الاختيارات + نص 'أخرى'."""
    selected = data.get("_endoscopy_selected", [])
    labels = [_PROC_LABEL[c] for c in selected if c != "other" and c in _PROC_LABEL]
    payload = {"list": labels, "other": (other_text or None)}
    data["endoscopy_procedures"] = json.dumps(payload, ensure_ascii=False)
    data.pop("_endoscopy_selected", None)


# ═══════════════════════════════════════════════════════════════════
# 5) الملاحظات (اختياري) → التقويم المشترك
# ═══════════════════════════════════════════════════════════════════
def _notes_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭️ لا توجد ملاحظات", callback_data="endoscopy_notes_skip")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
         InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")],
    ])


async def _prompt_notes(message, context):
    await message.reply_text(
        "📝 **ملاحظات**\n\n"
        "يرجى إدخال أي ملاحظات إضافية، أو اضغط الزر أدناه إذا لا توجد ملاحظات:",
        reply_markup=_notes_keyboard(),
        parse_mode="Markdown",
    )


async def handle_endoscopy_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الملاحظات (نص حر) → التقويم."""
    context.user_data['_conversation_state'] = ENDOSCOPY_NOTES
    text = update.message.text.strip()
    if text.lower() in ['لا يوجد', 'لا', 'no', 'none']:
        text = "لا يوجد"
    context.user_data.setdefault("report_tmp", {})["notes"] = text

    await update.message.reply_text("✅ تم الحفظ")
    await _render_followup_calendar(update.message, context)
    context.user_data['_conversation_state'] = ENDOSCOPY_FOLLOWUP_DATE
    return ENDOSCOPY_FOLLOWUP_DATE


async def handle_endoscopy_notes_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """زر ⏭️ لا توجد ملاحظات → التقويم."""
    query = update.callback_query
    await query.answer()
    context.user_data.setdefault("report_tmp", {})["notes"] = "لا يوجد"
    await _render_followup_calendar(query, context)
    context.user_data['_conversation_state'] = ENDOSCOPY_FOLLOWUP_DATE
    return ENDOSCOPY_FOLLOWUP_DATE


# ═══════════════════════════════════════════════════════════════════
# 6) سبب العودة → اختيار المترجم → البوابة/النشر (مشترك)
# ═══════════════════════════════════════════════════════════════════
async def handle_endoscopy_followup_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """سبب العودة → اختيار المترجم/البوابة."""
    context.user_data['_conversation_state'] = ENDOSCOPY_FOLLOWUP_REASON
    text = update.message.text.strip()
    valid, msg = validate_text_input(text, min_length=3)
    if not valid:
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\nيرجى إدخال سبب العودة:",
            reply_markup=_nav_buttons(show_back=True),
            parse_mode="Markdown",
        )
        return ENDOSCOPY_FOLLOWUP_REASON

    context.user_data["report_tmp"]["followup_reason"] = text
    await update.message.reply_text("✅ تم الحفظ")
    gate_result = await show_translator_selection(update.message, context, FLOW_KEY)
    if gate_result == "MEDICAL_REPORT_ASK":
        return gate_result
    return ENDOSCOPY_TRANSLATOR


__all__ = [
    'start_endoscopy_flow',
    'handle_endoscopy_complaint',
    'handle_endoscopy_type',
    'handle_endoscopy_result',
    'handle_endoscopy_procedure_toggle',
    'handle_endoscopy_procedures_done',
    'handle_endoscopy_procedures_other',
    'handle_endoscopy_notes',
    'handle_endoscopy_notes_skip',
    'handle_endoscopy_followup_reason',
    'ENDOSCOPY_TYPES',
    'ENDOSCOPY_PROCEDURE_OPTIONS',
]
