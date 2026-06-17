# modules/residency/profiles/documents.py
"""
High-level document actions for residency profiles:
  send_patient_pdf()        — generate & send a PDF document package
  send_patient_documents()  — send raw Telegram image files
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


async def send_patient_pdf(*, bot, message, profile_id: int) -> None:
    """
    Build a PDF document package for *profile_id* and send it to the chat.
    Sends a "⏳ جارٍ إنشاء ملف PDF…" notice first, then deletes it when done.
    """
    from modules.residency.profiles.repository import (
        get_profile_by_id,
        get_companions_for_profile,
        get_history_for_profile,
    )
    from services.residency_pdf_builder import build_residency_pdf

    profile = get_profile_by_id(profile_id)
    if profile is None:
        await message.reply_text("❌ لم يتم العثور على الملف.", parse_mode="Markdown")
        return

    companions = get_companions_for_profile(profile_id)
    history    = get_history_for_profile(profile_id, limit=50)

    progress = await message.reply_text("⏳ جارٍ إنشاء ملف PDF…")

    try:
        pdf_bytes = await build_residency_pdf(
            bot=bot,
            profile=profile,
            companions=companions,
            history=history,
        )

        safe_name = (profile.name or "profile").replace(" ", "_")[:30]
        filename  = f"residency_{safe_name}_{profile_id}.pdf"

        await bot.send_document(
            chat_id=message.chat_id,
            document=io.BytesIO(pdf_bytes),
            filename=filename,
            caption=f"📄 ملف إقامة — {profile.name}",
        )
        logger.info(
            f"[res.documents] PDF sent"
            f"  profile_id={profile_id}  size={len(pdf_bytes):,} bytes"
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
            pass


async def send_patient_documents(*, bot, message, profile_id: int) -> None:
    """
    Send all saved Telegram document images (passport / visa / residence)
    for the patient and each of their companions.
    """
    from modules.residency.profiles.repository import (
        get_profile_by_id,
        get_companions_for_profile,
    )

    profile    = get_profile_by_id(profile_id)
    companions = get_companions_for_profile(profile_id)

    if profile is None:
        await message.reply_text("❌ لم يتم العثور على الملف.", parse_mode="Markdown")
        return

    sent = 0

    async def _try_send(file_id: str, caption: str) -> None:
        nonlocal sent
        if not file_id:
            return
        try:
            await bot.send_photo(
                chat_id=message.chat_id, photo=file_id, caption=caption
            )
            sent += 1
        except Exception as exc:
            logger.warning(f"[res.documents] send_photo failed: {exc}")

    await _try_send(profile.passport_file_id,         f"📎 جواز — {profile.name}")
    await _try_send(profile.visa_file_id,              f"📎 تأشيرة — {profile.name}")
    await _try_send(profile.latest_residency_file_id,  f"🪪 إقامة — {profile.name}")

    for c in companions:
        await _try_send(c.passport_file_id,         f"📎 جواز مرافق — {c.name}")
        await _try_send(c.visa_file_id,              f"📎 تأشيرة مرافق — {c.name}")
        await _try_send(c.latest_residency_file_id,  f"🪪 إقامة مرافق — {c.name}")

    if sent == 0:
        await message.reply_text(
            "⚠️ لا توجد وثائق محفوظة لهذا المريض.", parse_mode="Markdown"
        )
    else:
        await message.reply_text(f"✅ تم إرسال {sent} وثيقة.", parse_mode="Markdown")

    logger.info(
        f"[res.documents] docs sent"
        f"  profile_id={profile_id}  sent={sent}"
    )
