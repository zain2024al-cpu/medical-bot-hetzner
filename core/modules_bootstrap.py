# core/modules_bootstrap.py
# Pre-registers every platform module with the core routing registry.
#
# Call bootstrap_all() ONCE at application startup, before registering
# any PTB handlers.  After this call, core.conversation.interrupt.register(app)
# will automatically cover all listed button sets.
#
# To add a new module:
#   1. Add a registry.register(...) block here.
#   2. Register its PTB handlers in the normal way.
#   Nothing else needs to change in the core.

import logging
from core.routing.registry import registry

logger = logging.getLogger(__name__)


def bootstrap_all() -> None:
    """Register all platform modules. Idempotent — safe to call more than once."""

    # ── Translators: medical report management ────────────────────────────────
    # This is the current production module.  Button strings must match exactly
    # what bot/keyboards.py returns from user_main_kb().
    registry.register(
        name="user_reports",
        menu_buttons={
            "📝 إضافة تقرير جديد",
            "✏️ تعديل التقارير",
            "🗑️ حذف التقارير",
            "📅 جدول اليوم",
            "🚀 ابدأ",
            "📋 ملخص الحالة",
            "📎 المرفقات الطبية",
        },
        keyboard_rows=[
            ["📝 إضافة تقرير جديد"],
            ["✏️ تعديل التقارير", "🗑️ حذف التقارير"],
            ["📅 جدول اليوم", "🚀 ابدأ"],
            ["📋 ملخص الحالة", "📎 المرفقات الطبية"],
        ],
        extra_wipe_keys={
            # Legacy report-flow keys (kept in sync with flow_interrupt._WIPE_KEYS)
            "report_tmp",
            "_nav_stack",
            "_conversation_state",
            "last_valid_state",
            "patient_page",
            "user_patient_page",
            "hospitals_page",
            "departments_page",
            "doctor_page",
            "edit_report_id",
            "delete_reports",
            "cs_patients",
            "cs_patient_id",
            "cs_page",
            "cs_patient_name",
            "ma_state",
            "print_type",
            "analysis_type",
            "edit_hospital_id",
            "patient_name_edit",
            "waiting_for_patients",
            "_current_search_type",
        },
    )

    # ── Healthcare: wound care and clinical tracking ──────────────────────────
    # The "▶️ ابدأ الآن" button is ONLY included in a user's reply keyboard
    # when the user has been explicitly granted the "healthcare" module via
    # core.access.access_service.grant_module().  dynamic_user_kb() enforces
    # this — the button never appears for translators or public users.
    registry.register(
        name="healthcare",
        menu_buttons={"▶️ ابدأ الآن"},
        keyboard_rows=[
            ["▶️ ابدأ الآن"],
        ],
        extra_wipe_keys={
            "_wc_add",      # woundcare session
            "_hcfu_add",    # medical follow-up session
            "_hcmed_add",   # medications session
            "_hcsup_add",   # supplies session
            "_hcoth_add",   # other healthcare session
        },
    )

    # ── General Services: arrivals, departures, public services ──────────────
    registry.register(
        name="general_services",
        menu_buttons={"🔧 الخدمات العامة"},
        keyboard_rows=[
            ["🔧 الخدمات العامة"],
        ],
        extra_wipe_keys={
            "_gsarr_add",   # arrivals session
            "_gsdep_add",   # departures session
            "_gspub_add",   # public services session
        },
    )

    # ── Residency: lifecycle management ──────────────────────────────────────
    registry.register(
        name="residency",
        menu_buttons={"🪪 الإقامة"},
        keyboard_rows=[["🪪 الإقامة"]],
        extra_wipe_keys={
            "_res_add",    # add-new-patient session
            "_res_ren",    # renewal session
            "_res_search_active",
            "_res_archive_page",
        },
    )

    # ── Future modules — uncomment and fill in when ready ────────────────────
    # registry.register(
    #     name="pharmacy",
    #     menu_buttons={"💊 الصيدلية"},
    #     keyboard_rows=[["💊 الصيدلية"]],
    # )
    # registry.register(
    #     name="services",
    #     menu_buttons={"🛠️ الخدمات"},
    #     keyboard_rows=[["🛠️ الخدمات"]],
    # )

    logger.info(
        f"[bootstrap] registered modules: {registry.all_modules()}"
        f"  total buttons: {len(registry.all_menu_buttons())}"
    )
