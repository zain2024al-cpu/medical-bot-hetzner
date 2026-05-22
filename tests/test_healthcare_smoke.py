# tests/test_healthcare_smoke.py
# Smoke tests for the healthcare / woundcare module — updated for 11-step spec.
# No Telegram, no DB connections, no PTB context.

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.healthcare.woundcare.session import (
    WoundcareAddSession,
    STEP_DATE, STEP_PATIENT, STEP_DEPARTMENT, STEP_OPERATION_NAME,
    STEP_PHASE, STEP_DESCRIPTION, STEP_SUPPLIES,
    STEP_IMAGES, STEP_NOTES, STEP_SPECIALIST, STEP_REVIEW,
)
from modules.healthcare.views import build_healthcare_menu
from modules.healthcare.woundcare.views import (
    build_woundcare_menu,
    build_notes_prompt, build_review,
    build_success, build_cancelled, build_error,
    HC, WCA,
)
from modules.healthcare.woundcare.flow import WOUNDCARE_SUPPLIES_OPTIONS
from shared.multiselect._models import Option
from shared.uploads._models import UploadedFile


# ── Session ───────────────────────────────────────────────────────────────────

def test_session_create_load_clear():
    ud = {}
    session = WoundcareAddSession.create(ud)
    assert session.step == STEP_DATE      # calendar picker is now the first step
    assert session.patient_name == ""
    assert "_wc_add" in ud

    loaded = WoundcareAddSession.load(ud)
    assert loaded is not None
    assert loaded.step == STEP_DATE

    WoundcareAddSession.clear(ud)
    assert WoundcareAddSession.load(ud) is None
    print("session create/load/clear OK")


def test_session_roundtrip():
    ud = {}
    session = WoundcareAddSession.create(ud)
    session.patient_id                = 42
    session.patient_name              = "أحمد محمد"
    session.medical_department_ids    = ["ortho"]
    session.medical_department_labels = ["العظام"]
    session.operation_name            = "شق وتصريف"
    session.phase                     = "phase_pre_op"
    session.phase_label               = "قبل العملية"
    session.condition_description     = "جرح عميق"
    session.supply_ids                = ["gauze"]
    session.supply_labels             = ["شاش معقم"]
    session.images = [
        UploadedFile("f1", "u1", "image/jpeg", 200_000, width=800, height=600).to_dict()
    ]
    session.notes = "ملاحظة اختبارية"
    session.step  = STEP_REVIEW
    session.save(ud)

    s2 = WoundcareAddSession.load(ud)
    assert s2.patient_id   == 42
    assert s2.patient_name == "أحمد محمد"
    assert s2.medical_department_ids    == ["ortho"]
    assert s2.operation_name            == "شق وتصريف"
    assert s2.phase                     == "phase_pre_op"
    assert s2.condition_description     == "جرح عميق"
    assert s2.supply_labels             == ["شاش معقم"]
    assert s2.image_count == 1
    assert s2.notes       == "ملاحظة اختبارية"
    assert s2.step        == STEP_REVIEW
    assert s2.is_complete
    print("session roundtrip OK")


def test_session_get_images():
    ud = {}
    s = WoundcareAddSession.create(ud)
    f = UploadedFile("fid", "uid", "image/jpeg", 300_000, width=1024, height=768)
    s.images = [f.to_dict()]
    files = s.get_images()
    assert len(files) == 1
    assert files[0] == f
    print("session get_images OK")


# ── Woundcare supplies options ────────────────────────────────────────────────

def test_supplies_options():
    assert len(WOUNDCARE_SUPPLIES_OPTIONS) >= 8
    ids = [o.id for o in WOUNDCARE_SUPPLIES_OPTIONS]
    assert "gauze"     in ids
    assert "gloves"    in ids
    assert "sup_other" in ids   # must have an "أخرى" option
    for opt in WOUNDCARE_SUPPLIES_OPTIONS:
        assert isinstance(opt, Option)
        assert opt.id
        assert opt.label
    print(f"woundcare supplies OK ({len(WOUNDCARE_SUPPLIES_OPTIONS)} options)")


# ── Views ─────────────────────────────────────────────────────────────────────

def test_view_healthcare_menu():
    text, kb = build_healthcare_menu()
    assert "الرعاية الصحية" in text
    kb_str = str(kb)
    assert f"{HC}:woundcare" in kb_str
    print("build_healthcare_menu OK")


