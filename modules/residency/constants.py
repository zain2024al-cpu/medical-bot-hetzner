# modules/residency/constants.py
RN = "rn"   # بادئة كولباك وحدة الإقامة

STATUS_WAITING_ARRIVAL = "WAITING_ARRIVAL"
STATUS_ACTIVE          = "ACTIVE"
STATUS_EXPIRY_PENDING  = "EXPIRY_PENDING"
STATUS_SUBMITTED       = "SUBMITTED"
STATUS_ISSUED          = "ISSUED"
# ✅ مريض **قديم** كان موجوداً قبل تفعيل وحدة الإقامة، أُدخِل يدوياً عبر
# "🏠 الحالات الموجودة" في الأدمن (لم يمرّ بتدفق "🛬 الوصول" إطلاقاً).
# بياناته الأساسية (جواز/تأشيرة/سكن) مكتملة، لكن بيانات **الإقامة** نفسها
# (تمديد/انتهاء) لم تُدخَل بعد — تُدخَل من هذا الزر ثم ينتقل لحالته
# الطبيعية ضمن الحالات الخمس أعلاه.
STATUS_LEGACY_PENDING  = "LEGACY_PENDING"

# ترتيب العرض في القائمة الرئيسية
STATUS_ORDER = [
    STATUS_WAITING_ARRIVAL,
    STATUS_LEGACY_PENDING,
    STATUS_ACTIVE,
    STATUS_EXPIRY_PENDING,
    STATUS_SUBMITTED,
    STATUS_ISSUED,
]

STATUS_ICONS = {
    STATUS_WAITING_ARRIVAL: "🟡",
    STATUS_LEGACY_PENDING:  "🏠",
    STATUS_ACTIVE:          "🟢",
    STATUS_EXPIRY_PENDING:  "🔴",
    STATUS_SUBMITTED:       "🔵",
    STATUS_ISSUED:          "🟣",
}

STATUS_LABELS = {
    STATUS_WAITING_ARRIVAL: "معلّق من الوصول",
    STATUS_LEGACY_PENDING:  "معلّقات من الحالات السابقة",
    STATUS_ACTIVE:          "الحالات النشطة",
    STATUS_EXPIRY_PENDING:  "معلّق انتهاء الإقامة",
    STATUS_SUBMITTED:       "تم التقديم(قيد الانتظار)",
    STATUS_ISSUED:          "توثيق التمديدات المصدره",
}


# تسميات مختصرة — للسجل حيث يتكرّر اسمان في كل سطر. التسمية الكاملة
# («معلّقات من الحالات السابقة») تجعل السطر ~١٠٠ حرف فيلتفّ ثلاث مرات
# على الجوال، والشاشة كلها تقترب من حدّ تليجرام (٤٠٩٦).
STATUS_SHORT = {
    STATUS_WAITING_ARRIVAL: "معلّق الوصول",
    STATUS_LEGACY_PENDING:  "حالات سابقة",
    STATUS_ACTIVE:          "نشطة",
    STATUS_EXPIRY_PENDING:  "معلّق انتهاء",
    STATUS_SUBMITTED:       "تم التقديم",
    STATUS_ISSUED:          "تمديد مُصدَر",
}


def status_chip(status: str) -> str:
    """أيقونة + تسمية مختصرة."""
    return f"{STATUS_ICONS.get(status, '⚪')} {STATUS_SHORT.get(status, status)}"


def status_line(status: str) -> str:
    return f"{STATUS_ICONS.get(status, '⚪')} {STATUS_LABELS.get(status, status)}"
