# tests/test_healthcare_flows.py
# Smoke tests for the healthcare operational workflow layer.
# Uses in-memory SQLite — no production DB touched.
# No Telegram, no PTB context required.

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Patch DB to use in-memory SQLite ─────────────────────────────────────────
import db.session as _db_session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base

_test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_test_engine)
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
_db_session.engine         = _test_engine
_db_session.SessionLocal   = _TestSessionLocal

# Patch get_db context manager too
from contextlib import contextmanager
@contextmanager
def _test_get_db():
    s = _TestSessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
_db_session.get_db = _test_get_db

# ── Bootstrap modules ─────────────────────────────────────────────────────────
from core.modules_bootstrap import bootstrap_all
bootstrap_all()


# ─────────────────────────────────────────────────────────────────────────────
# A. DB schema — new tables and columns exist
# ─────────────────────────────────────────────────────────────────────────────

def test_db_wound_record_has_specialist_name():
    from db.models import WoundRecord
    assert hasattr(WoundRecord, "specialist_name"), "WoundRecord must have specialist_name column"
    print("WoundRecord.specialist_name OK")


def test_db_new_tables_exist():
    from db.models import MedicalFollowupRecord, MedicationRecord, OtherHealthcareRecord
    assert MedicalFollowupRecord.__tablename__ == "medical_followup_records"
    assert MedicationRecord.__tablename__      == "medication_records"
    assert OtherHealthcareRecord.__tablename__ == "other_healthcare_records"
    print("new healthcare tables OK")


# ─────────────────────────────────────────────────────────────────────────────
# B. Top-level views
# ─────────────────────────────────────────────────────────────────────────────

def test_healthcare_menu_has_four_items():
    from modules.healthcare.views import build_healthcare_menu
    text, kb = build_healthcare_menu()
    buttons = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "hc:woundcare"    in buttons
    assert "hc:followup"     in buttons
    assert "hc:medications"  in buttons
    assert "hc:other"        in buttons
    print(f"healthcare menu 4-item OK  button count={len(buttons)}")


def test_format_arabic_date():
    from modules.healthcare.views import format_arabic_datetime
    result = format_arabic_datetime("")    # empty -> defaults to today
    assert result != "", "format_arabic_datetime should return a non-empty string"
    print(f"format_arabic_datetime OK  len={len(result)}")


def test_format_arabic_date_iso():
    from modules.healthcare.views import format_arabic_datetime
    result = format_arabic_datetime("2026-05-20T10:30:00")
    assert "mayo" in result.lower() or "مايو" in result, f"Expected Arabic month name, got {result!r}"
    print(f"format_arabic_date ISO OK  len={len(result)}")


# ─────────────────────────────────────────────────────────────────────────────
# C. Woundcare session
# ─────────────────────────────────────────────────────────────────────────────

def test_woundcare_session_create_load_clear():
    from modules.healthcare.woundcare.session import WoundcareAddSession, STEP_DATE
    ud = {}
    s = WoundcareAddSession.create(ud)
    assert s.step == STEP_DATE          # date-first: first step is date selection
    assert s.specialist_name == ""
    assert s.created_at != ""           # pre-populated with today's date

    loaded = WoundcareAddSession.load(ud)
    assert loaded is not None
    assert loaded.step == STEP_DATE
    assert loaded.specialist_name == ""

    WoundcareAddSession.clear(ud)
    assert WoundcareAddSession.load(ud) is None
    print("woundcare session create/load/clear OK")


def test_woundcare_session_specialist_persistence():
    from modules.healthcare.woundcare.session import WoundcareAddSession, STEP_SPECIALIST
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.specialist_name = "د. فضل"
    s.step = STEP_SPECIALIST
    s.save(ud)

    loaded = WoundcareAddSession.load(ud)
    assert loaded.specialist_name == "د. فضل"
    assert loaded.step == STEP_SPECIALIST
    print("woundcare specialist persistence OK")


# ─────────────────────────────────────────────────────────────────────────────
# D. Woundcare views
# ─────────────────────────────────────────────────────────────────────────────

def test_woundcare_phase_prompt_view():
    """Phase prompt has exactly 4 phase buttons plus cancel."""
    from modules.healthcare.woundcare.session import WoundcareAddSession
    from modules.healthcare.woundcare.views import build_phase_prompt
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.patient_name   = "محمد علي"
    s.operation_name = "شق وتصريف"
    text, kb = build_phase_prompt(s)
    assert "مرحلة المجارحة" in text
    buttons = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "wca:phase_pre_op"    in buttons
    assert "wca:phase_post_1"    in buttons
    assert "wca:phase_post_last" in buttons
    assert "wca:phase_chronic"   in buttons
    assert "wca:cancel"          in buttons
    print("woundcare phase_prompt view OK")


def test_woundcare_operation_name_prompt_view():
    """Operation name prompt — cancel only, no skip."""
    from modules.healthcare.woundcare.session import WoundcareAddSession
    from modules.healthcare.woundcare.views import build_operation_name_prompt
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.patient_name = "فاطمة"
    s.medical_department_labels = ["الجراحة العامة"]
    text, kb = build_operation_name_prompt(s)
    assert "اسم العملية" in text
    buttons = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "wca:cancel" in buttons
    assert not any("skip" in b for b in buttons), "operation_name must not have a skip button"
    print("woundcare operation_name_prompt view OK")


def test_woundcare_specialist_prompt_view():
    """Specialist prompt has 3 fixed buttons, no skip."""
    from modules.healthcare.woundcare.session import WoundcareAddSession
    from modules.healthcare.woundcare.views import build_specialist_prompt
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.patient_name = "محمد علي"
    text, kb = build_specialist_prompt(s)
    assert "اسم الصحي" in text
    buttons = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "wca:sp_fadl"     in buttons
    assert "wca:sp_sarour"   in buttons
    assert "wca:sp_zakariya" in buttons
    assert "wca:cancel"      in buttons
    # NO skip button allowed
    assert not any("skip" in b for b in buttons), "specialist prompt must not have a skip button"
    print("woundcare specialist_prompt view 3-button OK")


def test_woundcare_review_shows_all_fields():
    from modules.healthcare.woundcare.session import WoundcareAddSession
    from modules.healthcare.woundcare.views import build_review
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.patient_name              = "فاطمة أحمد"
    s.operation_name            = "شق وتصريف"
    s.phase_label               = "قبل العملية"
    s.medical_department_labels = ["الجراحة العامة"]
    s.supply_labels             = ["شاش معقم", "قفازات معقمة"]
    s.condition_ids             = ["clean", "mild_redness"]
    s.condition_labels          = ["الجرح نظيف (لا احمرار أو إفرازات)", "احمرار بسيط حول الجرح"]
    s.condition_other           = ""
    s.notes                     = "تمت المعالجة"
    s.specialist_name           = "د. فضل"
    s.images                    = []
    text, kb = build_review(s)
    assert "فاطمة أحمد"                         in text
    assert "شق وتصريف"                          in text
    assert "قبل العملية"                         in text
    assert "الجرح نظيف"                          in text
    assert "احمرار بسيط"                         in text
    assert "شاش معقم"                            in text
    assert "تمت المعالجة"                        in text
    assert "د. فضل"                              in text
    assert "🩹 *وصف حالة الجرح:*"               in text
    buttons = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "wca:confirm"         in buttons
    assert "wca:edit_notes"      in buttons
    assert "wca:edit_specialist" in buttons
    print("woundcare review view all fields OK")


# ─────────────────────────────────────────────────────────────────────────────
# D2. Wound condition multiselect
# ─────────────────────────────────────────────────────────────────────────────

def test_wound_condition_options_count():
    """WOUND_CONDITION_OPTIONS must have exactly 8 entries."""
    from modules.healthcare.woundcare.constants import WOUND_CONDITION_OPTIONS
    assert len(WOUND_CONDITION_OPTIONS) == 8, (
        f"Expected 8 condition options, got {len(WOUND_CONDITION_OPTIONS)}"
    )
    print(f"WOUND_CONDITION_OPTIONS count OK  ({len(WOUND_CONDITION_OPTIONS)} options)")


def test_wound_condition_other_id_constant():
    """CONDITION_OTHER_ID must be 'cond_other' and present in WOUND_CONDITION_OPTIONS."""
    from modules.healthcare.woundcare.constants import (
        WOUND_CONDITION_OPTIONS, CONDITION_OTHER_ID,
    )
    assert CONDITION_OTHER_ID == "cond_other"
    ids = [o.id for o in WOUND_CONDITION_OPTIONS]
    assert CONDITION_OTHER_ID in ids, "CONDITION_OTHER_ID must appear in WOUND_CONDITION_OPTIONS"
    # "أخرى" must be the last option
    assert WOUND_CONDITION_OPTIONS[-1].id == CONDITION_OTHER_ID
    print("CONDITION_OTHER_ID OK")


def test_wound_condition_options_labels():
    """All 8 official label strings must be present."""
    from modules.healthcare.woundcare.constants import WOUND_CONDITION_OPTIONS
    labels = [o.label for o in WOUND_CONDITION_OPTIONS]
    assert "الجرح ملتئم بالكامل"                in labels
    assert "الجرح نظيف (لا احمرار أو إفرازات)" in labels
    assert "احمرار بسيط حول الجرح"             in labels
    assert "الجرح مفتوح جزئياً"                in labels
    assert "تورم مع ألم موضعي أو حرارة موضعية" in labels
    assert "خروج قيح أو إفرازات دموية"         in labels
    assert "رائحة غير طبيعية"                  in labels
    assert "أخرى"                              in labels
    print("WOUND_CONDITION_OPTIONS all 8 labels present OK")


