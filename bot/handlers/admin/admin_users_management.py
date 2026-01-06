# =============================
# bot/handlers/admin/admin_users_management.py
# 👥 إدارة المستخدمين - نسخة مبسطة
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from db.session import SessionLocal
from db.models import Translator, Report
from bot.shared_auth import is_admin
from bot.decorators import admin_handler
from datetime import datetime
from sqlalchemy import func
import logging
import re

logger = logging.getLogger(__name__)

# States
UM_START, UM_SELECT_USER, UM_USER_ACTIONS, UM_SEARCH, UM_SUSPEND_REASON = range(600, 605)

def _escape_markdown_v2(text: str) -> str:
    """
    Helper function to escape special characters in MarkdownV2.
    From python-telegram-bot examples.
    """
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(r'([{}])'.format(re.escape(escape_chars)), r'\\\1', text)

async def start_user_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إدارة المستخدمين"""
    user = update.effective_user
    
    logger.info(f"🔍 محاولة الوصول لإدارة المستخدمين من: {user.id}")
    
    if not is_admin(user.id):
        logger.warning(f"❌ المستخدم {user.id} ليس أدمن")
        await update.message.reply_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
        return ConversationHandler.END
    
    logger.info(f"✅ الأدمن {user.id} دخل لإدارة المستخدمين")
    
    context.user_data.clear()
    await update.message.reply_text(
        "👥 **إدارة المستخدمين**\n\n"
        "اختر نوع العرض:",
        reply_markup=_main_kb(),
        parse_mode="Markdown"
    )
    return UM_START

def _main_kb():
    """لوحة المفاتيح الرئيسية"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 عرض جميع المستخدمين", callback_data="um:view_all")],
        [InlineKeyboardButton("⏳ المستخدمين المعلقين", callback_data="um:view_pending")],
        [InlineKeyboardButton("✅ المستخدمين النشطين", callback_data="um:view_approved")],
        [InlineKeyboardButton("🔒 المستخدمين المجمدين", callback_data="um:view_suspended")],
        [InlineKeyboardButton("🔍 بحث عن مستخدم", callback_data="um:search")],
        [InlineKeyboardButton("📊 إحصائيات", callback_data="um:stats")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="um:cancel")]
    ])

def _users_kb(users, user_type="all"):
    """لوحة مفاتيح المستخدمين"""
    buttons = []
    
    for user in users[:10]:  # حد أقصى 10 مستخدمين
        # تحديد الأيقونة بناءً على الحالة
        if getattr(user, 'is_suspended', False):
            status_icon = "🔒"
        elif user.is_approved:
            status_icon = "✅"
        else:
            status_icon = "⏳"
        
        button_text = f"{status_icon} {user.full_name}"
        buttons.append([InlineKeyboardButton(button_text, callback_data=f"um:user:{user.id}")])
    
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="um:back")])
    return InlineKeyboardMarkup(buttons)

def _user_actions_kb():
    """لوحة مفاتيح إجراءات المستخدم"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ موافقة", callback_data="um:approve")],
        [InlineKeyboardButton("❌ رفض", callback_data="um:reject")],
        [InlineKeyboardButton("🔒 تجميد", callback_data="um:suspend")],
        [InlineKeyboardButton("🔓 إلغاء تجميد", callback_data="um:unsuspend")],
        [InlineKeyboardButton("🚫 إخراج من البوت", callback_data="um:delete")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="um:back")]
    ])

@admin_handler
async def handle_user_management_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة جميع استدعاءات إدارة المستخدمين"""
    query = update.callback_query
    await query.answer()
    
    # إزالة البادئة "um:" للحصول على البيانات الفعلية
    if query.data.startswith("um:"):
        data = query.data[3:]  # إزالة "um:" من البداية
    else:
        data = query.data
    
    try:
        if data == "view_all":
            return await _show_all_users(query, context)
        elif data == "view_pending":
            return await _show_pending_users(query, context)
        elif data == "view_approved":
            return await _show_approved_users(query, context)
        elif data == "view_suspended":
            return await _show_suspended_users(query, context)
        elif data == "stats":
            return await _show_statistics(query, context)
        elif data == "search":
            return await _start_search(query, context)
        elif data.startswith("user:"):
            user_id = int(data.split(":")[1])
            return await _show_user_details(query, context, user_id)
        elif data in ["approve", "reject", "suspend", "unsuspend", "delete"]:
            return await _handle_user_action(query, context, data)
        elif data == "back":
            return await _back_to_main(query, context)
        elif data == "cancel":
            await query.edit_message_text("❌ تم إلغاء إدارة المستخدمين.")
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error in user management: {e}", exc_info=True)
        await query.edit_message_text("❌ حدث خطأ. يرجى المحاولة مرة أخرى.")
        return UM_START

