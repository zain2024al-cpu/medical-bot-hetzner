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

TRANSLATORS_SEED = [
    {"translator_id": 7345544036, "name": "ادريس"},
    {"translator_id": 1997643031, "name": "حسن"},
    {"translator_id": 6002303025, "name": "مصطفى"},
    {"translator_id": 8172870113, "name": "صبري"},
    {"translator_id": 5713657641, "name": "عزي"},
    {"translator_id": 591202186, "name": "زيد"},
    {"translator_id": 7504265481, "name": "نجم الدين"},
    {"translator_id": 7350590873, "name": "مهدي"},
    {"translator_id": 1938862867, "name": "واصل"},
    {"translator_id": 1982219162, "name": "ادم"},
    {"translator_id": 8310133494, "name": "هاشم"},
    {"translator_id": 7392642953, "name": "سعيد"},
    {"translator_id": 6043664891, "name": "محمد علي"},
    {"translator_id": 8054012415, "name": "عصام"},
    {"translator_id": 6979080725, "name": "معتز"},
    {"translator_id": 7536360652, "name": "عزالدين"},
]


def seed_translators_directory() -> int:
    try:
        from db.session import SessionLocal
        from db.models import TranslatorDirectory
        from sqlalchemy import or_

        with SessionLocal() as session:
            added_or_updated = 0
            for entry in TRANSLATORS_SEED:
                translator_id = entry["translator_id"]
                name = entry["name"]

                existing = session.query(TranslatorDirectory).filter(
                    or_(
                        TranslatorDirectory.translator_id == translator_id,
                        TranslatorDirectory.name.ilike(name)
                    )
                ).first()

                if existing:
                    updated = False
                    if existing.translator_id != translator_id:
                        existing.translator_id = translator_id
                        updated = True
                    if existing.name != name:
                        existing.name = name
                        updated = True
                    if updated:
                        added_or_updated += 1
                else:
                    session.add(TranslatorDirectory(translator_id=translator_id, name=name))
                    added_or_updated += 1

            if added_or_updated:
                session.commit()
            return added_or_updated
    except Exception as e:
        logger.error(f"Error seeding translators directory: {e}")
        return 0


def sync_reports_translator_ids() -> int:
    try:
        from db.session import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as session:
            result = session.execute(text("""
                UPDATE reports
                SET translator_id = (
                    SELECT translators.translator_id
                    FROM translators
                    WHERE TRIM(translators.name) = TRIM(reports.translator_name)
                )
                WHERE (translator_id IS NULL OR translator_id = 0)
                  AND translator_name IS NOT NULL
            """))
            session.commit()
            return result.rowcount or 0
    except Exception as e:
        logger.error(f"Error syncing report translator ids: {e}")
        return 0


def get_translators_from_database() -> List[Dict]:
    """
    الحصول على المترجمين من قاعدة البيانات
    """
    try:
        from db.session import SessionLocal
        from db.models import TranslatorDirectory
        
        with SessionLocal() as session:
            translators = session.query(TranslatorDirectory).order_by(TranslatorDirectory.name).all()
            
            result = []
            for t in translators:
                result.append({
                    'id': t.translator_id,
                    'name': t.name,
                    'telegram_id': t.translator_id,
                    'phone': None,
                    'is_approved': True
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
    الحصول على أسماء جميع المترجمين بترتيب محدد
    يحاول من قاعدة البيانات أولاً، ثم من الملف
    """
    # الترتيب المطلوب للصفحة الأولى
    priority_order = [
        "معتز", "ادم", "هاشم", "مصطفى", "حسن", "نجم الدين", "محمد علي",
        "صبري", "عزي", "سعيد", "عصام", "زيد", "مهدي", "ادريس",
        "واصل", "عزالدين", "عبدالسلام", "يحيى العنسي", "ياسر"
    ]
    
    # Try database first
    translators = get_translators_from_database()
    
    if translators:
        all_names = [t['name'] for t in translators]
    else:
        # Fallback to file
        all_names = get_translators_from_file()
    
    # ترتيب الأسماء: الأولوية أولاً ثم الباقي
    ordered_names = []
    remaining_names = []
    
    # إضافة الأسماء ذات الأولوية
    for name in priority_order:
        if name in all_names:
            ordered_names.append(name)
    
    # إضافة الأسماء المتبقية
    for name in all_names:
        if name not in priority_order:
            remaining_names.append(name)
    
    # دمج القوائم: الأولوية أولاً ثم الباقي
    return ordered_names + sorted(remaining_names)


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
        from db.models import TranslatorDirectory
        
        with SessionLocal() as session:
            t = session.query(TranslatorDirectory).filter_by(translator_id=translator_id).first()
            if t:
                return {
                    'id': t.translator_id,
                    'name': t.name,
                    'telegram_id': t.translator_id,
                    'phone': None,
                    'is_approved': True
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
        from db.models import TranslatorDirectory
        
        with SessionLocal() as session:
            existing = session.query(TranslatorDirectory).filter_by(name=name).first()
            if existing:
                logger.info(f"Translator already exists: {name}")
                return True

            translator_id_value = telegram_id if telegram_id is not None else None
            new_translator = TranslatorDirectory(
                translator_id=translator_id_value,
                name=name
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






