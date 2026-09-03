# services/chennai_daily_returns.py
#
# 🏥 نشر عودات مرضى تشناي ليوم غد في مجموعة تشناي — يومياً ٢١:٠٠.
#
# ⚠️ **يختلف عن `notification_service.send_daily_appointments_reminder`**
# اختلافاً جوهرياً وليس نسخة منه:
#   • ذاك يُرسل **خاصّاً لكل أدمن** ويشمل **كل** المرضى.
#   • هذا يُنشر في **مجموعة تشناي** ويشمل **مرضى تشناي وحدهم**.
# فالجمهور والنطاق مختلفان، ودمجهما كان سيُسرِّب مرضى غير تشناي إلى
# مجموعتها. ما يشتركان فيه — حقول تواريخ العودة الأربعة — مُعرَّف هنا
# صراحةً في `_RETURN_FIELDS` ليبقى مقروءاً عند أي تغيير.

from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# حدّ رسالة تليجرام ٤٠٩٦ حرفاً — تُقسَّم القائمة الطويلة على رسائل.
_PER_MESSAGE = 12

_DIV = "━" * 20
_THIN = "─" * 20

# (اسم الحقل، تسميته للقارئ) — العودات الأربع التي يعرفها النظام.
_RETURN_FIELDS = [
    ("followup_date", "عودة متابعة", "🔁"),
    ("app_reschedule_return_date", "عودة بعد تأجيل", "📆"),
    ("radiation_therapy_return_date", "عودة علاج إشعاعي", "☢️"),
    ("radiology_delivery_date", "استلام نتيجة أشعة", "🩻"),
]

_AR_DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس",
            "الجمعة", "السبت", "الأحد"]


def _tz_now():
    import pytz
    from config.settings import TIMEZONE
    return datetime.now(pytz.timezone(TIMEZONE))


def collect_returns(target_date) -> list[dict]:
    """كل عودات مرضى تشناي في يوم بعينه.

    ⚠️ **التقرير الواحد قد يحمل أكثر من تاريخ عودة** (متابعة + استلام
    أشعة مثلاً). فيُفرَد **صفّاً لكل نوع** لا صفّاً لكل تقرير — وإلا
    ظهر موعد وضاع الآخر بلا أن ينتبه أحد.
    """
    from db.session import SessionLocal
    from db.models import Report, Patient

    start = datetime.combine(target_date, datetime.min.time())
    end = datetime.combine(target_date, datetime.max.time())

    rows: list[dict] = []
    with SessionLocal() as s:
        # أسماء مرضى تشناي — المطابقة بالمعرّف أولاً ثم بالاسم، لأن
        # التقارير القديمة قد تحمل `patient_id = NULL` والاسم وحده.
        chennai = s.query(Patient).filter(Patient.patient_type == "chennai").all()
        chennai_ids = {p.id for p in chennai}
        chennai_names = {(p.full_name or "").strip() for p in chennai if p.full_name}

        if not chennai_ids and not chennai_names:
            logger.info("[chennai.returns] لا يوجد مرضى تشناي مسجَّلون")
            return []

        from sqlalchemy import or_
        conds = [getattr(Report, f).between(start, end) for f, _l, _i in _RETURN_FIELDS]
        candidates = s.query(Report).filter(or_(*conds)).all()

        for r in candidates:
            is_chennai = (r.patient_id in chennai_ids) if r.patient_id else \
                         ((r.patient_name or "").strip() in chennai_names)
            if not is_chennai:
                continue
            for field, label, icon in _RETURN_FIELDS:
                val = getattr(r, field, None)
                if not val or not (start <= val <= end):
                    continue
                rows.append({
                    "patient": (r.patient_name or "—").strip(),
                    "kind": label,
                    "icon": icon,
                    "time": (r.followup_time or "").strip() if field == "followup_date" else "",
                    "department": (r.followup_department or r.department or "").strip(),
                    "doctor": (r.doctor_name or "").strip(),
                    "reason": (r.followup_reason or "").strip(),
                    "translator": (r.translator_name or "").strip(),
                    "report_id": r.id,
                })

    # الترتيب بالوقت أولاً (وما بلا وقت في آخر يومه) ثم بالاسم
    rows.sort(key=lambda x: (x["time"] or "99:99", x["patient"]))
    logger.info(f"[chennai.returns] {len(rows)} عودة ليوم {target_date}")
    return rows


