# =============================
# bot/handlers/user/button_monitor.py
# 🔹 نظام مراقبة الأزرار غير المعالجة
# =============================

from telegram import Update
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)


async def catch_all_unhandled_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج عام لالتقاط جميع الأزرار غير المعالجة
    """
    query = update.callback_query
    
    if query:
        await query.answer("⚠️ هذا الزر غير متاح حالياً")
        logger.warning(f"Unhandled button callback: {query.data}")
    
    return None


