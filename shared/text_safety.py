# shared/text_safety.py
# Pure text-escaping helpers shared across all platform modules.
#
# No context reads, no database calls, no I/O — only text-in / text-out.
# Safe to call from any thread.
#
# ⚠️ لماذا هذا الملف موجود: شاشات كثيرة (تعديل التقرير، بطاقة النشر،
# تنبيهات الأدمن اليومية، ملخص الحالة...) تحشر نصاً حراً (شكوى/تشخيص/
# قرار طبيب/اسم مريض) داخل رسالة بـ parse_mode="Markdown". محرف واحد
# غير متزاوج من `_ * ` [` في ذلك النص الحر (شائع في نص طبي: "الحالة
# مستقرة* بانتظار المتابعة" أو "جرعة 500_مجم") يُسقط تحليل Telegram
# للرسالة بالكامل بـ BadRequest: Can't parse entities.
#
# قبل هذا الملف كانت الدالة نفسها معرَّفة بشكل مستقل مرتين
# (`user_reports_add_new_system/utils.py::escape_md_v1` و
# `services/broadcast_service.py::escape_markdown`)، وملفات أخرى كانت
# تستورد `telegram.helpers.escape_markdown` مباشرة كل مرة بدل استخدام
# غلاف موحَّد — نفس نمط "نفس المنطق منسوخ في أكثر من مكان" الذي أدّى
# لنسيان تطبيقه في ملفات جديدة أكثر من مرة. الآن: مكان واحد فقط يحتوي
# منطق التهريب الفعلي؛ الأسماء القديمة (`escape_md_v1`/`broadcast_
# service.escape_markdown`) أصبحت أغلفة رقيقة تستدعيه، فلا حاجة لتعديل
# عشرات مواضع الاستدعاء القائمة. أي كود جديد يبني رسالة Markdown من نص
# حر يجب أن يستورد `escape_markdown_v1` من هنا مباشرة.

from telegram.helpers import escape_markdown as _tg_escape_markdown


def escape_markdown_v1(text) -> str:
    """يهرّب محارف Markdown (النسخة القديمة v1 التي يستخدمها
    parse_mode="Markdown") من نص حر قبل حشره في رسالة تليجرام.

    escape_markdown(version=1) من مكتبة telegram هي التطبيق الرسمي
    لقواعد Telegram نفسها (وليست دالة مكتوبة يدوياً هنا قد تنحرف عنها).
    """
    return _tg_escape_markdown(str(text) if text is not None else "", version=1)