async def _show_all_users(query, context):
    """عرض جميع المستخدمين"""
    try:
        with SessionLocal() as s:
            users = s.query(Translator).order_by(Translator.created_at.desc()).all()
            
            if not users:
                await query.message.reply_text(
                    "📋 **لا يوجد مستخدمين مسجلين**\n\n"
                    "لم يتم تسجيل أي مستخدم بعد.\n\n"
                    "اختر خياراً آخر:",
                    reply_markup=_main_kb(),
                    parse_mode="Markdown"
                )
                try:
                    await query.delete_message()
                except:
                    pass
                return UM_START
            
            text = f"📋 **جميع المستخدمين ({len(users)})**\n\n"
            text += "اختر مستخدماً لعرض التفاصيل:"
            await query.edit_message_text(text, reply_markup=_users_kb(users), parse_mode="Markdown")
            return UM_SELECT_USER
    except Exception as e:
        logger.error(f"Error in _show_all_users: {e}", exc_info=True)
        await query.message.reply_text("❌ حدث خطأ. يرجى المحاولة مرة أخرى.", reply_markup=_main_kb())
        return UM_START

async def _show_pending_users(query, context):
    """عرض المستخدمين المعلقين"""
    try:
        with SessionLocal() as s:
            users = s.query(Translator).filter_by(is_approved=False).order_by(Translator.created_at.desc()).all()
            
            if not users:
                # استخدام reply بدلاً من edit لتجنب خطأ "Message is not modified"
                await query.message.reply_text(
                    "⏳ **لا يوجد مستخدمين معلقين**\n\n"
                    "✅ لا توجد طلبات انضمام بانتظار الموافقة.\n\n"
                    "اختر خياراً آخر:",
                    reply_markup=_main_kb(),
                    parse_mode="Markdown"
                )
                # حذف الرسالة القديمة
                try:
                    await query.delete_message()
                except:
                    pass
                return UM_START
            
            text = f"⏳ **المستخدمين المعلقين ({len(users)})**\n\n"
            text += "اختر مستخدماً لعرض التفاصيل:"
            await query.edit_message_text(text, reply_markup=_users_kb(users), parse_mode="Markdown")
            return UM_SELECT_USER
    except Exception as e:
        logger.error(f"Error in _show_pending_users: {e}", exc_info=True)
        await query.message.reply_text("❌ حدث خطأ. يرجى المحاولة مرة أخرى.", reply_markup=_main_kb())
        return UM_START

async def _show_approved_users(query, context):
    """عرض المستخدمين الموافق عليهم"""
    try:
        with SessionLocal() as s:
            users = s.query(Translator).filter_by(is_approved=True).order_by(Translator.created_at.desc()).all()
            
            if not users:
                await query.message.reply_text(
                    "✅ **لا يوجد مستخدمين نشطين**\n\n"
                    "لم يتم الموافقة على أي مستخدم بعد.\n\n"
                    "اختر خياراً آخر:",
                    reply_markup=_main_kb(),
                    parse_mode="Markdown"
                )
                try:
                    await query.delete_message()
                except:
                    pass
                return UM_START
            
            text = f"✅ **المستخدمين النشطين ({len(users)})**\n\n"
            text += "اختر مستخدماً لعرض التفاصيل:"
            await query.edit_message_text(text, reply_markup=_users_kb(users), parse_mode="Markdown")
            return UM_SELECT_USER
    except Exception as e:
        logger.error(f"Error in _show_approved_users: {e}", exc_info=True)
        await query.message.reply_text("❌ حدث خطأ. يرجى المحاولة مرة أخرى.", reply_markup=_main_kb())
        return UM_START

