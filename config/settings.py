# =============================
# config/settings.py — إعدادات البوت ✅ نسخة محسّنة للاستضافة السحابية
# =============================

import os
import logging
from dotenv import load_dotenv

# ── تحميل متغيرات البيئة ─────────────────────────────────────────────────────
# يتم تحميل كلا الملفين بالترتيب، مع override=True حتى تأخذ قيم الملف
# الأولوية على أي قيم موجودة مسبقاً في البيئة (مثل pm2 أو system env).
#
# ترتيب الأولوية (الأعلى يفوز):
#   1. config.env  (الملف الرئيسي للإعدادات)
#   2. .env        (ملف بديل مقبول أيضاً)
#   3. system env  (أدنى أولوية)
#
_CONFIG_DIR     = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT   = os.path.normpath(os.path.join(_CONFIG_DIR, '..'))
_CONFIG_ENV     = os.path.join(_PROJECT_ROOT, 'config.env')
_DOTENV         = os.path.join(_PROJECT_ROOT, '.env')

# load .env first (lower priority)
if os.path.isfile(_DOTENV):
    load_dotenv(_DOTENV, override=True)

# load config.env second (higher priority — overrides .env)
if os.path.isfile(_CONFIG_ENV):
    load_dotenv(_CONFIG_ENV, override=True)

_settings_logger = logging.getLogger("config.settings")
_settings_logger.info(
    f"[config] env loaded"
    f"  config.env={'✅' if os.path.isfile(_CONFIG_ENV) else '❌ missing'}"
    f"  .env={'✅' if os.path.isfile(_DOTENV) else '❌ missing'}"
    f"  project_root={_PROJECT_ROOT}"
)

# 🧭 توكن بوت التليجرام من @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN")

# 🌍 المنطقة الزمنية (للتذكيرات وجدول اليوم)
# بنجلور، الهند - توقيت IST (UTC+5:30)
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")

# 👑 معرفات الإداريين (ID Telegram) — يمكن وضع أكثر من ID مفصولة بفاصلة
ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
]

# 📢 معرف مجموعة الإشعارات (لإشعارات طلبات المستخدمين)
NOTIFICATIONS_GROUP_ID = os.getenv("NOTIFICATIONS_GROUP_ID", "")

# 📢 معرف مجموعة التقارير (لنشر التقارير)
REPORTS_GROUP_ID = os.getenv("REPORTS_GROUP_ID", "")

# 📄 معرف مجموعة التقارير الطبية (PDF الصور الطبية)
MEDICAL_REPORTS_GROUP_ID = os.getenv("MEDICAL_REPORTS_GROUP_ID", "-1002190577845")

# 🏥 معرف مجموعة توثيق الرعاية الصحية (نشر تقارير الوحدات الصحية)
HEALTHCARE_GROUP_ID = os.getenv("HEALTHCARE_GROUP_ID", "")

# 🔧 معرف مجموعة الخدمات العامة (نشر تقارير الوصول والمغادرة والخدمات)
GENERAL_SERVICES_GROUP_ID = os.getenv("GENERAL_SERVICES_GROUP_ID", "")

# 🪪 معرف مجموعة الإقامات (نشر أحداث الإقامات)
RESIDENCY_GROUP_ID = os.getenv("RESIDENCY_GROUP_ID", "")

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
PORT = int(os.getenv("PORT", "8080"))
DATABASE_URL = os.getenv("DATABASE_URL", "")

# 📊 إعدادات إضافية
WEB_CONCURRENCY = int(os.getenv("WEB_CONCURRENCY", "1"))
PYTHONUNBUFFERED = os.getenv("PYTHONUNBUFFERED", "1")
