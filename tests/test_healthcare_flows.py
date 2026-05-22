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
    s.patient_name            = "فاطمة أحمد"
    s.operation_name          = "شق وتصريف"
    s.phase_label             = "قبل العملية"
    s.medical_department_labels = ["الجراحة العامة"]
    s.supply_labels           = ["شاش معقم", "قفازات معقمة"]
    s.condition_description   = "جرح عميق مع التهاب"
    s.notes                   = "تمت المعالجة"
    s.specialist_name         = "د. فضل"
    s.images                  = []
    text, kb = build_review(s)
    assert "فاطمة أحمد"       in text
    assert "شق وتصريف"        in text
    assert "قبل العملية"       in text
    assert "شاش معقم"          in text
    assert "تمت المعالجة"      in text
    assert "د. فضل"            in text
    buttons = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "wca:confirm"        in buttons
    assert "wca:edit_notes"     in buttons
    assert "wca:edit_specialist" in buttons
    print("woundcare review view all fields OK")


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
    test_woundcare_db_save()
    test_woundcare_db_save_persisted()
    test_followup_session_lifecycle()
    test_followup_session_vitals_persistence()
    test_followup_specialist_prompt_fixed()
    test_followup_review_shows_all_fields()
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
