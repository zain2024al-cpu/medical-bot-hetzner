# modules/residency/constants.py

from modules.general_services.constants import STAFF_MAP  # re-export for convenience

# ── Status definitions ────────────────────────────────────────────────────────

RESIDENCY_STATUS_LABELS: dict[str, str] = {
    "active":             "✅ نشطة",
    "expiring":           "⚠️ تنتهي قريباً",
    "renewal_submitted":  "📋 تم التقديم",
    "issued":             "🪪 تم الإصدار",
    "dependent_pending":  "⏳ مرافقون معلقون",
    "expired":            "❌ منتهية",
    "inactive":           "🔒 غير نشطة",
}

RESIDENCY_STATUS_ICONS: dict[str, str] = {
    "active":             "✅",
    "expiring":           "⚠️",
    "renewal_submitted":  "📋",
    "issued":             "🪪",
    "dependent_pending":  "⏳",
    "expired":            "❌",
    "inactive":           "🔒",
}

# ── Thresholds ────────────────────────────────────────────────────────────────

EXPIRING_SOON_DAYS = 30       # Show in المتابعة if expiry within N days
PROFILES_PAGE_SIZE = 8        # Profiles per page in archive list
HISTORY_DISPLAY_LIMIT = 5     # Timeline entries shown in profile detail view
