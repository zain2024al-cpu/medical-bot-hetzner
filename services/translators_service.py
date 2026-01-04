# -*- coding: utf-8 -*-
"""
خدمة المترجمين الموحدة
Unified Translators Service - Single Source of Truth (Database)
"""

import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Cache
_TRANSLATORS_CACHE = None
_CACHE_TIMEOUT = 60  # seconds


def get_translators_from_database() -> List[Dict]:
    """
    الحصول على المترجمين من قاعدة البيانات
    """
    try:
        from db.session import SessionLocal
        from db.models import Translator
        
        with SessionLocal() as session:
            translators = session.query(Translator).filter(
                Translator.is_approved == True
            ).order_by(Translator.full_name).all()
            
            result = []
            for t in translators:
                result.append({
                    'id': t.id,
                    'name': t.full_name,
                    'telegram_id': t.telegram_id,
                    'phone': t.phone,
                    'is_approved': t.is_approved
                })
            
            logger.info(f"Loaded {len(result)} translators from database")
            return result
            
    except Exception as e:
        logger.error(f"Error loading translators from database: {e}")
        return []


def get_translators_from_file() -> List[str]:
    """
    الحصول على المترجمين من الملف (fallback)
    """
    possible_paths = [
        os.path.join(os.path.dirname(__file__), '..', 'data', 'translator_names.txt'),
        'data/translator_names.txt',
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    names = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                logger.info(f"Loaded {len(names)} translators from file")
                return names
            except Exception as e:
                logger.error(f"Error reading translator file: {e}")
    
    return []


def get_all_translator_names() -> List[str]:
    """
    الحصول على أسماء جميع المترجمين
    يحاول من قاعدة البيانات أولاً، ثم من الملف
    """
    # Try database first
    translators = get_translators_from_database()
    
    if translators:
        return [t['name'] for t in translators]
    
    # Fallback to file
    return get_translators_from_file()


def get_all_translators() -> List[Dict]:
    """
    الحصول على جميع المترجمين مع التفاصيل
    """
    translators = get_translators_from_database()
    
    if translators:
        return translators
    
    # Fallback: convert file names to dicts
    names = get_translators_from_file()
    return [{'id': i, 'name': name, 'telegram_id': None} for i, name in enumerate(names)]


def get_translator_by_name(name: str) -> Optional[Dict]:
    """
    البحث عن مترجم بالاسم
    """
    translators = get_all_translators()
    name_lower = name.lower().strip()
    
    for t in translators:
        if t['name'].lower() == name_lower:
            return t
    
    return None


def get_translator_by_id(translator_id: int) -> Optional[Dict]:
    """
    البحث عن مترجم بالID
    """
    try:
        from db.session import SessionLocal
        from db.models import Translator
        
        with SessionLocal() as session:
            t = session.query(Translator).filter_by(id=translator_id).first()
            if t:
                return {
                    'id': t.id,
                    'name': t.full_name,
                    'telegram_id': t.telegram_id,
                    'phone': t.phone,
                    'is_approved': t.is_approved
                }
    except Exception as e:
        logger.error(f"Error getting translator by id: {e}")
    
    return None


def add_translator(name: str, telegram_id: int = None, phone: str = None) -> bool:
    """
    إضافة مترجم جديد
    """
    try:
        from db.session import SessionLocal
        from db.models import Translator
        
        with SessionLocal() as session:
            # Check if exists
            existing = session.query(Translator).filter_by(full_name=name).first()
            if existing:
                logger.info(f"Translator already exists: {name}")
                return True
            
            new_translator = Translator(
                full_name=name,
                telegram_id=telegram_id,
                phone=phone,
                is_approved=True
            )
            session.add(new_translator)
            session.commit()
            
            logger.info(f"Added new translator: {name}")
            return True
            
    except Exception as e:
        logger.error(f"Error adding translator: {e}")
        return False


def sync_file_to_database() -> int:
    """
    مزامنة المترجمين من الملف إلى قاعدة البيانات
    Returns number of translators synced
    """
    file_names = get_translators_from_file()
    db_translators = get_translators_from_database()
    db_names = [t['name'].lower() for t in db_translators]
    
    count = 0
    for name in file_names:
        if name.lower() not in db_names:
            if add_translator(name):
                count += 1
    
    logger.info(f"Synced {count} translators from file to database")
    return count


def get_translators_count() -> int:
    """
    عدد المترجمين
    """
    return len(get_all_translator_names())


# For compatibility with old code
def load_translator_names() -> List[str]:
    """
    Alias for get_all_translator_names
    """
    return get_all_translator_names()


__all__ = [
    'get_all_translator_names',
    'get_all_translators',
    'get_translator_by_name',
    'get_translator_by_id',
    'add_translator',
    'sync_file_to_database',
    'get_translators_count',
    'load_translator_names',
]