async def _show_user_details(query, context, user_id):
    """عرض تفاصيل المستخدم"""
    from db.models import Report
    
    with SessionLocal() as s:
        user = s.query(Translator).filter_by(id=user_id).first()
        
        if not user:
            await query.edit_message_text("❌ المستخدم غير موجود.", reply_markup=_main_kb())
            return UM_START
        
        context.user_data["selected_user_id"] = user_id
        
        # حساب عدد التقارير (باستخدام func.count لتجنب مشاكل الأعمدة المفقودة)
        try:
            reports_count = s.query(func.count(Report.id)).filter_by(translator_id=user.id).scalar() or 0
        except Exception as e:
            logger.error(f"خطأ في حساب عدد التقارير: {e}")
            reports_count = 0
        
        # آخر تقرير (باستخدام فقط الأعمدة الأساسية)
        try:
            last_report = s.query(Report.id, Report.created_at).filter_by(translator_id=user.id).order_by(Report.created_at.desc()).first()
            last_activity = last_report.created_at.strftime('%Y-%m-%d %H:%M') if last_report and last_report.created_at else "لا يوجد"
        except Exception as e:
            logger.error(f"خطأ في جلب آخر تقرير: {e}")
            last_activity = "لا يوجد"
        
        status = "✅ نشط" if user.is_approved else "⏳ معلق"
        suspended = "🔒 مجمد" if getattr(user, 'is_suspended', False) else "🔓 نشط"
        
        text = f"👤 **تفاصيل المستخدم**\n"
        text += f"━━━━━━━━━━━━━━━━\n\n"
        text += f"🆔 **Database ID:** {user.id}\n"
        text += f"📱 **Telegram ID:** `{user.tg_user_id}`\n"
        text += f"👤 **الاسم:** {user.full_name}\n"
        text += f"📞 **الهاتف:** {user.phone_number or 'غير محدد'}\n\n"
        text += f"📅 **تاريخ التسجيل:** {user.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        text += f"⏰ **آخر نشاط:** {last_activity}\n\n"
        text += f"📊 **حالة الحساب:** {status}\n"
        text += f"🔐 **حالة الوصول:** {suspended}\n"
        text += f"📝 **عدد التقارير:** {reports_count}\n"
        
        if getattr(user, 'is_suspended', False) and getattr(user, 'suspended_at', None):
            text += f"\n⚠️ **تاريخ التجميد:** {user.suspended_at.strftime('%Y-%m-%d %H:%M')}\n"
            if getattr(user, 'suspension_reason', None):
                text += f"📋 **سبب التجميد:** {user.suspension_reason}\n"
        
        text += f"\n━━━━━━━━━━━━━━━━"
        
        await query.edit_message_text(text, reply_markup=_user_actions_kb(), parse_mode="Markdown")
        return UM_USER_ACTIONS

