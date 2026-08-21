# modules/general_services/staff.py
# قائمة مختصي الخدمات — **مشتقّة من الصلاحيات، لا مكتوبة يدوياً**.
#
# ⚠️ ما كان قبل هذا الملف:
# `STAFF_MAP` في constants.py كانت قاموساً ثابتاً باسمين مكتوبين في الكود
# ("رضاء"، "علي صالح"). أي موظف جديد يستلزم تعديل الكود ونشراً جديداً، وأي
# موظف يغادر يبقى اسمه ظاهراً حتى يُحذَف يدوياً.
#
# الآلية الآن (بطلب المستخدم صراحةً): المستخدم يقدّم طلباً للبوت → يوافق
# عليه الأدمن ويكتب له اسماً → يفتح له صلاحية "🔧 الخدمات العامة" من إدارة
# الوصول ⇒ **يظهر اسمه تلقائياً** في شاشات اختيار المختص. وسحب الصلاحية
# يُخفيه تلقائياً. بلا أي تعديل على الكود في الحالتين.
#
# 🔒 لماذا لا يُدرَج الأدمن تلقائياً: `is_admin` يمنح **وصولاً** لكل الوحدات،
# لكن كون الشخص أدمناً لا يعني أنه مختص خدمات يُنسَب إليه العمل. القائمة
# تقتصر على من مُنح الوحدة صراحةً — وهو بالضبط معنى "فتح الصلاحيات له".
#
# ✅ السجلات القديمة لا تتأثر: `specialist_label` مُخزَّن مع كل صف
# (ArrivalPatient/DepartureRecord/PublicService)، فأسماء من غادر تبقى
# ظاهرة في سجلّاته التاريخية حتى بعد اختفائه من قائمة الاختيار.

import logging

logger = logging.getLogger(__name__)

# مفتاح وحدة الصلاحيات (نفس الاسم المسجَّل في core/modules_bootstrap.py)
GS_MODULE_KEY = "general_services"

# بادئة معرّف الزر: sp_<tg_user_id>
STAFF_ID_PREFIX = "sp_"


def get_staff_map() -> dict[str, str]:
    """{معرّف الزر: الاسم المعروض} لكل من مُنح وحدة الخدمات العامة.

    مرتَّبة أبجدياً بالاسم ليثبت ترتيب الأزرار بين الشاشات.
    تعيد قاموساً فارغاً عند أي خطأ (يعرض المستدعي رسالة واضحة بدل الانهيار).
    """
    try:
        from core.access.access_service import list_users_with_module
        from services.translators_service import get_all_translators

        allowed = set(list_users_with_module(GS_MODULE_KEY))
        if not allowed:
            return {}

        out: dict[str, str] = {}
        for t in (get_all_translators() or []):
            tg_id = t.get("id")
            name = (t.get("name") or "").strip()
            if tg_id in allowed and name:
                out[f"{STAFF_ID_PREFIX}{tg_id}"] = name

        return dict(sorted(out.items(), key=lambda kv: kv[1]))
    except Exception as exc:
        logger.error(f"[gs.staff] تعذّر بناء قائمة المختصين: {exc}", exc_info=True)
        return {}


def staff_label(staff_id: str) -> str:
    """اسم المختص من معرّف الزر — "" إن لم يعد يملك الصلاحية."""
    return get_staff_map().get(staff_id, "")
