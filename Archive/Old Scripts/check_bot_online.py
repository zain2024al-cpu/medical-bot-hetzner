# ================================================
# فحص حالة البوت عبر الإنترنت
# ================================================

import asyncio
import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# إصلاح الترميز في Windows
if sys.platform == 'win32':
    os.system('chcp 65001 >nul')
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# تحميل الإعدادات
load_dotenv("config.env")

try:
    from telegram import Bot
    from telegram.error import TelegramError, NetworkError, TimedOut
except ImportError:
    print("خطأ: يجب تثبيت python-telegram-bot")
    print("قم بتشغيل: pip install python-telegram-bot")
    sys.exit(1)

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_colored(text, color=Colors.RESET):
    """طباعة نص ملون"""
    print(f"{color}{text}{Colors.RESET}")

async def check_bot_status():
    """فحص حالة البوت عبر Telegram API"""
    
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        print_colored("[ERROR] خطأ: لم يتم العثور على BOT_TOKEN في config.env", Colors.RED)
        return False
    
    print_colored("\n" + "="*60, Colors.BLUE)
    print_colored("فحص حالة البوت عبر الإنترنت", Colors.BOLD + Colors.BLUE)
    print_colored("="*60 + "\n", Colors.BLUE)
    
    bot = Bot(token=bot_token)
    
    results = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "bot_token": bot_token[:10] + "..." if bot_token else "غير موجود",
        "checks": {}
    }
    
    # 1. فحص getMe (التحقق من صحة التوكن)
    print_colored("1. فحص صحة التوكن (getMe)...", Colors.YELLOW)
    try:
        bot_info = await bot.get_me()
        results["checks"]["getMe"] = {
            "status": "نجح",
            "bot_username": bot_info.username,
            "bot_id": bot_info.id,
            "bot_name": bot_info.first_name,
            "can_join_groups": bot_info.can_join_groups,
            "can_read_all_group_messages": bot_info.can_read_all_group_messages,
            "supports_inline_queries": bot_info.supports_inline_queries
        }
        print_colored(f"   [OK] البوت متصل: @{bot_info.username} (ID: {bot_info.id})", Colors.GREEN)
        print_colored(f"   الاسم: {bot_info.first_name}", Colors.GREEN)
    except NetworkError as e:
        results["checks"]["getMe"] = {
            "status": "❌ فشل - خطأ في الشبكة",
            "error": str(e)
        }
        print_colored(f"   [ERROR] خطأ في الاتصال بالشبكة: {e}", Colors.RED)
        return False
    except TelegramError as e:
        results["checks"]["getMe"] = {
            "status": "فشل - خطأ في Telegram",
            "error": str(e)
        }
        print_colored(f"   [ERROR] خطأ في Telegram API: {e}", Colors.RED)
        return False
    except Exception as e:
        results["checks"]["getMe"] = {
            "status": "فشل - خطأ غير متوقع",
            "error": str(e)
        }
        print_colored(f"   [ERROR] خطأ غير متوقع: {e}", Colors.RED)
        return False
    
    # 2. فحص getUpdates (التحقق من أن البوت يستقبل التحديثات)
    print_colored("\n2. فحص استقبال التحديثات (getUpdates)...", Colors.YELLOW)
    try:
        updates = await bot.get_updates(limit=1, timeout=5)
        results["checks"]["getUpdates"] = {
            "status": "نجح",
            "pending_updates": len(updates),
            "message": "البوت يستقبل التحديثات بنجاح"
        }
        print_colored(f"   [OK] البوت يستقبل التحديثات (عدد التحديثات المعلقة: {len(updates)})", Colors.GREEN)
    except TimedOut:
        results["checks"]["getUpdates"] = {
            "status": "انتهت المهلة",
            "message": "البوت قد يكون مشغولاً أو لا يوجد تحديثات"
        }
        print_colored("   [WARNING] انتهت المهلة (هذا طبيعي إذا لم يكن هناك تحديثات)", Colors.YELLOW)
    except Exception as e:
        results["checks"]["getUpdates"] = {
            "status": "❌ فشل",
            "error": str(e)
        }
        print_colored(f"   [WARNING] تحذير: {e}", Colors.YELLOW)
    
    # 3. فحص getWebhookInfo (التحقق من إعدادات Webhook)
    print_colored("\n3. فحص إعدادات Webhook...", Colors.YELLOW)
    try:
        webhook_info = await bot.get_webhook_info()
        results["checks"]["webhook"] = {
            "status": "نجح",
            "url": webhook_info.url or "غير محدد",
            "has_custom_certificate": webhook_info.has_custom_certificate,
            "pending_update_count": webhook_info.pending_update_count,
            "last_error_date": webhook_info.last_error_date.strftime("%Y-%m-%d %H:%M:%S") if webhook_info.last_error_date else None,
            "last_error_message": webhook_info.last_error_message,
            "max_connections": webhook_info.max_connections
        }
        
        if webhook_info.url:
            print_colored(f"   [OK] Webhook مفعّل: {webhook_info.url}", Colors.GREEN)
            print_colored(f"   التحديثات المعلقة: {webhook_info.pending_update_count}", Colors.GREEN)
            if webhook_info.last_error_message:
                print_colored(f"   [WARNING] آخر خطأ: {webhook_info.last_error_message}", Colors.YELLOW)
        else:
            print_colored("   [INFO] Webhook غير مفعّل (البوت يعمل في وضع Polling)", Colors.BLUE)
    except Exception as e:
        results["checks"]["webhook"] = {
            "status": "❌ فشل",
            "error": str(e)
        }
        print_colored(f"   [WARNING] تحذير: {e}", Colors.YELLOW)
    
    # 4. فحص قاعدة البيانات (إذا كانت متاحة)
    print_colored("\n4. فحص قاعدة البيانات...", Colors.YELLOW)
    try:
        from db.session import SessionLocal
        from sqlalchemy import text
        
        with SessionLocal() as session:
            result = session.execute(text("SELECT 1")).scalar()
        
        results["checks"]["database"] = {
            "status": "نجح",
            "message": "قاعدة البيانات متصلة وتعمل بشكل صحيح"
        }
        print_colored("   [OK] قاعدة البيانات متصلة وتعمل بشكل صحيح", Colors.GREEN)
    except ImportError:
        results["checks"]["database"] = {
            "status": "غير متاح",
            "message": "مكتبات قاعدة البيانات غير مثبتة"
        }
        print_colored("   [WARNING] مكتبات قاعدة البيانات غير متاحة", Colors.YELLOW)
    except Exception as e:
        results["checks"]["database"] = {
            "status": "فشل",
            "error": str(e)
        }
        print_colored(f"   [ERROR] خطأ في قاعدة البيانات: {e}", Colors.RED)
    
    # 5. ملخص النتائج
    print_colored("\n" + "="*60, Colors.BLUE)
    print_colored("ملخص النتائج", Colors.BOLD + Colors.BLUE)
    print_colored("="*60, Colors.BLUE)
    
    all_passed = True
    for check_name, check_result in results["checks"].items():
        status = check_result.get("status", "غير معروف")
        if "نجح" in status or "OK" in status:
            print_colored(f"[OK] {check_name}: {status}", Colors.GREEN)
        elif "غير متاح" in status or "WARNING" in status or "انتهت" in status:
            print_colored(f"[WARNING] {check_name}: {status}", Colors.YELLOW)
        else:
            print_colored(f"[ERROR] {check_name}: {status}", Colors.RED)
            all_passed = False
    
    print_colored("\n" + "="*60, Colors.BLUE)
    if all_passed:
        print_colored("[OK] البوت يعمل بشكل صحيح عبر الإنترنت!", Colors.BOLD + Colors.GREEN)
    else:
        print_colored("[WARNING] البوت متصل ولكن هناك بعض المشاكل", Colors.BOLD + Colors.YELLOW)
    print_colored("="*60 + "\n", Colors.BLUE)
    
    # حفظ النتائج في ملف JSON
    try:
        with open("bot_status_check.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print_colored("[INFO] تم حفظ النتائج في: bot_status_check.json", Colors.BLUE)
    except Exception as e:
        print_colored(f"[WARNING] لم يتم حفظ النتائج: {e}", Colors.YELLOW)
    
    return all_passed

async def main():
    """الدالة الرئيسية"""
    try:
        success = await check_bot_status()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print_colored("\n\n[WARNING] تم إلغاء العملية من قبل المستخدم", Colors.YELLOW)
        sys.exit(1)
    except Exception as e:
        print_colored(f"\n\n[ERROR] خطأ غير متوقع: {e}", Colors.RED)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
