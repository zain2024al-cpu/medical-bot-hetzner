# ================================================
# db/repositories/hospital_repository.py
# 🔹 Hospital Repository - SQLite/SQLAlchemy
# ================================================

import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from db.session import get_db
from db.models import Hospital

logger = logging.getLogger(__name__)

class HospitalRepository:
    """Repository for Hospital operations"""
    
    def create_hospital(self, name: str, address: str = None) -> Optional[int]:
        """Create a new hospital"""
        try:
            with get_db() as db:
                # Check if hospital already exists
                existing = db.query(Hospital).filter(Hospital.name == name.strip()).first()
                if existing:
                    logger.warning(f"⚠️ Hospital already exists: {name}")
                    return existing.id
                
                hospital = Hospital(
                    name=name.strip(),
                    address=address,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                db.add(hospital)
                db.commit()
                db.refresh(hospital)
                
                logger.info(f"✅ Hospital created: {name}")
                return hospital.id
                
        except IntegrityError:
            logger.warning(f"⚠️ Hospital already exists: {name}")
            with get_db() as db:
                existing = db.query(Hospital).filter(Hospital.name == name.strip()).first()
                return existing.id if existing else None
        except Exception as e:
            logger.error(f"❌ Error creating hospital: {e}")
            return None
    
    def get_all(self) -> List[Hospital]:
        """Get all hospitals"""
        try:
            with get_db() as db:
                return db.query(Hospital).order_by(Hospital.name).all()
        except Exception as e:
            logger.error(f"❌ Error getting hospitals: {e}")
            return []
    
    def get_by_name(self, name: str) -> Optional[Hospital]:
        """Get hospital by name"""
        try:
            with get_db() as db:
                return db.query(Hospital).filter(Hospital.name == name.strip()).first()
        except Exception as e:
            return None


_hospital_repo = None

def get_hospital_repository() -> HospitalRepository:
    """Get the global HospitalRepository instance"""
    global _hospital_repo
    if _hospital_repo is None:
        _hospital_repo = HospitalRepository()
    return _hospital_repo
