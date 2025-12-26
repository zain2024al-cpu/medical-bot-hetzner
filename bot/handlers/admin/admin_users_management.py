# =============================
# bot/handlers/admin/admin_users_management.py
# 👥 إدارة المستخدمين - نسخة مبسطة
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from db.session import SessionLocal
from db.models import Translator, Report
from bot.shared_auth import is_admin
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
    if not text:
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(r'([{}])'.format(re.escape(escape_chars)), r'\\\1', text)

async def start_user_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إدارة المستخدمين"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info(f"✅ start_user_management called! Update ID: {update.update_id}")
    
    if not update.message:
        logger.error("❌ No message in update!")
        return ConversationHandler.END
    
    user = update.effective_user
    
    logger.info(f"✅ User ID: {user.id if user else 'None'}")
    logger.info(f"✅ Message text: '{update.message.text if update.message else 'None'}'")
    logger.info(f"🔍 محاولة الوصول لإدارة المستخدمين من: {user.id}")
    
    if not is_admin(user.id):
        logger.warning(f"❌ المستخدم {user.id} ليس أدمن")
        await update.message.reply_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
        return ConversationHandler.END
    
    logger.info(f"✅ الأدمن {user.id} دخل لإدارة المستخدمين")
    
    context.user_data.clear()
    
    try:
        await update.message.reply_text(
            "👥 **إدارة المستخدمين**\n\n"
            "اختر نوع العرض:",
            reply_markup=_main_kb(),
            parse_mode="Markdown"
        )
        logger.info(f"✅ Message sent successfully. Returning UM_START: {UM_START}")
        logger.info("=" * 80)
        return UM_START
    except Exception as e:
        logger.error(f"❌ Error sending message: {e}", exc_info=True)
        logger.info("=" * 80)
        return ConversationHandler.END

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

def _users_kb(users, user_type="all", page=0, users_per_page=10):
    """لوحة مفاتيح المستخدمين مع pagination"""
    buttons = []
    
    # حساب عدد الصفحات
    total_users = len(users)
    total_pages = (total_users + users_per_page - 1) // users_per_page if total_users > 0 else 1
    
    # التأكد من أن رقم الصفحة صحيح
    page = max(0, min(page, total_pages - 1))
    
    # حساب نطاق المستخدمين للصفحة الحالية
    start_idx = page * users_per_page
    end_idx = min(start_idx + users_per_page, total_users)
    users_for_page = users[start_idx:end_idx]
    
    # إضافة أزرار المستخدمين
    for user in users_for_page:
        # تحديد الأيقونة بناءً على الحالة
        if getattr(user, 'is_suspended', False):
            status_icon = "🔒"
        elif user.is_approved:
            status_icon = "✅"
        else:
            status_icon = "⏳"
        
        button_text = f"{status_icon} {user.full_name}"
        buttons.append([InlineKeyboardButton(button_text, callback_data=f"um:user:{user.id}")])
    
    # إضافة أزرار التنقل بين الصفحات
    nav_buttons = []
    if total_pages > 1:
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"um:page:{user_type}:{page - 1}"))
        
        # عرض رقم الصفحة الحالية
        nav_buttons.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="um:noop"))
        
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"um:page:{user_type}:{page + 1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
    
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

