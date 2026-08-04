# modules/general_services/constants.py

from shared.multiselect import Option

# ── Staff (specialist) map: ID → Arabic label ─────────────────────────────────
STAFF_MAP: dict[str, str] = {
    "sp_ridha": "رضاء",
    "sp_ali":   "علي صالح",
}

# ── Escort entity ("الجهة الموصلة") options ──────────────────────────────────
# الجهة التي أوصلت المريض/المرافق. تُستخدَم في **الواصلين والمغادرين معاً**
# (مصدر واحد لكليهما) بعد حذف HOSPITAL_MAP العربية القديمة التي كانت خاصة
# بالمغادرين — كان لكل شاشة قائمة مستقلة بتسميات مختلفة لنفس المستشفيات.
#
# خيار "أخرى" يُبقي مسار الكتابة اليدوية عاملاً لأي جهة خارج القائمة.
ESCORT_ENTITY_MAP: dict[str, str] = {
    "ee_manipal": "Manipal Hospital",
    "ee_aster":   "Aster Hospital",
    "ee_fortis":  "Fortis Hospital",
    "ee_sakra":   "Sakra Hospital",
    "ee_sparsh":  "Sparsh Hospital",
    "ee_apollo":  "Apollo Hospital",
    "ee_kims":    "Kims Hospital",
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
