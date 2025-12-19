#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
👤 نظام تتبع نشاط المستخدمين - User Activity Tracker
دمج مع نظام قاعدة البيانات الرئيسي
"""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import Session
from db.session import Base, SessionLocal

logger = logging.getLogger(__name__)

# ====================================================
# 📊 نموذج تتبع نشاط المستخدم
# ====================================================

class UserActivity(Base):
    """
    جدول تتبع نشاط المستخدمين
    """
    __tablename__ = "user_activity"
    
    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(150))
    full_name = Column(String(200))
    last_report_date = Column(DateTime)
    total_reports = Column(Integer, default=0)
    last_activity = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)  # ملاحظات إضافية
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ====================================================
# 🔧 دوال إدارة نشاط المستخدمين
# ====================================================

def init_user_activity_table():
    """
    إنشاء جدول تتبع النشاط إذا لم يكن موجوداً
    """
    try:
        from db.session import engine
        UserActivity.__table__.create(bind=engine, checkfirst=True)
        logger.info("✅ جدول user_activity جاهز")
        return True
    except Exception as e:
        logger.error(f"❌ خطأ في إنشاء جدول user_activity: {e}")
        return False


def update_user_activity(user_id: int, username: str = None, full_name: str = None):
    """
    تحديث نشاط المستخدم
    """
    try:
        with SessionLocal() as session:
            # البحث عن المستخدم
            user_activity = session.query(UserActivity).filter_by(user_id=user_id).first()
            
            if user_activity:
                # تحديث المستخدم الموجود
                user_activity.last_report_date = datetime.utcnow()
                user_activity.last_activity = datetime.utcnow()
                user_activity.total_reports += 1
                user_activity.updated_at = datetime.utcnow()
                
                if username:
                    user_activity.username = username
                if full_name:
                    user_activity.full_name = full_name
            else:
                # إنشاء مستخدم جديد
                user_activity = UserActivity(
                    user_id=user_id,
                    username=username,
                    full_name=full_name,
                    last_report_date=datetime.utcnow(),
                    last_activity=datetime.utcnow(),
                    total_reports=1
                )
                session.add(user_activity)
            
            session.commit()
            logger.info(f"✅ تم تحديث نشاط المستخدم: {user_id}")
            return True
            
    except Exception as e:
        logger.error(f"❌ خطأ في تحديث نشاط المستخدم: {e}")
        return False


def get_inactive_users(days_inactive: int = 1) -> List[Tuple[int, str, str]]:
    """
    الحصول على المستخدمين غير النشطين
    
    Args:
        days_inactive: عدد الأيام للاعتبار غير نشط
    
    Returns:
        قائمة tuples: (user_id, username, last_report_date)
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)
        
        with SessionLocal() as session:
            inactive_users = session.query(
                UserActivity.user_id,
                UserActivity.username,
                UserActivity.last_report_date
            ).filter(
                UserActivity.last_report_date < cutoff_date
            ).all()
            
            return inactive_users
            
    except Exception as e:
        logger.error(f"❌ خطأ في الحصول على المستخدمين غير النشطين: {e}")
        return []


def get_user_stats(user_id: int) -> Optional[dict]:
    """
    الحصول على إحصائيات مستخدم محدد
    """
    try:
        with SessionLocal() as session:
            user = session.query(UserActivity).filter_by(user_id=user_id).first()
            
            if not user:
                return None
            
            return {
                'user_id': user.user_id,
                'username': user.username,
                'full_name': user.full_name,
                'total_reports': user.total_reports,
                'last_report_date': user.last_report_date,
                'last_activity': user.last_activity,
                'days_since_last_report': (datetime.utcnow() - user.last_report_date).days if user.last_report_date else None
            }
            
    except Exception as e:
        logger.error(f"❌ خطأ في الحصول على إحصائيات المستخدم: {e}")
        return None


def get_all_users_activity() -> List[dict]:
    """
    الحصول على نشاط جميع المستخدمين
    """
    try:
        with SessionLocal() as session:
            users = session.query(UserActivity).all()
            
            result = []
            for user in users:
                result.append({
                    'user_id': user.user_id,
                    'username': user.username,
                    'full_name': user.full_name,
                    'total_reports': user.total_reports,
                    'last_report_date': user.last_report_date,
                    'last_activity': user.last_activity
                })
            
            return result
            
    except Exception as e:
        logger.error(f"❌ خطأ في الحصول على نشاط جميع المستخدمين: {e}")
        return []


# ====================================================
# 🔄 دمج مع نظام Translator الحالي
# ====================================================

def sync_with_translators():
    """
    مزامنة جدول user_activity مع جدول translators الحالي
    """
    try:
        from db.models import Translator
        
        with SessionLocal() as session:
            # الحصول على جميع المترجمين
            translators = session.query(Translator).all()
            
            synced_count = 0
            for translator in translators:
                # التحقق من وجود user_activity
                user_activity = session.query(UserActivity).filter_by(
                    user_id=translator.tg_user_id
                ).first()
                
                if not user_activity:
                    # إنشاء سجل جديد
                    user_activity = UserActivity(
                        user_id=translator.tg_user_id,
                        username=translator.full_name,
                        full_name=translator.full_name,
                        total_reports=0,
                        last_activity=translator.created_at
                    )
                    session.add(user_activity)
                    synced_count += 1
            
            session.commit()
            logger.info(f"✅ تمت مزامنة {synced_count} مستخدم")
            return True
            
    except Exception as e:
        logger.error(f"❌ خطأ في المزامنة: {e}")
        return False


# ====================================================
# 🧪 اختبار
# ====================================================

if __name__ == "__main__":
    print("="*60)
    print("🧪 اختبار نظام تتبع المستخدمين")
    print("="*60)
    
    # إنشاء الجدول
    if init_user_activity_table():
        print("✅ تم إنشاء الجدول")
    
    # اختبار تحديث نشاط
    update_user_activity(12345, "test_user", "Test User")
    print("✅ تم تحديث النشاط")
    
    # الحصول على إحصائيات
    stats = get_user_stats(12345)
    if stats:
        print(f"✅ الإحصائيات: {stats}")
    
    # مزامنة
    sync_with_translators()
    print("✅ تمت المزامنة")
    
    print("="*60)

