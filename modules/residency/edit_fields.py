# modules/residency/edit_fields.py
# "✏️ تعديل البيانات" — تصحيح أي حقل بعد إدخاله.
#
# ⚠️ لماذا وُجدت هذه الشاشة:
# منطق الاستئناف (`_build_legacy_state` / `_build_onboard_state`) **يتخطّى
# كل حقل مملوء** — وهذا صحيح لاستئناف تسلسل ناقص، لكنه يعني أن أي قيمة
# أُدخِلت خطأً (ملف مرفوع بالغلط، تاريخ مكتوب سهواً) **لا يُعاد سؤالها
# أبداً**: الرجوع يخرج من التسلسل، وإعادة الدخول تقفز فوق الحقل المملوء.
# ولم يكن ثمة أي مسار لتعديلها بعد اكتمال الحالة.
#
# الحلّ هنا مسار تصحيح صريح ومستقلّ عن التسلسل: يعرض القيم الحالية،
# ويُعيد سؤال الحقل المختار وحده، ويحفظ فوقه.
#
# 🔒 لا حذف: التعديل يكتب قيمة جديدة مكان القديمة فقط.

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.residency.constants import RN

# (المفتاح, التسمية, نوع الإدخال)
FIELDS = [
    ("expiry",  "📅 تاريخ انتهاء الإقامة", "date"),
    ("remind",  "🔔 تاريخ التنبيه",        "date"),
    ("lastiss", "🗓️ تاريخ آخر إصدار",     "date"),
    ("resfile", "🪪 صورة الإقامة",         "file"),
    ("photo",   "📷 الصورة الشخصية",       "file"),
]

_LABELS = {k: lbl for k, lbl, _ in FIELDS}
_KINDS = {k: kind for k, _, kind in FIELDS}


def field_label(key: str) -> str:
    return _LABELS.get(key, key)


def field_kind(key: str) -> str:
    return _KINDS.get(key, "date")


def current_value(person, key: str) -> str:
    """القيمة الحالية كما تُعرَض — "— (غير مُدخَل)" إن كانت فارغة."""
    if key == "expiry":
        v = (person.expiry_date or "").strip()
    elif key == "lastiss":
        v = (getattr(person, "last_issue_date", "") or "").strip()
    elif key == "remind":
        v = (person.reminder_date or "").strip()
    elif key == "resfile":
        return "✅ مرفوعة" if (person.residency_file_id or "").strip() else "— لا يوجد"
    elif key == "photo":
        return "✅ مرفوعة" if (person.photo_file_id or "").strip() else "— لا يوجد"
    else:
        v = ""
    return v or "— غير مُدخَل"


def build_person_picker(family) -> tuple[str, InlineKeyboardMarkup]:
    """من تريد تعديل بياناته؟ — المريض أو أحد مرافقيه."""
    lines = [
        "✏️ **تعديل البيانات**",
        "",
        "اختر الشخص المراد تصحيح بياناته:",
    ]
    rows = [[InlineKeyboardButton(
        f"👤 {family.root.name[:28]}", callback_data=f"{RN}:edit_{family.root.id}")]]
    for c in family.companions:
        rows.append([InlineKeyboardButton(
            f"👥 {c.name[:28]}", callback_data=f"{RN}:edit_{c.id}")])
    rows.append([InlineKeyboardButton(
        "⬅️ رجوع", callback_data=f"{RN}:family_{family.root.id}")])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


def build_edit_menu(person, back_to: str) -> tuple[str, InlineKeyboardMarkup]:
    """حقول الشخص بقيمها الحالية — الضغط يُعيد سؤال الحقل وحده."""
    lines = [
        "✏️ **تعديل البيانات**",
        "",
        f"👤 **{person.name}**",
        "",
        "القيم الحالية — اضغط أي حقل لتصحيحه:",
        "",
    ]
    rows = []
    for key, label, _ in FIELDS:
        val = current_value(person, key)
        lines.append(f"   {label}: {val}")
        rows.append([InlineKeyboardButton(
            f"{label}  ({val})"[:60], callback_data=f"{RN}:edf_{key}_{person.id}")])
    lines += ["", "_القيمة الجديدة تحلّ محلّ القديمة — لا يُحذف شيء._"]
    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=back_to)])
    return "\n".join(lines), InlineKeyboardMarkup(rows)


def build_file_prompt(person, key: str, back_to: str) -> tuple[str, InlineKeyboardMarkup]:
    label = field_label(key)
    text = (
        f"✏️ **تصحيح {label}**\n\n"
        f"👤 {person.name}\n"
        f"الحالي: {current_value(person, key)}\n\n"
        "أرسل الملف الجديد الآن 📎\n"
        "_سيحلّ محلّ الملف السابق._"
    )
    rows = []
    # 🗑️ الحذف يظهر فقط إن كان ثمة ملف — فلا زر بلا معنى
    if "✅" in current_value(person, key):
        rows.append([InlineKeyboardButton(
            f"🗑️ حذف {label}", callback_data=f"{RN}:edel_{key}_{person.id}")])
    rows.append([InlineKeyboardButton("⬅️ رجوع", callback_data=back_to)])
    return text, InlineKeyboardMarkup(rows)


def build_delete_confirm(person, key: str, back_to: str) -> tuple[str, InlineKeyboardMarkup]:
    """تأكيد صريح قبل الحذف — لا حذف بضغطة واحدة."""
    label = field_label(key)
    text = (
        f"🗑️ **حذف {label}**\n\n"
        f"👤 {person.name}\n\n"
        "سيُزال الملف من ملف الحالة ولن يُطبَع معه.\n"
        "_يمكنك رفع بديل في أي وقت._"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ نعم، احذفه", callback_data=f"{RN}:edelgo_{key}_{person.id}")],
        [InlineKeyboardButton("⬅️ إلغاء", callback_data=back_to)],
    ])
    return text, kb
