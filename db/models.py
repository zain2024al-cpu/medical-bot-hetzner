# ================================================
# db/models.py
# 🔹 SQLite Database Models - Pure SQLAlchemy
# ================================================

import logging
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Text, Float, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base

logger = logging.getLogger(__name__)

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
    report_date = Column(DateTime, default=datetime.utcnow, nullable=True, index=True)
    
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
    
    # Metadata
    status = Column(String(50), default="active", nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


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
    translator_id = Column(Integer, nullable=True)
    translator_name = Column(String(255), nullable=True)
    patient_name = Column(String(255), nullable=True)
    case_details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
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
    file_path = Column(String(500), nullable=True)
    upload_date = Column(DateTime, default=datetime.utcnow, nullable=True)
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
    evaluation_period = Column(String(100), nullable=True)
    total_reports = Column(Integer, default=0, nullable=True)
    quality_score = Column(Float, default=0.0, nullable=True)
    performance_score = Column(Float, default=0.0, nullable=True)
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)


class MonthlyEvaluation(Base):
    """Monthly evaluation tracking"""
    __tablename__ = "monthly_evaluations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    translator_id = Column(Integer, nullable=True)
    translator_name = Column(String(255), nullable=True)
    month = Column(Integer, nullable=True)
    year = Column(Integer, nullable=True)
    total_reports = Column(Integer, default=0, nullable=True)
    average_quality = Column(Float, default=0.0, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=True)


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
    'DailySchedule',
    'DailyPatient',
    'DailyReportTracking',
    'AdminNote',
    'ScheduleImage',
    'TranslatorSchedule',
    'TranslatorNotification',
    'TranslatorEvaluation',
    'MonthlyEvaluation',
    'FollowupTracking',
    'desc'
]
