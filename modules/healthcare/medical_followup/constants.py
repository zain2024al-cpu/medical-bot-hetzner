# modules/healthcare/medical_followup/constants.py
# Static data for the medical follow-up flow.
# flow.py / views.py import from here — never define lists/maps inline.

from shared.multiselect import Option

# ── Step 4: نوع الإجراء — 6 options, no "أخرى" ───────────────────────────────

PROCEDURE_TYPE_OPTIONS: list[Option] = [
    Option(id="routine",    label="فحص طبي روتيني",        icon="🩺"),
    Option(id="post_op",    label="متابعة ما بعد العملية",  icon="🏥"),
    Option(id="dressing",   label="تغيير ضمادة",            icon="🩹"),
    Option(id="medication", label="إعطاء دواء",             icon="💊"),
    Option(id="vitals_chk", label="قياس العلامات الحيوية",  icon="📊"),
    Option(id="clinical",   label="تقييم سريري",            icon="📋"),
]

# ── Step 5: الشكوى الرئيسية — 7 + أخرى = 8 ──────────────────────────────────

COMPLAINT_OPTIONS: list[Option] = [
    Option(id="cmp_pain",      label="ألم",                 icon="😣"),
    Option(id="cmp_redness",   label="احمرار",               icon="🔴"),
    Option(id="cmp_swelling",  label="تورم",                 icon="🫧"),
    Option(id="cmp_fever",     label="حمى / ارتفاع حرارة",  icon="🌡️"),
    Option(id="cmp_bleeding",  label="نزيف",                 icon="🩸"),
    Option(id="cmp_discharge", label="إفراز",                icon="💧"),
    Option(id="cmp_nausea",    label="قيء / غثيان",          icon="🤢"),
    Option(id="cmp_other",     label="أخرى",                 icon="📝"),
]

# ── Step 7: الأدوية والمستلزمات — 7 + أخرى = 8 ──────────────────────────────

MEDS_SUPPLY_OPTIONS: list[Option] = [
    Option(id="ms_antibiotic", label="مضاد حيوي",    icon="💊"),
    Option(id="ms_analgesic",  label="مسكن ألم",     icon="🩺"),
    Option(id="ms_bp_med",     label="دواء ضغط الدم", icon="❤️"),
    Option(id="ms_iv_fluid",   label="محلول وريدي",   icon="💧"),
    Option(id="ms_gauze",      label="شاش معقم",      icon="🩹"),
    Option(id="ms_eye_drops",  label="قطرة عيون",     icon="👁️"),
    Option(id="ms_bandage",    label="ضمادة",         icon="🔵"),
    Option(id="ms_other",      label="أخرى",          icon="📝"),
]

# ── Step 10: اسم الصحي — shared staff registry ───────────────────────────────

from modules.healthcare.staff import HC_SP_MAP as SP_MAP, HC_STAFF_LIST as STAFF_LIST

# ── "أخرى" guard IDs ─────────────────────────────────────────────────────────

DEPT_OTHER_ID         = "dept_other"
COMPLAINT_OTHER_ID    = "cmp_other"
MEDS_SUPPLY_OTHER_ID  = "ms_other"
