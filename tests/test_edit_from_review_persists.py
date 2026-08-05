# tests/test_edit_from_review_persists.py
# تعديل حقل من شاشة المراجعة يجب أن **يبقى محفوظاً**.
#
# ⚠️ العطل المُصلَح (ظهر في الإنتاج: «الأدوية» فارغة في تقرير منشور):
# معالِجات النتائج كانت تكتب في كائن الجلسة ثم تستدعي `_go_to_review`،
# و`_go_to_review` **يُعيد تحميل الجلسة من user_data** — فأي قيمة لم
# تُحفَظ تُمحى. فرع «التعديل من المراجعة» كان يعود بلا `session.save`،
# فيضيع اختيار المستخدم **بصمت**: لا خطأ، ولا رسالة، فقط حقل فارغ في
# التقرير بعد النشر.
#
# خمسة حقول كانت مصابة في المتابعة الطبية، واثنان في الخدمات العامة.
# هذا الاختبار يمنع عودة النمط.

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import modules.healthcare.medical_followup.flow as F
from modules.healthcare.medical_followup.session import MedicalFollowupSession


class _Sel:
    """نتيجة اختيار متعدد."""
    cancelled = False

    def __init__(self, ids, labels):
        self.ids, self.labels = ids, labels


class _Files:
    """نتيجة رفع ملفات."""
    cancelled = False
    ids, labels = [], []

    class _F:
        @staticmethod
        def to_dict():
            return {"file_id": "img1"}

    files = [_F()]


@pytest.fixture
def captured(monkeypatch):
    """يستبدل شاشة المراجعة بمن يلتقط الجلسة كما تُقرأ من user_data."""
    box = {}

    async def _fake_review(update, context):
        box["session"] = MedicalFollowupSession.load(context.user_data)

    monkeypatch.setattr(F, "_go_to_review", _fake_review)
    return box


@pytest.mark.parametrize("handler_name, result, attr, expected", [
    ("_on_department",   _Sel(["d1"], ["جراحة العظام"]),            "medical_department_labels", ["جراحة العظام"]),
    ("_on_proc_type",    _Sel(["p1"], ["معاينة وصرف دواء"]),        "procedure_type_labels",     ["معاينة وصرف دواء"]),
    ("_on_complaint",    _Sel(["c1"], ["ألم في مكان العملية"]),      "complaint_labels",          ["ألم في مكان العملية"]),
    ("_on_meds_supply",  _Sel(["m1", "m2"], ["باراسيتامول", "شاش"]), "meds_supply_labels",        ["باراسيتامول", "شاش"]),
    ("_on_images",       _Files(),                                   "images",                    [{"file_id": "img1"}]),
])
def test_edit_from_review_is_persisted(captured, handler_name, result, attr, expected):
    ctx = type("Ctx", (), {})()
    ctx.user_data = {}
    session = MedicalFollowupSession.create(ctx.user_data)
    session.edit_from_review = True
    session.save(ctx.user_data)

    handler = getattr(F, handler_name)
    asyncio.run(handler(result, type("Upd", (), {})(), ctx))

    reloaded = captured["session"]
    assert reloaded is not None, "شاشة المراجعة لم تُستدعَ"
    assert getattr(reloaded, attr) == expected, (
        f"{attr} ضاع عند التعديل من شاشة المراجعة — "
        f"الجلسة لم تُحفَظ قبل إعادة التحميل"
    )
