# ================================================
# test_bot_startup.py
# 🔹 اختبار تشغيل البوت بدون مشاكل الترميز
# ================================================

import sys
import os

# Fix Windows encoding issues
if sys.platform == 'win32':
    import locale
    try:
        # Set console to UTF-8
        os.system('chcp 65001 >nul')
        # Set Python default encoding
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

print('Testing bot startup...')

try:
    import warnings
    warnings.filterwarnings('ignore')
    print('Warnings configured')
    
    from config.settings import BOT_TOKEN
    print('Config loaded successfully')
    
    from db.session import init_database, engine
    print('Database session loaded')
    
    # Test database
    db_init = init_database()
    print(f'Database init: {db_init}')
    
    from bot.handlers_registry import register_all_handlers
    print('Handlers registry loaded')
    
    from telegram.ext import Application
    print('Telegram library loaded')
    
    print('All imports successful!')
    print('Bot should start properly...')
    
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()