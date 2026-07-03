# ================================================
# simple_bot.py - نسخة بسيطة بدون Unicode
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
from telegram.ext import Application
from config.settings import BOT_TOKEN

# Enable detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Disable warnings
warnings.filterwarnings("ignore", category=UserWarning, message=".*per_.*settings.*")

async def main():
    print("="*50)
    print("Starting Medical Bot...")
    print("="*50)
    
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        print("SUCCESS: Application created")
        
        bot_info = await app.bot.get_me()
        print(f"SUCCESS: Bot {bot_info.first_name} (@{bot_info.username}) is ready!")
        
        print("Starting polling...")
        await app.initialize()
        await app.start()
        
        print("SUCCESS: Bot is running!")
        print("Bot is listening for messages...")
        print("Press Ctrl+C to stop")
        
        # Simple message handler
        async def echo(update: Update, context):
            if update.message:
                await update.message.reply_text("Bot is working! Send /start to begin.")
        
        from telegram.ext import MessageHandler, filters
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
        
        await app.updater.start_polling(drop_pending_updates=True)
        
        # Keep running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("Stopping bot...")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        print("Bot stopped")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())