async def handle_user_management_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة جميع استدعاءات إدارة المستخدمين"""
    query = update.callback_query
    if not query:
        logger.error("❌ handle_user_management_callback: No query found")
        return ConversationHandler.END
    
    try:
        await query.answer()
    except Exception as e:
        logger.error(f"❌ Error answering query: {e}")
    
    # إزالة البادئة "um:" للحصول على البيانات الفعلية
    if not query.data:
        logger.error("❌ handle_user_management_callback: No query.data")
        return ConversationHandler.END
    
    if query.data.startswith("um:"):
        data = query.data[3:]  # إزالة "um:" من البداية
    else:
        data = query.data
    
    try:
        if data == "view_all":
            return await _show_all_users(query, context, page=0)
        elif data == "view_pending":
            return await _show_pending_users(query, context, page=0)
        elif data == "view_approved":
            return await _show_approved_users(query, context, page=0)
        elif data == "view_suspended":
            return await _show_suspended_users(query, context, page=0)
        elif data.startswith("page:"):
            # معالجة pagination: page:user_type:page_num
            try:
                parts = data.split(":")
                if len(parts) == 3:
                    user_type = parts[1]
                    page_num = int(parts[2])
                    if user_type == "all":
                        return await _show_all_users(query, context, page=page_num)
                    elif user_type == "pending":
                        return await _show_pending_users(query, context, page=page_num)
                    elif user_type == "approved":
                        return await _show_approved_users(query, context, page=page_num)
                    elif user_type == "suspended":
                        return await _show_suspended_users(query, context, page=page_num)
                    elif user_type == "search":
                        # إعادة البحث باستخدام النص المحفوظ
                        search_text = context.user_data.get("search_text", "")
                        if search_text:
                            return await _show_search_results(query, context, search_text, page=page_num)
                        else:
                            # إذا لم يكن هناك نص بحث محفوظ، العودة للقائمة الرئيسية
                            return await _back_to_main(query, context)
            except (ValueError, IndexError) as e:
                logger.error(f"❌ Error parsing page data: {e}")
        elif data == "noop":
            # لا شيء - المستخدم ضغط على زر رقم الصفحة
            await query.answer()
            return UM_SELECT_USER
        elif data == "stats":
            return await _show_statistics(query, context)
        elif data == "search":
            return await _start_search(query, context)
        elif data.startswith("user:"):
            try:
                user_id = int(data.split(":")[1])
                return await _show_user_details(query, context, user_id)
            except (ValueError, IndexError) as e:
                logger.error(f"❌ Error parsing user_id: {e}")
                await query.edit_message_text("❌ خطأ في رقم المستخدم.")
                return UM_START
        elif data in ["approve", "reject", "suspend", "unsuspend", "delete"]:
            return await _handle_user_action(query, context, data)
        elif data == "back":
            return await _back_to_main(query, context)
        elif data == "cancel":
            await query.edit_message_text("❌ تم إلغاء إدارة المستخدمين.")
            return ConversationHandler.END
        else:
            logger.warning(f"⚠️ Unknown callback data: {data}")
            await query.edit_message_text("❌ أمر غير معروف.")
            return UM_START
    except Exception as e:
        logger.error(f"❌ Error in user management callback: {e}", exc_info=True)
        try:
            await query.edit_message_text("❌ حدث خطأ. يرجى المحاولة مرة أخرى.")
        except:
            pass
        return UM_START

async def _show_all_users(query, context, page=0):
    """عرض جميع المستخدمين"""
    with SessionLocal() as s:
        users = s.query(Translator).order_by(Translator.created_at.desc()).all()
        
        if not users:
            await query.edit_message_text(
                "📋 **لا يوجد مستخدمين مسجلين**\n\n"
                "لم يتم تسجيل أي مستخدم بعد.\n\n"
                "اختر خياراً آخر:",
                reply_markup=_main_kb(),
                parse_mode="Markdown"
            )
            return UM_START
        
        users_per_page = 10
        total_users = len(users)
        total_pages = (total_users + users_per_page - 1) // users_per_page if total_users > 0 else 1
        page = max(0, min(page, total_pages - 1))
        start_idx = page * users_per_page
        end_idx = min(start_idx + users_per_page, total_users)
        
        text = f"📋 **جميع المستخدمين ({total_users})**\n\n"
        if total_pages > 1:
            text += f"📄 الصفحة {page + 1} من {total_pages} (المستخدمين {start_idx + 1}-{end_idx})\n\n"
        text += "اختر مستخدماً لعرض التفاصيل:"
        await query.edit_message_text(text, reply_markup=_users_kb(users, "all", page), parse_mode="Markdown")
        return UM_SELECT_USER

async def _show_pending_users(query, context, page=0):
    """عرض المستخدمين المعلقين"""
    with SessionLocal() as s:
        users = s.query(Translator).filter_by(is_approved=False).order_by(Translator.created_at.desc()).all()
        
        if not users:
            await query.edit_message_text(
                "⏳ **لا يوجد مستخدمين معلقين**\n\n"
                "✅ لا توجد طلبات انضمام بانتظار الموافقة.\n\n"
                "اختر خياراً آخر:",
                reply_markup=_main_kb(),
                parse_mode="Markdown"
            )
            return UM_START
        
        users_per_page = 10
        total_users = len(users)
        total_pages = (total_users + users_per_page - 1) // users_per_page if total_users > 0 else 1
        page = max(0, min(page, total_pages - 1))
        start_idx = page * users_per_page
        end_idx = min(start_idx + users_per_page, total_users)
        
        text = f"⏳ **المستخدمين المعلقين ({total_users})**\n\n"
        if total_pages > 1:
            text += f"📄 الصفحة {page + 1} من {total_pages} (المستخدمين {start_idx + 1}-{end_idx})\n\n"
        text += "اختر مستخدماً لعرض التفاصيل:"
        await query.edit_message_text(text, reply_markup=_users_kb(users, "pending", page), parse_mode="Markdown")
        return UM_SELECT_USER

async def _show_approved_users(query, context, page=0):
    """عرض المستخدمين الموافق عليهم"""
    with SessionLocal() as s:
        users = s.query(Translator).filter_by(is_approved=True).order_by(Translator.created_at.desc()).all()
        
        if not users:
            await query.edit_message_text(
                "✅ **لا يوجد مستخدمين نشطين**\n\n"
                "لم يتم الموافقة على أي مستخدم بعد.\n\n"
                "اختر خياراً آخر:",
                reply_markup=_main_kb(),
                parse_mode="Markdown"
            )
            return UM_START
        
        users_per_page = 10
        total_users = len(users)
        total_pages = (total_users + users_per_page - 1) // users_per_page if total_users > 0 else 1
        page = max(0, min(page, total_pages - 1))
        start_idx = page * users_per_page
        end_idx = min(start_idx + users_per_page, total_users)
        
        text = f"✅ **المستخدمين النشطين ({total_users})**\n\n"
        if total_pages > 1:
            text += f"📄 الصفحة {page + 1} من {total_pages} (المستخدمين {start_idx + 1}-{end_idx})\n\n"
        text += "اختر مستخدماً لعرض التفاصيل:"
        await query.edit_message_text(text, reply_markup=_users_kb(users, "approved", page), parse_mode="Markdown")
        return UM_SELECT_USER

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
            logger.error(f"خطأ في حساب عدد التقارير: {e}", exc_info=True)
            reports_count = 0
        
        # آخر تقرير (باستخدام فقط الأعمدة الأساسية)
        try:
            last_report = s.query(Report.id, Report.created_at).filter_by(translator_id=user.id).order_by(Report.created_at.desc()).first()
            if last_report and hasattr(last_report, 'created_at') and last_report.created_at:
                last_activity = last_report.created_at.strftime('%Y-%m-%d %H:%M')
            else:
                last_activity = "لا يوجد"
        except Exception as e:
            logger.error(f"خطأ في جلب آخر تقرير: {e}", exc_info=True)
            last_activity = "لا يوجد"
        
        # التحقق من الحقول قبل استخدامها
        is_approved = getattr(user, 'is_approved', False)
        is_suspended = getattr(user, 'is_suspended', False)
        
        status = "✅ نشط" if is_approved else "⏳ معلق"
        suspended = "🔒 مجمد" if is_suspended else "🔓 نشط"
        
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
        
        if is_suspended:
            suspended_at = getattr(user, 'suspended_at', None)
            if suspended_at:
                try:
                    text += f"\n⚠️ **تاريخ التجميد:** {suspended_at.strftime('%Y-%m-%d %H:%M')}\n"
                except:
                    text += f"\n⚠️ **تاريخ التجميد:** غير محدد\n"
            suspension_reason = getattr(user, 'suspension_reason', None)
            if suspension_reason:
                text += f"📋 **سبب التجميد:** {suspension_reason}\n"
        
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
            if hasattr(user, 'suspended_at'):
                user.suspended_at = None
            if hasattr(user, 'suspension_reason'):
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

async def _show_suspended_users(query, context, page=0):
    """عرض المستخدمين المجمدين"""
    with SessionLocal() as s:
        users = s.query(Translator).filter_by(is_suspended=True).order_by(Translator.suspended_at.desc()).all()
        
        if not users:
            await query.edit_message_text(
                "🔓 **لا يوجد مستخدمين مجمدين**\n\n"
                "✅ جميع المستخدمين نشطين حالياً.\n\n"
                "اختر خياراً آخر:",
                reply_markup=_main_kb(),
                parse_mode="Markdown"
            )
            return UM_START
        
        users_per_page = 10
        total_users = len(users)
        total_pages = (total_users + users_per_page - 1) // users_per_page if total_users > 0 else 1
        page = max(0, min(page, total_pages - 1))
        start_idx = page * users_per_page
        end_idx = min(start_idx + users_per_page, total_users)
        
        text = f"🔒 **المستخدمين المجمدين ({total_users})**\n\n"
        if total_pages > 1:
            text += f"📄 الصفحة {page + 1} من {total_pages} (المستخدمين {start_idx + 1}-{end_idx})\n\n"
        text += "اختر مستخدماً لعرض التفاصيل:"
        await query.edit_message_text(text, reply_markup=_users_kb(users, "suspended", page), parse_mode="Markdown")
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

async def _show_search_results(query, context, search_text, page=0):
    """عرض نتائج البحث (للاستخدام في pagination)"""
    with SessionLocal() as s:
        # البحث في الاسم والهاتف
        users = s.query(Translator).filter(
            (Translator.full_name.ilike(f"%{search_text}%")) | 
            (Translator.phone_number.ilike(f"%{search_text}%"))
        ).order_by(Translator.created_at.desc()).all()
        
        if not users:
            await query.edit_message_text(
                f"❌ **لم يتم العثور على نتائج**\n\n"
                f"لم يتم العثور على مستخدمين بـ: `{search_text}`\n\n"
                f"جرب مرة أخرى أو ارجع للقائمة الرئيسية.",
                reply_markup=_back_kb(),
                parse_mode="Markdown"
            )
            return UM_SEARCH
        
        users_per_page = 10
        total_users = len(users)
        total_pages = (total_users + users_per_page - 1) // users_per_page if total_users > 0 else 1
        page = max(0, min(page, total_pages - 1))
        start_idx = page * users_per_page
        end_idx = min(start_idx + users_per_page, total_users)
        
        text = f"🔍 **نتائج البحث عن:** `{search_text}`\n\n"
        text += f"📊 وجدت {total_users} نتيجة\n\n"
        if total_pages > 1:
            text += f"📄 الصفحة {page + 1} من {total_pages} (المستخدمين {start_idx + 1}-{end_idx})\n\n"
        text += "اختر مستخدماً لعرض التفاصيل:"
        
        await query.edit_message_text(text, reply_markup=_users_kb(users, "search", page), parse_mode="Markdown")
        return UM_SELECT_USER


async def handle_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    """معالجة البحث"""
    search_text = update.message.text.strip()
    
    # حفظ نص البحث في context للاستخدام في pagination
    context.user_data["search_text"] = search_text
    
    with SessionLocal() as s:
        # البحث في الاسم والهاتف
        users = s.query(Translator).filter(
            (Translator.full_name.ilike(f"%{search_text}%")) | 
            (Translator.phone_number.ilike(f"%{search_text}%"))
        ).order_by(Translator.created_at.desc()).all()
        
        if not users:
            await update.message.reply_text(
                f"❌ **لم يتم العثور على نتائج**\n\n"
                f"لم يتم العثور على مستخدمين بـ: `{search_text}`\n\n"
                f"جرب مرة أخرى أو ارجع للقائمة الرئيسية.",
                reply_markup=_back_kb(),
                parse_mode="Markdown"
            )
            return UM_SEARCH
        
        users_per_page = 10
        total_users = len(users)
        total_pages = (total_users + users_per_page - 1) // users_per_page if total_users > 0 else 1
        page = max(0, min(page, total_pages - 1))
        start_idx = page * users_per_page
        end_idx = min(start_idx + users_per_page, total_users)
        
        text = f"🔍 **نتائج البحث عن:** `{search_text}`\n\n"
        text += f"📊 وجدت {total_users} نتيجة\n\n"
        if total_pages > 1:
            text += f"📄 الصفحة {page + 1} من {total_pages} (المستخدمين {start_idx + 1}-{end_idx})\n\n"
        text += "اختر مستخدماً لعرض التفاصيل:"
        
        await update.message.reply_text(text, reply_markup=_users_kb(users, "search", page), parse_mode="Markdown")
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
        if hasattr(user, 'is_active'):
            user.is_active = False
        user.is_approved = False  # تأكد من إلغاء الموافقة أيضاً
        if hasattr(user, 'is_suspended'):
            user.is_suspended = False  # تأكد من إلغاء التجميد أيضاً
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
        user.suspended_at = datetime.now()
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
        user.suspended_at = datetime.now()
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

def register(app):
    """تسجيل الهاندلرز"""
    conv = ConversationHandler(
        entry_points=[
            # ✅ استخدام pattern مرن جداً - يطابق أي نص يحتوي على "إدارة المستخدمين"
            MessageHandler(
                filters.ChatType.PRIVATE & 
                filters.TEXT & 
                ~filters.COMMAND & 
                filters.Regex(r".*إدارة.*المستخدمين.*"),
                start_user_management
            ),
            # ✅ pattern بديل بدون ChatType للتوافق
            MessageHandler(
                filters.TEXT & 
                ~filters.COMMAND & 
                filters.Regex(r".*إدارة.*المستخدمين.*"),
                start_user_management
            ),
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
        per_message=False,  # ✅ تعطيل per_message للسماح بمعالجة الرسائل بشكل صحيح
    )
    # ✅ تسجيل ConversationHandler في group=0 لضمان الأولوية
    app.add_handler(conv, group=0)


