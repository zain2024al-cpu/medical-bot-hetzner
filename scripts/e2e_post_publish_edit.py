#!/usr/bin/env python3
"""
محاكاة end-to-end لدورة "تعديل تقرير بعد نشره" — بالدوال الحقيقية.

── لماذا سكربت لا اختبار pytest ────────────────────────────────────────────────
`user_reports_edit.py` يلتقط `SessionLocal` وقت الاستيراد
(`from db.session import SessionLocal`)، و`broadcast_service` يستوردها من
جديد داخل الدوال وقت الاستدعاء. وفي مجموعة الاختبارات الحالية يُعيد
`tests/test_rbac_smoke.py` ربط `db.session.SessionLocal` **عالمياً** لقاعدة
في الذاكرة. فوضع هذه الدورة داخل pytest يجعل نتيجتها رهينة ترتيب استيراد
الملفات — وهو بالضبط نوع تلوّث الاختبارات الموثَّق في
`tests/test_report_ownership.py`. السكربت هنا يعزل نفسه بقاعدة مؤقتة
خاصة به فلا يلمس شيئاً.

── ما الذي يتحقّق منه ─────────────────────────────────────────────────────────
    1. اختيار تقرير من القائمة              5. العودة لقائمة الحقول
    2. اختيار حقل نصّي وعرض قيمته           6. حفظ حقل تاريخ
    3. إدخال قيمة جديدة ومعاينتها           7. إعادة النشر وبناء البطاقة
    4. وصول التعديل لقاعدة البيانات فعلاً    8-9. سلامة البطاقة المنشورة

القيمة الجديدة المستخدَمة تحوي عمداً محارف Markdown خطِرة
(`التهاب معدة* مزمن_مع ارتجاع`) لأنها كانت تكسر الرسالة قبل إصلاح التهريب.

── التشغيل ────────────────────────────────────────────────────────────────────
    venv/bin/python scripts/e2e_post_publish_edit.py
"""

import asyncio
import logging
import os
import sys
import tempfile
import types
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

# ⚠️ قاعدة مؤقتة خاصة — تُضبَط **قبل** استيراد db.session لأن مسار القاعدة
# يُقرأ وقت الاستيراد. ولا تُستخدم قاعدة الإنتاج إطلاقاً مهما كانت البيئة.
_TMP_DB = os.path.join(tempfile.mkdtemp(prefix="e2e_edit_"), "e2e.db")
os.environ["DATABASE_PATH"] = _TMP_DB
os.environ["REPORTS_GROUP_ID"] = "-1009999999999"   # مجموعة وهمية لتفعيل مسار الإرسال

logging.basicConfig(level=logging.CRITICAL)

from db.session import init_database, SessionLocal          # noqa: E402
init_database()
from db.models import (                                      # noqa: E402
    Report, Patient, Hospital, Department, Doctor, Translator,
)
import bot.handlers.user.user_reports_edit as E              # noqa: E402

PASS: list[str] = []
FAIL: list[str] = []
USER = types.SimpleNamespace(id=999, full_name="مترجم التجربة", is_bot=False)
NEW_VALUE = "التهاب معدة* مزمن_مع ارتجاع"


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'✅' if cond else '❌'} {name}" + (f"   {detail}" if detail else ""))


class _Msg:
    def __init__(self):
        self.text = None
        self.chat = types.SimpleNamespace(id=999)

    async def reply_text(self, text, **kw):
        self.text = text
        return self


class _Query:
    def __init__(self, data):
        self.data = data
        self.text = None
        self.message = _Msg()
        self.from_user = USER

    async def answer(self, *a, **kw):
        pass

    async def edit_message_text(self, text, **kw):
        self.text = text

    async def edit_message_reply_markup(self, **kw):
        pass


class _FakeBot:
    """يلتقط ما كان سيُرسَل لتيليجرام بدل إرساله فعلاً."""

    def __init__(self):
        self.messages: list[str] = []

    async def send_message(self, chat_id, text, **kw):
        self.messages.append(text)
        return types.SimpleNamespace(
            message_id=1, chat=types.SimpleNamespace(id=chat_id))

    async def send_photo(self, **kw):
        return types.SimpleNamespace(message_id=2)

    async def send_document(self, **kw):
        return types.SimpleNamespace(message_id=3)