def test_woundcare_session_condition_fields_persist():
    """condition_ids, condition_labels, condition_other survive save/load round-trip."""
    from modules.healthcare.woundcare.session import (
        WoundcareAddSession, STEP_DESCRIPTION_OTHER,
    )
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.condition_ids    = ["clean", "cond_other"]
    s.condition_labels = ["الجرح نظيف (لا احمرار أو إفرازات)", "أخرى"]
    s.condition_other  = "التهاب شديد مع نزيف"
    s.step             = STEP_DESCRIPTION_OTHER
    s.save(ud)

    loaded = WoundcareAddSession.load(ud)
    assert loaded.condition_ids    == ["clean", "cond_other"]
    assert loaded.condition_labels == ["الجرح نظيف (لا احمرار أو إفرازات)", "أخرى"]
    assert loaded.condition_other  == "التهاب شديد مع نزيف"
    assert loaded.step             == STEP_DESCRIPTION_OTHER
    print("condition_ids / condition_labels / condition_other persistence OK")


def test_woundcare_session_condition_fields_default_empty():
    """Freshly created session has empty condition fields."""
    from modules.healthcare.woundcare.session import WoundcareAddSession
    ud = {}
    s = WoundcareAddSession.create(ud)
    assert s.condition_ids    == []
    assert s.condition_labels == []
    assert s.condition_other  == ""
    print("condition fields default-empty OK")


def test_step_description_other_constant_exists():
    """STEP_DESCRIPTION_OTHER constant must be importable from session."""
    from modules.healthcare.woundcare.session import STEP_DESCRIPTION_OTHER
    assert STEP_DESCRIPTION_OTHER == "description_other"
    print(f"STEP_DESCRIPTION_OTHER OK  value={STEP_DESCRIPTION_OTHER!r}")


def test_woundcare_description_other_prompt_view():
    """build_description_other_prompt renders correctly with known + 'أخرى' labels."""
    from modules.healthcare.woundcare.session import WoundcareAddSession
    from modules.healthcare.woundcare.views import build_description_other_prompt
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.patient_name     = "محمد علي"
    s.condition_labels = ["الجرح نظيف (لا احمرار أو إفرازات)", "أخرى"]
    text, kb = build_description_other_prompt(s)
    assert "محمد علي"                            in text
    assert "الجرح نظيف"                           in text  # known label shown
    assert "أخرى"                               not in text  # filtered out from known_text
    assert "وصف"                                 in text
    buttons = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "wca:back"   in buttons
    assert "wca:cancel" in buttons
    print("build_description_other_prompt view OK")


def test_woundcare_review_condition_bullet_list():
    """Review renders condition_labels as bullet points under 🩹 وصف حالة الجرح."""
    from modules.healthcare.woundcare.session import WoundcareAddSession
    from modules.healthcare.woundcare.views import build_review
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.patient_name              = "علي حسن"
    s.operation_name            = "تضميد"
    s.phase_label               = "مجارحة دورية / جرح مزمن"
    s.medical_department_labels = ["الجراحة"]
    s.supply_labels             = ["شاش معقم"]
    s.condition_ids             = ["healed", "clean"]
    s.condition_labels          = ["الجرح ملتئم بالكامل", "الجرح نظيف (لا احمرار أو إفرازات)"]
    s.condition_other           = ""
    s.specialist_name           = "د. زكريا"
    s.images                    = []
    text, kb = build_review(s)
    # New section label
    assert "🩹 *وصف حالة الجرح:*"              in text
    # Both labels as bullet points
    assert "• الجرح ملتئم بالكامل"              in text
    assert "• الجرح نظيف"                        in text
    # Old free-text label must NOT appear
    assert "📄 *وصف الحالة:*"                  not in text
    print("review condition bullet list OK")


def test_woundcare_review_condition_other_replaces_placeholder():
    """When condition_other is set, 'أخرى' in condition_labels is replaced in the review."""
    from modules.healthcare.woundcare.session import WoundcareAddSession
    from modules.healthcare.woundcare.views import build_review
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.patient_name              = "سمر"
    s.operation_name            = "تنظيف"
    s.phase_label               = "قبل العملية"
    s.medical_department_labels = ["الجراحة"]
    s.supply_labels             = ["شاش معقم"]
    s.condition_ids             = ["odor", "cond_other"]
    s.condition_labels          = ["رائحة غير طبيعية", "أخرى"]
    s.condition_other           = "انتفاخ وتقيح غير اعتيادي"
    s.specialist_name           = "د. فضل"
    s.images                    = []
    text, kb = build_review(s)
    assert "• رائحة غير طبيعية"                in text
    assert "• انتفاخ وتقيح غير اعتيادي"        in text   # condition_other replaces "أخرى"
    assert "• أخرى"                           not in text   # raw "أخرى" must NOT appear
    print("review condition_other replaces placeholder OK")


def test_woundcare_condition_description_db_text_generation():
    """Verify the bullet-text string sent to DB is generated correctly from labels."""
    condition_labels  = ["الجرح نظيف (لا احمرار أو إفرازات)", "أخرى"]
    condition_other   = "نزيف خفيف"
    _cond_for_db = list(condition_labels)
    if condition_other:
        _cond_for_db = [
            condition_other if lbl == "أخرى" else lbl
            for lbl in _cond_for_db
        ]
    result = "\n".join(f"• {lbl}" for lbl in _cond_for_db)
    assert "• الجرح نظيف"  in result
    assert "• نزيف خفيف"   in result
    assert "أخرى"          not in result
    print(f"condition DB text generation OK  len={len(result)}")


# ─────────────────────────────────────────────────────────────────────────────
# D3. Woundcare supplies options update
# ─────────────────────────────────────────────────────────────────────────────

def test_woundcare_supplies_options_count():
    """WOUNDCARE_SUPPLIES_OPTIONS must have exactly 10 entries."""
    from modules.healthcare.woundcare.constants import WOUNDCARE_SUPPLIES_OPTIONS
    assert len(WOUNDCARE_SUPPLIES_OPTIONS) == 10, (
        f"Expected 10 supply options, got {len(WOUNDCARE_SUPPLIES_OPTIONS)}"
    )
    print(f"WOUNDCARE_SUPPLIES_OPTIONS count OK  ({len(WOUNDCARE_SUPPLIES_OPTIONS)} options)")


def test_woundcare_supplies_ids_unchanged():
    """All original supply IDs must still be present (DB backward-compat)."""
    from modules.healthcare.woundcare.constants import WOUNDCARE_SUPPLIES_OPTIONS
    ids = [o.id for o in WOUNDCARE_SUPPLIES_OPTIONS]
    expected_ids = ["gauze", "gloves", "med_tape", "betadine", "saline",
                    "vsl_gauze", "rolled_g", "ab_cream", "brush", "sup_other"]
    for eid in expected_ids:
        assert eid in ids, f"ID {eid!r} missing from WOUNDCARE_SUPPLIES_OPTIONS"
    print("supply IDs unchanged (backward-compat) OK")


def test_woundcare_supplies_new_labels():
    """New official labels must all be present."""
    from modules.healthcare.woundcare.constants import WOUNDCARE_SUPPLIES_OPTIONS
    labels = [o.label for o in WOUNDCARE_SUPPLIES_OPTIONS]
    assert any("Sterile Gauze"       in l for l in labels), "Sterile Gauze label missing"
    assert any("Sterile Gloves"      in l for l in labels), "Sterile Gloves label missing"
    assert any("Medical Tape"        in l for l in labels), "Medical Tape label missing"
    assert any("Povidone-Iodine"     in l for l in labels), "Povidone-Iodine label missing"
    assert any("Normal Saline"       in l for l in labels), "Normal Saline label missing"
    assert any("Vaseline Gauze"      in l for l in labels), "Vaseline Gauze label missing"
    assert any("Rolled Gauze"        in l for l in labels), "Rolled Gauze label missing"
    assert any("Antibiotic Cream"    in l for l in labels), "Antibiotic Cream label missing"
    assert any("Under Pad"           in l for l in labels), "Under Pad label missing"
    assert "أخرى"                        in labels,          "أخرى label missing"
    print("all 10 supply labels present OK")


def test_woundcare_supplies_arabic_names_in_labels():
    """Arabic names must be embedded in the bilingual labels."""
    from modules.healthcare.woundcare.constants import WOUNDCARE_SUPPLIES_OPTIONS
    labels = [o.label for o in WOUNDCARE_SUPPLIES_OPTIONS]
    assert any("شاش معقم"        in l for l in labels), "شاش معقم missing"
    assert any("قفازات معقمة"    in l for l in labels), "قفازات معقمة missing"
    assert any("أيودين"           in l for l in labels), "أيودين missing"
    assert any("نورمال سالين"     in l for l in labels), "نورمال سالين missing"
    assert any("شاش فازلين"       in l for l in labels), "شاش فازلين missing"
    assert any("شاش شريط"         in l for l in labels), "شاش شريط missing"
    assert any("مرهم مضاد حيوي"  in l for l in labels), "مرهم مضاد حيوي missing"
    assert any("فرشة مجارحة"      in l for l in labels), "فرشة مجارحة missing"
    print("Arabic names embedded in supply labels OK")


def test_woundcare_supplies_other_is_last():
    """أخرى (sup_other) must be the last entry in the supplies list."""
    from modules.healthcare.woundcare.constants import WOUNDCARE_SUPPLIES_OPTIONS, SUPPLIES_OTHER_ID
    assert WOUNDCARE_SUPPLIES_OPTIONS[-1].id == SUPPLIES_OTHER_ID
    assert WOUNDCARE_SUPPLIES_OPTIONS[-1].label == "أخرى"
    print("sup_other is last OK")


