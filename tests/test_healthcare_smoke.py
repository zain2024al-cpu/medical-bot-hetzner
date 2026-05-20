# tests/test_healthcare_smoke.py
# Smoke test for the healthcare / woundcare module.
# No Telegram, no DB connections, no PTB context.

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.healthcare.woundcare.session import (
    WoundcareAddSession,
    STEP_PATIENT, STEP_WOUND_TYPE, STEP_IMAGES, STEP_NOTES, STEP_REVIEW,
)
from modules.healthcare.woundcare.views import (
    build_healthcare_menu, build_woundcare_menu,
    build_notes_prompt, build_review,
    build_success, build_cancelled, build_error,
    HC, WCA,
)
from modules.healthcare.woundcare.flow import WOUND_TYPE_OPTIONS
from shared.multiselect._models import Option
from shared.uploads._models import UploadedFile


# ── Session ───────────────────────────────────────────────────────────────────

def test_session_create_load_clear():
    ud = {}
    session = WoundcareAddSession.create(ud)
    assert session.step == STEP_PATIENT
    assert session.patient_name == ""
    assert "_wc_add" in ud

    loaded = WoundcareAddSession.load(ud)
    assert loaded is not None
    assert loaded.step == STEP_PATIENT

    WoundcareAddSession.clear(ud)
    assert WoundcareAddSession.load(ud) is None
    print("session create/load/clear OK")


def test_session_roundtrip():
    ud = {}
    session = WoundcareAddSession.create(ud)
    session.patient_id    = 42
    session.patient_name  = "أحمد محمد"
    session.wound_type_ids    = ["pressure", "diabetic"]
    session.wound_type_labels = ["جرح ضغط", "جرح سكري"]
    session.images = [
        UploadedFile("f1","u1","image/jpeg",200_000,width=800,height=600).to_dict()
    ]
    session.notes = "ملاحظة اختبارية"
    session.step  = STEP_REVIEW
    session.save(ud)

    s2 = WoundcareAddSession.load(ud)
    assert s2.patient_id == 42
    assert s2.patient_name == "أحمد محمد"
    assert s2.wound_type_ids == ["pressure", "diabetic"]
    assert s2.image_count == 1
    assert s2.notes == "ملاحظة اختبارية"
    assert s2.step == STEP_REVIEW
    assert s2.is_complete
    print("session roundtrip OK")


def test_session_get_images():
    ud = {}
    s = WoundcareAddSession.create(ud)
    f = UploadedFile("fid","uid","image/jpeg",300_000,width=1024,height=768)
    s.images = [f.to_dict()]
    files = s.get_images()
    assert len(files) == 1
    assert files[0] == f
    print("session get_images OK")


# ── Wound type options ────────────────────────────────────────────────────────

def test_wound_types():
    assert len(WOUND_TYPE_OPTIONS) >= 6
    ids = [o.id for o in WOUND_TYPE_OPTIONS]
    assert "pressure" in ids
    assert "diabetic" in ids
    assert "surgical" in ids
    for opt in WOUND_TYPE_OPTIONS:
        assert isinstance(opt, Option)
        assert opt.id
        assert opt.label
    print(f"wound types OK ({len(WOUND_TYPE_OPTIONS)} options)")


# ── Views ─────────────────────────────────────────────────────────────────────

def test_view_healthcare_menu():
    text, kb = build_healthcare_menu()
    assert "الرعاية الصحية" in text
    kb_str = str(kb)
    assert f"{HC}:woundcare" in kb_str
    print("build_healthcare_menu OK")


def test_view_woundcare_menu():
    text, kb = build_woundcare_menu()
    assert "رعاية الجروح" in text
    kb_str = str(kb)
    assert f"{WCA}:start" in kb_str
    assert f"{HC}:main" in kb_str
    print("build_woundcare_menu OK")


def test_view_notes_prompt():
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.patient_name       = "خالد علي"
    s.wound_type_labels  = ["جرح ضغط"]
    s.images             = [UploadedFile("f","u","image/jpeg",100_000).to_dict()]
    text, kb = build_notes_prompt(s)
    assert "إضافة ملاحظات" in text
    assert "خالد علي" in text
    kb_str = str(kb)
    assert f"{WCA}:skip_notes" in kb_str
    assert f"{WCA}:cancel" in kb_str
    print("build_notes_prompt OK")


