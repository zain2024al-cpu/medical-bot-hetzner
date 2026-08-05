# bot/group_guard.py
# يمنع البوت من الردّ على الرسائل داخل المجموعات.
#
# ── المشكلة التي يحلّها ───────────────────────────────────────────────────────
#
# مجموعات المتابعة (الرعاية الصحية، تشناي، التقارير، الخدمات، الإقامات)
# **تستقبل التقارير فقط** — النشر يتم من المحادثة الخاصة مع البوت. لكن 48 من
# أصل 50 معالِج رسائل/أوامر كانت مسجَّلة بلا قيد نوع المحادثة، فأي `/start`
# أو رسالة تطابق نص زر قائمة داخل المجموعة تجعل البوت يردّ **داخل المجموعة**
# ومعه لوحة المفاتيح، فتظهر أزرار النظام لكل أعضاء المجموعة.
#
# ── لماذا حارس واحد لا 48 تعديلاً ─────────────────────────────────────────────
#
# إضافة `filters.ChatType.PRIVATE` لكل معالِج تعني 48 موضعاً يجب ألّا يُنسى
# أيٌّ منها، **وكل معالِج جديد مستقبلاً يعيد الثغرة بصمت** — وهو نمط الخطأ
# المتكرر المسجَّل في MAINTENANCE_LOG.md. الحارس هنا نقطة واحدة تغطّي
# الموجود والقادم معاً.
#
# ── ما لا يتأثّر ──────────────────────────────────────────────────────────────
#
# • **إرسال** التقارير للمجموعات — الإرسال ليس تحديثاً وارداً أصلاً.
# • **أزرار بطاقة التقرير** داخل المجموعة («📂 فتح التقارير الطبية»،
#   «📅 عرض سبب التأجيل») — هذه CallbackQuery لا Message، ونوع التحديث
#   مختلف تماماً فلا يمسّه هذا الفلتر. تبقى تعمل كما هي.
#
# Handler group: -100 — أسبق من كل المجموعات المستخدَمة (أدناها -1 لجامع
# الرفع)، حتى يُوقَف التحديث قبل أن يراه أي معالِج آخر.

import logging

from telegram import Update
from telegram.ext import (
    ApplicationHandlerStop, ContextTypes, MessageHandler, filters,
)

logger = logging.getLogger(__name__)

# يُسجَّل مرة واحدة لكل محادثة حتى لا يُغرق اللوق برسالة لكل رسالة مجموعة
_seen: set[int] = set()


async def _ignore_non_private(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat and chat.id not in _seen:
        _seen.add(chat.id)
        logger.info(
            f"[group_guard] 🔇 تجاهل رسائل المحادثة {chat.id} (type={chat.type}) — "
            f"البوت يستقبل الأوامر من المحادثة الخاصة فقط"
        )
    raise ApplicationHandlerStop


def register_group_guard(app) -> None:
    app.add_handler(
        MessageHandler(~filters.ChatType.PRIVATE, _ignore_non_private),
        group=-100,
    )
    logger.info("[group_guard] registered (group -100) — non-private messages ignored")
