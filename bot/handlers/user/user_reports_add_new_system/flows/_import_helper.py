# =============================
# _import_helper.py
# Helper function لتحميل الملف الأصلي لتجنب circular import
# =============================

import os
import importlib.util
import logging

logger = logging.getLogger(__name__)

_original_module_cache = None

def load_original_module():
    """تحميل الملف الأصلي مرة واحدة فقط (cached)"""
    global _original_module_cache
    if _original_module_cache is None:
        import sys
        current_file = os.path.abspath(__file__)
        current_dir = os.path.dirname(current_file)  # flows/
        parent_dir = os.path.dirname(current_dir)  # user_reports_add_new_system/
        grandparent_dir = os.path.dirname(parent_dir)  # user/
        original_file = os.path.join(grandparent_dir, 'user_reports_add_new_system.py')
        
        if os.path.exists(original_file):
            try:
                # إضافة workspace root (الذي يحتوي على bot/) إلى sys.path
                handlers_dir = os.path.dirname(grandparent_dir)  # handlers/
                bot_dir = os.path.dirname(handlers_dir)  # bot/
                workspace_root = os.path.dirname(bot_dir)  # workspace root
                
                if workspace_root not in sys.path:
                    sys.path.insert(0, workspace_root)
                
                # استخدام اسم package صحيح للسماح بـ relative imports
                module_name = "bot.handlers.user.user_reports_add_new_system_original"
                spec = importlib.util.spec_from_file_location(module_name, original_file)
                _original_module_cache = importlib.util.module_from_spec(spec)
                
                # تعيين __package__ و __file__ للسماح بـ relative imports
                _original_module_cache.__package__ = "bot.handlers.user"
                _original_module_cache.__name__ = module_name
                _original_module_cache.__file__ = original_file
                
                spec.loader.exec_module(_original_module_cache)
                logger.debug(f"✅ Loaded original module from: {original_file}")
            except Exception as e:
                logger.error(f"❌ Error loading original module: {e}", exc_info=True)
                _original_module_cache = False  # Mark as failed
        else:
            logger.warning(f"⚠️ Original file not found: {original_file} - Using modular version only")
            _original_module_cache = False  # Mark as failed
    return _original_module_cache if _original_module_cache is not False else None

