# services/treatment_plan_service.py
"""
محرك عام لخطط العلاج بالجلسات/الدورات (Treatment Plans).

يخدم كل أنواع العلاج الحالية (العلاج الإشعاعي، الكيماوي، الموجه، المناعي،
غسيل الكلى) وأي نوع مستقبلي (مثل العلاج البيولوجي) بلا أي تعديل على هذا
الملف أو على قاعدة البيانات — فقط قيمة treatment_key جديدة.

الأنماط الثلاثة المدعومة (TreatmentPlan.mode):
  - "sessions":       عدّاد جلسات بسيط (current_session من total_sessions).
  - "cycles_uniform":  دورات بنفس عدد الجلسات لكل دورة (sessions_per_cycle).
  - "cycles_custom":   دورات بعدد جلسات مختلف لكل دورة (custom_cycle_sessions).

كل تعديل على خطة نشطة يُسجَّل في TreatmentPlanChangeLog (الخطة السابقة/
الجديدة/الوقت/المستخدم/السبب) قبل تطبيقه — سجل تدقيق كامل لا يُحذف.
"""

import json
import logging
from datetime import datetime

from db.session import SessionLocal
from db.models import TreatmentPlan, TreatmentPlanChangeLog

logger = logging.getLogger(__name__)


def _plan_to_dict(plan: TreatmentPlan) -> dict:
    """لقطة JSON-قابلة لكامل حالة الخطة — تُستخدَم في سجل التدقيق واللقطة
    الثابتة المحفوظة على كل تقرير."""
    return {
        "treatment_key": plan.treatment_key,
        "mode": plan.mode,
        "total_sessions": plan.total_sessions,
        "current_session": plan.current_session,
        "total_cycles": plan.total_cycles,
        "current_cycle": plan.current_cycle,
        "sessions_per_cycle": plan.sessions_per_cycle,
        "custom_cycle_sessions": plan.custom_cycle_sessions,
        "status": plan.status,
    }


def get_active_plan(patient_id: int, treatment_key: str) -> dict | None:
    """يجلب الخطة النشطة الحالية لمريض ضمن نوع علاج معيّن، أو None إن لم توجد."""
    if not patient_id:
        return None
    try:
        with SessionLocal() as s:
            plan = (
                s.query(TreatmentPlan)
                .filter_by(patient_id=patient_id, treatment_key=treatment_key, status="active")
                .order_by(TreatmentPlan.id.desc())
                .first()
            )
            if not plan:
                return None
            d = _plan_to_dict(plan)
            d["id"] = plan.id
            return d
    except Exception as exc:
        logger.error(f"[treatment_plan] get_active_plan failed: {exc}", exc_info=True)
        return None


def create_plan(
    patient_id: int, treatment_key: str, mode: str,
    total_sessions=None, total_cycles=None, sessions_per_cycle=None,
    custom_cycle_sessions=None, created_by=None, created_by_name=None,
) -> dict:
    """ينشئ خطة جديدة، تبدأ مباشرة من الجلسة/الدورة رقم 1 (هذا التقرير
    الحالي يمثّل أول جلسة في الخطة)."""
    with SessionLocal() as s:
        plan = TreatmentPlan(
            patient_id=patient_id,
            treatment_key=treatment_key,
            mode=mode,
            total_sessions=total_sessions,
            current_session=1,
            total_cycles=total_cycles,
            current_cycle=(1 if mode != "sessions" else None),
            sessions_per_cycle=sessions_per_cycle,
            custom_cycle_sessions=(
                json.dumps(custom_cycle_sessions, ensure_ascii=False) if custom_cycle_sessions else None
            ),
            status="active",
            created_by=created_by,
            created_by_name=created_by_name,
        )
        s.add(plan)
        s.commit()
        d = _plan_to_dict(plan)
        d["id"] = plan.id
        return d


def _cap_for_cycle(plan: TreatmentPlan, cycle_number: int) -> int:
    """سقف عدد الجلسات لدورة معيّنة (uniform أو custom)."""
    if plan.mode == "cycles_uniform":
        return plan.sessions_per_cycle or 1
    if plan.mode == "cycles_custom":
        try:
            lst = json.loads(plan.custom_cycle_sessions or "[]")
            idx = cycle_number - 1
            if 0 <= idx < len(lst):
                return int(lst[idx])
        except Exception:
            pass
    return 1