def test_view_woundcare_menu():
    text, kb = build_woundcare_menu()
    assert "الجرح" in text
    kb_str = str(kb)
    assert f"{WCA}:start" in kb_str
    assert f"{HC}:main"   in kb_str
    print("build_woundcare_menu OK")


def test_view_notes_prompt():
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.patient_name   = "خالد علي"
    s.operation_name = "تنظيف جرح"
    s.phase_label    = "قبل العملية"
    s.images         = [UploadedFile("f", "u", "image/jpeg", 100_000).to_dict()]
    text, kb = build_notes_prompt(s)
    assert "الملاحظات" in text
    assert "خالد علي"  in text
    kb_str = str(kb)
    assert f"{WCA}:skip_notes" in kb_str
    assert f"{WCA}:cancel"     in kb_str
    print("build_notes_prompt OK")


def test_view_review():
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.patient_name            = "سعيد يوسف"
    s.operation_name          = "شق وتصريف"
    s.phase_label             = "الأولى بعد العملية"
    s.condition_description   = "الجرح يتحسن ببطء"
    s.medical_department_labels = ["الجراحة العامة"]
    s.supply_labels           = ["شاش معقم", "قفازات معقمة"]
    s.images                  = [
        UploadedFile("f1", "u1", "image/jpeg", 100_000).to_dict(),
        UploadedFile("f2", "u2", "image/jpeg", 150_000).to_dict(),
    ]
    s.notes = "الجرح يتحسن ببطء"
    text, kb = build_review(s)
    assert "مراجعة تقرير المجارحة" in text
    assert "سعيد يوسف"              in text
    assert "شق وتصريف"              in text
    assert "الأولى بعد العملية"     in text
    assert "الجرح يتحسن ببطء"      in text
    kb_str = str(kb)
    assert f"{WCA}:confirm"    in kb_str
    assert f"{WCA}:cancel"     in kb_str
    assert f"{WCA}:edit_notes" in kb_str
    print("build_review OK")


def test_view_review_no_notes():
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.patient_name          = "فاطمة"
    s.operation_name        = "تنظيف جرح"
    s.phase_label           = "مجارحة دورية / جرح مزمن"
    s.condition_description = "جرح مزمن"
    s.images                = [UploadedFile("f", "u", "image/jpeg", 100_000).to_dict()]
    s.notes                 = ""
    text, kb = build_review(s)
    assert "مراجعة تقرير المجارحة" in text
    print("build_review (no notes) OK")


def test_view_success():
    text, kb = build_success(record_id=7, patient_name="أحمد", image_count=3)
    assert "7"     in text
    assert "أحمد"  in text
    kb_str = str(kb)
    assert f"{WCA}:start" in kb_str
    assert f"{HC}:main"   in kb_str
    print("build_success OK")


def test_view_cancelled():
    text, kb = build_cancelled()
    assert "إلغاء" in text
    kb_str = str(kb)
    assert f"{HC}:main" in kb_str
    print("build_cancelled OK")


def test_view_error():
    text, kb = build_error("رسالة خطأ محددة")
    assert "خطأ"              in text
    assert "رسالة خطأ محددة" in text
    print("build_error OK")


# ── Module bootstrap ──────────────────────────────────────────────────────────

def test_bootstrap_registers_healthcare():
    from core.routing.registry import registry
    from core.modules_bootstrap import bootstrap_all
    bootstrap_all()
    assert "healthcare" in registry.all_modules()
    assert "▶️ ابدأ الآن" in registry.all_menu_buttons()
    assert registry.resolve_button("▶️ ابدأ الآن") == "healthcare"
    print("bootstrap registers healthcare OK")


# ── Wipe key coverage ─────────────────────────────────────────────────────────

def test_wc_session_wiped_on_interrupt():
    from core.conversation.lifecycle import wipe_session
    from core.routing.registry import registry
    from core.modules_bootstrap import bootstrap_all
    bootstrap_all()

    healthcare_reg = registry.get("healthcare")
    assert healthcare_reg is not None
    assert "_wc_add" in healthcare_reg.extra_wipe_keys, \
        "_wc_add must be in healthcare extra_wipe_keys"

    ud = {"_wc_add": {"step": "notes"}, "report_tmp": "legacy", "other": "keep"}
    wipe_session(ud, healthcare_reg.extra_wipe_keys)
    assert "_wc_add"    not in ud, "_wc_add must be wiped"
    assert "report_tmp" not in ud
    assert "other"      in ud
    print("wipe_session clears _wc_add via extra_wipe_keys OK")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_session_create_load_clear()
    test_session_roundtrip()
    test_session_get_images()
    test_supplies_options()
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
