# ================================================
# bot/handlers/admin/admin_legacy_onboarding.py
# 🏠 الحالات الموجودة — إدخال المرضى القدامى لبوتَي الخدمات والإقامة
# ================================================
#
# ⚠️ لماذا هذه الشاشة موجودة أصلاً:
# وحدتا "🪪 الإقامة" و"🔧 الخدمات العامة" فُعِّلتا للمرضى الجدد الذين يمرّون
# بتدفق "🛬 الوصول"، وهو **نقطة الإنشاء الوحيدة** لأشخاص الإقامة حتى الآن
# (`modules/residency/models.py::create_profiles_from_arrival`). أما المرضى
# الموجودون هنا **قبل** تفعيل الوحدتين فلم يمرّوا بذلك التدفق إطلاقاً، فلا
# وجود لهم في أيٍّ منهما. هذه الشاشة هي المسار اليدوي الثاني لإدخالهم —
# مهمة مؤقتة تنتهي بانتهاء إدخال القدامى.
#
# ── ما الذي يُنشَأ عند الحفظ (ثلاثة أنظمة منفصلة لا رابط بينها) ─────────────
#   1) `ArrivalPatient` (+ `ArrivalCompanion`) بحالة "active"
#      → ليظهر في "🛫 المغادرين" (يقرأ جدول الوصول لا سجلّ المرضى).
#      ⚠️ **لا** يجعله يظهر في زر "🛬 الوصول" — ذاك يعرض الأسماء المعلّقة
#      من سجلّ المرضى (`pending_arrival`)، وهؤلاء ليسوا منها.
#   2) `Patient.gs_onboarded_at` على المريض الجذر + صفوف `Patient` جديدة
#      للمرافقين (نوع "companion")
#      → ليظهروا في "🔧 الخدمات العامة" (يستخدم only_companion_flow).
#      ⚠️ **لا يُغيَّر** `patient_type` للمريض الجذر إطلاقاً: تغييره كان
#      سيكسر تصنيفاً حقيقياً (مريض "chennai" يختفي من قسم تشناي، و
#      "pharmacy_only" يخرج من قصره على الصيدلية). انظر شرح العلَم في
#      `db/models.py` و`_type_visible`.
#   3) `ResidencyPerson` (جذر + مرافقون) بحالة `LEGACY_PENDING`
#      → ليظهر في زر "🏠 معلّقات من الحالات السابقة" داخل وحدة الإقامة،
#      حيث تُدخَل بيانات الإقامة نفسها لاحقاً (المرحلة الثانية).
#
# ── الفورمة (بطلب المستخدم حرفياً، بلا حقول إضافية) ────────────────────────
#   تأشيرة (تقويم، بلا تخطٍّ) → جواز (تقويم، بلا تخطٍّ) → صورة الجواز →
#   صورة التأشيرة مع ختم الدخول → صورة الإقامة (اختيارية) → السكن ورقم
#   الشقة → مرافقون؟ كم؟ → لكل مرافق: الاسم + نفس الفورمة → مراجعة → حفظ.

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CallbackQueryHandler, MessageHandler, filters,
)
from telegram.constants import ParseMode

from shared.calendar_picker import build_calendar, build_year_picker, build_month_picker

logger = logging.getLogger(__name__)

LEGO = "lego"                 # بادئة الكولباك
_SESSION_KEY = "_lego"
# ✅ حالة البحث السريع — منفصلة عن جلسة الفورمة لأن البحث يقع **قبل**
# اختيار المريض (لا توجد جلسة بعد).
_SEARCH_WAIT_KEY = "_lego_search_wait"   # بانتظار كتابة الأدمن للاسم
_SEARCH_Q_KEY    = "_lego_search_q"      # الاستعلام النشط (للتصفّح)
_PER_PAGE = 8

# ── الخطوات ───────────────────────────────────────────────────────────────────
S_VISA_EXPIRY      = "visa_expiry"
S_PASSPORT_EXPIRY  = "passport_expiry"
S_PASSPORT_FILE    = "passport_file"
S_VISA_FILE        = "visa_file"
S_HOUSING          = "housing"
S_HAS_COMPANION    = "has_companion"
S_COMPANION_COUNT  = "companion_count"
S_C_NAME           = "c_name"
S_REVIEW           = "review"

# خطوات المرافق مطابقة لخطوات المريض (نفس الفورمة) — يميّزها علم `in_companion`
# ⚠️ لا خطوة "صورة الإقامة" هنا (بطلب المستخدم): الإقامة تُوثَّق من بوت
# الإقامات عبر "🏠 معلّقات من الحالات السابقة" — فرفعها مرتين تكرار.
_PERSON_STEPS = [
    S_VISA_EXPIRY, S_PASSPORT_EXPIRY, S_PASSPORT_FILE, S_VISA_FILE,
]