# ⚠️ محارف Markdown في قيمة من البيانات تُفشِل **الرسالة كلها** لا سطرها:
# تليجرام يرفض النصّ بـ`Bad Request: can't parse entities`، فتضيع عودات
# الغد جميعاً بسبب اسمٍ فيه شرطة سفلية. تُنزَع من كل قيمة تأتي من قاعدة
# البيانات — والعناوين الثابتة في الشيفرة تحتفظ بتنسيقها.
_MD_UNSAFE = "*_`[]"


def _safe(text) -> str:
    t = str(text or "")
    for ch in _MD_UNSAFE:
        t = t.replace(ch, "")
    return t


def _day_title(d) -> str:
    return f"{_AR_DAYS[d.weekday()]} {d.isoformat()}"


def build_messages(rows: list[dict], target_date) -> list[str]:
    """رسالة أو أكثر — تُقسَّم القائمة الطويلة احتراماً لحدّ تليجرام."""
    header = [_DIV, "🏥  **عودات مرضى تشناي — غداً**", f"📅 {_day_title(target_date)}", _DIV]

    if not rows:
        # ⚠️ رسالة قصيرة بدل الصمت: الصمت لا يُميَّز عن عطل في المهمة،
        # فيظنّ الفريق أن «لا مواعيد» بينما المهمة لم تعمل أصلاً.
        return ["\n".join(header + ["", "✅ لا توجد عودات مسجَّلة ليوم غد."])]

    chunks = [rows[i:i + _PER_MESSAGE] for i in range(0, len(rows), _PER_MESSAGE)]
    out = []
    n = 0
    for ci, chunk in enumerate(chunks):
        lines = list(header)
        if len(chunks) > 1:
            lines.append(f"الجزء {ci + 1} من {len(chunks)}")
        lines.append("")
        for item in chunk:
            n += 1
            lines.append(f"*{n}.* {_safe(item['patient'])}")
            bits = [f"{item['icon']} {item['kind']}"]
            if item["time"]:
                bits.append(f"🕐 {_safe(item['time'])}")
            lines.append("   " + "  ·  ".join(bits))
            if item["department"]:
                lines.append(f"   🏢 {_safe(item['department'])}")
            if item["doctor"]:
                lines.append(f"   👨‍⚕️ {_safe(item['doctor'])}")
            if item["reason"]:
                lines.append(f"   📝 {_safe(item['reason'])[:120]}")
            lines.append("")
        if ci == len(chunks) - 1:
            lines.append(_THIN)
            lines.append(f"📊 الإجمالي: {len(rows)} عودة")
        out.append("\n".join(lines))
    return out


async def send_chennai_daily_returns(application, target_date=None) -> int:
    """يُنشر في مجموعة تشناي. يُرجِع عدد العودات المنشورة."""
    from telegram.constants import ParseMode
    from config.settings import CHENNAI_REPORTS_GROUP_ID

    gid = CHENNAI_REPORTS_GROUP_ID
    if not gid:
        logger.warning("[chennai.returns] CHENNAI_REPORTS_GROUP_ID غير مضبوط — أُلغي النشر")
        return 0
    try:
        gid = int(gid)
    except (ValueError, TypeError):
        pass

    day = target_date or (_tz_now() + timedelta(days=1)).date()
    rows = collect_returns(day)
    messages = build_messages(rows, day)

    sent = 0
    for msg in messages:
        try:
            await application.bot.send_message(
                chat_id=gid, text=msg, parse_mode=ParseMode.MARKDOWN)
            sent += 1
        except Exception as exc:
            # ⚠️ لا يُوقَف الباقي عند فشل جزء: فقدان جزء أفضل من فقدان الكل.
            logger.error(f"[chennai.returns] فشل إرسال جزء إلى {gid}: {exc}")

    logger.info(f"[chennai.returns] نُشِر {sent}/{len(messages)} رسالة "
                f"({len(rows)} عودة) ليوم {day}")
    return len(rows)
