# =============================
# config/settings.py — إعدادات البوت ✅ نسخة محسّنة للاستضافة السحابية
# =============================

import os
from dotenv import load_dotenv

# 🧭 تحميل متغيرات البيئة من ملف config.env (للتطوير المحلي فقط)
# في الاستضافة السحابية، المتغيرات تكون متوفرة مباشرة في البيئة
# محاولة تحميل من عدة مواقع محتملة
config_paths = [
    "config.env",  # المجلد الحالي أولاً
    "/root/medical-bot-hetzner/config.env",  # مسار Hetzner VPS
    "/home/botuser/medical-bot/temp_upload/config.env",  # مسار السيرفر الرئيسي
    "/home/botuser/medical-bot/config.env",  # مسار بديل
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.env"),  # مسار نسبي
]

config_loaded = False
for path in config_paths:
    if os.path.exists(path):
        if load_dotenv(path):
            config_loaded = True
            break

# 🧭 توكن بوت التليجرام من @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 🌍 المنطقة الزمنية (للتذكيرات وجدول اليوم)
# بنجلور، الهند - توقيت IST (UTC+5:30)
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")

# 👑 معرفات الإداريين (ID Telegram) — يمكن وضع أكثر من ID مفصولة بفاصلة
ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
]

# 🗂️ مسار قاعدة البيانات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "db", "medical_reports.db")

# 🖨️ إعدادات تقارير PDF
PDF_TITLE = "Medical Reports Summary"
PDF_AUTHOR = "Hospital Admin System"

# 🧠 إعدادات الذكاء الاصطناعي (تحليل البيانات)
AI_ENABLED = os.getenv("AI_ENABLED", "true").lower() in ("true", "1", "yes")
AI_MODEL_NAME = os.getenv("AI_MODEL_NAME", "gpt-4")
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "2000"))

# 🔑 OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# 🌐 إعدادات الاستضافة السحابية
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
PORT = int(os.getenv("PORT", "0"))  # 0 يعني لا يوجد port (وضع محلي)
DATABASE_URL = os.getenv("DATABASE_URL", "")

# 🔍 تحديد البيئة (محلي أو Hetzner)
HETZNER_DEPLOYMENT = os.getenv("HETZNER_DEPLOYMENT", "false").lower() == "true"
IS_LOCAL = not HETZNER_DEPLOYMENT and PORT == 0

# 📊 إعدادات إضافية
WEB_CONCURRENCY = int(os.getenv("WEB_CONCURRENCY", "1"))
PYTHONUNBUFFERED = os.getenv("PYTHONUNBUFFERED", "1")

# 👥 إعدادات المجموعات
# معرف المجموعة (سيتم الحصول عليه تلقائياً عند إضافة البوت للمجموعة)
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID", "")
# رابط المجموعة
GROUP_INVITE_LINK = os.getenv("GROUP_INVITE_LINK", "https://t.me/+Ok0L5LL3TX83MjA1")