_STEP_TITLES = {
    S_VISA_EXPIRY:     "📋 تاريخ انتهاء التأشيرة",
    S_PASSPORT_EXPIRY: "🛂 تاريخ انتهاء الجواز",
    S_PASSPORT_FILE:   "🛂 صورة الجواز",
    S_VISA_FILE:       "📋 صورة التأشيرة مع ختم الدخول",
    S_HOUSING:         "🏠 السكن ورقم الشقة",
}


# ── الإدخال اليدوي للتواريخ ───────────────────────────────────────────────────
# التقويم يخزّن دائماً بصيغة `%d/%m/%Y`. الكتابة اليدوية **تُطبَّع إلى نفس
# الصيغة حرفياً** قبل الحفظ، فلا يرى بقية النظام أي فرق بين المصدرين — وهذا
# شرط ألّا يتأثّر شيء آخر في البوت.
_DATE_FMT = "%d/%m/%Y"

# تلميح يُعرَض تحت التقويم — بدونه لا يعرف الأدمن أن الكتابة متاحة أصلاً
_MANUAL_HINT = (
    "\n\n✍️ _أو اكتب التاريخ يدوياً:_ `يوم/شهر/سنة`\n"
    "_مثال:_ `25/12/2027`"
)

# الأرقام العربية والفارسية ⇐ لاتينية (لوحة المفاتيح العربية تُخرِجها كثيراً)
_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def _parse_manual_date(text: str) -> str | None:
    """نصّ المستخدم ⇒ تاريخ بصيغة التقويم نفسها، أو None إن كان غير صالح.

    متسامح في المُدخَل (فواصل مختلفة، أرقام عربية، خانة واحدة) وصارم في
    المُخرَج. يرفض المستحيل فعلاً (31/02) لأن `datetime` هو المُتحقِّق.
    """
    raw = (text or "").strip().translate(_DIGIT_MAP)
    for sep in ("-", ".", "\\", " "):
        raw = raw.replace(sep, "/")
    parts = [p for p in raw.split("/") if p]
    if len(parts) != 3:
        return None
    try:
        d, m, y = (int(p) for p in parts)
        if not (1900 <= y <= 2100):     # يمنع سنة من خانتين أو خطأ طباعي فادح
            return None
        return datetime(y, m, d).strftime(_DATE_FMT)
    except (ValueError, TypeError):
        return None                     # يشمل 31/02 و32/13 وأي حرف غير رقمي


def _blank_person(name: str = "") -> dict:
    return {
        "name": name,
        "visa_expiry": "",
        "passport_expiry": "",
        "passport_file_id": "",
        "visa_file_id": "",
    }


@dataclass
class LegoSession:
    step: str
    patient_id: int
    patient_name: str
    person: dict                    # المريض الجذر
    companions: list                # مرافقون مكتملون
    current_companion: dict         # المرافق الجاري إدخاله
    companion_total: int
    in_companion: bool
    housing: str = ""

    def save(self, ud: dict) -> None:
        ud[_SESSION_KEY] = {
            "step": self.step, "patient_id": self.patient_id,
            "patient_name": self.patient_name, "person": self.person,
            "companions": self.companions, "current_companion": self.current_companion,
            "companion_total": self.companion_total, "in_companion": self.in_companion,
            "housing": self.housing,
        }

    @classmethod
    def load(cls, ud: dict) -> "LegoSession | None":
        raw = ud.get(_SESSION_KEY)
        if not raw:
            return None
        return cls(
            step=raw.get("step", S_VISA_EXPIRY),
            patient_id=raw.get("patient_id", 0),
            patient_name=raw.get("patient_name", ""),
            person=raw.get("person") or _blank_person(),
            companions=raw.get("companions") or [],
            current_companion=raw.get("current_companion") or {},
            companion_total=raw.get("companion_total", 0),
            in_companion=raw.get("in_companion", False),
            housing=raw.get("housing", ""),
        )

    @classmethod
    def clear(cls, ud: dict) -> None:
        ud.pop(_SESSION_KEY, None)

    @property
    def active(self) -> dict:
        """الشخص الجاري إدخاله: المرافق إن كنا داخل مرافق، وإلا المريض."""
        return self.current_companion if self.in_companion else self.person


# ── طبقة البيانات ─────────────────────────────────────────────────────────────

