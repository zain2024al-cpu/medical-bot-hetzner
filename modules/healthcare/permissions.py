# modules/healthcare/permissions.py
# Access control for the healthcare module.
# Extend this when role-based permissions are needed.

from telegram import Update
from telegram.ext import ContextTypes


async def can_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Return True if the user may access healthcare features.

    Current policy: any approved user.
    Future: check user role against "healthcare" or "nurse" role flag.
    """
    user_id = update.effective_user.id if update.effective_user else None
    if not user_id:
        return False

    try:
        from db.session import get_db
        from db.models import User
        with get_db() as db:
            user = db.query(User).filter_by(tg_user_id=user_id).first()
            return bool(user and user.is_approved and user.is_active)
    except Exception:
        return False


async def deny(update: Update) -> None:
    """Send a standard access-denied message."""
    msg = update.effective_message
    if msg:
        try:
            await msg.reply_text(
                "⛔️ ليس لديك صلاحية للوصول إلى وحدة الرعاية الصحية.\n"
                "تواصل مع المسؤول للحصول على الإذن."
            )
        except Exception:
            pass