def test_view_review():
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.patient_name       = "سعيد يوسف"
    s.wound_type_labels  = ["جرح سكري", "حرق"]
    s.images             = [
        UploadedFile("f1","u1","image/jpeg",100_000).to_dict(),
        UploadedFile("f2","u2","image/jpeg",150_000).to_dict(),
    ]
    s.notes = "الجرح يتحسن ببطء"
    text, kb = build_review(s)
    assert "مراجعة تقرير الجرح" in text
    assert "سعيد يوسف" in text
    assert "جرح سكري" in text
    assert "حرق" in text
    assert "2" in text
    assert "الجرح يتحسن ببطء" in text
    kb_str = str(kb)
    assert f"{WCA}:confirm" in kb_str
    assert f"{WCA}:cancel" in kb_str
    assert f"{WCA}:edit_notes" in kb_str
    print("build_review OK")


def test_view_review_no_notes():
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.patient_name      = "فاطمة"
    s.wound_type_labels = ["جرح ضغط"]
    s.images            = [UploadedFile("f","u","image/jpeg",100_000).to_dict()]
    s.notes             = ""
    text, kb = build_review(s)
    assert "مراجعة تقرير الجرح" in text
    print("build_review (no notes) OK")


def test_view_success():
    text, kb = build_success(record_id=7, patient_name="أحمد", image_count=3)
    assert "7" in text
    assert "أحمد" in text
    assert "3" in text
    kb_str = str(kb)
    assert f"{WCA}:start" in kb_str
    assert f"{HC}:main" in kb_str
    print("build_success OK")


def test_view_cancelled():
    text, kb = build_cancelled()
    assert "إلغاء" in text
    kb_str = str(kb)
    assert f"{HC}:main" in kb_str
    print("build_cancelled OK")


def test_view_error():
    text, kb = build_error("رسالة خطأ محددة")
    assert "خطأ" in text
    assert "رسالة خطأ محددة" in text
    print("build_error OK")


# ── Module bootstrap ──────────────────────────────────────────────────────────

def test_bootstrap_registers_healthcare():
    from core.routing.registry import registry
    from core.modules_bootstrap import bootstrap_all
    bootstrap_all()
    assert "healthcare" in registry.all_modules()
    assert "🏥 الرعاية الصحية" in registry.all_menu_buttons()
    assert registry.resolve_button("🏥 الرعاية الصحية") == "healthcare"
    print("bootstrap registers healthcare OK")


# ── Wipe key coverage ─────────────────────────────────────────────────────────

def test_wc_session_wiped_on_interrupt():
    # The interrupt system passes healthcare's extra_wipe_keys to wipe_session.
    # Verify that the registry has _wc_add in those keys and that wipe_session
    # clears it when passed those keys — exactly as interrupt_and_reset does.
    from core.conversation.lifecycle import wipe_session
    from core.routing.registry import registry
    from core.modules_bootstrap import bootstrap_all
    bootstrap_all()

    healthcare_reg = registry.get("healthcare")
    assert healthcare_reg is not None
    assert "_wc_add" in healthcare_reg.extra_wipe_keys, \
        "_wc_add must be in healthcare extra_wipe_keys"

    ud = {"_wc_add": {"step": "notes"}, "report_tmp": "legacy", "other": "keep"}
    # Pass extra_wipe_keys the same way interrupt_and_reset does:
    wipe_session(ud, healthcare_reg.extra_wipe_keys)
    assert "_wc_add" not in ud, "_wc_add must be wiped when extra_wipe_keys is passed"
    assert "report_tmp" not in ud
    assert "other" in ud
    print("wipe_session clears _wc_add via extra_wipe_keys OK")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_session_create_load_clear()
    test_session_roundtrip()
    test_session_get_images()
    test_wound_types()
    test_view_healthcare_menu()
    test_view_woundcare_menu()
    test_view_notes_prompt()
    test_view_review()
    test_view_review_no_notes()
    test_view_success()
    test_view_cancelled()
    test_view_error()
    test_bootstrap_registers_healthcare()
    test_wc_session_wiped_on_interrupt()
    print("\nALL TESTS PASSED")