def test_woundcare_review_supplies_section_label():
    """Review must use '🧰 *المستلزمات الطبية المستخدمة:*' — not the old short label."""
    from modules.healthcare.woundcare.session import WoundcareAddSession
    from modules.healthcare.woundcare.views import build_review
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.patient_name              = "اختبار"
    s.operation_name            = "تضميد"
    s.phase_label               = "قبل العملية"
    s.medical_department_labels = ["الجراحة"]
    s.condition_ids             = ["clean"]
    s.condition_labels          = ["الجرح نظيف (لا احمرار أو إفرازات)"]
    s.condition_other           = ""
    s.supply_labels             = ["Sterile Gauze — شاش معقم", "Medical Tape"]
    s.specialist_name           = "د. فضل"
    s.images                    = []
    text, kb = build_review(s)
    assert "🧰 *المستلزمات الطبية المستخدمة:*"  in text
    assert "🧰 *المستلزمات الطبية:*"           not in text   # old label must NOT appear
    assert "• Sterile Gauze"                      in text
    assert "• Medical Tape"                        in text
    print("review supplies section label updated OK")


def test_woundcare_supplies_other_prompt_view():
    """build_supplies_other_prompt shows selected supplies (excluding 'أخرى')."""
    from modules.healthcare.woundcare.session import WoundcareAddSession
    from modules.healthcare.woundcare.views import build_supplies_other_prompt
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.patient_name  = "نورة"
    s.supply_labels = ["Sterile Gauze — شاش معقم", "أخرى"]
    text, kb = build_supplies_other_prompt(s)
    assert "نورة"                          in text
    assert "Sterile Gauze"                  in text   # known label shown
    assert "أخرى"                         not in text  # filtered out
    buttons = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "wca:back"   in buttons
    assert "wca:cancel" in buttons
    print("build_supplies_other_prompt view OK")


def test_woundcare_supplies_session_persistence():
    """supply_ids / supply_labels survive save/load round-trip with new labels."""
    from modules.healthcare.woundcare.session import WoundcareAddSession, STEP_SUPPLIES
    ud = {}
    s = WoundcareAddSession.create(ud)
    s.supply_ids    = ["gauze", "betadine", "sup_other"]
    s.supply_labels = [
        "Sterile Gauze — شاش معقم",
        "Povidone-Iodine — أيودين",
        "أخرى",
    ]
    s.step = STEP_SUPPLIES
    s.save(ud)

    loaded = WoundcareAddSession.load(ud)
    assert loaded.supply_ids    == ["gauze", "betadine", "sup_other"]
    assert loaded.supply_labels == [
        "Sterile Gauze — شاش معقم",
        "Povidone-Iodine — أيودين",
        "أخرى",
    ]
    assert loaded.step == STEP_SUPPLIES
    print("supply session persistence with new labels OK")


# ─────────────────────────────────────────────────────────────────────────────
# E. Woundcare DB save
# ─────────────────────────────────────────────────────────────────────────────

def test_woundcare_db_save():
    from modules.healthcare.woundcare.models import save_wound_record
    saved = save_wound_record(
        patient_id=                None,
        patient_name=              "محمد علي",
        medical_department_ids=    ["ortho"],
        medical_department_labels= ["العظام"],
        operation_name=            "شق وتصريف",
        phase=                     "phase_pre_op",
        phase_label=               "قبل العملية",
        condition_description=     "جرح عميق",
        supply_ids=                ["gauze", "gloves"],
        supply_labels=             ["شاش معقم", "قفازات معقمة"],
        images=                    [],
        notes=                     "ملاحظة اختبار",
        specialist_name=           "د. فضل",
        created_by=                999,
    )
    assert saved.record_id > 0
    assert saved.patient_name == "محمد علي"
    assert saved.specialist_name == "د. فضل"
    assert saved.image_count == 0
    assert saved.operation_name == "شق وتصريف"
    print(f"woundcare DB save OK  id={saved.record_id}")


def test_woundcare_db_save_persisted():
    """Verify the record actually landed in the DB."""
    from modules.healthcare.woundcare.models import save_wound_record
    saved = save_wound_record(
        patient_id=None, patient_name="اختبار قاعدة البيانات",
        medical_department_ids=    ["cardio"],
        medical_department_labels= ["القلب"],
        operation_name=            "تنظيف جرح وتضميد",
        phase=                     "phase_chronic",
        phase_label=               "مجارحة دورية / جرح مزمن",
        condition_description=     "جرح مزمن",
        supply_ids=                [],
        supply_labels=             [],
        images=[], notes="", specialist_name="د. زكريا", created_by=1,
    )
    with _TestSessionLocal() as s:
        from db.models import WoundRecord
        row = s.query(WoundRecord).filter_by(id=saved.record_id).first()
        assert row is not None
        assert row.patient_name == "اختبار قاعدة البيانات"
        assert row.operation_name == "تنظيف جرح وتضميد"
    print("woundcare DB persistence OK")


# ─────────────────────────────────────────────────────────────────────────────
# F. Medical Follow-up session
# ─────────────────────────────────────────────────────────────────────────────

def test_followup_session_lifecycle():
    from modules.healthcare.medical_followup.session import (
        MedicalFollowupSession, STEP_DATE,
    )
    ud = {}
    s = MedicalFollowupSession.create(ud)
    assert s.step == STEP_DATE          # date-first: first step is date selection
    assert s.medical_department_ids  == []
    assert s.procedure_type_ids      == []
    assert s.complaint_ids           == []
    assert s.vitals_temp             == ""
    assert s.vitals_bp               == ""
    assert s.vitals_pulse            == ""
    assert s.vitals_spo2             == ""
    assert s.meds_supply_ids         == []
    assert s.specialist_name         == ""
    assert s.created_at              != ""
    MedicalFollowupSession.clear(ud)
    assert MedicalFollowupSession.load(ud) is None
    print("followup session lifecycle OK")


def test_followup_session_vitals_persistence():
    """Vitals fields survive save/load round-trip."""
    from modules.healthcare.medical_followup.session import (
        MedicalFollowupSession, STEP_VITALS_SPO2,
    )
    ud = {}
    s = MedicalFollowupSession.create(ud)
    s.vitals_temp  = "37.5 C"
    s.vitals_bp    = "120/80"
    s.vitals_pulse = "78"
    s.vitals_spo2  = "98%"
    s.step         = STEP_VITALS_SPO2
    s.save(ud)

    loaded = MedicalFollowupSession.load(ud)
    assert loaded.vitals_temp  == "37.5 C"
    assert loaded.vitals_bp    == "120/80"
    assert loaded.vitals_pulse == "78"
    assert loaded.vitals_spo2  == "98%"
    assert loaded.step         == STEP_VITALS_SPO2
    print("followup vitals persistence OK")


# ─────────────────────────────────────────────────────────────────────────────
# F2. Medical Follow-up views
# ─────────────────────────────────────────────────────────────────────────────

def test_followup_specialist_prompt_fixed():
    """Specialist prompt has 3 fixed buttons, no skip."""
    from modules.healthcare.medical_followup.session import MedicalFollowupSession
    from modules.healthcare.medical_followup.views import build_specialist_prompt
    ud = {}
    s = MedicalFollowupSession.create(ud)
    s.patient_name = "اختبار"
    text, kb = build_specialist_prompt(s)
    assert "اسم الصحي" in text
    buttons = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "hcfu:sp_fadl"     in buttons
    assert "hcfu:sp_sarour"   in buttons
    assert "hcfu:sp_zakariya" in buttons
    assert "hcfu:cancel"      in buttons
    assert not any("skip" in b for b in buttons), "followup specialist must not have skip"
    print("followup specialist_prompt 3-button OK")


def test_followup_review_shows_all_fields():
    from modules.healthcare.medical_followup.session import MedicalFollowupSession
    from modules.healthcare.medical_followup.views import build_review
    ud = {}
    s = MedicalFollowupSession.create(ud)
    s.patient_name              = "سارة خالد"
    s.medical_department_labels = ["القلب"]
    s.procedure_type_labels     = ["فحص طبي روتيني"]
    s.complaint_labels          = ["ألم"]
    s.vitals_temp               = "37.2"
    s.vitals_bp                 = "120/80"
    s.vitals_pulse              = "75"
    s.vitals_spo2               = "99%"
    s.meds_supply_labels        = ["مسكن ألم"]
    s.notes                     = "المريضة بحالة جيدة"
    s.specialist_name           = "د. سرور"
    s.images                    = []
    text, kb = build_review(s)
    assert "سارة خالد"        in text
    assert "القلب"             in text
    assert "فحص طبي روتيني"   in text
    assert "ألم"               in text
    assert "37.2"              in text
    assert "120/80"            in text
    assert "75"                in text
    assert "99%"               in text
    assert "مسكن ألم"          in text
    assert "المريضة بحالة جيدة" in text
    assert "د. سرور"           in text
    buttons = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "hcfu:confirm"         in buttons
    assert "hcfu:edit_notes"      in buttons
    assert "hcfu:edit_specialist" in buttons
    print("followup review all fields OK")


# ─────────────────────────────────────────────────────────────────────────────
# F3. Medical Follow-up — procedure type options update
# ─────────────────────────────────────────────────────────────────────────────

def test_followup_procedure_type_options_count():
    """PROCEDURE_TYPE_OPTIONS must have exactly 6 entries (no أخرى)."""
    from modules.healthcare.medical_followup.constants import PROCEDURE_TYPE_OPTIONS
    assert len(PROCEDURE_TYPE_OPTIONS) == 6, (
        f"Expected 6 procedure type options, got {len(PROCEDURE_TYPE_OPTIONS)}"
    )
    print(f"PROCEDURE_TYPE_OPTIONS count OK  ({len(PROCEDURE_TYPE_OPTIONS)} options)")


