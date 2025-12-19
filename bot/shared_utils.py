# =============================
# bot/utils.py
# 🧰 دوال مساعدة عامة للمشروع
# =============================
from datetime import datetime

# 🕓 تنسيق التاريخ بشكل موحد
def format_datetime(dt: datetime) -> str:
    """تنسيق التاريخ والوقت إلى صيغة موحدة."""
    if not dt:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M")

# 🧮 التحقق من أن النص يمثل عمرًا صحيحًا
def is_valid_age(age_text: str) -> bool:
    """يتحقق من أن العمر رقم صحيح ومناسب."""
    if not age_text.isdigit():
        return False
    age = int(age_text)
    return 0 < age < 120

# 📝 تنسيق النصوص الطويلة لتكون مناسبة للإرسال
def shorten_text(text: str, max_length: int = 200) -> str:
    """يقص النص الطويل مع إضافة (...) في النهاية."""
    if len(text) > max_length:
        return text[:max_length - 3] + "..."
    return text

# 🧹 تنظيف المدخلات من المسافات الزائدة
def clean_input(text: str) -> str:
    """يزيل الفراغات الزائدة من البداية والنهاية."""
    return text.strip() if text else ""

# 📅 تحويل نص تاريخ إلى كائن datetime
def parse_date(date_str: str) -> datetime | None:
    """يحاول تحويل نص إلى datetime، وإلا يعيد None."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
def summarize_text(text: str) -> str:
    """تلخيص بسيط مؤقت — يمكن تطويره لاحقًا."""
    return text[:400] + "..." if len(text) > 400 else text

