# ================================================
# db/repositories/user_repository.py
# 🔹 User Repository - SQLite/SQLAlchemy Data Access
# ================================================

import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from db.session import get_db
from db.models import User

logger = logging.getLogger(__name__)

class UserRepository:
    """
    Repository for User/Translator operations
    
    Provides:
    - CRUD operations
    - Search and filtering
    - Safe queries with error handling
    """
    
    # ================================================
    # CREATE
    # ================================================
    
    def create_user(self, tg_user_id: int, full_name: str = None, 
                   phone_number: str = None) -> Optional[User]:
        """
        Create a new user
        
        Args:
            tg_user_id: Telegram user ID (unique)
            full_name: User's full name
            phone_number: User's phone number
            
        Returns:
            Created user object or None if failed
        """
        try:
            with get_db() as db:
                # Check if user already exists
                existing_user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
                if existing_user:
                    logger.warning(f"⚠️ User already exists: {tg_user_id}")
                    return existing_user
                
                # Create new user
                user = User(
                    tg_user_id=tg_user_id,
                    full_name=full_name,
                    phone_number=phone_number,
                    is_active=True,
                    is_approved=False,
                    is_suspended=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                db.add(user)
                db.commit()
                db.refresh(user)
                
                logger.info(f"✅ User created: {tg_user_id}")
                return user
                
        except IntegrityError:
            logger.warning(f"⚠️ User already exists: {tg_user_id}")
            return self.get_by_tg_id(tg_user_id)
        except Exception as e:
            logger.error(f"❌ Error creating user: {e}")
            return None
    
    # ================================================
    # READ
    # ================================================
    
    def get_by_tg_id(self, tg_user_id: int) -> Optional[User]:
        """Get user by Telegram ID"""
        try:
            with get_db() as db:
                return db.query(User).filter(User.tg_user_id == tg_user_id).first()
        except Exception as e:
            logger.error(f"❌ Error getting user {tg_user_id}: {e}")
            return None
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        try:
            with get_db() as db:
                return db.query(User).filter(User.id == user_id).first()
        except Exception as e:
            logger.error(f"❌ Error getting user by ID: {e}")
            return None
    
    def get_all_active_users(self) -> List[User]:
        """Get all active users"""
        try:
            with get_db() as db:
                return db.query(User).filter(User.is_active == True).order_by(User.created_at.desc()).all()
        except Exception as e:
            logger.error(f"❌ Error getting active users: {e}")
            return []
    
    def get_all_approved_users(self) -> List[User]:
        """Get all approved users"""
        try:
            with get_db() as db:
                return db.query(User).filter(
                    User.is_approved == True,
                    User.is_suspended == False
                ).order_by(User.full_name).all()
        except Exception as e:
            logger.error(f"❌ Error getting approved users: {e}")
            return []
    
    def get_pending_approvals(self) -> List[User]:
        """Get users waiting for approval"""
        try:
            with get_db() as db:
                return db.query(User).filter(
                    User.is_approved == False,
                    User.is_suspended == False
                ).order_by(User.created_at).all()
        except Exception as e:
            logger.error(f"❌ Error getting pending users: {e}")
            return []
    
    # ================================================
    # UPDATE
    # ================================================
    
    def update_user(self, tg_user_id: int, **update_data) -> bool:
        """
        Update user information
        
        Args:
            tg_user_id: Telegram user ID
            **update_data: Fields to update as keyword arguments
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_db() as db:
                user = db.query(User).filter(User.tg_user_id == tg_user_id).first()
                
                if not user:
                    logger.warning(f"⚠️ User not found: {tg_user_id}")
                    return False
                
                # Update fields
                for key, value in update_data.items():
                    if hasattr(user, key):
                        setattr(user, key, value)
                
                # Update timestamp
                user.updated_at = datetime.utcnow()
                
                db.commit()
                logger.info(f"✅ User updated: {tg_user_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error updating user {tg_user_id}: {e}")
            return False
    
    def approve_user(self, tg_user_id: int) -> bool:
        """Approve a user"""
        return self.update_user(tg_user_id, is_approved=True)
    
    def suspend_user(self, tg_user_id: int, reason: str = None) -> bool:
        """Suspend a user"""
        return self.update_user(
            tg_user_id,
            is_suspended=True,
            is_active=False,
            suspension_reason=reason,
            suspended_at=datetime.utcnow()
        )
    
    def unsuspend_user(self, tg_user_id: int) -> bool:
        """Unsuspend a user"""
        return self.update_user(
            tg_user_id,
            is_suspended=False,
            is_active=True,
            suspension_reason=None,
            suspended_at=None
        )
    
    # ================================================
    # DELETE
    # ================================================
    
    def delete_user(self, tg_user_id: int) -> bool:
        """
        Delete a user (soft delete - set is_active to False)
        
        Note: We don't actually delete, we deactivate for data integrity
        """
        return self.update_user(tg_user_id, is_active=False)
    
    # ================================================
    # SEARCH
    # ================================================
    
    def search_users(self, query: str) -> List[User]:
        """
        Search users by name or phone
        
        Args:
            query: Search term
            
        Returns:
            List of matching users
        """
        try:
            with get_db() as db:
                search_pattern = f"%{query}%"
                return db.query(User).filter(
                    (User.full_name.ilike(search_pattern)) |
                    (User.phone_number.ilike(search_pattern))
                ).limit(50).all()
                
        except Exception as e:
            logger.error(f"❌ Error searching users: {e}")
            return []
    
    # ================================================
    # STATS
    # ================================================
    
    def get_user_count(self) -> int:
        """Get total number of users"""
        try:
            with get_db() as db:
                return db.query(User).count()
        except Exception as e:
            logger.error(f"❌ Error counting users: {e}")
            return 0
    
    def get_approved_count(self) -> int:
        """Get number of approved users"""
        try:
            with get_db() as db:
                return db.query(User).filter(User.is_approved == True).count()
        except Exception as e:
            return 0


# Global instance
_user_repo = None

def get_user_repository() -> UserRepository:
    """Get the global UserRepository instance"""
    global _user_repo
    if _user_repo is None:
        _user_repo = UserRepository()
    return _user_repo