def test_followup_procedure_type_options_labels():
    """All 6 official procedure type labels must be present."""
    from modules.healthcare.medical_followup.constants import PROCEDURE_TYPE_OPTIONS
    labels = [o.label for o in PROCEDURE_TYPE_OPTIONS]
    assert "معاينة وصرف دواء"                              in labels
    assert "إجراءات تمريضية (تركيب فراشة - ضرب إبر)"     in labels
    assert "إجراءات تمريضية (تغيير قسطرة بولية)"          in labels
    assert "متابعة ميدانية بعد خروج من المستشفى"          in labels
    assert "متابعة ميدانية دورية"                          in labels
    assert "حالة طارئة"                                    in labels
    print("PROCEDURE_TYPE_OPTIONS all 6 labels present OK")


def test_followup_procedure_type_ids_present():
    """All 6 IDs must be non-empty and unique."""
    from modules.healthcare.medical_followup.constants import PROCEDURE_TYPE_OPTIONS
    ids = [o.id for o in PROCEDURE_TYPE_OPTIONS]
    assert "exam_med"      in ids
    assert "nursing_iv"    in ids
    assert "nursing_cath"  in ids
    assert "field_post_dc" in ids
    assert "field_routine" in ids
    assert "emergency"     in ids
    assert len(set(ids)) == len(ids), "All procedure type IDs must be unique"
    print("PROCEDURE_TYPE_OPTIONS IDs OK")


def test_followup_procedure_type_no_other():
    """PROCEDURE_TYPE_OPTIONS must NOT contain an 'أخرى' option."""
    from modules.healthcare.medical_followup.constants import PROCEDURE_TYPE_OPTIONS
    ids    = [o.id    for o in PROCEDURE_TYPE_OPTIONS]
    labels = [o.label for o in PROCEDURE_TYPE_OPTIONS]
    assert "أخرى" not in labels, "procedure type must not have أخرى option"
    # No OTHER_ID constant expected for this multiselect
    print("PROCEDURE_TYPE_OPTIONS has no أخرى OK")


def test_followup_procedure_type_well_formed():
    """Each option must have a non-empty id, label, and icon."""
    from modules.healthcare.medical_followup.constants import PROCEDURE_TYPE_OPTIONS
    from shared.multiselect._models import Option
    for opt in PROCEDURE_TYPE_OPTIONS:
        assert isinstance(opt, Option)
        assert opt.id,    f"empty id in {opt!r}"
        assert opt.label, f"empty label in {opt!r}"
        assert opt.icon,  f"empty icon in {opt!r}"
    print("PROCEDURE_TYPE_OPTIONS well-formed OK")


def test_followup_procedure_type_session_persistence():
    """procedure_type_ids / procedure_type_labels persist through save/load."""
    from modules.healthcare.medical_followup.session import (
        MedicalFollowupSession, STEP_PROC_TYPE,
    )
    from modules.healthcare.medical_followup.constants import PROCEDURE_TYPE_OPTIONS
    ud = {}
    s = MedicalFollowupSession.create(ud)
    # Pick first two options from the new list
    s.procedure_type_ids    = [PROCEDURE_TYPE_OPTIONS[0].id, PROCEDURE_TYPE_OPTIONS[4].id]
    s.procedure_type_labels = [PROCEDURE_TYPE_OPTIONS[0].label, PROCEDURE_TYPE_OPTIONS[4].label]
    s.step                  = STEP_PROC_TYPE
    s.save(ud)

    loaded = MedicalFollowupSession.load(ud)
    assert loaded.procedure_type_ids    == s.procedure_type_ids
    assert loaded.procedure_type_labels == s.procedure_type_labels
    assert loaded.step                  == STEP_PROC_TYPE
    print("procedure_type session persistence OK")


def test_followup_review_procedure_type_section():
    """Review renders '📋 *نوع الإجراء:*' with new-label bullet points."""
    from modules.healthcare.medical_followup.session import MedicalFollowupSession
    from modules.healthcare.medical_followup.views import build_review
    ud = {}
    s = MedicalFollowupSession.create(ud)
    s.patient_name              = "اختبار"
    s.medical_department_labels = ["الجراحة"]
    s.procedure_type_labels     = ["معاينة وصرف دواء", "حالة طارئة"]
    s.complaint_labels          = ["ألم"]
    s.vitals_temp               = "37.0"
    s.vitals_bp                 = "120/80"
    s.vitals_pulse              = "72"
    s.vitals_spo2               = "98%"
    s.meds_supply_labels        = ["مضاد حيوي"]
    s.specialist_name           = "د. فضل"
    s.images                    = []
    text, kb = build_review(s)
    assert "📋 *نوع الإجراء:*"  in text
    assert "• معاينة وصرف دواء" in text
    assert "• حالة طارئة"       in text
    print("review procedure_type section with new labels OK")


# ─────────────────────────────────────────────────────────────────────────────
# F4. Medical Follow-up — complaint / symptom options update (Task G)
# ─────────────────────────────────────────────────────────────────────────────

def test_followup_complaint_options_count():
    """COMPLAINT_OPTIONS must have exactly 31 entries (30 named + أخرى)."""
    from modules.healthcare.medical_followup.constants import COMPLAINT_OPTIONS
    assert len(COMPLAINT_OPTIONS) == 31, (
        f"Expected 31 complaint options, got {len(COMPLAINT_OPTIONS)}"
    )
    print(f"complaint options count OK ({len(COMPLAINT_OPTIONS)})")


def test_followup_complaint_options_well_formed():
    """Every option must have a non-empty id, label, and icon."""
    from modules.healthcare.medical_followup.constants import COMPLAINT_OPTIONS
    from shared.multiselect._models import Option
    for opt in COMPLAINT_OPTIONS:
        assert isinstance(opt, Option)
        assert opt.id,    f"Option has empty id: {opt}"
        assert opt.label, f"Option has empty label: {opt}"
        assert opt.icon,  f"Option has empty icon: {opt}"
    print("complaint options well-formed OK")


def test_followup_complaint_ids_unique():
    """No two complaint options may share the same ID."""
    from modules.healthcare.medical_followup.constants import COMPLAINT_OPTIONS
    ids = [o.id for o in COMPLAINT_OPTIONS]
    assert len(ids) == len(set(ids)), f"Duplicate complaint IDs: {ids}"
    print("complaint option IDs unique OK")


def test_followup_complaint_other_is_last():
    """'أخرى' (id=cmp_other) must be the very last complaint option."""
    from modules.healthcare.medical_followup.constants import COMPLAINT_OPTIONS
    last = COMPLAINT_OPTIONS[-1]
    assert last.id    == "cmp_other", f"Last id should be cmp_other, got {last.id}"
    assert last.label == "أخرى",      f"Last label should be أخرى, got {last.label}"
    print("complaint other is last OK")


def test_followup_complaint_other_id_constant():
    """COMPLAINT_OTHER_ID constant must equal 'cmp_other'."""
    from modules.healthcare.medical_followup.constants import COMPLAINT_OTHER_ID
    assert COMPLAINT_OTHER_ID == "cmp_other"
    print("COMPLAINT_OTHER_ID constant OK")


def test_followup_complaint_key_ids_present():
    """Spot-check that representative IDs are present (DB stability)."""
    from modules.healthcare.medical_followup.constants import COMPLAINT_OPTIONS
    ids = {o.id for o in COMPLAINT_OPTIONS}
    required = {
        "visit_routine", "visit_post_op", "pain_surgical", "fever_chills",
        "headache", "dizziness", "dry_cough", "wet_cough", "nasal",
        "abdominal_pain", "diarrhea", "nausea", "vomiting", "bloating",
        "constipation", "gastric_pain", "mouth_ulcers", "anal_worms",
        "dysuria", "flank_pain", "urinary_freq", "catheter_change",
        "iv_fluids", "iv_antibiotic", "iv_gcsf", "skin_rash",
        "anxiety_insomnia", "back_pain", "joint_pain", "sore_throat",
        "cmp_other",
    }
    missing = required - ids
    assert not missing, f"Missing complaint IDs: {missing}"
    print(f"complaint key IDs present OK ({len(ids)} total)")


def test_followup_complaint_labels_spot_check():
    """Spot-check a sample of Arabic labels in COMPLAINT_OPTIONS."""
    from modules.healthcare.medical_followup.constants import COMPLAINT_OPTIONS
    labels = [o.label for o in COMPLAINT_OPTIONS]
    assert any("زيارة متابعة دورية"      in l for l in labels)
    assert any("حمى وقشعريرة"           in l for l in labels)
    assert any("صداع"                    in l for l in labels)
    assert any("سعال جاف"               in l for l in labels)
    assert any("إسهال"                   in l for l in labels)
    assert any("غثيان"                   in l for l in labels)
    assert any("إمساك"                   in l for l in labels)
    assert any("حرقة أثناء التبول"       in l for l in labels)
    assert any("قسطرة"                   in l for l in labels)
    assert any("G-CSF"                   in l for l in labels)
    assert any("أخرى"                    in l for l in labels)
    print("complaint labels spot-check OK")


def test_followup_complaint_session_persistence():
    """complaint_ids and complaint_labels survive save→load round-trip."""
    from modules.healthcare.medical_followup.session import MedicalFollowupSession
    ud = {}
    s = MedicalFollowupSession.create(ud)
    s.complaint_ids    = ["fever_chills", "headache", "cmp_other"]
    s.complaint_labels = ["حمى وقشعريرة", "صداع وألم في الرأس", "آلام مستمرة"]
    s.save(ud)
    s2 = MedicalFollowupSession.load(ud)
    assert s2.complaint_ids    == ["fever_chills", "headache", "cmp_other"]
    assert s2.complaint_labels == ["حمى وقشعريرة", "صداع وألم في الرأس", "آلام مستمرة"]
    print("complaint session persistence OK")


