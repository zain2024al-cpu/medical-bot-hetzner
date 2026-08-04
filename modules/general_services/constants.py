# modules/general_services/constants.py

from shared.multiselect import Option

# ── Hospital map: ID → Arabic label ──────────────────────────────────────────
HOSPITAL_MAP: dict[str, str] = {
    "h_manipal":  "مانيبال",
    "h_aster":    "استر",
    "h_fortis":   "فورتيز",
    "h_kims":     "كيمس",
    "h_apollo":   "ابولو",
    "h_sparsh":   "سبارش",
    "h_sakra":    "ساكرا",
}

# ── Staff (specialist) map: ID → Arabic label ─────────────────────────────────
STAFF_MAP: dict[str, str] = {
    "sp_ridha": "رضاء",
    "sp_ali":   "علي صالح",
}

# ── Escort entity ("الجهة الموصلة") options ──────────────────────────────────
# الجهة التي أوصلت المريض/المرافق عند الوصول. كانت تُدخَل نصاً حراً، فأصبحت
# أزراراً جاهزة لتوحيد التسميات (نفس نمط STAFF_MAP/HOSPITAL_MAP أعلاه).
#
# ⚠️ القيم أدناه **مبدئية مؤقتة** — المستخدم سيزوّدنا بالقائمة الحقيقية.
# عند وصولها: عدّل هذا الثابت وحده لا غير، لا يوجد أي مكان آخر يسرد الجهات.
# خيار "أخرى" يُبقي مسار الكتابة اليدوية الأصلي عاملاً لأي جهة خارج القائمة.
ESCORT_ENTITY_MAP: dict[str, str] = {
    "ee_ministry": "الملحقية الطبية",
    "ee_hospital": "المستشفى",
    "ee_office":   "المكتب",
    "ee_relative": "أحد الأقارب",
    "ee_self":     "بمفرده",
}

# مُعرّف خيار "أخرى" — يفتح شاشة الكتابة اليدوية بدل الحفظ المباشر.
ESCORT_ENTITY_OTHER_ID = "ee_other"

# ── Public service type options (multiselect) ─────────────────────────────────
PUBLIC_SERVICE_OPTIONS: list[Option] = [
    Option(id="ps_visa",      label="معاملة تأشيرة"),
    Option(id="ps_medical",   label="متابعة طبية"),
    Option(id="ps_transport", label="نقل ومواصلات"),
    Option(id="ps_housing",   label="سكن وإقامة"),
    Option(id="ps_financial", label="شؤون مالية"),
    Option(id="ps_insurance", label="تأمين صحي"),
    Option(id="ps_document",  label="معاملة وثيقة"),
    Option(id="ps_other",     label="أخرى"),
]
