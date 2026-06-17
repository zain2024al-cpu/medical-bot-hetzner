# =============================
# config/settings.py — إعدادات البوت ✅ نسخة محسّنة للاستضافة السحابية
# =============================

import os
from dotenv import load_dotenv

# 🧭 تحميل متغيرات البيئة من ملف config.env (للتطوير المحلي فقط)
# في الاستضافة السحابية، المتغيرات تكون متوفرة مباشرة في البيئة
# ✅ استخدام المسار المطلق لضمان العمل بغض النظر عن مجلد التشغيل
_CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_ENV_PATH = os.path.join(_CONFIG_DIR, '..', 'config.env')
_CONFIG_ENV_PATH = os.path.normpath(_CONFIG_ENV_PATH)
try:
    load_dotenv(_CONFIG_ENV_PATH)
except FileNotFoundError:
    pass  # طبيعي في الاستضافة السحابية

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
