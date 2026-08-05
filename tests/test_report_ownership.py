# tests/test_report_ownership.py
# من يحقّ له تعديل/حذف تقرير — can_modify_report في bot/shared_auth.py.
#
# ⚠️ الحالة الحاسمة هنا: `test_legacy_report_denied_to_unregistered_user`.
# الفحص القديم كان يرفض بشرطٍ موجب:
#     if translator and report.translator_id != translator.id: → رفض
# فإن لم يكن للمستخدم صفٌّ في users صارت translator = None، فلا يتحقّق
# الشرط ولا يُرفض شيء — **فيمرّ الحذف**. أي مستخدم غير مسجَّل كان يستطيع
# حذف أي تقرير قديم لأي مترجم. هذا الاختبار يمنع عودة تلك الثغرة.
#
# قاعدة بيانات في الذاكرة — لا تُمَسّ قاعدة الإنتاج.

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, Report, Translator

# ⚠️ لا يُستبدَل db.session.SessionLocal العام هنا عمداً: test_rbac_smoke.py
# يستبدله أيضاً، فيفوز آخر ملف يُستورَد ويُفشل الآخر عند تشغيل المجموعة كاملة
# (كلٌّ ينجح منفرداً — وهو تلوّث اختبارات يصعب تشخيصه).
# لا حاجة لذلك أصلاً: can_modify_report تستقبل الجلسة كوسيط.
_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_engine)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

import bot.shared_auth as shared_auth

OWNER_TG, OTHER_TG, STRANGER_TG, ADMIN_TG = 111, 222, 999, 500


@pytest.fixture(autouse=True)
def _admin(monkeypatch):
    # ADMIN_IDS تأتي من البيئة وقد تكون فارغة أثناء الاختبار
    monkeypatch.setattr(shared_auth, "is_admin", lambda uid: uid == ADMIN_TG)


@pytest.fixture
def data():
    with _Session() as s:
        s.query(Report).delete()
        s.query(Translator).delete()
        owner = Translator(full_name="مالك", tg_user_id=OWNER_TG)
        s.add(owner)
        s.add(Translator(full_name="آخر", tg_user_id=OTHER_TG))
        s.flush()
        legacy = Report(patient_name="قديم", hospital_name="H", medical_action="كشف",
                        submitted_by_user_id=None, translator_id=owner.id, status="active")
        modern = Report(patient_name="حديث", hospital_name="H", medical_action="كشف",
                        submitted_by_user_id=OWNER_TG, translator_id=owner.id, status="active")
        s.add_all([legacy, modern])
        s.commit()
        yield legacy.id, modern.id


def _check(report_id, actor):
    with _Session() as s:
        rep = s.query(Report).filter_by(id=report_id).first()
        return shared_auth.can_modify_report(rep, actor, s)


def test_owner_may_modify_both(data):
    legacy, modern = data
    assert _check(legacy, OWNER_TG) is True
    assert _check(modern, OWNER_TG) is True


def test_other_translator_denied(data):
    legacy, modern = data
    assert _check(legacy, OTHER_TG) is False
    assert _check(modern, OTHER_TG) is False


def test_legacy_report_denied_to_unregistered_user(data):
    """الثغرة المُصلَحة: مستخدم بلا صفٍّ في users كان يمرّ على التقرير القديم."""
    legacy, modern = data
    assert _check(legacy, STRANGER_TG) is False
    assert _check(modern, STRANGER_TG) is False


def test_admin_may_modify_both(data):
    legacy, modern = data
    assert _check(legacy, ADMIN_TG) is True
    assert _check(modern, ADMIN_TG) is True


def test_missing_actor_or_report_denied(data):
    legacy, _ = data
    assert _check(legacy, None) is False
    with _Session() as s:
        assert shared_auth.can_modify_report(None, OWNER_TG, s) is False
