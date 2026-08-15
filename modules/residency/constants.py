# modules/residency/constants.py
RN = "rn"   # بادئة كولباك وحدة الإقامة

STATUS_WAITING_ARRIVAL = "WAITING_ARRIVAL"
STATUS_ACTIVE          = "ACTIVE"
STATUS_EXPIRY_PENDING  = "EXPIRY_PENDING"
STATUS_SUBMITTED       = "SUBMITTED"
STATUS_ISSUED          = "ISSUED"

# ترتيب العرض في القائمة الرئيسية
STATUS_ORDER = [
    STATUS_WAITING_ARRIVAL,
    STATUS_ACTIVE,
    STATUS_EXPIRY_PENDING,
    STATUS_SUBMITTED,
    STATUS_ISSUED,
]

STATUS_ICONS = {
    STATUS_WAITING_ARRIVAL: "🟡",
    STATUS_ACTIVE:          "🟢",
    STATUS_EXPIRY_PENDING:  "🔴",
    STATUS_SUBMITTED:       "🔵",
    STATUS_ISSUED:          "🟣",
}

STATUS_LABELS = {
    STATUS_WAITING_ARRIVAL: "معلّق من الوصول",
    STATUS_ACTIVE:          "الحالات النشطة",
    STATUS_EXPIRY_PENDING:  "معلّق انتهاء الإقامة",
    STATUS_SUBMITTED:       "تم التقديم(قيد الانتظار)",
    STATUS_ISSUED:          "توثيق التمديدات المصدره",
}


def status_line(status: str) -> str:
    return f"{STATUS_ICONS.get(status, '⚪')} {STATUS_LABELS.get(status, status)}"
