# ================================================
# db/models.py
# 🔹 SQLite Database Models - Pure SQLAlchemy
# ================================================

import logging
from datetime import datetime, date, timedelta, timezone
from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Text, Float, ForeignKey, UniqueConstraint, create_engine
from sqlalchemy.ext.declarative import declarative_base

logger = logging.getLogger(__name__)


def _now_ist_naive():
    """التوقيت المحلي IST (UTC+5:30) بدون tzinfo - لحفظ report_date"""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)
    except Exception:
        ist = timezone(timedelta(hours=5, minutes=30))
        return datetime.now(timezone.utc).astimezone(ist).replace(tzinfo=None)

Base = declarative_base()

# ================================================
# User / Translator Model
# ================================================

class User(Base):
    """User/Translator model"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tg_user_id = Column(Integer, unique=True, nullable=True, index=True)
    chat_id = Column(Integer, nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    role = Column(String(50), default="user", nullable=True)
    status = Column(String(50), default="pending", nullable=True)
    is_approved = Column(Boolean, default=False, index=True, nullable=True)
    is_admin = Column(Boolean, default=False, nullable=True)
    is_active = Column(Boolean, default=True, index=True, nullable=True)
    is_suspended = Column(Boolean, default=False, nullable=True)
    suspension_reason = Column(Text, nullable=True)
    suspended_at = Column(DateTime, nullable=True)
    registration_date = Column(DateTime, default=datetime.utcnow, nullable=True)
    last_active = Column(DateTime, default=datetime.utcnow, nullable=True)
    total_reports = Column(Integer, default=0, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


class TranslatorDirectory(Base):
    __tablename__ = "translators"
    
    translator_id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=True, index=True)


# ================================================
# Patient Model
# ================================================

class Patient(Base):
    """Patient model"""
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(255), nullable=True, index=True)
    file_number = Column(String(100), nullable=True, index=True)
    phone_number = Column(String(50), nullable=True)
    age = Column(Integer, nullable=True)
    disease = Column(Text, nullable=True)
    nationality = Column(String(100), nullable=True)
    # ✅ نوع ظهور المريض:
    #   NULL أو "general" → يظهر في كل شاشات اختيار المرضى (السلوك الحالي).
    #   "pharmacy_only"   → يظهر فقط داخل 💊 صرف الأدوية و🩺 المستلزمات الطبية.
    # كل المرضى الحاليين NULL تلقائياً = general، فلا يتغيّر أي سلوك قائم.
    patient_type = Column(String(30), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


# ================================================
# Hospital Model
# ================================================

class Hospital(Base):
    """Hospital model"""
    __tablename__ = "hospitals"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True, index=True)
    address = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


# ================================================
# Department Model
# ================================================

class Department(Base):
    """Department model"""
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=True)
    hospital_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


# ================================================
# Doctor Model
# ================================================

class Doctor(Base):
    """Doctor model"""
    __tablename__ = "doctors"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=True, index=True)
    full_name = Column(String(255), nullable=True)
    specialty = Column(String(255), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


# ================================================
# Report Model
# ================================================

class Report(Base):
    """Medical Report model"""
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Keys (all nullable for flexibility)
    translator_id = Column(Integer, nullable=True, index=True)
    patient_id = Column(Integer, nullable=True, index=True)
    hospital_id = Column(Integer, nullable=True)
    department_id = Column(Integer, nullable=True)
    doctor_id = Column(Integer, nullable=True)
    
    # Denormalized fields for fast access (all nullable)
    translator_name = Column(String(255), nullable=True)
    patient_name = Column(String(255), nullable=True, index=True)
    patient_file_number = Column(String(100), nullable=True)
    patient_phone = Column(String(50), nullable=True)
    patient_age = Column(Integer, nullable=True)
    patient_disease = Column(Text, nullable=True)
    patient_nationality = Column(String(100), nullable=True)
    hospital_name = Column(String(255), nullable=True)
    department = Column(String(255), nullable=True, index=True)
    doctor_name = Column(String(255), nullable=True)
    specialty = Column(String(255), nullable=True)
    
    # Report details
    visit_date = Column(DateTime, nullable=True)
    visit_time = Column(String(50), nullable=True)
    report_date = Column(DateTime, default=_now_ist_naive, nullable=True, index=True)
    
    # Medical details
    medical_action = Column(String(255), nullable=True)
    complaint_text = Column(Text, nullable=True)
    doctor_decision = Column(Text, nullable=True)
    case_status = Column(String(255), nullable=True)
    diagnosis = Column(Text, nullable=True)
    treatment_plan = Column(Text, nullable=True)
    medications = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Follow-up
    followup_date = Column(DateTime, nullable=True, index=True)
    followup_time = Column(String(50), nullable=True)
    followup_department = Column(String(255), nullable=True)
    followup_reason = Column(Text, nullable=True)
    # حقول خاصة بتأجيل الموعد
    app_reschedule_reason = Column(Text, nullable=True)
    app_reschedule_return_date = Column(DateTime, nullable=True)
    app_reschedule_return_reason = Column(Text, nullable=True)
    
    # Metadata
    status = Column(String(50), default="active", nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
    
    # ✅ معرف المستخدم الذي أنشأ التقرير (Telegram User ID)
    submitted_by_user_id = Column(Integer, nullable=True, index=True)
    
    # ✅ معرف الرسالة في المجموعة (لحذفها لاحقاً)
    group_message_id = Column(Integer, nullable=True)
    
    # ✅ حقول الأشعة والفحوصات
    radiology_type = Column(String(255), nullable=True)
    radiology_delivery_date = Column(DateTime, nullable=True)
    
    # ✅ حقول العلاج الإشعاعي
    radiation_therapy_type = Column(String(255), nullable=True)
    radiation_therapy_session_number = Column(String(100), nullable=True)
    radiation_therapy_remaining = Column(String(100), nullable=True)
    radiation_therapy_recommendations = Column(Text, nullable=True)  # ملاحظات أو توصيات
    radiation_therapy_return_date = Column(DateTime, nullable=True)
    radiation_therapy_return_reason = Column(Text, nullable=True)
    radiation_therapy_final_notes = Column(Text, nullable=True)
    radiation_therapy_completed = Column(Boolean, default=False, nullable=True)
    
    # ✅ حقل رقم الغرفة والطابق
    room_number = Column(String(255), nullable=True)

    # ✅ حقول التقرير الطبي الورقي (1=نعم, 0=لا, None=لم يُسأل)
    has_paper_report = Column(Integer, nullable=True)
    no_paper_report_reason = Column(Text, nullable=True)


# ================================================
# Schedule Model
# ================================================

class Schedule(Base):
    """Schedule image tracking"""
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    translator_id = Column(Integer, nullable=True, index=True)
    translator_name = Column(String(255), nullable=True)
    file_path = Column(String(500), nullable=True)
    upload_date = Column(DateTime, default=datetime.utcnow, nullable=True)
    extracted_text = Column(Text, nullable=True)
    status = Column(String(50), default="active", nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)


# ================================================
# Followup Model
# ================================================

class Followup(Base):
    """Follow-up appointment tracking"""
    __tablename__ = "followups"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, nullable=True)
    patient_id = Column(Integer, nullable=True)
    patient_name = Column(String(255), nullable=True)
    patient_phone = Column(String(50), nullable=True)
    followup_date = Column(DateTime, nullable=True, index=True)
    department = Column(String(255), nullable=True)
    translator_id = Column(Integer, nullable=True, index=True)
    translator_name = Column(String(255), nullable=True)
    status = Column(String(50), default="pending", nullable=True, index=True)
    reminder_sent = Column(Boolean, default=False, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


# ================================================
# User Activity Model
# ================================================

class UserActivity(Base):
    """User activity tracking"""
    __tablename__ = "user_activity"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True, index=True)
    activity_type = Column(String(100), nullable=True, index=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=True, index=True)


# ================================================
# Healthcare — Wound Care Records
# ================================================

class WoundRecord(Base):
    """Wound care record created by the healthcare module — official 11-step workflow."""
    __tablename__ = "wound_records"

    id                       = Column(Integer, primary_key=True, autoincrement=True)
    patient_id               = Column(Integer, nullable=True, index=True)
    patient_name             = Column(String(255), nullable=True, index=True)
    medical_departments_json = Column(Text, nullable=True)           # JSON list of dept labels
    operation_name           = Column(String(500), nullable=True)    # اسم العملية (free text)
    phase                    = Column(String(100), nullable=True)     # phase key e.g. "phase_pre_op"
    phase_label              = Column(String(255), nullable=True)    # e.g. "قبل العملية"
    condition_description    = Column(Text, nullable=True)           # وصف الحالة
    supplies_json            = Column(Text, nullable=True)           # JSON list of supply labels
    image_file_ids           = Column(Text, nullable=True)           # JSON list of Telegram file_ids
    image_count              = Column(Integer, default=0, nullable=True)
    notes                    = Column(Text, nullable=True)
    specialist_name          = Column(String(255), nullable=True)    # healthcare specialist name
    created_by               = Column(Integer, nullable=True, index=True)  # tg_user_id
    created_at               = Column(DateTime, default=datetime.utcnow, index=True, nullable=True)
    updated_at               = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


# ================================================
# RBAC — Module Access Control
# ================================================

class UserModuleAccess(Base):
    """
    Per-user module activation records.
    One row per (tg_user_id, module_key); soft-delete via is_active.
    """
    __tablename__ = "user_module_access"
    __table_args__ = (
        UniqueConstraint("tg_user_id", "module_key", name="uq_user_module"),
    )

    id         = Column(Integer, primary_key=True, autoincrement=True)
    tg_user_id = Column(Integer, nullable=False, index=True)
    module_key = Column(String(100), nullable=False)
    granted_by = Column(Integer, nullable=True)    # admin tg_user_id who granted
    granted_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    revoked_by = Column(Integer, nullable=True)    # admin tg_user_id who revoked
    revoked_at = Column(DateTime, nullable=True)
    is_active  = Column(Boolean, default=True, nullable=False, index=True)


# ================================================
# Healthcare — Medical Follow-up Records
# ================================================

class MedicalFollowupRecord(Base):
    """Medical follow-up and therapeutic procedure records — official 11-step workflow."""
    __tablename__ = "medical_followup_records"

    id                       = Column(Integer, primary_key=True, autoincrement=True)
    patient_id               = Column(Integer, nullable=True, index=True)
    patient_name             = Column(String(255), nullable=True, index=True)
    medical_departments_json = Column(Text, nullable=True)    # JSON list of dept labels
    procedure_type_json      = Column(Text, nullable=True)    # JSON list of procedure type labels
    complaint_labels_json    = Column(Text, nullable=True)    # JSON list of complaint labels
    vitals_temp              = Column(String(50), nullable=True)   # درجة الحرارة
    vitals_bp                = Column(String(50), nullable=True)   # ضغط الدم
    vitals_pulse             = Column(String(50), nullable=True)   # النبض
    vitals_spo2              = Column(String(50), nullable=True)   # SpO2
    meds_supply_labels_json  = Column(Text, nullable=True)    # JSON list of med/supply labels
    image_file_ids           = Column(Text, nullable=True)    # JSON list of Telegram file_ids
    image_count              = Column(Integer, default=0, nullable=True)
    notes                    = Column(Text, nullable=True)
    specialist_name          = Column(String(255), nullable=True)
    created_by               = Column(Integer, nullable=True, index=True)
    created_at               = Column(DateTime, default=datetime.utcnow, index=True, nullable=True)
    updated_at               = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


# ================================================
# Healthcare — Medication Dispensing Records
# ================================================

class MedicationRecord(Base):
    """Medication dispensing records."""
    __tablename__ = "medication_records"

    id                       = Column(Integer, primary_key=True, autoincrement=True)
    patient_id               = Column(Integer, nullable=True, index=True)
    patient_name             = Column(String(255), nullable=True, index=True)
    medical_departments_json = Column(Text, nullable=True)     # JSON list of medical specialty labels
    item_count               = Column(Integer, default=0, nullable=True)  # عدد الأصناف
    dispense_source          = Column(String(50), nullable=True)           # الصيدلية / المخزن
    image_file_ids           = Column(Text, nullable=True)
    image_count              = Column(Integer, default=0, nullable=True)
    notes                    = Column(Text, nullable=True)
    specialist_name          = Column(String(255), nullable=True)
    created_by               = Column(Integer, nullable=True, index=True)
    created_at               = Column(DateTime, default=datetime.utcnow, index=True, nullable=True)
    updated_at               = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


# ================================================
# Healthcare — Medical Supplies Records
# ================================================

class SuppliesRecord(Base):
    """Medical supplies dispensing records (mirrors MedicationRecord structure)."""
    __tablename__ = "supplies_records"

    id                       = Column(Integer, primary_key=True, autoincrement=True)
    patient_id               = Column(Integer, nullable=True, index=True)
    patient_name             = Column(String(255), nullable=True, index=True)
    medical_departments_json = Column(Text, nullable=True)     # JSON list of medical specialty labels
    item_count               = Column(Integer, default=0, nullable=True)  # عدد الأصناف
    dispense_source          = Column(String(50), nullable=True)           # الصيدلية / المخزن
    image_file_ids           = Column(Text, nullable=True)
    image_count              = Column(Integer, default=0, nullable=True)
    notes                    = Column(Text, nullable=True)
    specialist_name          = Column(String(255), nullable=True)
    created_by               = Column(Integer, nullable=True, index=True)
    created_at               = Column(DateTime, default=datetime.utcnow, index=True, nullable=True)
    updated_at               = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


# ================================================
# Healthcare — Pharmacy Financial Records
# ================================================

class PharmacyFinancialRecord(Base):
    """
    البيانات المالية المرتبطة 1:1 بعملية صرف محدَّدة (MedicationRecord أو
    SuppliesRecord) كانت جهة صرفها "الصيدلية". بدون ForeignKey (نفس نمط
    المشروع) — source_type/source_record_id يُحلّان عبر استعلام صريح.
    """
    __tablename__ = "pharmacy_financial_records"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    source_type       = Column(String(20), nullable=False, index=True)   # "medication" | "supplies"
    source_record_id  = Column(Integer, nullable=False, index=True)      # MedicationRecord.id / SuppliesRecord.id
    invoice_number    = Column(String(100), nullable=True)               # رقم الفاتورة
    expense_item      = Column(String(255), nullable=True)               # بند الصرف
    invoice_total     = Column(Float, nullable=True)                     # إجمالي الفاتورة
    discount_percent  = Column(Float, nullable=True)                     # نسبة التخفيض %
    discount_amount   = Column(Float, nullable=True)                     # مبلغ الخصم (محسوب في بايثون)
    net_amount        = Column(Float, nullable=True)                     # صافي المبلغ (محسوب في بايثون)
    created_by        = Column(Integer, nullable=True, index=True)
    created_at        = Column(DateTime, default=datetime.utcnow, index=True, nullable=True)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    def __repr__(self):
        return f"<PharmacyFinancialRecord(id={self.id}, {self.source_type}#{self.source_record_id}, net={self.net_amount})>"


# ================================================
# Healthcare — Other / Miscellaneous Records
# ================================================

class OtherHealthcareRecord(Base):
    """Catch-all healthcare record for miscellaneous actions."""
    __tablename__ = "other_healthcare_records"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    patient_id      = Column(Integer, nullable=True, index=True)
    patient_name    = Column(String(255), nullable=True, index=True)
    action_ids      = Column(Text, nullable=True)       # JSON list of action IDs
    action_labels   = Column(Text, nullable=True)       # JSON list of display labels
    image_file_ids  = Column(Text, nullable=True)
    image_count     = Column(Integer, default=0, nullable=True)
    notes           = Column(Text, nullable=True)
    specialist_name = Column(String(255), nullable=True)
    created_by      = Column(Integer, nullable=True, index=True)
    created_at      = Column(DateTime, default=datetime.utcnow, index=True, nullable=True)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


# ================================================
# General Services — Arrival Batches
# ================================================

class ArrivalBatch(Base):
    """Header record for one arrival batch (a group of patients arriving together)."""
    __tablename__ = "gs_arrival_batches"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    hospital_id      = Column(String(50),  nullable=True)
    hospital_label   = Column(String(255), nullable=True)
    specialist_id    = Column(String(50),  nullable=True)
    specialist_label = Column(String(255), nullable=True)
    patient_count    = Column(Integer, default=0, nullable=True)
    created_by       = Column(Integer, nullable=True, index=True)
    created_at       = Column(DateTime, default=datetime.utcnow, index=True, nullable=True)


class ArrivalPatient(Base):
    """One patient within an arrival batch."""
    __tablename__ = "gs_arrival_patients"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    batch_id            = Column(Integer, nullable=True, index=True)
    name                = Column(String(255), nullable=True, index=True)
    visa_expiry         = Column(String(50),  nullable=True)
    has_companion       = Column(Boolean, default=False, nullable=True)
    passport_file_id    = Column(String(255), nullable=True)
    visa_file_id        = Column(String(255), nullable=True)
    residence_file_id   = Column(String(255), nullable=True)
    residence_expiry    = Column(String(50),  nullable=True)
    notes               = Column(Text, nullable=True)
    arrival_status      = Column(String(20), default="active", nullable=True)
    departure_record_id = Column(Integer, nullable=True)
    created_at          = Column(DateTime, default=datetime.utcnow, nullable=True)


class ArrivalCompanion(Base):
    """Companion record attached to one ArrivalPatient."""
    __tablename__ = "gs_arrival_companions"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    patient_id          = Column(Integer, nullable=True, index=True)
    name                = Column(String(255), nullable=True)
    passport_file_id    = Column(String(255), nullable=True)
    visa_file_id        = Column(String(255), nullable=True)
    residence_file_id   = Column(String(255), nullable=True)
    residence_expiry    = Column(String(50),  nullable=True)
    created_at          = Column(DateTime, default=datetime.utcnow, nullable=True)


# ================================================
# General Services — Departure Records
# ================================================

class DepartureRecord(Base):
    """Single departure record — one or more patients leaving together."""
    __tablename__ = "gs_departure_records"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    patients_text    = Column(Text,        nullable=True)
    hospital_id      = Column(String(50),  nullable=True)
    hospital_label   = Column(String(255), nullable=True)
    arrival_patient_ids = Column(Text,       nullable=True)   # JSON list of int
    image_file_ids   = Column(Text,        nullable=True)   # JSON list
    image_count      = Column(Integer, default=0, nullable=True)
    notes            = Column(Text,        nullable=True)
    specialist_id    = Column(String(50),  nullable=True)
    specialist_label = Column(String(255), nullable=True)
    created_by       = Column(Integer, nullable=True, index=True)
    created_at       = Column(DateTime, default=datetime.utcnow, index=True, nullable=True)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


# ================================================
# General Services — Public Service Records
# ================================================

class PublicServiceRecord(Base):
    """Public / administrative service record for a patient."""
    __tablename__ = "gs_public_service_records"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    patient_id        = Column(Integer, nullable=True, index=True)
    patient_name      = Column(String(255), nullable=True, index=True)
    service_type_json = Column(Text,        nullable=True)   # JSON list of labels
    item_count        = Column(Integer, default=0, nullable=True)
    image_file_ids    = Column(Text,        nullable=True)   # JSON list
    image_count       = Column(Integer, default=0, nullable=True)
    notes             = Column(Text,        nullable=True)
    specialist_id     = Column(String(50),  nullable=True)
    specialist_label  = Column(String(255), nullable=True)
    created_by        = Column(Integer, nullable=True, index=True)
    created_at        = Column(DateTime, default=datetime.utcnow, index=True, nullable=True)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


# ================================================
# Healthcare — Custom "أخرى" Options
# ================================================

class CustomOption(Base):
    """
    User-defined values entered via the 'أخرى' button in any healthcare multiselect.
    Saved persistently so they appear as ready-made options the next time the same
    multiselect is opened — no re-typing needed.

    context examples: "hc_department", "wc_supplies", "fu_complaint", "fu_meds_supply"
    """
    __tablename__ = "custom_options"
    __table_args__ = (
        UniqueConstraint("context", "label", name="uq_custom_option"),
    )

    id         = Column(Integer, primary_key=True, autoincrement=True)
    context    = Column(String(100), nullable=False, index=True)
    label      = Column(String(255), nullable=False)
    use_count  = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)


# ================================================
# Additional Models
# ================================================

class Note(Base):
    """Notes"""
    __tablename__ = "notes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String(255), nullable=True)
    note_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


class InitialCase(Base):
    """Initial case tracking"""
    __tablename__ = "initial_cases"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, nullable=True)
    patient_name = Column(String(255), nullable=True)
    patient_age = Column(String(50), nullable=True)
    main_complaint = Column(Text, nullable=True)
    current_history = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    previous_procedures = Column(Text, nullable=True)
    test_details = Column(Text, nullable=True)
    case_details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    created_by = Column(Integer, nullable=True)
    status = Column(String(50), default="pending", nullable=True)


class Evaluation(Base):
    """Translator evaluation"""
    __tablename__ = "evaluations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    translator_id = Column(Integer, nullable=True)
    translator_name = Column(String(255), nullable=True)
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    total_reports = Column(Integer, default=0, nullable=True)
    quality_score = Column(Float, default=0.0, nullable=True)
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)


# Additional models for compatibility
class DailySchedule(Base):
    """Daily schedule tracking"""
    __tablename__ = "daily_schedules"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    translator_id = Column(Integer, nullable=True)
    translator_name = Column(String(255), nullable=True)
    date = Column(DateTime, default=datetime.utcnow, nullable=True, index=True)
    shift_type = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    photo_file_id = Column(String(255), nullable=True)
    photo_path = Column(String(500), nullable=True)
    uploaded_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


class DailyPatient(Base):
    """Daily patient tracking"""
    __tablename__ = "daily_patients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    translator_id = Column(Integer, nullable=True)
    translator_name = Column(String(255), nullable=True)
    patient_name = Column(String(255), nullable=True)
    patient_count = Column(Integer, default=0, nullable=True)
    date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)


# ================================================
# Residency — Lifecycle Management
# ================================================

class ResidencyProfile(Base):
    """
    Master residency record for one patient.
    Created automatically from an ArrivalBatch (source='arrivals')
    or manually by staff (source='manual').
    """
    __tablename__ = "res_profiles"

    id                       = Column(Integer, primary_key=True, autoincrement=True)
    # Link back to arrivals (nullable — manual entries have no arrival record)
    arrival_patient_id       = Column(Integer, nullable=True, index=True)
    source                   = Column(String(20),  default="arrivals")   # "arrivals" | "manual"
    name                     = Column(String(255), nullable=False, index=True)
    # Status lifecycle:
    # active → expiring → renewal_submitted → issued → (dependent_pending) → …
    status                   = Column(String(30),  default="active", index=True)
    # Document numbers / dates
    residency_number         = Column(String(100), default="")
    issue_date               = Column(String(50),  default="")   # ISO date string YYYY-MM-DD
    expiry_date              = Column(String(50),  default="")   # ISO date string YYYY-MM-DD
    # Latest known Telegram file_ids for each document
    passport_file_id         = Column(String(255), default="")
    visa_file_id             = Column(String(255), default="")
    latest_residency_file_id = Column(String(255), default="")
    # Extra
    notes                    = Column(Text, default="")
    created_by               = Column(Integer, nullable=True, index=True)
    created_at               = Column(DateTime, default=datetime.utcnow, index=True, nullable=True)
    updated_at               = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


class ResidencyCompanion(Base):
    """
    One companion attached to a ResidencyProfile.
    Created from arrival companions automatically, or added manually.
    """
    __tablename__ = "res_companions"

    id                       = Column(Integer, primary_key=True, autoincrement=True)
    profile_id               = Column(Integer, nullable=False, index=True)   # FK → res_profiles.id
    arrival_companion_id     = Column(Integer, nullable=True)                # FK → gs_arrival_companions.id
    name                     = Column(String(255), nullable=False, index=True)
    status                   = Column(String(30),  default="active", index=True)
    residency_number         = Column(String(100), default="")
    issue_date               = Column(String(50),  default="")
    expiry_date              = Column(String(50),  default="")
    passport_file_id         = Column(String(255), default="")
    visa_file_id             = Column(String(255), default="")
    latest_residency_file_id = Column(String(255), default="")
    notes                    = Column(Text, default="")
    created_at               = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at               = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


class ResidencyUpdate(Base):
    """
    Append-only audit / timeline log for every status change or document update
    on a ResidencyProfile or its companions.
    """
    __tablename__ = "res_updates"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    profile_id       = Column(Integer, nullable=False, index=True)   # FK → res_profiles.id
    companion_id     = Column(Integer, nullable=True)                # FK → res_companions.id (companion event)
    # action_type values:
    #   profile_created | manual_add | renewal_submitted | issued
    #   companion_issued | companion_skipped | status_changed | note_added
    action_type      = Column(String(50),  nullable=False)
    action_label     = Column(String(255), default="")
    old_status       = Column(String(30),  default="")
    new_status       = Column(String(30),  default="")
    old_expiry_date  = Column(String(50),  default="")
    new_expiry_date  = Column(String(50),  default="")
    residency_file_id = Column(String(255), default="")
    notes            = Column(Text, default="")
    performed_by     = Column(Integer, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow, index=True, nullable=True)


class DailyReportTracking(Base):
    """Daily report tracking"""
    __tablename__ = "daily_report_tracking"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    translator_id = Column(Integer, nullable=True)
    translator_name = Column(String(255), nullable=True)
    date = Column(Date, default=date.today, nullable=True, index=True)
    expected_reports = Column(Integer, default=0, nullable=True)
    actual_reports = Column(Integer, default=0, nullable=True)
    is_completed = Column(Boolean, default=False, nullable=True)
    reminder_sent = Column(Boolean, default=False, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)


class AdminNote(Base):
    """Admin notes"""
    __tablename__ = "admin_notes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, nullable=True)
    admin_name = Column(String(255), nullable=True)
    note_text = Column(Text, nullable=True)
    target_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


class ScheduleImage(Base):
    """Schedule image tracking"""
    __tablename__ = "schedule_images"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    translator_id = Column(Integer, nullable=True)
    translator_name = Column(String(255), nullable=True)
    file_id = Column(String(255), nullable=True)  # Telegram file_id for quick access
    file_path = Column(String(500), nullable=True)
    uploader_id = Column(Integer, nullable=True)  # ID of admin who uploaded
    upload_date = Column(DateTime, default=datetime.utcnow, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=True)  # Alias for compatibility
    extracted_text = Column(Text, nullable=True)
    status = Column(String(50), default="active", nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)


class TranslatorSchedule(Base):
    """Translator schedule management"""
    __tablename__ = "translator_schedules"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    translator_id = Column(Integer, nullable=True)
    translator_name = Column(String(255), nullable=True)
    schedule_date = Column(DateTime, nullable=True)
    shift_start = Column(String(50), nullable=True)
    shift_end = Column(String(50), nullable=True)
    status = Column(String(50), default="active", nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


class TranslatorNotification(Base):
    """Translator notifications"""
    __tablename__ = "translator_notifications"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    translator_id = Column(Integer, nullable=True)
    translator_name = Column(String(255), nullable=True)
    notification_text = Column(Text, nullable=True)
    notification_type = Column(String(100), nullable=True)
    is_read = Column(Boolean, default=False, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)


class TranslatorEvaluation(Base):
    """Translator evaluation"""
    __tablename__ = "translator_evaluations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    translator_id = Column(Integer, nullable=True)
    translator_name = Column(String(255), nullable=True)
    report_id = Column(Integer, nullable=True)
    evaluation_date = Column(DateTime, nullable=True)
    timing_score = Column(Integer, nullable=True)
    quality_score = Column(Integer, nullable=True)
    regularity_score = Column(Integer, nullable=True)
    total_score = Column(Integer, nullable=True)
    timing_notes = Column(Text, nullable=True)
    quality_notes = Column(Text, nullable=True)
    general_notes = Column(Text, nullable=True)
    evaluator_id = Column(Integer, nullable=True)
    is_manual = Column(Boolean, default=False, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)


class MonthlyEvaluation(Base):
    """Monthly evaluation tracking"""
    __tablename__ = "monthly_evaluations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    translator_id = Column(Integer, nullable=True)
    translator_name = Column(String(255), nullable=True)
    month = Column(Integer, nullable=True)
    year = Column(Integer, nullable=True)
    total_reports = Column(Integer, default=0, nullable=True)
    work_days = Column(Integer, default=0, nullable=True)
    # حقول التقييم التفصيلية
    on_time_reports = Column(Integer, default=0, nullable=True)
    late_reports = Column(Integer, default=0, nullable=True)
    timing_points = Column(Float, default=0.0, nullable=True)
    quality_points = Column(Float, default=0.0, nullable=True)
    regularity_points = Column(Float, default=0.0, nullable=True)
    total_points = Column(Float, default=0.0, nullable=True)
    final_rating = Column(Integer, default=0, nullable=True)
    performance_level = Column(String(50), nullable=True)
    monthly_notes = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


class FollowupTracking(Base):
    """Follow-up tracking"""
    __tablename__ = "followup_tracking"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, nullable=True)
    patient_id = Column(Integer, nullable=True)
    patient_name = Column(String(255), nullable=True)
    patient_phone = Column(String(50), nullable=True)
    followup_date = Column(DateTime, nullable=True)
    department = Column(String(255), nullable=True)
    translator_id = Column(Integer, nullable=True)
    translator_name = Column(String(255), nullable=True)
    status = Column(String(50), default="pending", nullable=True)
    reminder_sent = Column(Boolean, default=False, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


class PendingReport(Base):
    """تتبع التقارير الطبية المعلقة (التي بدون مرافقات جاهزة)

    عند إرفاق التقرير والمترجم يقول "لا يوجد تقارير طبية"
    نحفظ المعلومات هنا لمتابعتها
    """
    __tablename__ = "pending_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, nullable=True, index=True)
    patient_id = Column(Integer, nullable=True)
    patient_name = Column(String(255), nullable=True, index=True)
    department = Column(String(255), nullable=True)
    translator_id = Column(Integer, nullable=True)
    translator_name = Column(String(255), nullable=True, index=True)
    no_report_reason = Column(Text, nullable=True)  # السبب لعدم وجود التقرير
    status = Column(String(50), default="pending", nullable=True, index=True)  # pending, completed, cancelled
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True, index=True)
    completed_at = Column(DateTime, nullable=True)  # متى تم إكمال المرافقات
    days_waiting = Column(Integer, default=0, nullable=True)  # عدد الأيام في الانتظار

    def __repr__(self):
        return f"<PendingReport(id={self.id}, patient={self.patient_name}, dept={self.department}, status={self.status})>"


class MedicalAttachmentFile(Base):
    """سجل كل ملف طبي مُرفق بتقرير — لدعم زر "📂 فتح التقارير الطبية".

    يُنشأ سطر واحد لكل ملف عند إرساله الفعلي (بعد الحصول على الـ
    file_id النهائي من رسالة تيليجرام المُرسلة)، وليس عند الرفع
    المؤقت من المستخدم — لأن بعض المسارات (الصور → PDF، المستندات
    المعاد رفعها بعد تنزيلها) تُنتج file_id جديداً مختلفاً عن الأصلي.
    """
    __tablename__ = "medical_attachment_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, nullable=False, index=True)
    file_id = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=True)       # photo|document|video|audio|voice
    file_name = Column(String(500), nullable=True)
    uploaded_by = Column(String(255), nullable=True)
    uploaded_by_tg_id = Column(Integer, nullable=True)
    source = Column(String(50), nullable=True)          # "creation" | "late_upload"
    upload_order = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True, index=True)

    def __repr__(self):
        return f"<MedicalAttachmentFile(id={self.id}, report_id={self.report_id}, type={self.file_type})>"


# Helper function for backward compatibility
def desc(field):
    """SQLAlchemy desc() compatibility"""
    from sqlalchemy import desc as sa_desc
    return sa_desc(field)


# Alias for backward compatibility
Translator = User

# Export all models
__all__ = [
    'Base',
    'User',
    'Translator',
    'TranslatorDirectory',
    'Patient',
    'Hospital',
    'Department',
    'Doctor',
    'Report',
    'Schedule',
    'Followup',
    'UserActivity',
    'Note',
    'InitialCase',
    'Evaluation',
    'DailyPatient',
    'DailyReportTracking',
    'AdminNote',
    'ScheduleImage',
    'TranslatorSchedule',
    'TranslatorNotification',
    'TranslatorEvaluation',
    'MonthlyEvaluation',
    'FollowupTracking',
    'PendingReport',
    'WoundRecord',
    'MedicalFollowupRecord',
    'MedicationRecord',
    'SuppliesRecord',
    'OtherHealthcareRecord',
    'UserModuleAccess',
    'ArrivalBatch',
    'ArrivalPatient',
    'ArrivalCompanion',
    'DepartureRecord',
    'PublicServiceRecord',
    'desc'
]
