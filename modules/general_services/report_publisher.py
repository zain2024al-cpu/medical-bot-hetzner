# modules/general_services/report_publisher.py
# Unified publish system for all general-services sub-modules.
# Errors are logged and swallowed — publication failure never crashes the flow.

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from telegram import InputMediaPhoto

from config.settings import (
    ADMIN_IDS, GENERAL_SERVICES_GROUP_ID, GS_ARRIVALS_GROUP_ID, GS_NOTIFY_ADMINS,
)

logger = logging.getLogger(__name__)


@dataclass
class GSPublishData:
    """Data passed to publish() by every GS sub-module."""
    workflow_type:    str           # "arrivals" | "departures" | "public_services"
    workflow_label:   str           # Arabic label
    workflow_icon:    str           # emoji
    body_lines:       list[str]     # pre-formatted Arabic lines for the report body
    images:           list[dict] = field(default_factory=list)  # UploadedFile.to_dict() list
    # 📎 وثائق تُجمَّع في ملف PDF واحد منظَّم (غلاف + صفحة لكل وثيقة بعنوان
    # يعرّف صاحبها) وتُنشَر في المجموعة **بعد** النصّ: [{"file_id", "caption"}].
    # ⚠️ مستقلّة عن `images`: تلك صور تُرسَل فور النصّ كألبوم مباشر، وهذه
    # وثائق نوعها مجهول (صورة أو ملف) كانت تُرسَل فرادى فتضيع بين إشعارات
    # المجموعة — فصارت ملفاً واحداً بدلاً من ذلك (طلب المستخدم صراحةً).
    documents:        list[dict] = field(default_factory=list)
    # 📨 نسخ خاصة (أدمن + مُدخِل) بجانب المجموعة. ⚠️ الافتراضي True فلا يتغيّر
    # شيء للمغادرة والخدمات العامة؛ الوصول يُعطِّله لأن له مجموعته، وتعود
    # النسخ الخاصة تلقائياً **فقط** إن لم تستلم المجموعة التقرير.
    private_copies:   bool = True
    created_by_id:    Optional[int] = None
    created_by_name:  str = ""
    record_date:      str = field(default_factory=lambda: datetime.utcnow().isoformat())


async def _send_text(bot, chat_id, text: str) -> bool:
    """يرسل نصّ التقرير. يُرجِع هل وصل.

    ⚠️ Markdown أولاً ثم نصّ عادي: القيم المُدخَلة (أسماء، ملاحظات) قد تحمل
    `_ * [` فيرفض تليجرام الرسالة كلها بـ`can't parse entities`. وهذا كان
    احتمالاً نظرياً مأمون العاقبة ما دامت النسخ الخاصة تصل الأدمن؛ أما وقد
    صارت المجموعة قناة الوصول الوحيدة، فالرفض يعني تقريراً لا يصل أحداً.
    الأسطر الخام (`*`) تظهر في النسخة العادية، وهذا أهون من الضياع.
    """
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        return True
    except Exception as first:
        try:
            await bot.send_message(chat_id=chat_id, text=text)
            logger.warning(f"[gs_publisher] Markdown رُفض إلى {chat_id} ({first}) — وصل نصّاً عادياً")
            return True
        except Exception as second:
            logger.warning(f"[gs_publisher] فشل الإرسال إلى {chat_id}: {first} / {second}")
            return False


async def _send_private_copies(bot, data: GSPublishData, text: str) -> None:
    notified_user_ids: set[int] = set()

    if GS_NOTIFY_ADMINS:
        for admin_id in ADMIN_IDS:
            if await _send_text(bot, admin_id, text):
                notified_user_ids.add(admin_id)
    else:
        logger.info("[gs_publisher] GS_NOTIFY_ADMINS=0 — تُخطّى إشعارات الأدمن الخاصة")

    # ✅ عرض التقرير الفعلي لمن نشره — لم يكن يرى إلا رسالة نجاح مختصرة
    # («تم الحفظ والنشر») لا محتوى التقرير نفسه، بصرف النظر عن كونه أدمناً
    # مُدرَجاً في ADMIN_IDS أو عضو صلاحية وحدة فقط. مستقل تماماً عن
    # GS_NOTIFY_ADMINS/إعداد مجموعة الخدمات — طلب المستخدم صراحةً.
    if data.created_by_id and data.created_by_id not in notified_user_ids:
        await _send_text(bot, data.created_by_id, text)


