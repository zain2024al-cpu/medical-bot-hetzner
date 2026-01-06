# ================================================
# bot/handlers/user/user_start.py
# 🔹 بدء استخدام النظام من قبل المستخدم (المترجم)
# ================================================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from datetime import datetime
import hashlib
import logging

logger = logging.getLogger(__name__)

from bot.shared_auth import ensure_translator_record, is_user_approved, register_pending_user
from bot.keyboards import user_main_kb, start_persistent_kb
from telegram.ext import ConversationHandler


# 🌟 قائمة الرسائل التحفيزية (30 رسالة متنوعة)
MOTIVATIONAL_QUOTES = [
    "النجاح هو مجموع الجهود الصغيرة المتكررة يوماً بعد يوم 💪",
    "كل يوم جديد هو فرصة لتكون أفضل مما كنت عليه بالأمس ✨",
    "الإتقان في العمل هو طريقك نحو التميز والنجاح 🎯",
    "لا تستسلم، البدايات دائماً صعبة لكن النتائج رائعة 🌟",
    "العمل الجاد اليوم هو راحة الغد وسعادة المستقبل 🚀",
    "كن صادقاً في عملك، فالصدق أساس كل نجاح حقيقي 💎",
    "التفاني في العمل يصنع الفرق بين الجيد والممتاز ⭐",
    "كل تقرير تكتبه بإتقان هو بصمة تتركها في عملك 📝",
    "الجودة أهم من الكمية، أتقن عملك مهما كان صغيراً ✅",
    "النجاح ليس نهاية الطريق، بل رحلة من التطور المستمر 🌈",
    "ثق بنفسك، أنت قادر على إنجاز أكثر مما تتخيل 💪",
    "الدقة في العمل الطبي تنقذ الأرواح وتصنع الفرق 🏥",
    "كل يوم هو فرصة جديدة لتعلم شيء جديد وتطوير مهاراتك 📚",
    "التزامك بعملك اليوم يبني سمعتك غداً 🏆",
    "العمل بضمير هو أعظم إنجاز يمكن أن تحققه 💯",
    "لا تقارن نفسك بالآخرين، قارن نفسك اليوم بنفسك بالأمس 📈",
    "الإيجابية في العمل تصنع بيئة أفضل للجميع 😊",
    "كل جهد تبذله اليوم هو استثمار في مستقبلك المهني 💼",
    "التفاؤل والعزيمة مفتاحان لكل نجاح ترغب بتحقيقه 🔑",
    "اصبر على صعوبات اليوم، فالنجاح قادم لا محالة 🌅",
    "التركيز والانضباط يحولان الأهداف إلى إنجازات حقيقية 🎯",
    "كن فخوراً بكل عمل تنجزه، مهما كان بسيطاً 🌟",
    "المثابرة والإصرار يهزمان أي صعوبة مهما كانت كبيرة 💪",
    "عملك الجاد اليوم سيكافئك غداً بأجمل الثمار 🍎",
    "التميز ليس حظاً، بل هو نتيجة عمل دؤوب ومستمر ⚡",
    "كل خطوة صغيرة تقربك من هدفك الكبير 👣",
    "الإخلاص في العمل يفتح أبواب النجاح على مصراعيها 🚪",
    "لا تخف من الأخطاء، بل تعلم منها واستمر في التقدم 📊",
    "قيمتك في عملك تكمن في الجودة وليس في السرعة فقط ⏰",
    "ابتسم وابدأ يومك بطاقة إيجابية، النجاح ينتظرك 😊"
]


def get_daily_quote():
    """الحصول على رسالة تحفيزية بناءً على تاريخ اليوم"""
    today = datetime.now().date().isoformat()
    # استخدام hash للحصول على نفس الرسالة طوال اليوم
    hash_value = int(hashlib.md5(today.encode()).hexdigest(), 16)
    index = hash_value % len(MOTIVATIONAL_QUOTES)
    return MOTIVATIONAL_QUOTES[index]