def test_followup_complaint_session_defaults_empty():
    """Fresh session starts with empty complaint lists."""
    from modules.healthcare.medical_followup.session import MedicalFollowupSession
    ud = {}
    s = MedicalFollowupSession.create(ud)
    assert s.complaint_ids    == []
    assert s.complaint_labels == []
    print("complaint session defaults empty OK")


def test_followup_complaint_other_prompt_view():
    """build_complaint_other_prompt must mention the patient and previously selected complaints."""
    from modules.healthcare.medical_followup.session import MedicalFollowupSession
    from modules.healthcare.medical_followup.views import build_complaint_other_prompt
    ud = {}
    s = MedicalFollowupSession.create(ud)
    s.patient_name     = "محمد عبدالله"
    s.complaint_ids    = ["fever_chills", "cmp_other"]
    s.complaint_labels = ["حمى وقشعريرة", "أخرى"]
    text, kb = build_complaint_other_prompt(s)
    assert "محمد عبدالله" in text
    assert "حمى وقشعريرة" in text
    kb_str = str(kb)
    assert "back"   in kb_str
    assert "cancel" in kb_str
    print("build_complaint_other_prompt view OK")


def test_followup_review_complaint_section_header():
    """build_review must use '😷 *الشكوى الرئيسية / الأعراض:*' header."""
    from modules.healthcare.medical_followup.session import MedicalFollowupSession
    from modules.healthcare.medical_followup.views import build_review
    ud = {}
    s = MedicalFollowupSession.create(ud)
    s.patient_name              = "فاطمة علي"
    s.medical_department_ids    = ["gen_med"]
    s.medical_department_labels = ["الطب العام"]
    s.procedure_type_ids        = ["exam_med"]
    s.procedure_type_labels     = ["معاينة وصرف دواء"]
    s.complaint_ids             = ["fever_chills", "headache"]
    s.complaint_labels          = ["حمى وقشعريرة", "صداع وألم في الرأس"]
    s.vitals_temp               = "37.5"
    s.vitals_bp                 = "120/80"
    s.vitals_pulse              = "88"
    s.vitals_spo2               = "98%"
    s.meds_supply_ids           = []
    s.meds_supply_labels        = []
    s.specialist_name           = "د. فضل"
    text, kb = build_review(s)
    assert "😷 *الشكوى الرئيسية / الأعراض:*" in text, (
        "Review must contain '😷 *الشكوى الرئيسية / الأعراض:*'"
    )
    assert "• حمى وقشعريرة"       in text
    assert "• صداع وألم في الرأس" in text
    print("review complaint section header OK")


def test_followup_review_complaint_bullet_list():
    """Review renders each complaint label as a bullet point."""
    from modules.healthcare.medical_followup.session import MedicalFollowupSession
    from modules.healthcare.medical_followup.views import build_review
    ud = {}
    s = MedicalFollowupSession.create(ud)
    s.patient_name              = "خالد"
    s.medical_department_ids    = ["ortho"]
    s.medical_department_labels = ["العظام"]
    s.procedure_type_ids        = ["field_routine"]
    s.procedure_type_labels     = ["متابعة ميدانية دورية"]
    s.complaint_ids             = ["back_pain", "joint_pain", "dizziness"]
    s.complaint_labels          = ["ألم في الظهر", "ألم في المفاصل", "دوخة ودوار"]
    s.vitals_temp               = "36.8"
    s.vitals_bp                 = "110/70"
    s.vitals_pulse              = "72"
    s.vitals_spo2               = "99%"
    s.meds_supply_ids           = []
    s.meds_supply_labels        = []
    s.specialist_name           = "د. سرور"
    text, kb = build_review(s)
    assert "• ألم في الظهر"     in text
    assert "• ألم في المفاصل"   in text
    assert "• دوخة ودوار"       in text
    print("review complaint bullet list OK")


def test_followup_complaint_other_label_replaced():
    """When STEP_COMPLAINT_OTHER text is entered, 'أخرى' in complaint_labels is replaced."""
    # This mirrors the logic in flow.py _handle_text_input (STEP_COMPLAINT_OTHER branch)
    complaint_labels = ["حمى وقشعريرة", "أخرى"]
    free_text = "ألم في الأذن"
    updated = [free_text if lbl == "أخرى" else lbl for lbl in complaint_labels]
    assert updated == ["حمى وقشعريرة", "ألم في الأذن"]
    assert "أخرى" not in updated
    print("complaint_other label replacement logic OK")


# ─────────────────────────────────────────────────────────────────────────────
# F5. Medical Follow-up — medications & supplies options update (Task H)
# ─────────────────────────────────────────────────────────────────────────────

def test_followup_meds_options_count():
    """MEDS_SUPPLY_OPTIONS must have exactly 65 entries."""
    from modules.healthcare.medical_followup.constants import MEDS_SUPPLY_OPTIONS
    assert len(MEDS_SUPPLY_OPTIONS) == 65, (
        f"Expected 65 meds/supply options, got {len(MEDS_SUPPLY_OPTIONS)}"
    )
    print(f"meds options count OK ({len(MEDS_SUPPLY_OPTIONS)})")


def test_followup_meds_options_well_formed():
    """Every option must have a non-empty id, label, and icon."""
    from modules.healthcare.medical_followup.constants import MEDS_SUPPLY_OPTIONS
    from shared.multiselect._models import Option
    for opt in MEDS_SUPPLY_OPTIONS:
        assert isinstance(opt, Option)
        assert opt.id,    f"Option has empty id: {opt}"
        assert opt.label, f"Option has empty label: {opt}"
        assert opt.icon,  f"Option has empty icon: {opt}"
    print("meds options well-formed OK")


def test_followup_meds_ids_unique():
    """No two meds/supply options may share the same ID."""
    from modules.healthcare.medical_followup.constants import MEDS_SUPPLY_OPTIONS
    ids = [o.id for o in MEDS_SUPPLY_OPTIONS]
    assert len(ids) == len(set(ids)), f"Duplicate meds IDs: {[i for i in ids if ids.count(i) > 1]}"
    print("meds option IDs unique OK")


def test_followup_meds_other_is_last():
    """'Other (Specify)' (id=ms_other) must be the very last meds/supply option."""
    from modules.healthcare.medical_followup.constants import MEDS_SUPPLY_OPTIONS
    last = MEDS_SUPPLY_OPTIONS[-1]
    assert last.id    == "ms_other",        f"Last id should be ms_other, got {last.id}"
    assert last.label == "Other (Specify)", f"Last label should be 'Other (Specify)', got {last.label}"
    print("meds other is last OK")


def test_followup_meds_other_id_constant():
    """MEDS_SUPPLY_OTHER_ID constant must equal 'ms_other'."""
    from modules.healthcare.medical_followup.constants import MEDS_SUPPLY_OTHER_ID
    assert MEDS_SUPPLY_OTHER_ID == "ms_other"
    print("MEDS_SUPPLY_OTHER_ID constant OK")


def test_followup_meds_key_ids_present():
    """Spot-check that one representative ID from each category is present."""
    from modules.healthcare.medical_followup.constants import MEDS_SUPPLY_OPTIONS
    ids = {o.id for o in MEDS_SUPPLY_OPTIONS}
    required = {
        # IV
        "iv_pcm_inf", "iv_dns_inf", "iv_ns_inf", "iv_rl_inf",
        "iv_panto_inj", "iv_rani_inj", "iv_hyos_inj", "iv_vitc_inj",
        "iv_vitb_inj", "iv_diclo_inj", "iv_ceft_inj", "iv_emes_inj",
        "iv_meto_inj", "iv_tram_inj", "iv_dexa_inj", "iv_neuro_inj", "iv_metro_inf",
        # Oral analgesics
        "oral_dolo", "oral_ultr", "oral_diclo", "oral_flex",
        # Respiratory
        "resp_chest", "resp_dry_syp", "resp_exp_syp", "resp_mont", "resp_lcet",
        # Antibiotics
        "ab_augm", "ab_azith", "ab_levof", "ab_cotri", "ab_niftas", "ab_metro",
        # GI
        "gi_pantoD_10", "gi_pantoD_1m", "gi_panto40", "gi_emes4", "gi_dompe",
        "gi_hyos_tab", "gi_mucaine", "gi_colospa", "gi_cizasp", "gi_bisth",
        "gi_esog", "gi_somp_hp",
        # Antiparasitic
        "ap_alben", "ap_dulco", "ap_duphal",
        # Urology
        "uro_tams", "uro_urisp", "uro_cyst", "uro_urik",
        # Supplements
        "supl_vitc", "supl_multiv", "supl_appet", "supl_plac",
        # Topical
        "top_mupi", "top_wan", "top_mug",
        # Medical supplies
        "msup_cann", "msup_ivset", "msup_syr", "msup_cath", "msup_ubag",
        "msup_none", "ms_other",
    }
    missing = required - ids
    assert not missing, f"Missing meds IDs: {missing}"
    print(f"meds key IDs present OK ({len(ids)} total)")