async def publish(bot, data: GSPublishData) -> None:
    """Publish a GS record to the GS group (+ private copies unless disabled)."""
    text = _build_text(data)

    if data.private_copies:
        await _send_private_copies(bot, data, text)

    group_id = _resolve_group_id(data.workflow_type)
    group_ok = False
    if not group_id:
        logger.warning("[gs_publisher] لا مجموعة مضبوطة لتقارير %s — تُخطّى المجموعة",
                       data.workflow_type)
    else:
        group_ok = await _send_text(bot, group_id, text)

        if data.images:
            await _send_images(bot, group_id, data)

        if data.documents:
            _spawn_documents_delivery(bot, group_id, data)

    # ⚠️ **الاحتياط**: النسخ الخاصة أُلغيت لهذا النوع، فالمجموعة قناته الوحيدة.
    # إن لم تستلم التقرير (بوت أُخرج منها، صلاحية نُزعت، مجموعة غير مضبوطة)
    # صارت النسخ الخاصة هي ما يمنع أن يضيع التقرير بصمت — البيانات محفوظة في
    # القاعدة، لكن لا أحد يعلم أنها وصلت.
    if not data.private_copies and not group_ok:
        logger.warning("[gs_publisher] المجموعة لم تستلم تقرير %s — نُسَخ خاصة احتياطية",
                       data.workflow_type)
        await _send_private_copies(bot, data, text)


def _build_text(data: GSPublishData) -> str:
    from modules.general_services.views import format_arabic_datetime
    date_str = format_arabic_datetime(data.record_date)
    lines = [
        f"*{data.workflow_icon} {data.workflow_label}*",
        f"📅 *التاريخ:*  {date_str}",
        "",
    ] + data.body_lines
    return "\n".join(lines)


async def _send_images(bot, group_id, data: GSPublishData) -> None:
    file_ids = [d.get("file_id") for d in data.images if d.get("file_id")]
    if not file_ids:
        return
    caption = f"📎 {data.workflow_icon} {data.workflow_label}"
    if len(file_ids) == 1:
        try:
            await bot.send_photo(chat_id=group_id, photo=file_ids[0], caption=caption)
        except Exception as exc:
            logger.warning(f"[gs_publisher] photo send failed: {exc}")
        return
    media = [
        InputMediaPhoto(media=fid, caption=caption if i == 0 else "")
        for i, fid in enumerate(file_ids[:10])
    ]
    try:
        await bot.send_media_group(chat_id=group_id, media=media)
    except Exception as exc:
        logger.warning(f"[gs_publisher] media group failed: {exc}")


# ⚠️ مراجع قوية للمهام الخلفية: `create_task` لا يحتفظ بمرجع لمهمته، والمهمة
# التي لا مرجع لها قد يجمعها جامع المهملات قبل أن تنتهي — فتضيع بقيّة
# الملفات بلا أثر.
_BG_TASKS: set[asyncio.Task] = set()

# فاصل بين ملفّات الوثائق المتعدّدة (نادراً ما يتجاوز الأمر ملفاً واحداً؛
# يحدث فقط حين تتجاوز الدفعة حدّ الحجم ويُقسَّم الناتج) — يخفّف الاصطدام
# بقيد معدّل تليجرام لرفع الملفات.
_DOC_SPACING_SEC = 0.6
_MAX_RETRY_AFTER = 3


def _retry_seconds(exc) -> float:
    ra = getattr(exc, "retry_after", 1)
    return float(ra.total_seconds() if hasattr(ra, "total_seconds") else ra)


async def _send_one_pdf(bot, group_id, buf, filename: str, caption: str) -> bool:
    """يرفع ملف PDF واحداً. يُرجِع هل نُشر.

    ⚠️ `RetryAfter` (قيد معدّل الرفع) يُنتظَر ثم يُعاد **الملف نفسه** لا
    يُتخطّى: تخطّيه يعني جزءاً كاملاً من الوثائق ضائعاً في المجموعة بلا
    أن ينتبه أحد.
    """
    from telegram.error import RetryAfter

    for _ in range(_MAX_RETRY_AFTER):
        try:
            buf.seek(0)
            await bot.send_document(chat_id=group_id, document=buf, filename=filename,
                                    caption=caption)
            return True
        except RetryAfter as exc:
            wait = _retry_seconds(exc) + 1
            logger.info(f"[gs_publisher] قيد معدّل — انتظار {wait:.0f}ث ثم إعادة رفع الملف")
            await asyncio.sleep(wait)
        except Exception as exc:
            logger.error(f"[gs_publisher] فشل رفع ملف الوثائق {filename!r}: {exc}")
            return False
    return False