def get_arabic_date():
    """تنسيق التاريخ والوقت بالعربي"""
    now = datetime.now()
    
    # أيام الأسبوع بالعربي
    days_ar = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    day_name = days_ar[now.weekday()]
    
    # أشهر السنة بالعربي
    months_ar = [
        "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
        "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
    ]
    month_name = months_ar[now.month - 1]
    
    # تنسيق الوقت
    hour = now.hour
    minute = now.strftime("%M")
    
    # تحديد الفترة (صباحاً/مساءً)
    if 5 <= hour < 12:
        period = "صباحاً"
        greeting = "صباح الخير"
    elif 12 <= hour < 17:
        period = "ظهراً"
        greeting = "مساء الخير"
    elif 17 <= hour < 21:
        period = "مساءً"
        greeting = "مساء الخير"
    else:
        period = "ليلاً"
        greeting = "مساء الخير"
    
    date_str = f"{day_name}، {now.day} {month_name} {now.year}"
    time_str = f"{hour}:{minute} {period}"
    
    return date_str, time_str, greeting


# 🟢 أمر /start للمستخدم
async def user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج أمر /start للمستخدمين"""
    try:
        user = update.effective_user
        tg_id = user.id

        # ✅ التحقق من أن المستخدم أدمن أولاً
        from bot.shared_auth import is_admin
        if is_admin(tg_id):
            # إذا كان أدمن، أرسله إلى لوحة الأدمن
            from bot.handlers.admin.admin_start import admin_start
            await admin_start(update, context)
            return
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ Error in user_start (admin check): {e}", exc_info=True)
        if update and update.message:
            try:
                await update.message.reply_text("❌ حدث خطأ، يرجى المحاولة مرة أخرى.")
            except:
                pass
        return

    try:
        # ✅ التأكد من أن المستخدم مسجل في قاعدة البيانات (مع الموافقة التلقائية)
        from db.session import SessionLocal
        from db.models import Translator
        
        with SessionLocal() as s:
            tr = s.query(Translator).filter_by(tg_user_id=tg_id).first()
            if not tr:
                # ⚠️ إنشاء المستخدم بدون موافقة تلقائية - يحتاج موافقة الأدمن
                tr = Translator(
                    tg_user_id=tg_id,
                    full_name=user.first_name or "بدون اسم",
                    is_active=True,
                    is_approved=False  # ❌ يحتاج موافقة أدمن أولاً
                )
                s.add(tr)
                s.commit()
                created_at = tr.created_at
                logger.info(f"مستخدم جديد ينتظر الموافقة: {user.first_name} (ID: {tg_id})")
                
                # إرسال تنبيه للأدمن فوراً
                from config.settings import ADMIN_IDS
                import logging
                logger = logging.getLogger(__name__)
                
                if not ADMIN_IDS:
                    logger.warning("⚠️ لا يوجد أدمن محدد في ADMIN_IDS!")
                    print("⚠️ لا يوجد أدمن محدد في ADMIN_IDS!")
                else:
                    logger.info(f"📨 محاولة إرسال إشعار إلى {len(ADMIN_IDS)} أدمن...")
                    print(f"📨 محاولة إرسال إشعار إلى {len(ADMIN_IDS)} أدمن: {ADMIN_IDS}")
                    success_count = 0
                    failed_admins = []
                    
                    for admin_id in ADMIN_IDS:
                        try:
                            keyboard = InlineKeyboardMarkup([
                                [
                                    InlineKeyboardButton("✅ قبول", callback_data=f"approve:{tg_id}"),
                                    InlineKeyboardButton("❌ رفض", callback_data=f"reject:{tg_id}")
                                ]
                            ])
                            
                            # محاولة إرسال الإشعار
                            await context.bot.send_message(
                                chat_id=admin_id,
                                text=f"🔔 **طلب انضمام جديد!**\n\n"
                                     f"👤 **الاسم:** {user.first_name or 'بدون اسم'}\n"
                                     f"🆔 **Telegram ID:** `{tg_id}`\n"
                                     f"📅 **التاريخ:** {created_at.strftime('%Y-%m-%d %H:%M') if created_at else 'الآن'}\n\n"
                                     f"⚠️ يرجى الموافقة أو الرفض:",
                                reply_markup=keyboard,
                                parse_mode="Markdown"
                            )
                            success_count += 1
                            logger.info(f"✅ تم إرسال إشعار للأدمن {admin_id}")
                            print(f"✅ تم إرسال إشعار للأدمن {admin_id}")
                            
                        except Exception as e:
                            error_msg = str(e)
                            failed_admins.append((admin_id, error_msg))
                            
                            # تحليل نوع الخطأ
                            if "bot was blocked by the user" in error_msg.lower():
                                logger.error(f"❌ الأدمن {admin_id} قام بحظر البوت!")
                                print(f"❌ الأدمن {admin_id} قام بحظر البوت!")
                            elif "chat not found" in error_msg.lower():
                                logger.error(f"❌ الأدمن {admin_id} لم يبدأ محادثة مع البوت بعد!")
                                print(f"❌ الأدمن {admin_id} لم يبدأ محادثة مع البوت بعد! (يجب أن يضغط /start)")
                            else:
                                logger.error(f"❌ فشل إرسال إشعار للأدمن {admin_id}: {e}")
                                print(f"❌ فشل إرسال إشعار للأدمن {admin_id}: {e}")
                    
                    # تقرير نهائي
                    logger.info(f"📊 تم إرسال الإشعار بنجاح إلى {success_count} من {len(ADMIN_IDS)} أدمن")
                    print(f"📊 تم إرسال الإشعار بنجاح إلى {success_count} من {len(ADMIN_IDS)} أدمن")
                    
                    if failed_admins:
                        print(f"⚠️ فشل الإرسال لـ {len(failed_admins)} أدمن:")
                        for admin_id, error in failed_admins:
                            print(f"   - الأدمن {admin_id}: {error[:100]}")
                        logger.warning(f"⚠️ فشل الإرسال لـ {len(failed_admins)} أدمن")
                
                # إرسال رسالة للمستخدم الجديد
                notification_status = ""
                if success_count == len(ADMIN_IDS):
                    notification_status = "✅ تم إشعار الإدارة بطلبك."
                elif success_count > 0:
                    notification_status = f"⚠️ تم إشعار بعض الإدارة ({success_count}/{len(ADMIN_IDS)})."
                else:
                    notification_status = "⚠️ لم يتم إرسال إشعار تلقائي.\n💡 يرجى التواصل مع الإدارة مباشرة."
                
                await update.message.reply_text(
                    f"👋 مرحباً {user.first_name}!\n\n"
                    f"📝 تم تسجيل طلبك بنجاح.\n\n"
                    f"{notification_status}\n\n"
                    f"⏳ طلبك قيد المراجعة من قبل الإدارة.\n"
                    f"سيتم إشعارك فور الموافقة على طلبك.\n\n"
                    f"⏱️ الوقت المتوقع: عادة خلال 24 ساعة.\n\n"
                    f"📋 **معلومات مهمة:**\n"
                    f"• يمكنك متابعة حالة طلبك من زر \"المستخدمين المعلقين\"\n"
                    f"• ستتلقى إشعاراً فورياً عند الموافقة على طلبك\n\n"
                    f"شكراً لصبرك! 🙏",
                    reply_markup=start_persistent_kb(),
                    parse_mode="Markdown"
                )
                return  # إيقاف التنفيذ - المستخدم ينتظر الموافقة
                
            elif not tr.full_name or tr.full_name == "بدون اسم":
                # تحديث الاسم إذا لزم الأمر
                tr.full_name = user.first_name or "بدون اسم"
                s.commit()
            
            # حفظ القيم المهمة قبل إغلاق الجلسة
            is_approved = tr.is_approved
            is_suspended = tr.is_suspended
            suspension_reason = tr.suspension_reason
        
        # ⚠️ التحقق من أن المستخدم معتمد (بعد إغلاق الجلسة)
        if not is_approved:
            await update.message.reply_text(
                f"👋 مرحباً {user.first_name}!\n\n"
                f"⏳ طلبك لا يزال قيد المراجعة من قبل الإدارة.\n\n"
                f"⏱️ سيتم إشعارك فور الموافقة على طلبك.\n\n"
                f"شكراً لصبرك! 🙏",
                reply_markup=start_persistent_kb()
            )
            return
        
        # ⚠️ التحقق من أن المستخدم ليس موقوفاً
        if is_suspended:
            reason = suspension_reason or "لا يوجد سبب محدد"
            await update.message.reply_text(
                f"🚫 عذراً {user.first_name}!\n\n"
                f"تم تعليق حسابك مؤقتاً.\n\n"
                f"📋 السبب: {reason}\n\n"
                f"للمزيد من المعلومات، يرجى التواصل مع الإدارة.",
                reply_markup=start_persistent_kb()
            )
            return

        # ✅ إعادة تعيين ConversationHandler عند الضغط على /start
        # مسح جميع بيانات المحادثة السابقة
        context.user_data.clear()
        
        # ✅ عرض رسالة ترحيب متجددة مع زر "ابدأ الآن"
        date_str, time_str, greeting = get_arabic_date()
        daily_quote = get_daily_quote()
        
        welcome_message = f"""╔════════════════════╗
  🌟 {greeting} {user.first_name or 'المترجم'}
