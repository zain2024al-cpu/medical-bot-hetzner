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
            "📎 المرفقات الطبية",
        },
        keyboard_rows=[
            ["📝 إضافة تقرير جديد"],
            ["🗑️ حذف التقارير", "📎 المرفقات الطبية"],
            ["✏️ تعديل التقارير", "📅 جدول اليوم"],
            ["🚀 ابدأ"],
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
    #
    # ✅ نفس النص "▶️ ابدأ الآن" مُستخدَم أيضاً في general_services وresidency
    # أدناه — الزر الثلاثة يتصرّف بنفس السلوك تماماً (إعادة تشغيل كاملة عبر
    # user_start، مثل "🚀 ابدأ" في بوت المترجمين)، ومُسجَّل مرة واحدة فقط
    # في bot/handlers/user/user_start.py::register() — لا معالِج مخصَّص هنا
    # بعد الآن (كان `modules/healthcare/menu.py::_show_menu` يفتح قائمة
    # الرعاية الصحية مباشرة بدل التشغيل الكامل؛ حُذف بطلب المستخدم صراحةً
    # ليتطابق السلوك).
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

    # ── Chennai healthcare: مرضى مدينة تشناي ─────────────────────────────────
    # قسم منفصل — نفس تدفقات الرعاية الصحية حرفياً (المجارحة/المتابعة
    # الطبية/صرف الأدوية/المستلزمات/إجراءات أخرى)، لكن:
    #   • قائمة المرضى: مرضى تشناي حصراً (patient_type="chennai").
    #   • النشر: مجموعة تشناي (CHENNAI_REPORTS_GROUP_ID) بدل مجموعة
    #     الرعاية الصحية الاعتيادية — يُشتق من نوع المريض نفسه (انظر
    #     modules/healthcare/report_publisher.py) فيبقى صحيحاً حتى لو
    #     اختير مريض تشناي من قسم الرعاية الصحية الاعتيادية (يظهر فيها
    #     أيضاً — نفس مبدأ تقارير تشناي).
    # يُمنح من "إدارة الوصول" منفصلاً عن "healthcare" — يمكن لمستخدم أن
    # يملك القسمين معاً أو أحدهما فقط.
    registry.register(
        name="chennai_healthcare",
        menu_buttons={"🏙️ الرعاية الصحية - تشناي"},
        keyboard_rows=[
            ["🏙️ الرعاية الصحية - تشناي"],
        ],
        extra_wipe_keys={
            "hc_city",
            "_force_hc_city",
        },
    )

    # ── Chennai reports: مرضى مدينة تشناي ────────────────────────────────────
    # قسم منفصل داخل بوت المترجمين — نفس تدفق التقارير حرفياً (نفس
    # المستشفيات/الأقسام/أنواع الإجراءات)، لكن:
    #   • قائمة المرضى: مرضى تشناي حصراً (patient_type="chennai").
    #   • النشر: مجموعة تشناي (CHENNAI_REPORTS_GROUP_ID) للتقرير والمرفقات.
    # يُمنح من "إدارة الوصول" كبقية الوحدات، ويمكن لمترجم أن يملك هذا
    # القسم والقسم الاعتيادي معاً.
    # ✅ لوحة تحكم كاملة كالمترجم الاعتيادي — الفارق الوحيد أن زر إضافة
    # التقرير هو زر تشناي. بقية الأزرار (تعديل/حذف/المرفقات/جدول اليوم)
    # تعمل على تقارير المستخدم نفسه، فهي صحيحة تلقائياً لمترجم تشناي.
    # (إزالة التكرار في dynamic_user_kb تمنع ازدواج الصفوف لمن يملك
    #  القسمين معاً.)
    registry.register(
        name="chennai_reports",
        menu_buttons={
            "🏙️ إضافة تقرير جديد - تشناي",
            "✏️ تعديل التقارير",
            "🗑️ حذف التقارير",
            "📅 جدول اليوم",
            "🚀 ابدأ",
            "📎 المرفقات الطبية",
        },
        keyboard_rows=[
            ["🏙️ إضافة تقرير جديد - تشناي"],
            ["🗑️ حذف التقارير", "📎 المرفقات الطبية"],
            ["✏️ تعديل التقارير", "📅 جدول اليوم"],
            ["🚀 ابدأ"],
        ],
        extra_wipe_keys={
            "report_city",
            "_force_report_city",
        },
    )

    # ── General Services: arrivals, departures, public services ──────────────
    # ✅ "▶️ ابدأ الآن" — نفس زر إعادة التشغيل الكامل (رسالة ترحيب + إعادة بناء
    # لوحة المفاتيح عبر user_start) المستخدَم أصلاً في الرعاية الصحية، بطلب
    # المستخدم صراحةً ليتوفّر أيضاً هنا وفي الإقامات.
    registry.register(
        name="general_services",
        menu_buttons={"🔧 الخدمات العامة", "▶️ ابدأ الآن"},
        keyboard_rows=[
            ["🔧 الخدمات العامة"],
            ["▶️ ابدأ الآن"],
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
        menu_buttons={"🪪 الإقامة", "▶️ ابدأ الآن"},
        keyboard_rows=[
            ["🪪 الإقامة"],
            ["▶️ ابدأ الآن"],
        ],
        extra_wipe_keys={
            "_res_add",    # add-new-patient session
            "_res_ren",    # renewal session
            "_res_search_active",
            "_res_archive_page",
        },
    )

    # ── Pharmacy financial report (💰) ─────────────────────────────────────────
    # Granted by admins to a designated "pharmacist" user via the existing
    # "🔑 إدارة الصلاحيات" screen — admin sees this button regardless (hardcoded
    # in admin_main_kb()), the grant only controls non-admin visibility here.
    registry.register(
        name="pharmacy_finance",
        menu_buttons={"💰 التقرير المالي"},
        keyboard_rows=[["💰 التقرير المالي"]],
        extra_wipe_keys={"_hcphfin_add"},
    )

    # ── Pharmacy evacuation ledger print (🖨️) ──────────────────────────────────
    # Deliberately a SEPARATE module_key from pharmacy_finance — an admin may
    # want to grant one without the other.
    registry.register(
        name="pharmacy_print",
        menu_buttons={"🖨️ طباعة مسير الإخلاء"},
        keyboard_rows=[["🖨️ طباعة مسير الإخلاء"]],
        extra_wipe_keys={"_hcphprint_ledger"},
    )

    # ── Future modules — uncomment and fill in when ready ────────────────────
    # registry.register(
    #     name="services",
    #     menu_buttons={"🛠️ الخدمات"},
    #     keyboard_rows=[["🛠️ الخدمات"]],
    # )

    logger.info(
        f"[bootstrap] registered modules: {registry.all_modules()}"
        f"  total buttons: {len(registry.all_menu_buttons())}"
    )