def test_followup_meds_labels_spot_check():
    """Spot-check a sample of labels from each category."""
    from modules.healthcare.medical_followup.constants import MEDS_SUPPLY_OPTIONS
    labels = [o.label for o in MEDS_SUPPLY_OPTIONS]
    # IV
    assert any("Paracetamol 1g infusion"    in l for l in labels)
    assert any("DNS infusion"               in l for l in labels)
    assert any("Ceftriaxone 1g INJ."        in l for l in labels)
    assert any("Metronidazole infusion"     in l for l in labels)
    # Oral
    assert any("Dolo tab"                   in l for l in labels)
    assert any("Flexon MR"                  in l for l in labels)
    # Respiratory
    assert any("Cheston Cold Total"         in l for l in labels)
    assert any("Montelukast"                in l for l in labels)
    # Antibiotics
    assert any("Augmentin 625mg"            in l for l in labels)
    assert any("Levofloxacin 750mg"         in l for l in labels)
    # GI
    assert any("Pantosec D SR"              in l for l in labels)
    assert any("Sompraz HP kit"             in l for l in labels)
    # Antiparasitic
    assert any("Albendazole"                in l for l in labels)
    assert any("Duphalac"                   in l for l in labels)
    # Urology
    assert any("Tamsulosin"                 in l for l in labels)
    assert any("Urikind KM"                 in l for l in labels)
    # Supplements
    assert any("Multivitamin"               in l for l in labels)
    assert any("Placida"                    in l for l in labels)
    # Topical
    assert any("Mupirocin ointment"         in l for l in labels)
    assert any("Mouth ulcer gel"            in l for l in labels)
    # Medical supplies
    assert any("IV cannula"                 in l for l in labels)
    assert any("Urinary catheter"           in l for l in labels)
    assert any("لا يحتاج إعطاء"            in l for l in labels)
    assert any("Other (Specify)"            in l for l in labels)
    print("meds labels spot-check OK")


def test_followup_meds_icons_match_categories():
    """Verify each category group uses the correct icon."""
    from modules.healthcare.medical_followup.constants import MEDS_SUPPLY_OPTIONS
    icon_map = {o.id: o.icon for o in MEDS_SUPPLY_OPTIONS}
    assert icon_map["iv_pcm_inf"]   == "💉"
    assert icon_map["oral_dolo"]    == "💊"
    assert icon_map["resp_chest"]   == "🫁"
    assert icon_map["ab_augm"]      == "💊"
    assert icon_map["gi_pantoD_10"] == "💊"
    assert icon_map["ap_alben"]     == "🪱"
    assert icon_map["uro_tams"]     == "💊"
    assert icon_map["supl_vitc"]    == "🍊"
    assert icon_map["top_mupi"]     == "🧴"
    assert icon_map["msup_cann"]    == "🏥"
    assert icon_map["msup_none"]    == "✅"
    assert icon_map["ms_other"]     == "📝"
    print("meds category icons OK")


def test_followup_meds_session_persistence():
    """meds_supply_ids and meds_supply_labels survive save→load round-trip."""
    from modules.healthcare.medical_followup.session import MedicalFollowupSession
    ud = {}
    s = MedicalFollowupSession.create(ud)
    s.meds_supply_ids    = ["iv_pcm_inf", "ab_augm", "msup_cann"]
    s.meds_supply_labels = [
        "Paracetamol 1g infusion",
        "Augmentin 625mg tab 1-1-1 for 5 days",
        "IV cannula and cannula fixator",
    ]
    s.save(ud)
    s2 = MedicalFollowupSession.load(ud)
    assert s2.meds_supply_ids    == ["iv_pcm_inf", "ab_augm", "msup_cann"]
    assert s2.meds_supply_labels == [
        "Paracetamol 1g infusion",
        "Augmentin 625mg tab 1-1-1 for 5 days",
        "IV cannula and cannula fixator",
    ]
    print("meds session persistence OK")


def test_followup_meds_session_defaults_empty():
    """Fresh session starts with empty meds lists."""
    from modules.healthcare.medical_followup.session import MedicalFollowupSession
    ud = {}
    s = MedicalFollowupSession.create(ud)
    assert s.meds_supply_ids    == []
    assert s.meds_supply_labels == []
    print("meds session defaults empty OK")


def test_followup_meds_other_prompt_view():
    """build_meds_supply_other_prompt shows patient name and already-selected items."""
    from modules.healthcare.medical_followup.session import MedicalFollowupSession
    from modules.healthcare.medical_followup.views import build_meds_supply_other_prompt
    ud = {}
    s = MedicalFollowupSession.create(ud)
    s.patient_name      = "أحمد السيد"
    s.meds_supply_ids   = ["iv_pcm_inf", "ms_other"]
    s.meds_supply_labels = ["Paracetamol 1g infusion", "Other (Specify)"]
    text, kb = build_meds_supply_other_prompt(s)
    assert "أحمد السيد"              in text
    assert "Paracetamol 1g infusion" in text   # known item shown
    assert "Other (Specify)"    not in text    # filtered out from known list
    kb_str = str(kb)
    assert "back"   in kb_str
    assert "cancel" in kb_str
    print("build_meds_supply_other_prompt view OK")


def test_followup_meds_other_label_replaced():
    """When STEP_MEDS_SUPPLY_OTHER text is entered, 'Other (Specify)' in labels is replaced."""
    meds_labels = ["Paracetamol 1g infusion", "Other (Specify)"]
    free_text   = "Azithromycin 500mg tab OD for 3 days"
    updated = [free_text if lbl == "Other (Specify)" else lbl for lbl in meds_labels]
    assert updated == ["Paracetamol 1g infusion", "Azithromycin 500mg tab OD for 3 days"]
    assert "Other (Specify)" not in updated
    print("meds_other label replacement logic OK")


def test_followup_review_meds_section_header():
    """build_review must use '💊 *الأدوية والمستلزمات الطبية:*' header."""
    from modules.healthcare.medical_followup.session import MedicalFollowupSession
    from modules.healthcare.medical_followup.views import build_review
    ud = {}
    s = MedicalFollowupSession.create(ud)
    s.patient_name              = "سارة محمد"
    s.medical_department_ids    = ["gen_med"]
    s.medical_department_labels = ["الطب العام"]
    s.procedure_type_ids        = ["exam_med"]
    s.procedure_type_labels     = ["معاينة وصرف دواء"]
    s.complaint_ids             = ["fever_chills"]
    s.complaint_labels          = ["حمى وقشعريرة"]
    s.vitals_temp               = "38.2"
    s.vitals_bp                 = "130/85"
    s.vitals_pulse              = "95"
    s.vitals_spo2               = "97%"
    s.meds_supply_ids           = ["iv_pcm_inf", "ab_augm", "msup_cann"]
    s.meds_supply_labels        = [
        "Paracetamol 1g infusion",
        "Augmentin 625mg tab 1-1-1 for 5 days",
        "IV cannula and cannula fixator",
    ]
    s.specialist_name           = "د. فضل"
    text, kb = build_review(s)
    assert "💊 *الأدوية والمستلزمات الطبية:*" in text, (
        "Review must contain '💊 *الأدوية والمستلزمات الطبية:*'"
    )
    assert "• Paracetamol 1g infusion"                  in text
    assert "• Augmentin 625mg tab 1-1-1 for 5 days"    in text
    assert "• IV cannula and cannula fixator"            in text
    print("review meds section header OK")


def test_followup_review_meds_bullet_list():
    """Review renders each selected med/supply as a bullet point."""
    from modules.healthcare.medical_followup.session import MedicalFollowupSession
    from modules.healthcare.medical_followup.views import build_review
    ud = {}
    s = MedicalFollowupSession.create(ud)
    s.patient_name              = "علي حسن"
    s.medical_department_ids    = ["ortho"]
    s.medical_department_labels = ["العظام"]
    s.procedure_type_ids        = ["nursing_iv"]
    s.procedure_type_labels     = ["إجراءات تمريضية (تركيب فراشة - ضرب إبر)"]
    s.complaint_ids             = ["back_pain"]
    s.complaint_labels          = ["ألم في الظهر"]
    s.vitals_temp               = "36.9"
    s.vitals_bp                 = "118/76"
    s.vitals_pulse              = "70"
    s.vitals_spo2               = "99%"
    s.meds_supply_ids           = ["iv_diclo_inj", "iv_vitb_inj", "msup_ivset"]
    s.meds_supply_labels        = [
        "Diclofenac 75mg INJ.",
        "Vitamin B Complex INJ.",
        "IV set",
    ]
    s.specialist_name           = "د. زكريا"
    text, kb = build_review(s)
    assert "• Diclofenac 75mg INJ."    in text
    assert "• Vitamin B Complex INJ."  in text
    assert "• IV set"                  in text
    print("review meds bullet list OK")


def test_followup_meds_no_selection_shows_dash():
    """When no meds selected, review shows '—' for the meds section."""
    from modules.healthcare.medical_followup.session import MedicalFollowupSession
    from modules.healthcare.medical_followup.views import build_review
    ud = {}
    s = MedicalFollowupSession.create(ud)
    s.patient_name              = "خالد"
    s.medical_department_ids    = ["gen_med"]
    s.medical_department_labels = ["الطب العام"]
    s.procedure_type_ids        = ["field_routine"]
    s.procedure_type_labels     = ["متابعة ميدانية دورية"]
    s.complaint_ids             = ["visit_routine"]
    s.complaint_labels          = ["زيارة متابعة دورية (لا توجد شكوى جديدة)"]
    s.vitals_temp               = "36.5"
    s.vitals_bp                 = "115/75"
    s.vitals_pulse              = "68"
    s.vitals_spo2               = "99%"
    s.meds_supply_ids           = []
    s.meds_supply_labels        = []
    s.specialist_name           = "د. فضل"
    text, kb = build_review(s)
    assert "💊 *الأدوية والمستلزمات الطبية:*" in text
    assert "  —" in text   # empty list renders as dash
    print("review meds empty shows dash OK")


# ─────────────────────────────────────────────────────────────────────────────
# G. Medical Follow-up DB save
# ─────────────────────────────────────────────────────────────────────────────