def _seed() -> int:
    with SessionLocal() as s:
        for model, kw in [
            (Patient,    dict(full_name="مريض التجربة")),
            (Hospital,   dict(name="Apollo (Chennai)")),
            (Department, dict(name="باطنية عامة")),
            (Doctor,     dict(name="د. سرور")),
            (Translator, dict(full_name="م. خالد", tg_user_id=USER.id)),
        ]:
            if not s.query(model).first():
                s.add(model(**kw))
        s.commit()
        p, h, d, dr, tr = (s.query(m).first() for m in
                           (Patient, Hospital, Department, Doctor, Translator))
        rep = Report(
            patient_id=p.id, patient_name=p.full_name,
            hospital_id=h.id, hospital_name=h.name,
            department_id=d.id, department=d.name,
            doctor_id=dr.id, doctor_name=dr.name,
            translator_id=tr.id, translator_name=tr.full_name,
            medical_action="استشارة جديدة",
            complaint_text="ألم في البطن", diagnosis="تشخيص قديم",
            doctor_decision="قرار قديم",
            report_date=datetime(2026, 8, 5, 14, 30),
            created_at=datetime(2026, 8, 5, 14, 30),
            submitted_by_user_id=USER.id,
        )
        s.add(rep)
        s.commit()
        return rep.id


def _upd(**kw):
    base = dict(effective_user=USER,
                effective_chat=types.SimpleNamespace(id=999),
                callback_query=None, message=None)
    base.update(kw)
    return types.SimpleNamespace(**base)


async def run(report_id: int) -> None:
    ctx = types.SimpleNamespace(user_data={}, bot=None)

    q = _Query(f"edit_report:{report_id}")
    await E.handle_report_selection(_upd(callback_query=q), ctx)
    check("1. اختيار التقرير يعرض قائمة الحقول",
          bool(q.text) and "تعديل" in q.text,
          f"report_id={ctx.user_data.get('edit_report_id')}")

    q2 = _Query("edit_field:diagnosis")
    await E.handle_field_selection(_upd(callback_query=q2), ctx)
    check("2. اختيار حقل التشخيص يعرض قيمته الحالية",
          "تشخيص قديم" in (q2.text or ""))

    msg = _Msg()
    msg.text = NEW_VALUE
    await E.handle_new_value(_upd(message=msg, effective_message=msg), ctx)
    check("3. القيمة الجديدة محفوظة في الجلسة ومعاينتها ظهرت",
          ctx.user_data.get("new_value") == NEW_VALUE)

    q3 = _Query("edit_confirm_save_text")
    await E.handle_confirm_edit(_upd(callback_query=q3), ctx)
    with SessionLocal() as s:
        saved = s.query(Report).filter_by(id=report_id).first().diagnosis
    check("4. التعديل وصل قاعدة البيانات فعلاً", saved == NEW_VALUE,
          f"القيمة الآن: {saved!r}")

    check("5. العودة لقائمة الحقول بعد الحفظ", bool(q3.text))

    ctx.user_data["edit_field"] = "followup_date"
    ctx.user_data["new_value"] = "2026-09-01"
    await E.save_edit_to_database(_Query("noop"), ctx)
    with SessionLocal() as s:
        fu = s.query(Report).filter_by(id=report_id).first().followup_date
    check("6. حفظ حقل تاريخ (followup_date)",
          fu is not None and fu.strftime("%Y-%m-%d") == "2026-09-01", str(fu))

    bot = _FakeBot()
    ctx.bot = bot
    q4 = _Query("edit_republish")
    await E.handle_republish(_upd(callback_query=q4), ctx)
    card = "\n".join(bot.messages)
    check("7. إعادة النشر تبني البطاقة وترسلها",
          bool(bot.messages), f"{len(bot.messages)} رسالة")

    if card:
        backslash = chr(92)
        stray = sum(1 for i, c in enumerate(card)
                    if c == "_" and (i == 0 or card[i - 1] != backslash))
        check("8. القيمة المعدَّلة ظهرت في البطاقة المنشورة",
              "التهاب معدة" in card)
        check("9. لا محارف Markdown خام تكسر البطاقة", stray == 0,
              f"_ غير مُهرَّبة: {stray}")


def main() -> int:
    rid = _seed()
    print(f"\n📄 تقرير تجريبي #{rid}   (قاعدة مؤقتة: {_TMP_DB})")
    print("─" * 60)
    asyncio.run(run(rid))
    print("─" * 60)
    print(f"نجح {len(PASS)} / فشل {len(FAIL)}")
    if FAIL:
        print("الفاشل: " + " | ".join(FAIL))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