def _fetch_candidates(page: int, query: str = "") -> tuple[list, int, int]:
    """المرضى المؤهَّلون للإدخال: نشطون، غير مؤرشفين (لم يسافروا)، ولم
    يُدخَلوا مسبقاً، وليسوا مرافقين.

    query — بحث جزئي بالاسم (غير حسّاس لحالة الأحرف). فارغ = كل المؤهَّلين.
    ⚠️ الفلاتر نفسها تُطبَّق على البحث حرفياً — فلا يعرض البحث اسماً
    مؤرشفاً أو مُدخَلاً مسبقاً (وهذا سبب عدم استخدام بحث تيليجرام المدمج
    المشترك هنا: معالِجه يطبّق قواعد تدفق التقارير لا قواعد هذه الشاشة).
    """
    from db.session import SessionLocal
    from db.models import Patient
    from sqlalchemy import or_

    with SessionLocal() as s:
        q = s.query(Patient).filter(
            Patient.full_name.isnot(None), Patient.full_name != "",
            Patient.archived_at.is_(None),        # لم يسافر (أرشيف المسافرين)
            Patient.gs_onboarded_at.is_(None),    # لم يُدخَل مسبقاً
            or_(Patient.patient_type != "companion", Patient.patient_type.is_(None)),
        )
        if query:
            q = q.filter(Patient.full_name.ilike(f"%{query}%"))
        total = q.count()
        pages = (total + _PER_PAGE - 1) // _PER_PAGE
        rows = (
            q.order_by(Patient.full_name.asc())
            .offset(page * _PER_PAGE).limit(_PER_PAGE).all()
        )
        return [{"id": p.id, "name": p.full_name} for p in rows], total, pages


def _onboarded_count() -> int:
    from db.session import SessionLocal
    from db.models import Patient
    with SessionLocal() as s:
        return s.query(Patient).filter(Patient.gs_onboarded_at.isnot(None)).count()


def _already_onboarded(patient_id: int) -> bool:
    """حارس ضد الإدخال المزدوج (ضغطتان متتاليتان/جلستان متوازيتان)."""
    from db.session import SessionLocal
    from db.models import Patient
    with SessionLocal() as s:
        p = s.query(Patient).filter_by(id=patient_id).first()
        return bool(p and p.gs_onboarded_at)


def _persist(session: LegoSession, admin_id: int | None) -> tuple[bool, str]:
    """يكتب الأنظمة الثلاثة في معاملة واحدة. يعيد (نجاح, رسالة)."""
    from db.session import SessionLocal
    from db.models import (
        Patient, ArrivalPatient, ArrivalCompanion, ResidencyPerson, ResidencyStatusLog,
    )
    from modules.residency.constants import STATUS_LEGACY_PENDING

    now = datetime.utcnow()
    p = session.person
    try:
        with SessionLocal() as s:
            root = s.query(Patient).filter_by(id=session.patient_id).first()
            if root is None:
                return False, "لم يُعثر على المريض في السجلّ."
            if root.gs_onboarded_at:
                return False, "هذا المريض مُدخَل مسبقاً."

            # (1) جدول الوصول — ليظهر في "🛫 المغادرين"
            ap = ArrivalPatient(
                name=session.patient_name,
                visa_expiry=p["visa_expiry"], passport_expiry=p["passport_expiry"],
                passport_file_id=p["passport_file_id"], visa_file_id=p["visa_file_id"],
                residence_address=session.housing,
                has_companion=bool(session.companions),
                arrival_status="active",
                notes="أُدخِل يدوياً عبر 🏠 الحالات الموجودة (مريض قديم، لم يمرّ بتدفق الوصول)",
            )
            s.add(ap)
            s.flush()

            # (3) وحدة الإقامة — الجذر
            rp = ResidencyPerson(
                name=session.patient_name,
                status=STATUS_LEGACY_PENDING,
                created_by=admin_id,
            )
            s.add(rp)
            s.flush()
            s.add(ResidencyStatusLog(
                person_id=rp.id, old_status="", new_status=STATUS_LEGACY_PENDING,
                performed_by=admin_id,
            ))

            for c in session.companions:
                s.add(ArrivalCompanion(
                    patient_id=ap.id, name=c["name"],
                    visa_expiry=c["visa_expiry"], passport_expiry=c["passport_expiry"],
                    passport_file_id=c["passport_file_id"], visa_file_id=c["visa_file_id"],
                ))
                # (2) صف مريض جديد للمرافق — ليظهر في الخدمات العامة
                s.add(Patient(
                    full_name=c["name"], patient_type="companion",
                    companion_of_id=root.id, gs_onboarded_at=now,
                ))
                comp = ResidencyPerson(
                    name=c["name"], parent_id=rp.id,
                    status=STATUS_LEGACY_PENDING, created_by=admin_id,
                )
                s.add(comp)
                s.flush()
                s.add(ResidencyStatusLog(
                    person_id=comp.id, old_status="", new_status=STATUS_LEGACY_PENDING,
                    performed_by=admin_id,
                ))

            # (2) علَم المريض الجذر — بلا أي مساس بـpatient_type
            root.gs_onboarded_at = now
            s.commit()

        logger.info(
            f"[lego] onboarded patient_id={session.patient_id} "
            f"name={session.patient_name!r} companions={len(session.companions)}"
        )
        return True, ""
    except Exception as exc:
        logger.error(f"[lego] فشل الحفظ: {exc}", exc_info=True)
        return False, str(exc)[:150]


