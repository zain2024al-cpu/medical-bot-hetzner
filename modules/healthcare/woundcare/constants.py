# modules/healthcare/woundcare/constants.py
# Static data for the woundcare flow.
# flow.py / views.py import from here — never define lists/maps inline.

from shared.multiselect import Option

# ── Step 7: المستلزمات الطبية ─────────────────────────────────────────────────

WOUNDCARE_SUPPLIES_OPTIONS: list[Option] = [
    Option(id="gauze",     label="شاش معقم",       icon="🩹"),
    Option(id="gloves",    label="قفازات معقمة",    icon="🧤"),
    Option(id="med_tape",  label="Medical Tape",     icon="🩹"),
    Option(id="betadine",  label="Povidone-Iodine",  icon="🟤"),
    Option(id="saline",    label="Normal Saline",    icon="💧"),
    Option(id="vsl_gauze", label="Vaseline Gauze",   icon="🩹"),
    Option(id="rolled_g",  label="Rolled Gauze",     icon="🩹"),
    Option(id="ab_cream",  label="Antibiotic Cream", icon="🧴"),
    Option(id="brush",     label="فرشة مجارحة",      icon="🖌️"),
    Option(id="sup_other", label="أخرى",             icon="📝"),
]

# ── Step 5: مرحلة المجارحة — callback action → Arabic display label ───────────

PHASE_MAP: dict[str, str] = {
    "phase_pre_op":    "قبل العملية",
    "phase_post_1":    "الأولى بعد العملية",
    "phase_post_last": "بعد العملية الأخيرة",
    "phase_chronic":   "مجارحة دورية / جرح مزمن",
}

# ── Step 10: اسم الصحي — shared staff registry ───────────────────────────────

from modules.healthcare.staff import HC_SP_MAP as SP_MAP, HC_STAFF_LIST as STAFF_LIST

# ── "أخرى" guard IDs ─────────────────────────────────────────────────────────

DEPT_OTHER_ID     = "dept_other"
SUPPLIES_OTHER_ID = "sup_other"
