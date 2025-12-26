# ================================================
# bot/handlers/shared/universal_fallback.py
# 🛡️ معالج شامل لجميع الرسائل غير المعالجة
# ================================================

import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters
from telegram.error import TimedOut, NetworkError
from bot.shared_auth import is_admin
from bot.keyboards import admin_main_kb, user_main_kb, start_persistent_kb

logger = logging.getLogger(__name__)

# ================================================
# Universal Fallback Handler
# ================================================

async def handle_unexpected_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج شامل لجميع الرسائل غير المتوقعة
    يضمن أن البوت يستجيب دائماً ولا يعلق
    """
    try:
        # Timeout protection - إذا استغرق المعالج أكثر من 3 ثواني، أرسل رد سريع
        try:
            response = await asyncio.wait_for(
                _process_unexpected_message(update, context),
                timeout=3.0
            )
            return response
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ Handler timeout for update {update.update_id}")
            await _send_quick_response(update, context)
            return
    except Exception as e:
        logger.error(f"❌ Error in handle_unexpected_message: {e}", exc_info=True)
        try:
            await _send_quick_response(update, context)
        except:
            pass
        return

async def _process_unexpected_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسالة غير المتوقعة"""
    
    # التحقق من نوع الرسالة
    if update.message:
        message_text = update.message.text or ""
        user = update.effective_user
        
        # التحقق من أن المستخدم أدمن
        is_user_admin = is_admin(user.id) if user else False
        
        # إذا كانت الرسالة في محادثة نشطة، تحقق من أنها ليست رسالة عشوائية
        # إذا كانت رسالة عشوائية في محادثة نشطة، أرسل توجيه سريع
        if context.user_data.get('_conversation_state'):
            # التحقق من أن الرسالة ليست أمراً معروفاً
            known_commands = ["/start", "/cancel", "/help", "إلغاء", "مساعدة", "help"]
            if not any(cmd in message_text.lower() for cmd in known_commands):
                # رسالة عشوائية في محادثة نشطة - أرسل توجيه سريع
                try:
                    await update.message.reply_text(
                        "⚠️ **أنت في محادثة نشطة**\n\n"
                        "يرجى إكمال العملية الحالية أو استخدام 'إلغاء' للخروج.",
                        parse_mode="Markdown"
                    )
                except:
                    pass
            logger.debug(f"📝 Conversation active, message: {message_text[:50]}")
            return
        
        # معالجة الرسائل العشوائية
        if message_text:
            # رسائل مساعدة شائعة
            help_keywords = ["مساعدة", "help", "مساعده", "ماذا يمكنك", "ماذا تفعل", "ماذا تعمل"]
            if any(keyword in message_text.lower() for keyword in help_keywords):
                await _send_help_response(update, context, is_user_admin)
                return
            
            # رسائل ترحيب
            greeting_keywords = ["مرحبا", "مرحبا", "السلام", "سلام", "hello", "hi", "أهلا"]
            if any(keyword in message_text.lower() for keyword in greeting_keywords):
                await _send_greeting_response(update, context, is_user_admin)
                return
            
            # رسائل إلغاء
            cancel_keywords = ["إلغاء", "الغاء", "cancel", "إلغ", "تراجع"]
            if any(keyword in message_text.lower() for keyword in cancel_keywords):
                await _send_cancel_response(update, context)
                return
        
        # رسالة عامة - توجيه المستخدم
        await _send_general_guidance(update, context, is_user_admin)
        
    elif update.callback_query:
        # معالجة callback queries غير المعالجة
        query = update.callback_query
        try:
            await query.answer("⚠️ هذا الزر غير متاح حالياً")
        except:
            pass

