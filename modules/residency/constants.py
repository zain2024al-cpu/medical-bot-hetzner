# modules/residency/constants.py

from modules.general_services.constants import STAFF_MAP  # re-export for convenience

# ── Status definitions ────────────────────────────────────────────────────────

RESIDENCY_STATUS_LABELS: dict[str, str] = {
    "active":             "✅ نشطة",
    "expiring":           "⚠️ تنتهي قريباً",
    "renewal_submitted":  "📤 تم الرفع — بانتظار الإقامة الجديدة",
    "extension_received": "📥 تم استلام التمديد",
    "issued":             "🪪 تم الإصدار",
    "dependent_pending":  "⏳ مرافقون معلقون",
    "expired":            "❌ منتهية",
    "inactive":           "🔒 غير نشطة",
}

RESIDENCY_STATUS_ICONS: dict[str, str] = {
    "active":             "✅",
    "expiring":           "⚠️",
    "renewal_submitted":  "📤",
    "extension_received": "📥",
    "issued":             "🪪",
    "dependent_pending":  "⏳",
    "expired":            "❌",
    "inactive":           "🔒",
}

# ── دورة أوراق المستشفى ────────────────────────────────────────────────────────
#
# active/expiring → renewal_submitted → issued
#                   📤 تم الرفع        (عبر مسار rnr: — زر «🪪 تجديد الإقامة»
#                   (من شاشة المتابعة)  المتاح دائماً على ملف المريض)
#
# ⚠️ لا زر تقدّم-تدريجي على ملف المريض بعد الآن (قرار المستخدم: كان مربكاً
# بكثرة الأزرار) — «🪪 تجديد الإقامة» وحده ينقل مباشرة لتسجيل الإقامة
# الجديدة من أي حالة. `renewal_submitted` يبقى قابلاً للوصول فقط من شاشة
# «⏰ المتابعة» (`mark_renewal_submitted`)، و`extension_received` صار غير
# مُستخدَم من أي مسار جديد — يبقى في القاموسين أدناه فقط لعرض ملفات قديمة
# قد تحمل هذه الحالة من قبل هذا التغيير.

# الحالات التي تعني «الدورة جارية» — تُعرض في شاشة متابعة الأوراق دائماً
# بغضّ النظر عن قرب تاريخ الانتهاء، لأن الورق عند المستشفى فعلاً.
PAPERS_IN_PROGRESS: tuple[str, ...] = ("renewal_submitted", "extension_received")

# ── مجموعات الحالات المستخدَمة في الاستعلامات ─────────────────────────────────
#
# ⚠️ مصدر واحد عمداً: كانت هذه المجموعة مكتوبة **يدوياً في استعلامين منفصلين**
# داخل followup/repository.py. أي حالة جديدة تُضاف لأحدهما وتُنسى في الآخر
# تُخفي أصحابها من «المتابعة» أو من التنبيه اليومي **بلا أي خطأ في اللوق** —
# وهو أخطر أنواع الأعطال هنا لأنه صامت تماماً.

# من يُتابَع في شاشة المتابعة وفي التنبيه اليومي (إقامةً وجوازاً).
TRACKABLE_STATUSES: tuple[str, ...] = (
    "active", "expiring", "renewal_submitted", "extension_received", "issued",
)

# المرافق الذي ما زال ينتظر إقامته بينما صدرت إقامة مريضه.
COMPANION_PENDING_STATUSES: tuple[str, ...] = (
    "active", "expiring", "renewal_submitted", "extension_received",
)

# ── Thresholds ────────────────────────────────────────────────────────────────

EXPIRING_SOON_DAYS = 30       # الإقامة: تنبيه قبل الانتهاء بشهر
PASSPORT_EXPIRING_SOON_DAYS = 180   # الجواز: تنبيه قبل الانتهاء بـ6 أشهر
PROFILES_PAGE_SIZE = 8        # Profiles per page in archive list
