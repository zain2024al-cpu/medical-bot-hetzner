# ================================================
# bot/handlers/shared/group_handler.py
# 🔹 معالجة الرسائل في المجموعات
# ================================================

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, CommandHandler, filters
from telegram.constants import ChatType
import logging

logger = logging.getLogger(__name__)

# استيراد إعدادات المجموعة
from config.settings import GROUP_CHAT_ID, GROUP_INVITE_LINK
from bot.shared_auth import is_admin


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل في المجموعات"""
    try:
        chat = update.effective_chat
        
        # التحقق من أن الرسالة في مجموعة
        if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            return
        
        # حفظ معرف المجموعة في الإعدادات (إذا لم يكن موجوداً)
        if not GROUP_CHAT_ID and chat.id:
            logger.info("="*60)
            logger.info(f"📝 تم اكتشاف معرف المجموعة: {chat.id}")
            logger.info(f"📝 اسم المجموعة: {chat.title}")
            logger.info(f"📝 نوع المجموعة: {chat.type}")
            logger.info("="*60)
            logger.info(f"⚠️ يرجى إضافة معرف المجموعة في ملف config.env:")
            logger.info(f"GROUP_CHAT_ID={chat.id}")
            logger.info("="*60)
            # يمكن حفظه في ملف config.env أو قاعدة البيانات
            # هنا سنكتفي بتسجيله في السجلات
        
        # إذا كانت الرسالة تحتوي على أمر /start أو /help، نرد عليها
        if update.message and update.message.text:
            text = update.message.text.strip()
            
            if text in ["/start", "/help", "مساعدة"]:
                await update.message.reply_text(
                    f"👋 مرحباً في المجموعة!\n\n"
                    f"🤖 أنا بوت التقارير الطبية الذكي.\n\n"
                    f"💡 يمكنك استخدامي في الدردشة الخاصة لإضافة التقارير الطبية.\n\n"
                    f"📋 للبدء، اضغط على /start في الدردشة الخاصة معي.\n\n"
                    f"🔗 رابط المجموعة: {GROUP_INVITE_LINK}",
                    disable_web_page_preview=True
                )
                return
        
        # تجاهل الرسائل الأخرى في المجموعة (يمكن تخصيصها لاحقاً)
        logger.debug(f"📨 رسالة في المجموعة {chat.id}: {text[:50] if update.message and update.message.text else 'غير نصية'}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة رسالة المجموعة: {e}", exc_info=True)


async def get_group_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر للحصول على معرف المجموعة (للأدمن فقط)"""
    try:
        user = update.effective_user
        
        # التحقق من أن المستخدم أدمن
        if not is_admin(user.id):
            await update.message.reply_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
            return
        
        chat = update.effective_chat
        
        # التحقق من أن الرسالة في مجموعة
        if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await update.message.reply_text("⚠️ هذا الأمر يعمل فقط في المجموعات.")
            return
        
        # إرسال معرف المجموعة
        group_info = (
            f"📋 **معلومات المجموعة:**\n\n"
            f"🆔 **معرف المجموعة:** `{chat.id}`\n"
            f"📝 **اسم المجموعة:** {chat.title}\n"
            f"👥 **نوع المجموعة:** {chat.type}\n\n"
            f"💡 **لإضافة المعرف في config.env:**\n"
            f"`GROUP_CHAT_ID={chat.id}`"
        )
        
        await update.message.reply_text(
            group_info,
            parse_mode="Markdown"
        )
        
        logger.info(f"📝 تم طلب معرف المجموعة من {user.first_name} (ID: {user.id})")
        logger.info(f"📝 معرف المجموعة: {chat.id} ({chat.title})")
        
    except Exception as e:
        logger.error(f"❌ خطأ في get_group_id_command: {e}", exc_info=True)
        if update.message:
            try:
                await update.message.reply_text("❌ حدث خطأ في الحصول على معرف المجموعة.")
            except:
                pass


async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأعضاء الجدد في المجموعة"""
    try:
        chat = update.effective_chat
        
        # التحقق من أن الرسالة في مجموعة
        if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            return
        
        # التحقق من وجود أعضاء جدد
        if update.message and update.message.new_chat_members:
            for member in update.message.new_chat_members:
                # إذا كان العضو الجديد هو البوت نفسه
                if member.is_bot and member.id == context.bot.id:
                    welcome_text = (
                        f"🤖 مرحباً! أنا بوت التقارير الطبية الذكي.\n\n"
                        f"💡 يمكنك استخدامي في الدردشة الخاصة لإضافة التقارير الطبية.\n\n"
                        f"📋 للبدء، اضغط على /start في الدردشة الخاصة معي.\n\n"
                        f"🔗 رابط المجموعة: {GROUP_INVITE_LINK}"
                    )
                    await update.message.reply_text(
                        welcome_text,
                        disable_web_page_preview=True
                    )
                    logger.info(f"✅ تم إضافة البوت إلى المجموعة: {chat.id} ({chat.title})")
                else:
                    # ترحيب بالأعضاء الجدد (اختياري)
                    logger.debug(f"👤 عضو جديد في المجموعة: {member.first_name}")
        
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة عضو جديد: {e}", exc_info=True)


def register(app):
    """تسجيل handlers المجموعات"""
    # أمر للحصول على معرف المجموعة (للأدمن فقط)
    app.add_handler(
        CommandHandler("get_group_id", get_group_id_command)
    )
    
    # معالج الرسائل في المجموعات (بعد جميع handlers الأخرى)
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
            handle_group_message
        )
    )
    
    # معالج الأوامر في المجموعات
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.COMMAND,
            handle_group_message
        )
    )
    
    # معالج الأعضاء الجدد
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.StatusUpdate.NEW_CHAT_MEMBERS,
            handle_new_member
        )
    )
    
    logger.info("✅ تم تسجيل handlers المجموعات")