# ── شاشات ─────────────────────────────────────────────────────────────────────

def _cancel_row() -> list:
    return [InlineKeyboardButton("❌ إلغاء", callback_data=f"{LEGO}:cancel")]


async def _show_list(query, page: int, search: str = "") -> None:
    rows, total, pages = _fetch_candidates(page, search)
    done = _onboarded_count()

    kb = []
    if not rows:
        if search:
            text = (
                f"🔍 **نتائج البحث: «{search}»**\n\n"
                "⚠️ لا يوجد اسم مطابق بين المرضى المتبقّين.\n"
                "_(قد يكون أُدخِل مسبقاً، أو مؤرشفاً كمسافر.)_"
            )
        else:
            text = (
                "🏠 **الحالات الموجودة**\n\n"
                "✅ لا توجد أسماء متبقية — تم إدخال جميع المرضى القدامى."
            )
    else:
        head = f"🔍 **نتائج البحث: «{search}»**" if search else "🏠 **الحالات الموجودة**"
        text = (
            f"{head}\n\n"
            f"📊 **المتبقّون:** {total}   •   ✅ **أُدخِلوا:** {done}\n"
            f"📄 **صفحة:** {page + 1} من {pages}\n\n"
            "اختر المريض لإدخال بياناته في بوتَي الخدمات والإقامة:"
        )
        for r in rows:
            kb.append([InlineKeyboardButton(
                f"👤 {r['name']}", callback_data=f"{LEGO}:pick:{r['id']}:{page}"
            )])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"{LEGO}:page:{page-1}"))
    if page < pages - 1:
        nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"{LEGO}:page:{page+1}"))
    if nav:
        kb.append(nav)

    # ✅ البحث السريع — يختصر تصفّح عشرات الصفحات للوصول لاسم واحد
    kb.append([InlineKeyboardButton("🔍 بحث بالاسم", callback_data=f"{LEGO}:search")])
    if search:
        kb.append([InlineKeyboardButton("📋 عرض كل الأسماء", callback_data=f"{LEGO}:all")])
    # ↩️ تصحيح إدخال خاطئ (عدد مرافقين غلط، تواريخ غلط…) بلا فقدان المريض
    kb.append([InlineKeyboardButton(
        "↩️ تصحيح إدخال سابق", callback_data=f"{LEGO}:undo:0")])
    kb.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")])

    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN
    )


async def _show_undo_list(query, page: int = 0) -> None:
    """المُدخَلون سابقاً — لاختيار من يُراد تصحيح إدخاله."""
    from services.patients_service import get_legacy_onboarded_patients

    rows, total, pages = get_legacy_onboarded_patients(page, 8)
    if not rows:
        text = (
            "↩️ **تصحيح إدخال سابق**\n\n"
            "لا يوجد أي مريض مُدخَل عبر «🏠 الحالات الموجودة» بعد."
        )
        kb = [[InlineKeyboardButton("🔙 رجوع", callback_data=f"{LEGO}:all")]]
    else:
        text = (
            "↩️ **تصحيح إدخال سابق**\n\n"
            f"📊 **العدد:** {total}   •   📄 **صفحة:** {page + 1} من {pages}\n\n"
            "اختر المريض الذي تريد **إلغاء إدخاله** لإعادة إدخاله صحيحاً:"
        )
        kb = []
        for r in rows:
            suffix = f" (+{r['companions']} مرافق)" if r["companions"] else ""
            kb.append([InlineKeyboardButton(
                f"👤 {r['name']}{suffix}",
                callback_data=f"{LEGO}:undopick:{r['id']}:{page}",
            )])
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(
                "◀️ السابق", callback_data=f"{LEGO}:undo:{page - 1}"))
        if page < pages - 1:
            nav.append(InlineKeyboardButton(
                "التالي ▶️", callback_data=f"{LEGO}:undo:{page + 1}"))
        if nav:
            kb.append(nav)
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"{LEGO}:all")])

    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN
    )


