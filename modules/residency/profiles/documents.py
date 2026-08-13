# modules/residency/profiles/documents.py
"""
High-level document actions for residency profiles:
  send_patient_pdf()  — generate & send a PDF document package
"""

from __future__ import annotations

import asyncio
import io
import logging

logger = logging.getLogger(__name__)


async def _download_document_images(bot, file_ids: list[str]) -> dict[str, bytes]:
    """
    يحمّل صور الوثائق من تيليجرام (I/O شبكي — يبقى async) قبل تمريرها
    لباني PDF المتزامن، الذي لا يعرف عن كائن البوت شيئاً.

    فشل تحميل صورة واحدة لا يوقف البقية — تُستبعَد من الحزمة ويُسجَّل
    تحذير، فالمستخدم يحصل على حزمة ناقصة بدل رسالة فشل كاملة.
    """
    images: dict[str, bytes] = {}
    # dict.fromkeys يزيل التكرار مع حفظ ترتيب أول ظهور — لا فائدة عملية من
    # تحميل نفس file_id مرتين لو تكرّر عرضياً بين مريض ومرافق.
    for fid in dict.fromkeys(file_ids):
        try:
            tg_file = await bot.get_file(fid)
            images[fid] = bytes(await tg_file.download_as_bytearray())
        except Exception as exc:
            logger.warning(f"[res.documents] فشل تحميل صورة وثيقة file_id={fid}: {exc}")
    return images


async def send_patient_pdf(*, bot, message, profile_id: int) -> None:
    """
    Build a PDF document package for *profile_id* and send it to the chat.
    Sends a "⏳ جارٍ إنشاء ملف PDF…" notice first, then deletes it when done.
    """
    from modules.residency.profiles.repository import (
        get_profile_by_id,
        get_companions_for_profile,
    )
    from services.residency_profile_pdf import build_profile_pdf

    profile = get_profile_by_id(profile_id)
    if profile is None:
        await message.reply_text("❌ لم يتم العثور على الملف.", parse_mode="Markdown")
        return

    companions = get_companions_for_profile(profile_id)

    progress = await message.reply_text("⏳ جارٍ إنشاء ملف PDF…")

    try:
        # ✅ ترتيب العرض: جواز → تأشيرة → إقامة (آخر نسخة فقط — العمود
        # latest_residency_file_id لا يخزّن غيرها أصلاً) → فورم C (المريض
        # وحده، وثيقة عائلية) → نفس المجموعة (بلا فورم C) لكل مرافق بالترتيب.
        file_ids: list[str] = [
            fid for fid in (
                profile.passport_file_id, profile.visa_file_id,
                profile.latest_residency_file_id,
                getattr(profile, "form_c_file_id", ""),
            ) if fid
        ]
        for c in companions:
            file_ids += [
                fid for fid in (c.passport_file_id, c.visa_file_id, c.latest_residency_file_id)
                if fid
            ]

        images = await _download_document_images(bot, file_ids)

        # reportlab متزامن وسريع، لكنه يُنفَّذ في خيط منفصل حتى لا يوقف
        # حلقة الأحداث عن بقية المستخدمين أثناء بناء ملف كبير.
        pdf_bytes = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: build_profile_pdf(
                profile=profile, companions=companions, images=images,
            ),
        )

        safe_name = (profile.name or "profile").replace(" ", "_")[:30]
        filename  = f"residency_{safe_name}_{profile_id}.pdf"

        await bot.send_document(
            chat_id=message.chat_id,
            document=io.BytesIO(pdf_bytes),
            filename=filename,
            caption=f"📄 حزمة وثائق — {profile.name}",
        )
        logger.info(
            f"[res.documents] PDF sent"
            f"  profile_id={profile_id}  size={len(pdf_bytes):,} bytes"
            f"  images={len(images)}/{len(set(file_ids))}"
        )

    except Exception as exc:
        logger.exception(
            f"[res.documents] PDF generation failed  profile_id={profile_id}: {exc}"
        )
        await message.reply_text(
            "❌ فشل إنشاء ملف PDF. حاول مجدداً.", parse_mode="Markdown"
        )
    finally:
        try:
            await progress.delete()
        except Exception:
            logger.debug("تم تجاهل استثناء في send_patient_pdf", exc_info=True)