async def _send_quick_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال رد سريع في حالة timeout"""
    try:
        if update.message:
            await update.message.reply_text(
                "⏳ **جاري المعالجة...**\n\n"
                "يرجى المحاولة مرة أخرى.",
                reply_markup=start_persistent_kb()
            )
    except Exception as e:
        logger.error(f"❌ Failed to send quick response: {e}")

async def _send_help_response(update: Update, context: ContextTypes.DEFAULT_TYPE, is_admin: bool):
    """إرسال رسالة مساعدة"""
    try:
        user = update.effective_user
        if is_admin:
            help_text = (
                "👑 **لوحة تحكم الأدمن**\n\n"
                "يمكنك استخدام الأزرار التالية:\n\n"
                "➕ إضافة حالة أولية\n"
                "🖨️ طباعة التقارير\n"
                "👥 إدارة المستخدمين\n"
                "📊 تقييم المترجمين\n"
                "👑 إدارة الأدمنين\n"
                "📊 تحليل البيانات\n"
                "📅 إدارة الجدول\n\n"
                "أو استخدم /start للعودة للقائمة الرئيسية"
            )
            await update.message.reply_text(
                help_text,
                reply_markup=admin_main_kb(),
                parse_mode="Markdown"
            )
        else:
            help_text = (
                "ℹ️ **مساعدة**\n\n"
                "يمكنك استخدام الأزرار التالية:\n\n"
                "📝 إضافة تقرير جديد\n"
                "✏️ تعديل التقارير\n"
                "📅 جدول اليوم\n"
                "📋 التقرير الأولي للمرضى\n\n"
                "أو استخدم /start للعودة للقائمة الرئيسية"
            )
            await update.message.reply_text(
                help_text,
                reply_markup=user_main_kb(),
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"❌ Error sending help response: {e}")

async def _send_greeting_response(update: Update, context: ContextTypes.DEFAULT_TYPE, is_admin: bool):
    """إرسال رسالة ترحيب"""
    try:
        user = update.effective_user
        greeting = f"👋 مرحباً {user.first_name or 'المستخدم'}!\n\n"
        greeting += "كيف يمكنني مساعدتك اليوم؟\n\n"
        greeting += "استخدم /start للبدء"
        
        keyboard = admin_main_kb() if is_admin else user_main_kb()
        await update.message.reply_text(
            greeting,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"❌ Error sending greeting response: {e}")

async def _send_cancel_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال رسالة إلغاء"""
    try:
        # تنظيف بيانات المحادثة
        context.user_data.clear()
        
        await update.message.reply_text(
            "✅ **تم الإلغاء**\n\n"
            "يمكنك البدء من جديد باستخدام /start",
            reply_markup=start_persistent_kb(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"❌ Error sending cancel response: {e}")

async def _send_general_guidance(update: Update, context: ContextTypes.DEFAULT_TYPE, is_admin: bool):
    """إرسال توجيه عام"""
    try:
        user = update.effective_user
        
        # تنظيف أي بيانات محادثة قديمة
        if context.user_data.get('_conversation_state'):
            context.user_data.clear()
        
        guidance = (
            f"👋 مرحباً {user.first_name or 'المستخدم'}!\n\n"
            "⚠️ **لم أفهم رسالتك**\n\n"
            "يمكنك:\n"
            "• استخدام /start للبدء\n"
            "• استخدام الأزرار في لوحة المفاتيح\n"
            "• كتابة 'مساعدة' للحصول على المساعدة\n"
            "• كتابة 'إلغاء' للخروج من أي محادثة نشطة\n\n"
            "💡 **نصيحة:** استخدم الأزرار في لوحة المفاتيح للتنقل بسهولة"
        )
        
        keyboard = admin_main_kb() if is_admin else user_main_kb()
        
        # محاولة إرسال الرسالة مع retry
        max_retries = 2
        for attempt in range(max_retries):
            try:
                await update.message.reply_text(
                    guidance,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                break
            except (TimedOut, NetworkError) as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                else:
                    logger.error(f"❌ Failed to send guidance after {max_retries} attempts: {e}")
                    raise
    except Exception as e:
        logger.error(f"❌ Error sending general guidance: {e}")
        # محاولة أخيرة - إرسال رسالة بسيطة بدون تنسيق
        try:
            await update.message.reply_text(
                "👋 مرحباً! استخدم /start للبدء",
                reply_markup=start_persistent_kb()
            )
        except:
            pass

async def handle_unexpected_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة callback queries غير المعالجة"""
    try:
        query = update.callback_query
        if query:
            await query.answer("⚠️ هذا الزر غير متاح حالياً")
            
            # محاولة إرسال رسالة توجيهية
            try:
                user = update.effective_user
                is_user_admin = is_admin(user.id) if user else False
                
                guidance = (
                    "⚠️ **هذا الزر غير متاح**\n\n"
                    "يرجى استخدام /start للعودة للقائمة الرئيسية"
                )
                
                keyboard = admin_main_kb() if is_user_admin else user_main_kb()
                await query.message.reply_text(
                    guidance,
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
            except:
                pass
    except Exception as e:
        logger.error(f"❌ Error in handle_unexpected_callback: {e}")

# ================================================
# Registration
# ================================================

def register(app):
    """تسجيل معالجات الرسائل الشاملة"""
    logger.info("📋 تسجيل universal fallback handlers...")
    
    # معالج للرسائل النصية غير المعالجة (بأولوية منخفضة)
    # يجب أن يكون في group عالي (يتم تنفيذه آخراً)
    # يستخدم filters.TEXT فقط - لا يطابق COMMANDs أو MEDIA
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.PHOTO & ~filters.DOCUMENT,
            handle_unexpected_message
        ),
        group=99  # أولوية منخفضة جداً - يتم تنفيذه بعد جميع handlers الأخرى
    )
    
    # معالج لـ callback queries غير المعالجة (يجب أن يكون pattern محدد لتجنب التعارض)
    # لا نستخدم pattern=".*" لأنه قد يتعارض مع handlers أخرى
    # بدلاً من ذلك، نستخدم pattern محدد للـ callbacks غير المعالجة
    app.add_handler(
        CallbackQueryHandler(
            handle_unexpected_callback,
            pattern=r"^(?!admin:|um:|nav:|save:|edit:|confirm_delete:|select_edit:).*"  # يطابق callbacks غير المعالجة
        ),
        group=99  # أولوية منخفضة
    )
    
    logger.info("✅ تم تسجيل universal fallback handlers")