async def _show_undo_confirm(query, pid: int, page: int) -> None:
    """ما الذي سيُلغى بالضبط — قبل أي تنفيذ."""
    from services.patients_service import get_deletable_family_impact

    impact = get_deletable_family_impact(f"p-{pid}")
    if impact is None:
        await query.answer("⚠️ لم يُعثر على المريض", show_alert=True)
        await _show_undo_list(query, page)
        return

    lines = [
        "↩️ **تأكيد تصحيح الإدخال**",
        "",
        f"👤 **{impact['name']}**",
        "",
        "**سيُلغى:**",
        f"   🤝 المرافقون: {len(impact['companions'])}",
        f"   🪪 أشخاص الإقامة: {impact['residency']}",
        f"   🛬 صفوف الوصول: {impact['arrivals']} (+{impact['arrival_companions']} مرافق)",
    ]
    if impact["companions"]:
        lines.append("")
        lines.append("**المرافقون الذين سيُحذَفون:**")
        lines += [f"   • {c}" for c in impact["companions"]]
    lines += [
        "",
        "✅ **المريض نفسه يبقى** في سجلّ المرضى مع كل تقاريره،",
        "ويعود لقائمة «🏠 الحالات الموجودة» لإدخاله من جديد.",
    ]

    kb = [
        [InlineKeyboardButton("↩️ نعم، ألغِ الإدخال",
                              callback_data=f"{LEGO}:undogo:{pid}:{page}")],
        [InlineKeyboardButton("🔙 إلغاء", callback_data=f"{LEGO}:undo:{page}")],
    ]
    await query.edit_message_text(
        "\n".join(lines), reply_markup=InlineKeyboardMarkup(kb),
        parse_mode=ParseMode.MARKDOWN,
    )


def _who(session: LegoSession) -> str:
    if session.in_companion:
        idx = len(session.companions) + 1
        nm = session.current_companion.get("name") or f"المرافق {idx}"
        return f"🤝 {nm} (مرافق {idx} من {session.companion_total})"
    return f"👤 {session.patient_name}"


async def _render_step(query_or_msg, session: LegoSession, *, edit: bool) -> None:
    """يرسم شاشة الخطوة الحالية. `edit=True` لتعديل رسالة كولباك."""
    step = session.step
    header = f"{_who(session)}\n\n"

    if step in (S_VISA_EXPIRY, S_PASSPORT_EXPIRY):
        today = datetime.now()
        text, kb = build_calendar(
            today.year, today.month, LEGO, f"{LEGO}:cancel", quick_jump=True,
        )
        text = header + f"**{_STEP_TITLES[step]}**\n\n" + text + _MANUAL_HINT
    elif step in (S_PASSPORT_FILE, S_VISA_FILE):
        rows = [_cancel_row()]
        text = header + (
            f"**{_STEP_TITLES[step]}**\n\n"
            "أرسل الصورة أو الملف الآن 📎"
        )
        kb = InlineKeyboardMarkup(rows)
    elif step == S_HOUSING:
        text = header + (
            "**🏠 السكن ورقم الشقة**\n\n"
            "اكتب اسم السكن ورقم الشقة معاً\n"
            "_(مثال: عمارة النور — شقة 12)_"
        )
        kb = InlineKeyboardMarkup([_cancel_row()])
    elif step == S_HAS_COMPANION:
        text = header + "**🤝 هل يوجد مرافقون لهذا المريض؟**"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ نعم", callback_data=f"{LEGO}:comp_yes"),
             InlineKeyboardButton("❌ لا", callback_data=f"{LEGO}:comp_no")],
            _cancel_row(),
        ])
    elif step == S_COMPANION_COUNT:
        text = header + "**🔢 كم عدد المرافقين؟**"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(str(n), callback_data=f"{LEGO}:cnt:{n}") for n in (1, 2, 3)],
            [InlineKeyboardButton(str(n), callback_data=f"{LEGO}:cnt:{n}") for n in (4, 5, 6)],
            _cancel_row(),
        ])
    elif step == S_C_NAME:
        idx = len(session.companions) + 1
        text = (
            f"🤝 **المرافق {idx} من {session.companion_total}**\n\n"
            "اكتب اسم المرافق الكامل:"
        )
        kb = InlineKeyboardMarkup([_cancel_row()])
    else:
        text, kb = _build_review(session)

    if edit:
        await query_or_msg.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else:
        await query_or_msg.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


