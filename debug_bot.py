# ================================================
# debug_bot.py - تشغيل البوت مع Debug تفصيلي
# ================================================

import sys
import os
if sys.platform == 'win32':
    os.system('chcp 65001 >nul')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

import asyncio
import logging
import warnings
from telegram import Update
from telegram.ext import Application, PicklePersistence, Defaults
from telegram.constants import ParseMode
from config.settings import BOT_TOKEN

# Enable detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Disable warnings
warnings.filterwarnings("ignore", category=UserWarning, message=".*per_.*settings.*")

async def test_run():
    print("="*50)
    print("Starting Bot Debug Test...")
    print("="*50)
    
    # Test 1: Create Application
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        print("✅ Application created successfully")
    except Exception as e:
        print(f"❌ Application creation failed: {e}")
        return
    
    # Test 2: Get bot info
    try:
        bot_info = await app.bot.get_me()
        print(f"✅ Bot info: {bot_info.first_name} (@{bot_info.username})")
    except Exception as e:
        print(f"❌ Bot info failed: {e}")
        return
    
    # Test 3: Initialize polling
    try:
        print("🚀 Starting polling mode...")
        await app.initialize()
        print("✅ App initialized")
        
        await app.start()
        print("✅ App started")
        
        await app.updater.start_polling()
        print("✅ Polling started")
        
        print("🎉 Bot is running! Press Ctrl+C to stop...")
        
        # Keep running for 30 seconds
        await asyncio.sleep(30)
        
        print("🛑 Stopping bot...")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        print("✅ Bot stopped gracefully")
        
    except Exception as e:
        print(f"❌ Polling failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_run())