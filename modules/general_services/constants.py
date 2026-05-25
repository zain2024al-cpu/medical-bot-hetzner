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