╚════════════════════╝

💭 *{daily_quote}*

📅 {date_str}
⏰ {time_str}

━━━━━━━━━━━━━━━━━━━━

👇 اضغط على الزر أدناه للبدء:"""
        
        # زر "ابدأ الآن" - يظهر دائماً مع كل دخول (Inline)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 ابدأ الآن", callback_data="start_main_menu")]
        ])
        
        # إرسال الرسالة الترحيبية مع زر "ابدأ الآن" (Inline)
        await update.message.reply_text(
            welcome_message,
            parse_mode="Markdown",
            reply_markup=keyboard  # InlineKeyboardMarkup للزر "ابدأ الآن"
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ Error in user_start: {e}", exc_info=True)
        if update and update.message:
            try:
                await update.message.reply_text(
                    f"❌ حدث خطأ: {str(e)}\n\nيرجى المحاولة مرة أخرى أو التواصل مع الإدارة.",
                    reply_markup=start_persistent_kb()
                )
            except:
                pass


# 🎯 معالجة زر "ابدأ الآن"
async def handle_start_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض القائمة الرئيسية عند الضغط على زر ابدأ الآن"""
    query = update.callback_query
    await query.answer("تم فتح القائمة الرئيسية ✅")
    
    # إعادة تعيين ConversationHandler عند الضغط على زر "ابدأ الآن"
    context.user_data.clear()
    
    # إرسال القائمة الرئيسية (الأزرار الثابتة) مع زر /start الثابت
    await query.message.reply_text(
        "📋 اختر العملية المطلوبة:",
        reply_markup=user_main_kb()  # user_main_kb يحتوي على الأزرار الرئيسية
    )


# 🔹 تسجيل الهاندلرز الخاصة بالمستخدم
def register(app):
    app.add_handler(CommandHandler("start", user_start))
    # معالج للرسائل النصية "/start" (عند الضغط على الزر من ReplyKeyboardMarkup)
    app.add_handler(MessageHandler(filters.Regex("^/start$"), user_start))
    app.add_handler(MessageHandler(filters.Regex("^🚀 أبدا استخدام النظام$"), user_start))
    app.add_handler(MessageHandler(filters.Regex("^🚀 ابدأ$"), user_start))  # معالج لزر "ابدأ" في الكيبورد
    app.add_handler(CallbackQueryHandler(handle_start_main_menu, pattern="^start_main_menu$"))
