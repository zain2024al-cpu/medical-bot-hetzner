# modules/healthcare/woundcare/constants.py
# Static data for the woundcare flow.
# flow.py / views.py import from here — never define lists/maps inline.

from shared.multiselect import Option

# ── Step 7: المستلزمات الطبية المستخدمة ──────────────────────────────────────
# IDs are stable — never change them (existing DB records store supply_ids).

WOUNDCARE_SUPPLIES_OPTIONS: list[Option] = [
    Option(id="gauze",     label="Sterile Gauze — شاش معقم",                    icon="🩹"),
    Option(id="gloves",    label="Sterile Gloves — قفازات معقمة",               icon="🧤"),
    Option(id="med_tape",  label="Medical Tape",                                 icon="🩹"),
    Option(id="betadine",  label="Povidone-Iodine — أيودين",                    icon="🟤"),
    Option(id="saline",    label="Normal Saline — نورمال سالين",                icon="💧"),
    Option(id="vsl_gauze", label="Vaseline Gauze — شاش فازلين",                 icon="🩹"),
    Option(id="rolled_g",  label="Rolled Gauze — شاش شريط",                     icon="🩹"),
    Option(id="ab_cream",  label="Antibiotic Cream (Mupirocin) — مرهم مضاد حيوي", icon="🧴"),
    Option(id="brush",     label="Under Pad — فرشة مجارحة",                     icon="🛏️"),
    Option(id="sup_other", label="أخرى",                                        icon="📝"),
]

# ── Step 5: مرحلة المجارحة — callback action → Arabic display label ───────────

PHASE_MAP: dict[str, str] = {
    "phase_pre_op":    "قبل العملية",
    "phase_post_1":    "الأولى بعد العملية",
    "phase_post_last": "بعد العملية",
    "phase_chronic":   "مجارحة دورية / جرح مزمن",
}

# ── Step 10: اسم الصحي — shared staff registry ───────────────────────────────

from modules.healthcare.staff import HC_SP_MAP as SP_MAP, HC_STAFF_LIST as STAFF_LIST

# ── Step 6: وصف حالة الجرح / العملية — official 8-option form ───────────────

WOUND_CONDITION_OPTIONS: list[Option] = [
    Option(id="healed",       label="الجرح ملتئم بالكامل",                icon="✅"),
    Option(id="clean",        label="الجرح نظيف (لا احمرار أو إفرازات)", icon="🟢"),
    Option(id="mild_redness", label="احمرار بسيط حول الجرح",             icon="🔴"),
    Option(id="partial_open", label="الجرح مفتوح جزئياً",                icon="⚠️"),
    Option(id="swelling",     label="تورم مع ألم موضعي أو حرارة موضعية", icon="🌡️"),
    Option(id="discharge",    label="خروج قيح أو إفرازات دموية",         icon="🩸"),
    Option(id="odor",         label="رائحة غير طبيعية",                  icon="💨"),
    Option(id="cond_other",   label="أخرى",                              icon="📝"),
]

# ── "أخرى" guard IDs ─────────────────────────────────────────────────────────

DEPT_OTHER_ID      = "dept_other"
SUPPLIES_OTHER_ID  = "sup_other"
CONDITION_OTHER_ID = "cond_other"
