# shared/departments.py
# Master department registry — single source of truth for ALL medical department
# definitions used across the platform.
#
# Consumers
# ─────────
#   Healthcare module
#       get_department_options()  →  list[Option] for the "القسم الطبي" multiselect
#       (woundcare · medical_followup · medications all read from here)
#
#   Translator module
#       PREDEFINED_DEPARTMENTS    →  dict[main_dept → [sub_depts]] for hierarchical
#                                    single-select (imported via user_reports_add_helpers)
#       DIRECT_DEPARTMENTS        →  list[str] of flat leaf departments (no drill-down)
#
# Adding or renaming a department here automatically reflects in both systems.

from shared.multiselect import Option


# ── Healthcare multiselect — ordered flat specialty list ─────────────────────
# These are the choices shown in every healthcare "القسم الطبي" multiselect.
# Order: most-common surgical/medical specialties first, then ancillary/support.

_MEDICAL_SPECIALTIES: list[tuple[str, str, str]] = [
    # (id,         label,                                  icon)
    # Core/direct specialties — stable backward-compatible IDs.
    # Labels match DIRECT_DEPARTMENTS equivalents exactly.
    ("neuro",      "المخ والأعصاب",                        "🧠"),
    ("urology",    "المسالك البولية",                       "🫀"),
    ("cardio",     "القلب",                                "❤️"),
    ("ortho",      "العظام",                               "🦴"),
    ("oncology",   "الأورام",                              "🎗️"),
    ("peds",       "الأطفال",                              "🧒"),
    ("obgyn",      "النساء والتوليد",                       "👶"),
    ("rehab",      "العلاج الطبيعي وإعادة التأهيل",       "🏋️"),
    ("ent",        "الأذن والأنف والحنجرة",                 "👂"),
    ("derm",       "الأمراض الجلدية",                      "🩹"),
    ("psych",      "الطب النفسي",                          "🧠"),
    ("emerg",      "الطوارئ",                              "🚨"),
    ("icu",        "العناية المركزة",                       "🏥"),
    ("anesth",     "التخدير",                              "💉"),
    ("nuclear",    "الطب النووي",                          "⚛️"),
    ("dental",     "طب الأسنان",                           "🦷"),
    ("pain",       "علاج وإدارة الألم",                    "💊"),
    ("radio",      "العلاج الإشعاعي",                      "☢️"),
]

# ── Icon assignment for each PREDEFINED main-department group ─────────────────
# Sub-departments inherit their group's icon in the healthcare multiselect.

_PREDEFINED_DEPT_ICONS: dict[str, str] = {
    "الجراحة":            "🔪",
    "الباطنية":           "⚕️",
    "طب وجراحة العيون":  "👁️",
    "طب الأطفال":         "🧒",
}


def get_department_options(include_other: bool = True) -> list[Option]:
    """
    Return the COMPLETE medical department list for healthcare multiselect.

    Builds from two sources so that healthcare always reflects the full
    translator registry without any manual synchronization:

    1. _MEDICAL_SPECIALTIES — 18 core/direct specialties (stable IDs preserved
       for backward compatibility with existing session/DB records).
    2. All sub-specialties from PREDEFINED_DEPARTMENTS — flattened, appended
       after the core list, deduplicated by label.

    If include_other=True (default), appends 'أخرى' at the end so users can
    add a department not on the list via free-text input (saved for next time).
    """
    opts: list[Option] = [
        Option(id=id_, label=label, icon=icon)
        for id_, label, icon in _MEDICAL_SPECIALTIES
    ]

    # Flatten every sub-department from PREDEFINED_DEPARTMENTS.
    # Skip any label already present (covers the 12 DIRECT_DEPARTMENTS equivalents).
    existing_labels: set[str] = {o.label for o in opts}
    for main_dept, sub_depts in PREDEFINED_DEPARTMENTS.items():
        icon = _PREDEFINED_DEPT_ICONS.get(main_dept, "🏥")
        for sub_dept in sub_depts:
            if sub_dept not in existing_labels:
                # Stable ID: words joined by underscore (Arabic kept as-is)
                dept_id = "_".join(sub_dept.split())
                opts.append(Option(id=dept_id, label=sub_dept, icon=icon))
                existing_labels.add(sub_dept)

    if include_other:
        opts.append(Option(id="dept_other", label="أخرى", icon="📝"))
    return opts


# ── Translator — hierarchical department registry ─────────────────────────────
# Used by the translator's department-selection screen (main dept → sub-dept drill-down).
# Keys are the main-department display names; values are the sub-department lists.

PREDEFINED_DEPARTMENTS: dict[str, list[str]] = {
    "الجراحة": [
        "الجراحة العامة",
        "جراحة العظام",
        "جراحة التجميل",
        "جراحة الأورام",
        "جراحة القلب",
        "جراحة الصدر",
        "جراحة المخ والأعصاب",
        "جراحة المسالك البولية",
        "جراحة الجهاز الهضمي",
        "جراحة الأوعية الدموية",
        "جراحة الكبد والقنوات الصفراوية",
        "جراحة الوجه والفكين",
    ],
    "الباطنية": [
        "باطنية عامة",
        "باطنية الجهاز الهضمي",
        "باطنية الجهاز التنفسي والصدر",
        "الغدد الصماء والسكري",
        "باطنية المخ والأعصاب",
        "باطنية الأورام",
        "باطنية الكلى",
        "باطنية القلب",
        "باطنية الصدر",
        "باطنية الكبد",
        "أمراض الدم",
        "الأمراض المعدية",
        "الروماتيزم والمناعة",
    ],
    "طب وجراحة العيون": [
        "عيون - القرنية وتصحيح النظر",
        "عيون - الشبكية والجسم الزجاجي",
        "عيون - الجلوكوما وضغط العين",
        "عيون - المياه البيضاء والعدسات",
        "عيون - العصب البصري",
        "عيون - تجميل",
        "عيون - أطفال وحول",
        "عيون - إعادة التأهيل البصري",
    ],
    "طب الأطفال": [
        "أطفال - عام",
        "أطفال - جراحة",
        "أطفال - مخ وأعصاب",
        "أطفال - قلب",
        "أطفال - كلى ومسالك",
        "أطفال - دم وأورام",
        "أطفال - غدد",
        "أطفال - جهاز تنفسي وصدر",
        "أطفال - جهاز هضمي",
        "أطفال - روماتيزم وأمراض مناعية",
        "أطفال - أمراض وراثية وجينات",
        "أطفال - طوارئ",
        "أطفال - عناية مركزة",
    ],
}


# ── Translator — direct (leaf) departments ────────────────────────────────────
# Shown as flat "🏷️ Name" buttons in the translator's department menu.
# No sub-department drill-down for these entries.

DIRECT_DEPARTMENTS: list[str] = [
    "الأذن والأنف والحنجرة",
    "الأمراض الجلدية",
    "النساء والتوليد",
    "الطب النووي",
    "طب الأسنان",
    "العلاج الطبيعي وإعادة التأهيل",
    "علاج وإدارة الألم",
    "الطب النفسي",
    "الطوارئ",
    "التخدير",
    "العناية المركزة",
    "العلاج الإشعاعي",
]