def test_followup_db_save():
    from modules.healthcare.medical_followup.models import save_followup_record
    saved = save_followup_record(
        patient_id=                None,
        patient_name=              "اختبار متابعة",
        medical_department_ids=    ["cardio"],
        medical_department_labels= ["القلب"],
        procedure_type_ids=        ["routine"],
        procedure_type_labels=     ["فحص طبي روتيني"],
        complaint_ids=             ["cmp_pain"],
        complaint_labels=          ["ألم"],
        vitals_temp=               "37.0",
        vitals_bp=                 "120/80",
        vitals_pulse=              "72",
        vitals_spo2=               "98%",
        meds_supply_ids=           ["ms_analgesic"],
        meds_supply_labels=        ["مسكن ألم"],
        images=                    [],
        notes=                     "حالة مستقرة",
        specialist_name=           "د. سرور",
        created_by=                1,
    )
    assert saved.record_id > 0
    assert saved.patient_name == "اختبار متابعة"
    assert saved.specialist_name == "د. سرور"
    assert saved.image_count == 0
    assert "القلب" in saved.department_labels
    assert "فحص طبي روتيني" in saved.procedure_type_labels
    print(f"followup DB save OK  id={saved.record_id}")


def test_followup_db_save_persisted():
    """Verify the record landed in the DB."""
    from modules.healthcare.medical_followup.models import save_followup_record
    saved = save_followup_record(
        patient_id=None, patient_name="اختبار قاعدة المتابعة",
        medical_department_ids=["neuro"], medical_department_labels=["المخ والأعصاب"],
        procedure_type_ids=["post_op"],   procedure_type_labels=["متابعة ما بعد العملية"],
        complaint_ids=["cmp_fever"],      complaint_labels=["حمى / ارتفاع حرارة"],
        vitals_temp="38.5", vitals_bp="110/70", vitals_pulse="90", vitals_spo2="96%",
        meds_supply_ids=["ms_antibiotic"], meds_supply_labels=["مضاد حيوي"],
        images=[], notes="", specialist_name="د. زكريا", created_by=2,
    )
    with _TestSessionLocal() as s:
        from db.models import MedicalFollowupRecord
        row = s.query(MedicalFollowupRecord).filter_by(id=saved.record_id).first()
        assert row is not None
        assert row.patient_name == "اختبار قاعدة المتابعة"
        assert row.vitals_temp  == "38.5"
    print("followup DB persistence OK")


# ─────────────────────────────────────────────────────────────────────────────
# H. Medications
# ─────────────────────────────────────────────────────────────────────────────

def test_medication_session_lifecycle():
    from modules.healthcare.medications.session import (
        MedicationSession, STEP_DATE, STEP_COUNT,
    )
    ud = {}
    s = MedicationSession.create(ud)
    assert s.step == STEP_DATE          # date-first: first step is date selection
    assert s.medical_department_ids    == []
    assert s.medical_department_labels == []
    assert s.item_count == 0
    MedicationSession.clear(ud)
    assert MedicationSession.load(ud) is None
    print("medication session lifecycle OK")


def test_medication_session_dept_persistence():
    from modules.healthcare.medications.session import MedicationSession, STEP_COUNT
    ud = {}
    s = MedicationSession.create(ud)
    s.medical_department_ids    = ["cardio", "ortho"]
    s.medical_department_labels = ["القلب", "العظام"]
    s.item_count = 5
    s.step = STEP_COUNT
    s.save(ud)
    loaded = MedicationSession.load(ud)
    assert loaded.medical_department_ids    == ["cardio", "ortho"]
    assert loaded.medical_department_labels == ["القلب", "العظام"]
    assert loaded.item_count == 5
    print("medication dept+count persistence OK")


def test_medication_db_save():
    from modules.healthcare.medications.models import save_medication_record
    saved = save_medication_record(
        patient_id=None, patient_name="اختبار دواء",
        medical_department_ids=["cardio"], medical_department_labels=["القلب"],
        item_count=3,
        images=[], notes="جرعتان يومياً", specialist_name="سرور",
        created_by=1,
    )
    assert saved.record_id > 0
    assert saved.department_labels == ["القلب"]
    assert saved.item_count == 3
    assert saved.specialist_name == "سرور"
    print(f"medication DB save OK  id={saved.record_id}")


# ─────────────────────────────────────────────────────────────────────────────
# I. Other healthcare
# ─────────────────────────────────────────────────────────────────────────────

def test_other_session_lifecycle():
    from modules.healthcare.other.session import OtherHealthcareSession, STEP_DATE
    ud = {}
    s = OtherHealthcareSession.create(ud)
    assert s.step == STEP_DATE          # date-first: first step is date selection
    OtherHealthcareSession.clear(ud)
    assert OtherHealthcareSession.load(ud) is None
    print("other_hc session lifecycle OK")


def test_other_db_save():
    from modules.healthcare.other.models import save_other_record
    saved = save_other_record(
        patient_id=None, patient_name="اختبار أخرى",
        operation_ids=["vitals"], operation_labels=["قياس العلامات الحيوية"],
        images=[], notes="ضغط طبيعي", specialist_name="الممرض خالد",
        created_by=1,
    )
    assert saved.record_id > 0
    print(f"other_hc DB save OK  id={saved.record_id}")


# ─────────────────────────────────────────────────────────────────────────────
# J. Report publisher (no bot — structural test only)
# ─────────────────────────────────────────────────────────────────────────────

def test_report_publisher_build_text():
    from modules.healthcare.report_publisher import HealthcarePublishData, _build_report_text
    data = HealthcarePublishData(
        workflow_type=   "woundcare",
        workflow_label=  "المجارحة",
        workflow_icon=   "🩺",
        record_id=       42,
        patient_name=    "محمد أحمد",
        operations=      [],
        images=          [],
        notes=           "تمت المعالجة",
        specialist_name= "د. فضل",
        created_by_id=   999,
        created_by_name= "المستخدم 1",
        record_date=     "2026-05-21T10:00:00",
    )
    text = _build_report_text(data)
    assert "محمد أحمد"   in text
    assert "د. فضل"      in text
    assert "تمت المعالجة" in text
    assert "مايو"         in text   # Arabic month in date
    # No extra_sections -> no department section
    assert "القسم الطبي" not in text
    print(f"report publisher text build OK  len={len(text)}")


def test_report_publisher_medications_with_dept():
    """Medications report uses extra_sections for dept + item_count."""
    from modules.healthcare.report_publisher import HealthcarePublishData, _build_report_text
    dept_text = "  • القلب\n  • العظام"
    data = HealthcarePublishData(
        workflow_type=   "medications",
        workflow_label=  "صرف الأدوية",
        workflow_icon=   "💊",
        record_id=       7,
        patient_name=    "سارة خالد",
        extra_sections=  [
            ("🏥 *الأقسام المختارة:*",      dept_text),
            ("🔢 *عدد الأصناف:*  4",        ""),
        ],
        operations=      [],
        images=          [],
        notes=           "",
        specialist_name= "فضل",
        created_by_id=   1,
        created_by_name= "user1",
        record_date=     "2026-05-21T10:00:00",
    )
    text = _build_report_text(data)
    assert "سارة خالد"        in text
    assert "القلب"             in text
    assert "العظام"            in text
    assert "4"                 in text
    assert "الأقسام المختارة" in text
    assert "عدد الأصناف"      in text
    assert "فضل"               in text
    print(f"medications dept report via extra_sections OK  len={len(text)}")


def test_report_publisher_followup_with_vitals():
    """Followup report uses extra_sections including vitals block."""
    from modules.healthcare.report_publisher import HealthcarePublishData, _build_report_text
    data = HealthcarePublishData(
        workflow_type=   "followup",
        workflow_label=  "المتابعة الطبية",
        workflow_icon=   "📋",
        record_id=       15,
        patient_name=    "أحمد علي",
        extra_sections=  [
            ("🏥 *القسم الطبي:*",           "  • القلب"),
            ("📋 *نوع الإجراء:*",           "  • فحص طبي روتيني"),
            ("😷 *الشكوى الرئيسية:*",       "  • ألم"),
            ("❤️ *العلامات الحيوية:*",      "  37.2\n  120/80\n  75\n  98%"),
            ("💊 *الأدوية والمستلزمات:*",   "  • مسكن ألم"),
        ],
        operations=      [],
        images=          [],
        notes=           "",
        specialist_name= "د. زكريا",
        created_by_id=   1,
        created_by_name= "user1",
        record_date=     "2026-05-21T10:00:00",
    )
    text = _build_report_text(data)
    assert "أحمد علي"        in text
    assert "القسم الطبي"     in text
    assert "العلامات الحيوية" in text
    assert "الأدوية والمستلزمات" in text
    print(f"followup vitals report OK  len={len(text)}")


def test_medication_review_shows_dept_and_count():
    """Review screen shows القسم and عدد الأصناف; no medication categories."""
    from modules.healthcare.medications.session import MedicationSession
    from modules.healthcare.medications.views import build_review
    ud = {}
    s = MedicationSession.create(ud)
    s.patient_name              = "ناصر علي"
    s.medical_department_ids    = ["cardio"]
    s.medical_department_labels = ["القلب"]
    s.item_count                = 3
    s.images                    = []
    s.specialist_name           = "زكريا"
    text, kb = build_review(s)
    assert "ناصر علي"          in text
    assert "القلب"              in text
    assert "3"                  in text
    assert "القسم الطبي"       in text
    assert "عدد الأصناف"       in text
    assert "زكريا"              in text
    buttons = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "hcmed:confirm"         in buttons
    assert "hcmed:edit_notes"      in buttons
    assert "hcmed:edit_specialist" in buttons
    print("medication review with dept+count OK")


