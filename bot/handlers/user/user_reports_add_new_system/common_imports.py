# =============================
# common_imports.py
# Imports المشتركة بين جميع ملفات النظام
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, CommandHandler, InlineQueryHandler, ChosenInlineResultHandler, filters
from telegram.constants import ChatType
from telegram.helpers import escape_markdown
import logging
from datetime import datetime, timedelta
import calendar
import hashlib
from zoneinfo import ZoneInfo

# إعداد logger
logger = logging.getLogger(__name__)

# Imports مع معالجة الأخطاء
try:
    from bot.shared_auth import ensure_approved
except ImportError:
    ensure_approved = lambda *a, **kw: True

try:
    from db.session import SessionLocal
except ImportError:
    SessionLocal = None

try:
    from db.models import Translator, Report, Patient, Hospital, Department, Doctor
except ImportError:
    Translator = Report = Patient = Hospital = Department = Doctor = None

try:
    from config.settings import TIMEZONE
except ImportError:
    TIMEZONE = 'Asia/Kolkata'  # توقيت الهند (IST = UTC+5:30)

from ..user_reports_add_helpers import (
    PREDEFINED_HOSPITALS, PREDEFINED_DEPARTMENTS, DIRECT_DEPARTMENTS,
    PREDEFINED_ACTIONS, validate_text_input, validate_english_only, save_report_to_db,
    broadcast_report, create_evaluation
)

from services.error_monitoring import error_monitor
from services.doctors_smart_search import search_doctors

# ثوابت
MONTH_NAMES_AR = {
    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
    5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس",
    9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
}

WEEKDAYS_AR = ["س", "أ", "ث", "ر", "خ", "ج", "س"]






