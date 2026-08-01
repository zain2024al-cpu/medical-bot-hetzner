# -*- coding: utf-8 -*-
"""التوقيت المحلي لوحدات الرعاية الصحية.

المستخدمون يعملون بتوقيت الهند (Asia/Kolkata = UTC+5:30)، بينما كانت
الوحدات تختم السجلات بـ ``datetime.utcnow()``. الفرق يعني أن أي عمل يقع
بين 00:00 و 05:29 بتوقيت الهند كان يُخزَّن باسم **اليوم السابق** — فيختفي
ذلك اليوم من مسير الإخلاء الذي يفلتر حسب التاريخ التقويمي.

نفس منطق ``db.models._now_ist_naive``: قيمة naive بلا ``tzinfo`` لأن أعمدة
``DateTime`` في القاعدة تُخزَّن بلا منطقة زمنية.
"""
from datetime import datetime, timedelta, timezone

__all__ = ["now_ist"]


def now_ist() -> datetime:
    """الوقت الحالي بتوقيت الهند (UTC+5:30) بدون tzinfo."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)
    except Exception:
        ist = timezone(timedelta(hours=5, minutes=30))
        return datetime.now(timezone.utc).astimezone(ist).replace(tzinfo=None)
