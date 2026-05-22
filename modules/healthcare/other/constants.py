# modules/healthcare/other/constants.py
# Static data for the "other healthcare" catch-all flow.
# flow.py imports from here — never define lists inline.

from shared.multiselect import Option

# ── Step 2: نوع الإجراء — 7 + أخرى = 8 ──────────────────────────────────────

ACTION_OPTIONS: list[Option] = [
    Option(id="assessment", label="تقييم المريض",          icon="📋"),
    Option(id="vitals",     label="قياس العلامات الحيوية", icon="🩺"),
    Option(id="education",  label="تثقيف المريض",          icon="📚"),
    Option(id="transfer",   label="تنسيق تحويل",           icon="🚑"),
    Option(id="doc",        label="توثيق طبي",             icon="📄"),
    Option(id="consult",    label="استشارة",               icon="💬"),
    Option(id="postop",     label="متابعة ما بعد العملية", icon="🏥"),
    Option(id="other_act",  label="أخرى",                  icon="📝"),
]