async def _handle_user_action(query, context, action):
    """معالجة إجراءات المستخدم"""
    user_id = context.user_data.get("selected_user_id")
    if not user_id:
        await query.edit_message_text("❌ لم يتم اختيار مستخدم.", reply_markup=_main_kb())
        return UM_START
    
    with SessionLocal() as s:
        user = s.query(Translator).filter_by(id=user_id).first()
        if not user:
            await query.edit_message_text("❌ المستخدم غير موجود.", reply_markup=_main_kb())
            return UM_START
        
        user_tg_id = user.tg_user_id
        user_name = user.full_name
        
        if action == "approve":
            user.is_approved = True
            user.is_suspended = False
            s.commit()
            message = f"✅ **تم الموافقة على المستخدم**\n\n👤 {user_name}"
            
            # إرسال إشعار للمستخدم
            try:
                await context.bot.send_message(
                    chat_id=user_tg_id,
                    text="🎉 **مرحباً بك!**\n\n"
                         "✅ تم الموافقة على حسابك.\n"
                         "يمكنك الآن استخدام النظام بالكامل.\n\n"
                         "اضغط /start للبدء!",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"فشل إرسال إشعار الموافقة: {e}")
                
        elif action == "reject":
            s.delete(user)
            s.commit()
            message = f"❌ **تم رفض المستخدم**\n\n👤 {user_name}"
            
            # إرسال إشعار للمستخدم
            try:
                await context.bot.send_message(
                    chat_id=user_tg_id,
                    text="❌ **تم رفض طلبك**\n\n"
                         "عذراً، لم تتم الموافقة على حسابك.\n"
                         "للمزيد من المعلومات، يرجى التواصل مع الإدارة.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"فشل إرسال إشعار الرفض: {e}")
                
        elif action == "suspend":
            # حفظ معلومات المستخدم للاستخدام لاحقاً
            context.user_data["suspend_user_id"] = user_id
            context.user_data["suspend_user_name"] = user_name
            context.user_data["suspend_user_tg_id"] = user_tg_id
            
            # طلب سبب التجميد
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚠️ مخالفة للنظام", callback_data="suspend_reason:violation")],
                [InlineKeyboardButton("📉 أداء ضعيف", callback_data="suspend_reason:performance")],
                [InlineKeyboardButton("🚫 سلوك غير لائق", callback_data="suspend_reason:behavior")],
                [InlineKeyboardButton("⏰ تأخر في التقارير", callback_data="suspend_reason:late")],
                [InlineKeyboardButton("✏️ سبب آخر (أدخل يدوياً)", callback_data="suspend_reason:custom")],
                [InlineKeyboardButton("🔙 إلغاء", callback_data="um:back")]
            ])
            
            await query.edit_message_text(
                f"🔒 **تجميد المستخدم: {user_name}**\n\n"
                f"اختر سبب التجميد:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            return UM_SUSPEND_REASON
                
        elif action == "unsuspend":
            user.is_suspended = False
            user.suspended_at = None
            user.suspension_reason = None
            s.commit()
            message = f"🔓 **تم إلغاء تجميد المستخدم بنجاح**\n\n"
            message += f"👤 **الاسم:** {user_name}\n"
            message += f"📅 **التاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            message += f"✅ يمكنه الآن استخدام النظام بشكل كامل."
            
            # إرسال إشعار للمستخدم
            try:
                await context.bot.send_message(
                    chat_id=user_tg_id,
                    text="🔓 **تم تفعيل حسابك**\n\n"
                         "✅ تم إلغاء تجميد حسابك.\n"
                         "يمكنك الآن استخدام النظام بالكامل.\n\n"
                         "اضغط /start للمتابعة!",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"فشل إرسال إشعار إلغاء التجميد: {e}")
                
        elif action == "delete":
            # طلب تأكيد الحذف
            context.user_data["delete_user_id"] = user_id
            context.user_data["delete_user_name"] = user_name
            context.user_data["delete_user_tg_id"] = user_tg_id
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚠️ نعم، احذف نهائياً", callback_data="confirm_delete:yes")],
                [InlineKeyboardButton("❌ لا، إلغاء", callback_data="confirm_delete:no")]
            ])
            
            await query.edit_message_text(
                f"⚠️ **تحذير: حذف نهائي!**\n\n"
                f"👤 **المستخدم:** {user_name}\n\n"
                f"🗑 هل أنت متأكد من حذف هذا المستخدم **نهائياً**؟\n\n"
                f"⚠️ **تحذيرات:**\n"
                f"❌ سيتم حذف جميع بياناته\n"
                f"❌ لا يمكن التراجع عن هذا الإجراء\n"
                f"❌ سيتم إخراجه من البوت نهائياً\n\n"
                f"💡 **نصيحة:** إذا كنت تريد إيقافه مؤقتاً، استخدم 'تجميد' بدلاً من الحذف.",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            return UM_USER_ACTIONS
        
        await query.edit_message_text(f"{message}\n\n👥 إدارة المستخدمين:", reply_markup=_main_kb(), parse_mode="Markdown")
        return UM_START

async def _show_suspended_users(query, context):
    """عرض المستخدمين المجمدين"""
    with SessionLocal() as s:
        users = s.query(Translator).filter_by(is_suspended=True).order_by(Translator.suspended_at.desc()).all()
        
        if not users:
            await query.message.reply_text(
                "🔓 **لا يوجد مستخدمين مجمدين**\n\n"
                "✅ جميع المستخدمين نشطين حالياً.\n\n"
                "اختر خياراً آخر:",
                reply_markup=_main_kb(),
                parse_mode="Markdown"
            )
            try:
                await query.delete_message()
            except:
                pass
            return UM_START
        
        text = f"🔒 **المستخدمين المجمدين ({len(users)})**\n\n"
        text += "اختر مستخدماً لعرض التفاصيل:"
        await query.edit_message_text(text, reply_markup=_users_kb(users), parse_mode="Markdown")
        return UM_SELECT_USER


async def _show_statistics(query, context):
    """عرض إحصائيات المستخدمين"""
    from db.models import Report
    
    with SessionLocal() as s:
        total_users = s.query(Translator).count()
        approved_users = s.query(Translator).filter_by(is_approved=True).count()
        pending_users = s.query(Translator).filter_by(is_approved=False).count()
        suspended_users = s.query(Translator).filter_by(is_suspended=True).count()
        active_users = s.query(Translator).filter_by(is_approved=True, is_suspended=False).count()
        
        total_reports = s.query(Report).count()
        
        # أكثر المترجمين نشاطاً
        from sqlalchemy import func
        top_translators = s.query(
            Translator.full_name,
            func.count(Report.id).label('report_count')
        ).join(Report, Translator.id == Report.translator_id, isouter=True)\
         .group_by(Translator.id)\
         .order_by(func.count(Report.id).desc())\
         .limit(5).all()
        
        text = f"📊 **إحصائيات المستخدمين**\n"
        text += f"━━━━━━━━━━━━━━━━\n\n"
        text += f"👥 **إجمالي المستخدمين:** {total_users}\n"
        text += f"✅ **المعتمدين:** {approved_users}\n"
        text += f"⏳ **المعلقين:** {pending_users}\n"
        text += f"🔒 **المجمدين:** {suspended_users}\n"
        text += f"🟢 **النشطين:** {active_users}\n\n"
        text += f"📝 **إجمالي التقارير:** {total_reports}\n\n"
        
        if top_translators:
            text += f"🏆 **أكثر المترجمين نشاطاً:**\n\n"
            for i, (name, count) in enumerate(top_translators, 1):
                text += f"{i}. **{name}** - {count} تقرير\n"
        
        text += f"\n━━━━━━━━━━━━━━━━"
        
        await query.edit_message_text(text, reply_markup=_back_kb(), parse_mode="Markdown")
        return UM_START


async def _start_search(query, context):
    """بدء البحث عن مستخدم"""
    await query.edit_message_text(
        "🔍 **البحث عن مستخدم**\n\n"
        "أرسل اسم المستخدم أو رقم الهاتف للبحث:",
        reply_markup=_back_kb(),
        parse_mode="Markdown"
    )
    return UM_SEARCH


async def handle_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة البحث"""
    search_text = update.message.text.strip()
    
    with SessionLocal() as s:
        # البحث في الاسم والهاتف
        users = s.query(Translator).filter(
            (Translator.full_name.ilike(f"%{search_text}%")) | 
            (Translator.phone_number.ilike(f"%{search_text}%"))
        ).all()
        
        if not users:
            await update.message.reply_text(
                f"❌ **لم يتم العثور على نتائج**\n\n"
                f"لم يتم العثور على مستخدمين بـ: `{search_text}`\n\n"
                f"جرب مرة أخرى أو ارجع للقائمة الرئيسية.",
                reply_markup=_back_kb(),
                parse_mode="Markdown"
            )
            return UM_SEARCH
        
        text = f"🔍 **نتائج البحث عن:** `{search_text}`\n\n"
        text += f"وجدت {len(users)} نتيجة\n\n"
        
        await update.message.reply_text(text, reply_markup=_users_kb(users), parse_mode="Markdown")
        return UM_SELECT_USER


async def handle_delete_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة تأكيد الحذف"""
    query = update.callback_query
    await query.answer()
    
    confirmation = query.data.split(":")[1]
    
    if confirmation == "no":
        # إلغاء الحذف
        await query.edit_message_text(
            "✅ **تم إلغاء الحذف**\n\n"
            "لم يتم حذف المستخدم.\n\n"
            "👥 إدارة المستخدمين:",
            reply_markup=_main_kb(),
            parse_mode="Markdown"
        )
        return UM_START
    
    # تنفيذ الحذف
    user_id = context.user_data.get("delete_user_id")
    user_name = context.user_data.get("delete_user_name")
    user_tg_id = context.user_data.get("delete_user_tg_id")
    
    if not user_id:
        await query.edit_message_text("❌ خطأ: لم يتم العثور على المستخدم.", reply_markup=_main_kb())
        return UM_START
    
    with SessionLocal() as s:
        user = s.query(Translator).filter_by(id=user_id).first()
        if not user:
            await query.edit_message_text("❌ المستخدم غير موجود.", reply_markup=_main_kb())
            return UM_START
        
        # حذف المستخدم (Soft Delete)
        user.is_active = False
        user.is_approved = False  # تأكد من إلغاء الموافقة أيضاً
        user.is_suspended = False # تأكد من إلغاء التجميد أيضاً
        s.commit()
    
    message = f"🗑 **تم إلغاء تنشيط حساب المستخدم**\n\n"
    message += f"👤 **الاسم:** {user_name}\n"
    message += f"📅 **التاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    message += f"✅ **تم بنجاح:**\n"
    message += f"- إلغاء تنشيط الحساب في قاعدة البيانات\n"
    message += f"- إزالة وصوله من البوت نهائياً\n"
    message += f"- إرسال إشعار له\n\n"
    message += f"⚠️ **ملاحظة:** يمكن إعادة تنشيط الحساب إذا لزم الأمر."
    
    # إرسال إشعار للمستخدم
    try:
        await context.bot.send_message(
            chat_id=user_tg_id,
            text=f"🚫 **تم إلغاء تنشيط حسابك**\n\n"
                 f"تم إلغاء وصولك إلى نظام التقارير الطبية.\n"
                 f"لن تتمكن من استخدام البوت بعد الآن.\n\n"
                 f"للمزيد من المعلومات أو الاستفسار، يرجى التواصل مع الإدارة.",
            parse_mode="Markdown"
        )
        logger.info(f"✅ تم إرسال إشعار الإخراج إلى {user_name}")
    except Exception as e:
        logger.error(f"❌ فشل إرسال إشعار الإخراج: {e}")
    
    await query.edit_message_text(f"{message}\n\n👥 إدارة المستخدمين:", reply_markup=_main_kb(), parse_mode="Markdown")
    return UM_START


async def handle_suspend_reason_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار سبب التجميد"""
    query = update.callback_query
    await query.answer()
    
    reason_type = query.data.split(":")[1]
    
    # أسباب محددة مسبقاً
    reasons = {
        "violation": "⚠️ مخالفة للنظام واللوائح",
        "performance": "📉 أداء ضعيف في العمل",
        "behavior": "🚫 سلوك غير لائق مع الفريق",
        "late": "⏰ تأخر متكرر في تسليم التقارير"
    }
    
    if reason_type == "custom":
        # طلب إدخال سبب مخصص
        await query.edit_message_text(
            "✏️ **إدخال سبب التجميد**\n\n"
            "اكتب سبب التجميد:",
            parse_mode="Markdown"
        )
        return UM_SUSPEND_REASON
    else:
        # استخدام سبب محدد مسبقاً
        reason = reasons.get(reason_type, "سبب غير محدد")
        await _execute_suspension(query, context, reason)
        return UM_START


async def handle_custom_suspend_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة سبب التجميد المخصص"""
    reason = update.message.text.strip()
    
    if len(reason) < 3:
        await update.message.reply_text(
            "⚠️ **السبب قصير جداً**\n\n"
            "يرجى إدخال سبب واضح (3 أحرف على الأقل):",
            parse_mode="Markdown"
        )
        return UM_SUSPEND_REASON
    
    # تنفيذ التجميد
    await _execute_suspension_message(update, context, reason)
    return UM_START


async def _execute_suspension(query, context, reason):
    """تنفيذ التجميد (من callback)"""
    user_id = context.user_data.get("suspend_user_id")
    user_name = context.user_data.get("suspend_user_name")
    user_tg_id = context.user_data.get("suspend_user_tg_id")
    
    if not user_id:
        await query.edit_message_text("❌ خطأ: لم يتم العثور على المستخدم.", reply_markup=_main_kb())
        return
    
    with SessionLocal() as s:
        user = s.query(Translator).filter_by(id=user_id).first()
        if not user:
            await query.edit_message_text("❌ المستخدم غير موجود.", reply_markup=_main_kb())
            return
        
        user.is_suspended = True
        user.suspended_at = datetime.utcnow()
        user.suspension_reason = reason
        s.commit()
    
    message = f"🔒 **تم تجميد المستخدم بنجاح**\n\n"
    message += f"👤 **الاسم:** {user_name}\n"
    message += f"📋 **السبب:** {reason}\n"
    message += f"📅 **التاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    message += f"⚠️ **ملاحظة:** لن يتمكن المستخدم من استخدام النظام حتى يتم إلغاء التجميد."
    
    # إرسال إشعار للمستخدم
    try:
        await context.bot.send_message(
            chat_id=user_tg_id,
            text=f"🔒 **تم تجميد حسابك**\n\n"
                 f"⚠️ تم إيقاف وصولك للنظام مؤقتاً.\n\n"
                 f"📋 **السبب:** {reason}\n\n"
                 f"للمزيد من المعلومات أو الاستفسار، يرجى التواصل مع الإدارة.",
            parse_mode="Markdown"
        )
        logger.info(f"✅ تم إرسال إشعار التجميد إلى {user_name} (من callback)")
    except Exception as e:
        logger.error(f"❌ فشل إرسال إشعار التجميد: {e}")
    
    await query.edit_message_text(f"{message}\n\n👥 إدارة المستخدمين:", reply_markup=_main_kb(), parse_mode="Markdown")


async def _execute_suspension_message(update, context, reason):
    """تنفيذ التجميد (من رسالة نصية)"""
    user_id = context.user_data.get("suspend_user_id")
    user_name = context.user_data.get("suspend_user_name")
    user_tg_id = context.user_data.get("suspend_user_tg_id")
    
    if not user_id:
        await update.message.reply_text("❌ خطأ: لم يتم العثور على المستخدم.", reply_markup=_main_kb())
        return
    
    with SessionLocal() as s:
        user = s.query(Translator).filter_by(id=user_id).first()
        if not user:
            await update.message.reply_text("❌ المستخدم غير موجود.", reply_markup=_main_kb())
            return
        
        user.is_suspended = True
        user.suspended_at = datetime.utcnow()
        user.suspension_reason = reason
        s.commit()
    
    message = f"🔒 **تم تجميد المستخدم بنجاح**\n\n"
    message += f"👤 **الاسم:** {user_name}\n"
    message += f"📋 **السبب:** {reason}\n"
    message += f"📅 **التاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    message += f"⚠️ **ملاحظة:** لن يتمكن المستخدم من استخدام النظام حتى يتم إلغاء التجميد."
    
    # إرسال إشعار للمستخدم
    try:
        await context.bot.send_message(
            chat_id=user_tg_id,
            text=f"🔒 **تم تجميد حسابك**\n\n"
                 f"⚠️ تم إيقاف وصولك للنظام مؤقتاً.\n\n"
                 f"📋 **السبب:** {reason}\n\n"
                 f"للمزيد من المعلومات أو الاستفسار، يرجى التواصل مع الإدارة.",
            parse_mode="Markdown"
        )
        logger.info(f"✅ تم إرسال إشعار التجميد إلى {user_name}")
    except Exception as e:
        logger.error(f"❌ فشل إرسال إشعار التجميد: {e}")
    
    await update.message.reply_text(f"{message}\n\n👥 إدارة المستخدمين:", reply_markup=_main_kb(), parse_mode="Markdown")


def _back_kb():
    """زر الرجوع فقط"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="um:back")]
    ])


async def _back_to_main(query, context):
    """العودة للقائمة الرئيسية"""
    await query.edit_message_text(
        "👥 **إدارة المستخدمين**\n\n"
        "اختر نوع العرض:",
        reply_markup=_main_kb(),
        parse_mode="Markdown"
    )
    return UM_START

async def cancel_user_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء إدارة المستخدمين"""
    context.user_data.clear()
    await update.message.reply_text("❌ تم إلغاء إدارة المستخدمين.")
    return ConversationHandler.END

# ================================================
# ✅ دمج وظائف القبول/الرفض من admin_users.py
# ================================================
async def handle_user_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة القبول/الرفض للمستخدمين الجدد (من الإشعارات)"""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = int(data.split(":")[1])

    with SessionLocal() as s:
        tr = s.query(Translator).filter_by(tg_user_id=user_id).first()

        if not tr:
            await query.edit_message_text("⚠️ المستخدم لم يعد موجوداً في قاعدة البيانات.")
            return

        if data.startswith("approve:"):
            tr.is_approved = True
            tr.updated_at = datetime.now()
            s.commit()
            await query.edit_message_text(f"✅ تم قبول المستخدم: {tr.full_name}")

            # إخطار المستخدم بأنه تم قبوله
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="🎉 تم قبولك من قبل الإدارة! يمكنك الآن استخدام النظام."
                )
            except Exception:
                pass

        elif data.startswith("reject:"):
            user_name = tr.full_name
            s.delete(tr)
            s.commit()
            await query.edit_message_text(f"❌ تم رفض المستخدم: {user_name}")

def register(app):
    """تسجيل الهاندلرز"""
    # ✅ تسجيل معالج القبول/الرفض (من الإشعارات)
    app.add_handler(CallbackQueryHandler(handle_user_approval, pattern="^(approve|reject):"))
    
    # ✅ تسجيل ConversationHandler لإدارة المستخدمين الكاملة
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^👥 إدارة المستخدمين$"), start_user_management)
        ],
        states={
            UM_START: [
                CallbackQueryHandler(handle_user_management_callback, pattern=r"^um:")
            ],
            UM_SELECT_USER: [
                CallbackQueryHandler(handle_user_management_callback, pattern=r"^um:")
            ],
            UM_USER_ACTIONS: [
                CallbackQueryHandler(handle_delete_confirmation, pattern=r"^confirm_delete:"),
                CallbackQueryHandler(handle_user_management_callback, pattern=r"^um:")
            ],
            UM_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_query),
                CallbackQueryHandler(handle_user_management_callback, pattern=r"^um:")
            ],
            UM_SUSPEND_REASON: [
                CallbackQueryHandler(handle_suspend_reason_callback, pattern=r"^suspend_reason:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_suspend_reason),
                CallbackQueryHandler(handle_user_management_callback, pattern=r"^um:")
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^إلغاء$|^الغاء$|^cancel$"), cancel_user_management),
            CallbackQueryHandler(handle_user_management_callback, pattern=r"^um:cancel$")
        ],
        name="user_management_conv",
        per_chat=True,
        per_user=True,
        per_message=False,
    )
    app.add_handler(conv)