def advance_plan(plan_id: int) -> dict:
    """يُقدِّم الخطة خطوة واحدة (جلسة جديدة) لتقرير جديد قيد الإنشاء الآن،
    ويحفظ الوضع الجديد. لا يُوقَف عند تجاوز العدد الكلي — يستمر بالعدّ
    ببساطة (يمكن تعديل الخطة لاحقاً في أي وقت عبر edit_plan)."""
    with SessionLocal() as s:
        plan = s.get(TreatmentPlan, plan_id)
        if not plan:
            return {}

        if plan.mode == "sessions":
            plan.current_session = (plan.current_session or 0) + 1
        else:
            cur_session = (plan.current_session or 0) + 1
            cap = _cap_for_cycle(plan, plan.current_cycle or 1)
            if cur_session > cap:
                # الدورة الحالية اكتملت — الانتقال للدورة التالية، الجلسة 1
                plan.current_cycle = (plan.current_cycle or 1) + 1
                plan.current_session = 1
            else:
                plan.current_session = cur_session

        plan.updated_at = datetime.utcnow()
        s.commit()
        d = _plan_to_dict(plan)
        d["id"] = plan.id
        return d


def edit_plan(
    plan_id: int, changes: dict, changed_by=None, changed_by_name=None, reason: str = None,
) -> dict:
    """يعدّل خطة نشطة — يسجّل الحالة قبل وبعد في TreatmentPlanChangeLog
    أولاً، ثم يطبّق التعديل. changes: أي من حقول TreatmentPlan المسموح
    تعديلها (total_sessions/total_cycles/sessions_per_cycle/
    custom_cycle_sessions/current_session/current_cycle).

    ✅ current_session/current_cycle: تصحيح يدوي مباشر لرقم الجلسة/الدورة
    الحالية (بخلاف advance_plan الذي يزيدها +1 تلقائياً فقط) — لمرضى بدأوا
    الجلسات فعلياً قبل إنشاء الخطة في هذا النظام، فيحتاج المترجم مطابقة
    العدّاد مع الرقم الحقيقي دفعة واحدة."""
    with SessionLocal() as s:
        plan = s.get(TreatmentPlan, plan_id)
        if not plan:
            return {}

        previous_snapshot = json.dumps(_plan_to_dict(plan), ensure_ascii=False)

        if "total_sessions" in changes:
            plan.total_sessions = changes["total_sessions"]
        if "total_cycles" in changes:
            plan.total_cycles = changes["total_cycles"]
        if "sessions_per_cycle" in changes:
            plan.sessions_per_cycle = changes["sessions_per_cycle"]
        if "custom_cycle_sessions" in changes:
            plan.custom_cycle_sessions = json.dumps(changes["custom_cycle_sessions"], ensure_ascii=False)
        if "current_session" in changes:
            plan.current_session = changes["current_session"]
        if "current_cycle" in changes:
            plan.current_cycle = changes["current_cycle"]

        plan.updated_at = datetime.utcnow()
        new_snapshot = json.dumps(_plan_to_dict(plan), ensure_ascii=False)

        log = TreatmentPlanChangeLog(
            plan_id=plan.id,
            previous_snapshot=previous_snapshot,
            new_snapshot=new_snapshot,
            changed_by=changed_by,
            changed_by_name=changed_by_name,
            reason=(reason or None),
        )
        s.add(log)
        s.commit()

        d = _plan_to_dict(plan)
        d["id"] = plan.id
        return d


def format_progress_text(plan: dict) -> str:
    """نص عربي جاهز للعرض في الشاشة وفي التقرير — يُستخدَم أيضاً كلقطة
    ثابتة تُحفظ في Report.treatment_plan_summary."""
    if not plan:
        return ""
    if plan["mode"] == "sessions":
        total = plan.get("total_sessions")
        cur = plan.get("current_session")
        return f"📋 **الخطة العلاجية:** {total} جلسة\n📍 **الجلسة الحالية:** {cur} من {total}"
    # cycles_uniform / cycles_custom
    total_cycles = plan.get("total_cycles")
    cur_cycle = plan.get("current_cycle")
    if plan["mode"] == "cycles_uniform":
        cap = plan.get("sessions_per_cycle")
    else:
        try:
            lst = json.loads(plan.get("custom_cycle_sessions") or "[]")
            idx = (cur_cycle or 1) - 1
            cap = lst[idx] if 0 <= idx < len(lst) else "?"
        except Exception:
            cap = "?"
    cur_session = plan.get("current_session")
    return (
        f"📋 **الدورة الحالية:** {cur_cycle} من {total_cycles}\n"
        f"📍 **الجلسة الحالية:** {cur_session} من {cap}"
    )