def test_medication_specialist_prompt_has_three_buttons():
    """Specialist prompt shows exactly 3 staff buttons, no skip."""
    from modules.healthcare.medications.session import MedicationSession
    from modules.healthcare.medications.views import build_specialist_prompt
    ud = {}
    s = MedicationSession.create(ud)
    s.patient_name = "اختبار"
    text, kb = build_specialist_prompt(s)
    assert "اسم الصحي" in text
    all_callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "hcmed:sp_sarour"   in all_callbacks
    assert "hcmed:sp_fadl"     in all_callbacks
    assert "hcmed:sp_zakariya" in all_callbacks
    assert not any("skip_specialist" in cb for cb in all_callbacks)
    print("specialist prompt 3-button OK")


# ─────────────────────────────────────────────────────────────────────────────
# K. Shared department registry
# ─────────────────────────────────────────────────────────────────────────────

def test_shared_department_registry_structure():
    """get_department_options() returns well-formed Option list from shared registry."""
    from shared.departments import get_department_options
    from shared.multiselect._models import Option
    opts = get_department_options(include_other=True)
    assert len(opts) >= 18, f"Expected ≥18 options, got {len(opts)}"
    ids    = [o.id for o in opts]
    labels = [o.label for o in opts]
    # Core specialties present
    assert "neuro"      in ids
    assert "cardio"     in ids
    assert "ortho"      in ids
    assert "oncology"   in ids
    assert "peds"       in ids
    assert "obgyn"      in ids
    assert "rehab"      in ids
    assert "ent"        in ids
    # Expanded specialties from translator registry
    assert "derm"       in ids
    assert "psych"      in ids
    assert "emerg"      in ids
    assert "icu"        in ids
    # "أخرى" appended when include_other=True
    assert "dept_other" in ids
    assert "أخرى"       in labels
    # All options are well-formed
    for o in opts:
        assert isinstance(o, Option)
        assert o.id
        assert o.label
        assert o.icon
    print(f"shared department registry OK  ({len(opts)} options including أخرى)")


def test_shared_department_registry_no_other():
    """include_other=False omits the free-text option."""
    from shared.departments import get_department_options
    opts = get_department_options(include_other=False)
    ids = [o.id for o in opts]
    assert "dept_other" not in ids
    print(f"shared registry no-other OK  ({len(opts)} options)")


def test_shared_department_registry_labels_consistent():
    """DEPARTMENT_OPTIONS in views.py comes from shared registry — same list."""
    from shared.departments import get_department_options
    from modules.healthcare.views import DEPARTMENT_OPTIONS
    shared_opts = get_department_options(include_other=True)
    assert len(DEPARTMENT_OPTIONS) == len(shared_opts), (
        "healthcare DEPARTMENT_OPTIONS and shared registry must have same length"
    )
    for h, s in zip(DEPARTMENT_OPTIONS, shared_opts):
        assert h.id    == s.id,    f"id mismatch: {h.id!r} vs {s.id!r}"
        assert h.label == s.label, f"label mismatch: {h.label!r} vs {s.label!r}"
    print("DEPARTMENT_OPTIONS matches shared registry ✓")


def test_all_healthcare_flows_share_same_departments():
    """
    All three healthcare flows that use 'القسم الطبي' must reference the
    same DEPARTMENT_OPTIONS from modules.healthcare.views (sourced from shared).
    """
    from modules.healthcare.views import DEPARTMENT_OPTIONS as hc_opts
    # woundcare imports directly from healthcare.views
    from modules.healthcare.woundcare.flow import DEPARTMENT_OPTIONS as wc_opts  # type: ignore[attr-defined]
    # medications now imports from healthcare.views too
    from modules.healthcare.medications.flow import DEPARTMENT_OPTIONS as med_opts  # type: ignore[attr-defined]
    assert wc_opts is hc_opts,  "woundcare DEPARTMENT_OPTIONS must be the healthcare.views object"
    assert med_opts is hc_opts, "medications DEPARTMENT_OPTIONS must be the healthcare.views object"
    print("all healthcare flows share single DEPARTMENT_OPTIONS ✓")


def test_shared_translator_hierarchy_structure():
    """PREDEFINED_DEPARTMENTS and DIRECT_DEPARTMENTS are exported from shared registry."""
    from shared.departments import PREDEFINED_DEPARTMENTS, DIRECT_DEPARTMENTS
    assert isinstance(PREDEFINED_DEPARTMENTS, dict)
    assert len(PREDEFINED_DEPARTMENTS) >= 4, "Expect at least 4 main departments"
    assert isinstance(DIRECT_DEPARTMENTS, list)
    assert len(DIRECT_DEPARTMENTS) >= 10, "Expect at least 10 direct departments"
    # Each main dept has a non-empty sub-dept list
    for main, subs in PREDEFINED_DEPARTMENTS.items():
        assert isinstance(subs, list) and len(subs) > 0, \
            f"Main dept {main!r} must have sub-departments"
    print(f"translator registry OK  "
          f"({len(PREDEFINED_DEPARTMENTS)} main, {len(DIRECT_DEPARTMENTS)} direct)")


# ─────────────────────────────────────────────────────────────────────────────
# L. Bootstrap wipe keys include all healthcare sessions
# ─────────────────────────────────────────────────────────────────────────────

def test_bootstrap_healthcare_wipe_keys():
    from core.routing.registry import registry
    reg = registry.get("healthcare")
    assert reg is not None
    wipe = reg.extra_wipe_keys
    assert "_wc_add"    in wipe, "woundcare session key missing from wipe set"
    assert "_hcfu_add"  in wipe, "followup session key missing from wipe set"
    assert "_hcmed_add" in wipe, "medications session key missing from wipe set"
    assert "_hcoth_add" in wipe, "other session key missing from wipe set"
    print(f"bootstrap wipe keys OK: {wipe}")


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_db_wound_record_has_specialist_name()
    test_db_new_tables_exist()
    test_healthcare_menu_has_four_items()
    test_format_arabic_date()
    test_format_arabic_date_iso()
    test_woundcare_session_create_load_clear()
    test_woundcare_session_specialist_persistence()
    test_woundcare_phase_prompt_view()
    test_woundcare_operation_name_prompt_view()
    test_woundcare_specialist_prompt_view()
    test_woundcare_review_shows_all_fields()
    # D2. Wound condition multiselect
    test_wound_condition_options_count()
    test_wound_condition_other_id_constant()
    test_wound_condition_options_labels()
    test_woundcare_session_condition_fields_persist()
    test_woundcare_session_condition_fields_default_empty()
    test_step_description_other_constant_exists()
    test_woundcare_description_other_prompt_view()
    test_woundcare_review_condition_bullet_list()
    test_woundcare_review_condition_other_replaces_placeholder()
    test_woundcare_condition_description_db_text_generation()
    # D3. Supplies options update
    test_woundcare_supplies_options_count()
    test_woundcare_supplies_ids_unchanged()
    test_woundcare_supplies_new_labels()
    test_woundcare_supplies_arabic_names_in_labels()
    test_woundcare_supplies_other_is_last()
    test_woundcare_review_supplies_section_label()
    test_woundcare_supplies_other_prompt_view()
    test_woundcare_supplies_session_persistence()
    # E. DB save
    test_woundcare_db_save()
    test_woundcare_db_save_persisted()
    test_followup_session_lifecycle()
    test_followup_session_vitals_persistence()
    test_followup_specialist_prompt_fixed()
    test_followup_review_shows_all_fields()
    # F3. Procedure type options update
    test_followup_procedure_type_options_count()
    test_followup_procedure_type_options_labels()
    test_followup_procedure_type_ids_present()
    test_followup_procedure_type_no_other()
    test_followup_procedure_type_well_formed()
    test_followup_procedure_type_session_persistence()
    test_followup_review_procedure_type_section()
    # F4. Complaint options update
    test_followup_complaint_options_count()
    test_followup_complaint_options_well_formed()
    test_followup_complaint_ids_unique()
    test_followup_complaint_other_is_last()
    test_followup_complaint_other_id_constant()
    test_followup_complaint_key_ids_present()
    test_followup_complaint_labels_spot_check()
    test_followup_complaint_session_persistence()
    test_followup_complaint_session_defaults_empty()
    test_followup_complaint_other_prompt_view()
    test_followup_review_complaint_section_header()
    test_followup_review_complaint_bullet_list()
    test_followup_complaint_other_label_replaced()
    # F5. Meds & supplies options update
    test_followup_meds_options_count()
    test_followup_meds_options_well_formed()
    test_followup_meds_ids_unique()
    test_followup_meds_other_is_last()
    test_followup_meds_other_id_constant()
    test_followup_meds_key_ids_present()
    test_followup_meds_labels_spot_check()
    test_followup_meds_icons_match_categories()
    test_followup_meds_session_persistence()
    test_followup_meds_session_defaults_empty()
    test_followup_meds_other_prompt_view()
    test_followup_meds_other_label_replaced()
    test_followup_review_meds_section_header()
    test_followup_review_meds_bullet_list()
    test_followup_meds_no_selection_shows_dash()
    test_followup_db_save()
    test_followup_db_save_persisted()
    test_medication_session_lifecycle()
    test_medication_session_dept_persistence()
    test_medication_db_save()
    test_other_session_lifecycle()
    test_other_db_save()
    test_report_publisher_build_text()
    test_report_publisher_medications_with_dept()
    test_report_publisher_followup_with_vitals()
    test_medication_review_shows_dept_and_count()
    test_medication_specialist_prompt_has_three_buttons()
    test_shared_department_registry_structure()
    test_shared_department_registry_no_other()
    test_shared_department_registry_labels_consistent()
    test_all_healthcare_flows_share_same_departments()
    test_shared_translator_hierarchy_structure()
    test_bootstrap_healthcare_wipe_keys()
    print("\nALL HEALTHCARE TESTS PASSED")