async def _deliver_documents(bot, group_id, data: GSPublishData) -> None:
    """يجمع وثائق الدفعة في ملف PDF واحد منظَّم (أو أكثر إن تجاوز الحجم
    حدّ الرفع) ويرفعه إلى المجموعة — بدل صور متفرّقة تضيع بين إشعاراتها.
    """
    from modules.general_services.views import format_arabic_datetime
    from services.arrival_documents_pdf import build_arrival_documents_pdfs

    batch_label = (f"{data.workflow_icon} {data.workflow_label} — "
                   f"{format_arabic_datetime(data.record_date)}")
    try:
        files, included, dl_failed = await build_arrival_documents_pdfs(
            data.documents, bot, batch_label)
    except Exception:
        logger.exception("[gs_publisher] فشل بناء ملف وثائق %s", data.workflow_type)
        files, included, dl_failed = [], 0, len(data.documents)

    up_failed = 0
    if included:
        for i, buf in enumerate(files, start=1):
            suffix = f"_{i}" if len(files) > 1 else ""
            filename = f"وثائق_{data.workflow_type}{suffix}.pdf"
            caption = f"📎 وثائق الدفعة ({included} وثيقة)" if len(files) == 1 else (
                f"📎 وثائق الدفعة — الجزء {i} من {len(files)}")
            ok = await _send_one_pdf(bot, group_id, buf, filename, caption)
            if not ok:
                up_failed += 1
            if i < len(files):
                await asyncio.sleep(_DOC_SPACING_SEC)

    logger.info(f"[gs_publisher] وثائق {data.workflow_type}: {included} وثيقة في "
                f"{len(files) - up_failed}/{len(files)} ملف (تعذّر تنزيل {dl_failed})")

    # ⚠️ الفشل يُبلَّغ به مُدخِلُ الدفعة ولا يُبتلَع بسطر سجلّ: هذه المهمة تعمل
    # في الخلفية بعد أن رأى نجاح الحفظ، فبلا هذا يظنّ أن المجموعة اكتملت.
    if (dl_failed or up_failed or not included) and data.created_by_id:
        lines = []
        if not included:
            lines.append("⚠️ تعذّر تجميع أي وثيقة في ملف — راجع الدفعة من البوت.")
        elif dl_failed:
            lines.append(f"⚠️ تعذّر تنزيل {dl_failed} وثيقة عند تجميعها في الملف "
                         f"(بقيت {included} في الملف المرفوع).")
        if up_failed:
            lines.append(f"⚠️ تعذّر رفع {up_failed} من {len(files)} ملف وثائق إلى المجموعة.")
        try:
            await bot.send_message(chat_id=data.created_by_id, text=chr(10).join(lines))
        except Exception as exc:
            logger.warning(f"[gs_publisher] تعذّر إبلاغ المُدخِل بفشل الوثائق: {exc}")


def _spawn_documents_delivery(bot, group_id, data: GSPublishData) -> None:
    """يُطلِق إرسال الوثائق في الخلفية ولا ينتظره.

    ⚠️ لا `await` مباشر: عشرات الملفات مع قيد معدّل تليجرام قد تستغرق دقائق،
    وشاشة نجاح الحفظ تنتظر هذه الدالة — فيبدو البوت معلَّقاً بعد أن نجح الحفظ.
    """
    async def _run():
        try:
            await _deliver_documents(bot, group_id, data)
        except Exception:
            logger.exception("[gs_publisher] فشل غير متوقَّع في نشر الوثائق")

    task = asyncio.get_running_loop().create_task(_run())
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)


def _resolve_group_id(workflow_type: str = "") -> int | str | None:
    """مجموعة النشر لهذا النوع من التقارير.

    تقارير **الوصول** لها مجموعتها الخاصة، وبقية الخدمات العامة
    (المغادرة والخدمات) تبقى في مجموعتها كما كانت.

    السطر الثاني (`or GENERAL_SERVICES_GROUP_ID`) دفاعيّ: إعداد الوصول لا
    يكون فارغاً في التشغيل الفعلي (له افتراضي مُثبَّت)، لكنه يمنع ضياع
    تقرير الوصول لو صار فارغاً يوماً — يصل مجموعةً غير مثالية بدل ألّا
    يصل أحداً.
    """
    gid = GS_ARRIVALS_GROUP_ID if workflow_type == "arrivals" else ""
    gid = gid or GENERAL_SERVICES_GROUP_ID
    if not gid:
        return None
    try:
        return int(gid)
    except (ValueError, TypeError):
        return str(gid) if gid else None