def _person_summary(p: dict) -> str:
    def mark(v):
        return "✅" if v else "—"
    # ⚠️ `.get` لا فهرسة مباشرة: أي مفتاح ناقص يجب أن يُعرَض "—" لا أن
    # يُسقِط الشاشة كلها (هذا بالضبط ما سبّب عطل المرافق الثاني).
    return (
        f"   📋 التأشيرة: {p.get('visa_expiry') or '—'}\n"
        f"   🛂 الجواز: {p.get('passport_expiry') or '—'}\n"
        f"   📎 المرفقات: جواز {mark(p.get('passport_file_id'))} · "
        f"تأشيرة {mark(p.get('visa_file_id'))}\n"
    )


def _build_review(session: LegoSession) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        "📋 **مراجعة قبل الحفظ**\n",
        f"👤 **{session.patient_name}**",
        _person_summary(session.person),
        f"   🏠 السكن: {session.housing or '—'}\n",
    ]
    if session.companions:
        lines.append(f"🤝 **المرافقون ({len(session.companions)}):**")
        for c in session.companions:
            lines.append(f"• **{c['name']}**")
            lines.append(_person_summary(c))
    else:
        lines.append("🤝 **المرافقون:** لا يوجد\n")

    lines.append(
        "\n⚠️ بعد الحفظ سيظهر هذا المريض في:\n"
        "• 🔧 الخدمات العامة  • 🛫 المغادرين\n"
        "• 🪪 الإقامة → 🏠 معلّقات من الحالات السابقة"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ حفظ", callback_data=f"{LEGO}:save")],
        _cancel_row(),
    ])
    return "\n".join(lines), kb


# ── الانتقال بين الخطوات ──────────────────────────────────────────────────────

def _advance(session: LegoSession) -> None:
    """ينقل الجلسة للخطوة التالية حسب موضعها الحالي."""
    step = session.step

    if step in _PERSON_STEPS:
        i = _PERSON_STEPS.index(step)
        if i + 1 < len(_PERSON_STEPS):
            session.step = _PERSON_STEPS[i + 1]
            return
        # انتهت فورمة هذا الشخص
        if session.in_companion:
            session.companions.append(dict(session.current_companion))
            # 🔴 كان `{}` — فيفقد المرافق **الثاني فصاعداً** كل مفتاح لا
            # يُكتَب صراحةً في خطواته، فينفجر `_person_summary` بـKeyError
            # في شاشة المراجعة ويموت المعالِج بلا رد ⇒ الشاشة "تعلّق".
            session.current_companion = _blank_person()
            if len(session.companions) < session.companion_total:
                session.step = S_C_NAME
            else:
                session.in_companion = False
                session.step = S_REVIEW
        else:
            session.step = S_HOUSING
        return

    if step == S_HOUSING:
        session.step = S_HAS_COMPANION
    elif step == S_C_NAME:
        session.step = _PERSON_STEPS[0]


# ── المعالِجات ────────────────────────────────────────────────────────────────

