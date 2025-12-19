# ================================================
# db/repositories/patient_repository.py
# 🔹 Patient Repository - SQLite/SQLAlchemy
# ================================================

import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from db.session import get_db
from db.models import Patient

logger = logging.getLogger(__name__)

class PatientRepository:
    """Repository for Patient operations"""
    
    def create_patient(self, full_name: str, file_number: str = None, 
                      phone_number: str = None, age: int = None,
                      disease: str = None, nationality: str = None) -> Optional[int]:
        """Create a new patient"""
        try:
            with get_db() as db:
                patient = Patient(
                    full_name=full_name.strip() if full_name else None,
                    file_number=file_number.strip() if file_number else None,
                    phone_number=phone_number,
                    age=age,
                    disease=disease,
                    nationality=nationality,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                db.add(patient)
                db.commit()
                db.refresh(patient)
                
                logger.info(f"✅ Patient created: {full_name}")
                return patient.id
                
        except Exception as e:
            logger.error(f"❌ Error creating patient: {e}")
            return None
    
    def get_by_id(self, patient_id: int) -> Optional[Patient]:
        """Get patient by ID"""
        try:
            with get_db() as db:
                return db.query(Patient).filter(Patient.id == patient_id).first()
        except Exception as e:
            logger.error(f"❌ Error getting patient: {e}")
            return None
    
    def search_by_name(self, name_query: str, limit: int = 50) -> List[Patient]:
        """Search patients by name"""
        try:
            with get_db() as db:
                safe_query = name_query.strip()
                search_pattern = f"%{safe_query}%"
                
                return db.query(Patient).filter(
                    Patient.full_name.ilike(search_pattern)
                ).order_by(Patient.created_at.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"❌ Error searching patients: {e}")
            return []
    
    def search_by_file_number(self, file_number: str) -> Optional[Patient]:
        """Find patient by file number"""
        try:
            with get_db() as db:
                return db.query(Patient).filter(
                    Patient.file_number == file_number.strip()
                ).first()
        except Exception as e:
            logger.error(f"❌ Error finding patient by file number: {e}")
            return None
    
    def update_patient(self, patient_id: int, **update_data) -> bool:
        """Update patient information"""
        try:
            with get_db() as db:
                patient = db.query(Patient).filter(Patient.id == patient_id).first()
                
                if not patient:
                    logger.warning(f"⚠️ Patient not found: {patient_id}")
                    return False
                
                # Update fields
                for key, value in update_data.items():
                    if hasattr(patient, key):
                        setattr(patient, key, value)
                
                patient.updated_at = datetime.utcnow()
                
                db.commit()
                return True
                
        except Exception as e:
            logger.error(f"❌ Error updating patient: {e}")
            return False


_patient_repo = None

def get_patient_repository() -> PatientRepository:
    """Get the global PatientRepository instance"""
    global _patient_repo
    if _patient_repo is None:
        _patient_repo = PatientRepository()
    return _patient_repo
