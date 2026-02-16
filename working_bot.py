import sys
import os
if sys.platform == 'win32':
    os.system('chcp 65001 >nul')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

import asyncio
from telegram.ext import Application
from config.settings import BOT_TOKEN

async def main():
    print("Starting simple bot...")
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Get bot info
    bot_info = await app.bot.get_me()
    print(f"Bot started: {bot_info.first_name} (@{bot_info.username})")
    
    # Simple command handler
    from telegram.ext import CommandHandler, MessageHandler, filters
    
    async def start(update, context):
        await update.message.reply_text("Bot is working! Send any message and I'll reply.")
    
    async def echo(update, context):
        await update.message.reply_text(f"You said: {update.message.text}")
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    print("Starting polling...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())