def _is_admin(uid: int | None) -> bool:
    try:
        from bot.shared_auth import is_admin
        return bool(uid) and is_admin(uid)
    except Exception:
        logger.warning("[lego] تعذّر التحقق من صلاحية الأدمن", exc_info=True)
        return False


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    uid = query.from_user.id if query.from_user else None
    if not _is_admin(uid):
        await query.answer("🚫 هذه الشاشة للأدمن فقط", show_alert=True)
        return
    await query.answer()

    action = (query.data or "")[len(LEGO) + 1:]
    ud = context.user_data

    # ── الدخول والقائمة ──────────────────────────────────────────────────
    if action == "menu" or action.startswith("page:"):
        LegoSession.clear(ud)
        page = int(action.split(":")[1]) if action.startswith("page:") else 0
        if action == "menu":
            ud.pop(_SEARCH_Q_KEY, None)     # دخول جديد = قائمة كاملة
        ud.pop(_SEARCH_WAIT_KEY, None)
        await _show_list(query, page, ud.get(_SEARCH_Q_KEY, ""))
        return

    # ── ↩️ تصحيح إدخال سابق ──────────────────────────────────────────────
    if action.startswith("undo:"):
        LegoSession.clear(ud)
        await _show_undo_list(query, int(action.split(":")[1]))
        return

    if action.startswith("undopick:"):
        _, pid, page = action.split(":")
        await _show_undo_confirm(query, int(pid), int(page))
        return

    if action.startswith("undogo:"):
        from services.patients_service import undo_legacy_onboarding
        _, pid, page = action.split(":")
        ok, info = undo_legacy_onboarding(int(pid))
        if ok:
            await query.answer(f"↩️ أُلغي إدخال {info}", show_alert=False)
        else:
            await query.answer(f"⚠️ {info}", show_alert=True)
        await _show_undo_list(query, int(page))
        return

    if action == "search":
        LegoSession.clear(ud)
        ud[_SEARCH_WAIT_KEY] = True
        await query.edit_message_text(
            "🔍 **البحث عن مريض**\n\n"
            "اكتب الاسم أو جزءاً منه (حرفان على الأقل):",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع للقائمة", callback_data=f"{LEGO}:all")]
            ]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if action == "all":
        ud.pop(_SEARCH_Q_KEY, None)
        ud.pop(_SEARCH_WAIT_KEY, None)
        await _show_list(query, 0)
        return

    if action == "cancel":
        LegoSession.clear(ud)
        await _show_list(query, 0, ud.get(_SEARCH_Q_KEY, ""))
        return

    if action.startswith("pick:"):
        parts = action.split(":")
        pid, page = int(parts[1]), int(parts[2])
        if _already_onboarded(pid):
            await query.answer("⚠️ هذا المريض مُدخَل مسبقاً", show_alert=True)
            await _show_list(query, page, ud.get(_SEARCH_Q_KEY, ""))
            return
        from db.session import SessionLocal
        from db.models import Patient
        with SessionLocal() as s:
            row = s.query(Patient).filter_by(id=pid).first()
            name = row.full_name if row else ""
        if not name:
            await query.answer("⚠️ لم يُعثر على المريض", show_alert=True)
            return
        session = LegoSession(
            step=_PERSON_STEPS[0], patient_id=pid, patient_name=name,
            person=_blank_person(name), companions=[], current_companion={},
            companion_total=0, in_companion=False,
        )
        session.save(ud)
        await _render_step(query, session, edit=True)
        return

    session = LegoSession.load(ud)
    if session is None:
        await _show_list(query, 0)
        return

    # ── التقويم ──────────────────────────────────────────────────────────
    if action.startswith(("cal_prev:", "cal_next:", "cal_yprev:", "cal_ynext:", "cal_setmonth:")):
        parts = action.split(":")
        y, m = int(parts[1]), int(parts[2])
        text, kb = build_calendar(y, m, LEGO, f"{LEGO}:cancel", quick_jump=True)
        await query.edit_message_text(
            f"{_who(session)}\n\n**{_STEP_TITLES[session.step]}**\n\n"
            + text + _MANUAL_HINT,
            reply_markup=kb, parse_mode=ParseMode.MARKDOWN,
        )
        return

    if action.startswith(("cal_years:", "cal_yearpage:")):
        text, kb = build_year_picker(int(action.split(":")[1]), LEGO, f"{LEGO}:cancel")
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        return

    if action.startswith("cal_setyear:"):
        text, kb = build_month_picker(int(action.split(":")[1]), LEGO, f"{LEGO}:cancel")
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        return

    if action == "cal_noop":
        return

    if action.startswith("cal_pick:"):
        parts = action.split(":")
        picked = datetime(int(parts[1]), int(parts[2]), int(parts[3])).strftime("%d/%m/%Y")
        if session.step == S_VISA_EXPIRY:
            session.active["visa_expiry"] = picked
        elif session.step == S_PASSPORT_EXPIRY:
            session.active["passport_expiry"] = picked
        else:
            return
        _advance(session)
        session.save(ud)
        await _render_step(query, session, edit=True)
        return

    # ── المرافقون ────────────────────────────────────────────────────────
    if action == "comp_no" and session.step == S_HAS_COMPANION:
        session.step = S_REVIEW
        session.save(ud)
        await _render_step(query, session, edit=True)
        return

    if action == "comp_yes" and session.step == S_HAS_COMPANION:
        session.step = S_COMPANION_COUNT
        session.save(ud)
        await _render_step(query, session, edit=True)
        return

    if action.startswith("cnt:") and session.step == S_COMPANION_COUNT:
        session.companion_total = int(action.split(":")[1])
        session.in_companion = True
        session.current_companion = _blank_person()
        session.step = S_C_NAME
        session.save(ud)
        await _render_step(query, session, edit=True)
        return

    # ── الحفظ ────────────────────────────────────────────────────────────
    if action == "save" and session.step == S_REVIEW:
        ok, err = _persist(session, uid)
        LegoSession.clear(ud)
        if ok:
            n = len(session.companions)
            await query.edit_message_text(
                f"✅ **تم حفظ {session.patient_name}**\n\n"
                f"🤝 المرافقون: {n}\n\n"
                "أصبح يظهر الآن في:\n"
                "• 🔧 الخدمات العامة   • 🛫 المغادرين\n"
                "• 🪪 الإقامة → 🏠 معلّقات من الحالات السابقة",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ إدخال مريض آخر", callback_data=f"{LEGO}:menu")],
                    [InlineKeyboardButton("🔙 رجوع", callback_data="manage_patients")],
                ]),
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await query.edit_message_text(
                f"❌ **تعذّر الحفظ**\n\n{err}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 رجوع", callback_data=f"{LEGO}:menu")]
                ]),
                parse_mode=ParseMode.MARKDOWN,
            )
        return


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يستقبل صور/ملفات خطوات المرفقات — لا يعمل إلا داخل جلسة نشطة."""
    session = LegoSession.load(context.user_data)
    if session is None or session.step not in (S_PASSPORT_FILE, S_VISA_FILE):
        return                      # ⚠️ لا نبتلع رسائل التدفقات الأخرى
    msg = update.message
    if not msg:
        return

    file_id = ""
    if msg.photo:
        file_id = msg.photo[-1].file_id
    elif msg.document:
        file_id = msg.document.file_id
    if not file_id:
        await msg.reply_text("⚠️ أرسل صورة أو ملفاً.")
        return

    key = {
        S_PASSPORT_FILE: "passport_file_id",
        S_VISA_FILE: "visa_file_id",
    }[session.step]
    session.active[key] = file_id
    _advance(session)
    session.save(context.user_data)
    await _render_step(msg, session, edit=False)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يستقبل استعلام البحث، والسكن، واسم المرافق — لا يعمل إلا ضمن حالة
    خاصة بهذه الشاشة."""
    ud = context.user_data
    msg = update.message

    # ── البحث السريع (قبل وجود أي جلسة فورمة) ────────────────────────
    if ud.get(_SEARCH_WAIT_KEY):
        q_text = ((msg.text or "").strip() if msg else "")
        if len(q_text) < 2:
            await msg.reply_text("⚠️ اكتب حرفين على الأقل للبحث.")
            return
        ud.pop(_SEARCH_WAIT_KEY, None)
        ud[_SEARCH_Q_KEY] = q_text

        # ⚠️ رسالة جديدة لا تعديل: الرد على رسالة نصية لا يملك رسالة
        # كولباك لتعديلها. نغلّف msg بواجهة edit_message_text المتوقَّعة
        # في _show_list بلا تكرار منطق العرض.
        class _AsNew:
            @staticmethod
            async def edit_message_text(text, reply_markup=None, parse_mode=None):
                await msg.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)

        await _show_list(_AsNew, 0, q_text)
        return

    session = LegoSession.load(ud)
    _TEXT_STEPS = (S_HOUSING, S_C_NAME, S_VISA_EXPIRY, S_PASSPORT_EXPIRY)
    if session is None or session.step not in _TEXT_STEPS:
        return                      # ⚠️ لا نبتلع رسائل التدفقات الأخرى
    text = (msg.text or "").strip() if msg else ""
    if len(text) < 2:
        await msg.reply_text("⚠️ النص قصير جداً، أعد الإدخال.")
        return

    if session.step in (S_VISA_EXPIRY, S_PASSPORT_EXPIRY):
        picked = _parse_manual_date(text)
        if picked is None:
            # ⚠️ لا تُستهلَك الخطوة عند الخطأ: التقويم يبقى معروضاً كما هو
            await msg.reply_text(
                "⚠️ تاريخ غير صالح.\n"
                "اكتبه بصيغة `يوم/شهر/سنة` — مثال: `25/12/2027`\n"
                "أو اختر من التقويم أعلاه.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        key = ("visa_expiry" if session.step == S_VISA_EXPIRY
               else "passport_expiry")
        session.active[key] = picked
    elif session.step == S_HOUSING:
        session.housing = text
    else:
        session.current_companion["name"] = text

    _advance(session)
    session.save(context.user_data)
    await _render_step(msg, session, edit=False)


def register(app) -> None:
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=rf"^{LEGO}:"), group=21)
    app.add_handler(
        MessageHandler(filters.PHOTO | filters.Document.ALL, handle_media), group=22,
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text), group=22,
    )
    logger.info("[lego] 🏠 الحالات الموجودة — handlers registered (cb group 21, msg group 22)")
