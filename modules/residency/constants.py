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

# ── دورة أوراق المستشفى — وحدة «📤 الرفع والمتابعة» ───────────────────────────
#
# active/expiring → renewal_submitted → extension_received → issued
#                   📤 تم الرفع         📥 تم استلام        (عبر مسار rnr:)
#                   بانتظار الإقامة      التمديد
#
# ⚠️ هذه سلسلة الحالات نفسها لا متتبِّعاً موازياً: «تم الرفع وجاري الانتظار»
# هو `renewal_submitted` الموجود أصلاً بمسمّاه القديم «تم التقديم». بناء حقل
# ثانٍ بنفس المعنى هو نمط الخطأ المتكرر المسجَّل في MAINTENANCE_LOG.md.

# ما يُكتب على زر التقدّم عند كل حالة، وإلى أي حالة ينقل.
# القيمة None ⇐ الزر لا يغيّر حالة بل يفتح مسار الإصدار `rnr:` (تقويم الإقامة
# الجديدة + رفع الملفات للمريض ومرافقيه)، وهو من يضبط `issued`.
#
# ✅ مصدر الحقيقة الوحيد للمرحلتين معاً: الشاشة تقرأ منه أي زر تعرض،
# والمستودع يقرأ منه إلى أين ينقل — فلا تنحرف الشاشة عن المنطق.
PAPERS_ADVANCE: dict[str, tuple[str, str | None]] = {
    "active":             ("📤 تم الرفع",              "renewal_submitted"),
    "expiring":           ("📤 تم الرفع",              "renewal_submitted"),
    "expired":            ("📤 تم الرفع",              "renewal_submitted"),
    "issued":             ("📤 تم الرفع",              "renewal_submitted"),
    "dependent_pending":  ("📤 تم الرفع",              "renewal_submitted"),
    "renewal_submitted":  ("📥 تم استلام التمديد",     "extension_received"),
    "extension_received": ("🪪 تسجيل الإقامة الجديدة", None),
}

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
HISTORY_DISPLAY_LIMIT = 5     # Timeline entries shown in profile detail view
