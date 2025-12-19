# ================================================
# bot/user_interface.py
# 🔹 واجهة المستخدم المنفصلة
# ================================================

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler
from bot.shared_auth import ensure_translator_record, is_user_approved, register_pending_user, is_admin
from bot.keyboards import user_main_kb, cancel_kb, new_user_kb, user_main_inline_kb, user_compact_inline_kb
from db.session import SessionLocal
from db.models import Translator

# حالات المحادثة لتسجيل المستخدم الجديد
WAITING_FOR_NAME, WAITING_FOR_PHONE = range(2)


# 🟢 أمر /start للمستخدم (تم نقله إلى bot/handlers/user/user_start.py)
# هذه الدالة معطلة الآن - استخدم الملف الجديد
async def user_start_old(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id

    # ✅ التحقق من أن المستخدم أدمن أولاً
    if is_admin(tg_id):
        # إذا كان أدمن، أرسله إلى لوحة الأدمن
        from bot.admin_interface import admin_start
        await admin_start(update, context)
        return

    # ✅ التحقق من وجود المستخدم في قاعدة البيانات (مع التسجيل التلقائي)
    with SessionLocal() as s:
        existing_user = s.query(Translator).filter_by(tg_user_id=tg_id).first()
        
        if existing_user:
            # المستخدم موجود
            if existing_user.is_suspended:
                # المستخدم مجمد
                await update.message.reply_text(
                    "🚫 **حسابك مجمد**\n\n"
                    "عذراً، تم تجميد حسابك مؤقتاً من قبل الإدارة.\n"
                    "يرجى التواصل مع الإدارة لمزيد من التفاصيل."
                )
                return
            else:
                # المستخدم معتمد → إظهار لوحة الاستخدام الثابتة
                await update.message.reply_text(
                    f"👋 أهلاً {existing_user.full_name}!\nاختر أحد الخيارات من القائمة:",
                    reply_markup=user_main_kb()
                )
        else:
            # مستخدم جديد - التسجيل التلقائي ✅
            new_user = Translator(
                tg_user_id=tg_id,
                full_name=user.first_name or "بدون اسم",
                is_active=True,
                is_approved=True  # ✅ الموافقة التلقائية
            )
            s.add(new_user)
            s.commit()
            print(f"✅ تم تسجيل مستخدم جديد تلقائياً: {user.first_name or 'بدون اسم'}")
            
            await update.message.reply_text(
                f"👋 أهلاً بك {user.first_name}!\n\n"
                "تم تسجيلك في النظام بنجاح ✅\n"
                "اختر أحد الخيارات من القائمة:",
                reply_markup=user_main_kb()
            )

# بدء عملية التسجيل
async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية التسجيل للمستخدم الجديد"""
    user = update.effective_user
    tg_id = user.id

    # التحقق من أن المستخدم ليس أدمن
    if is_admin(tg_id):
        await update.message.reply_text("أنت أدمن، لا تحتاج للتسجيل.")
        return ConversationHandler.END

    # التحقق من أن المستخدم غير مسجل بالفعل
    with SessionLocal() as s:
        existing_user = s.query(Translator).filter_by(tg_user_id=tg_id).first()
        if existing_user:
            if existing_user.is_approved:
                await update.message.reply_text(
                    f"أهلاً {existing_user.full_name}! أنت مسجل بالفعل.",
                    reply_markup=user_main_kb()
                )
            else:
                await update.message.reply_text(
                    "⏳ تم استلام طلبك. بانتظار موافقة الإدارة."
                )
            return ConversationHandler.END

    # بدء عملية التسجيل
    await update.message.reply_text(
        "👋 أهلاً بك! يبدو أنك مستخدم جديد.\n\n"
        "يرجى إدخال اسمك الكامل للبدء:",
        reply_markup=cancel_kb()
    )
    return WAITING_FOR_NAME

# معالجة اسم المستخدم الجديد
async def handle_user_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اسم المستخدم الجديد"""
    user = update.effective_user
    full_name = update.message.text.strip()
    
    # حفظ الاسم في السياق
    context.user_data['full_name'] = full_name
    
    await update.message.reply_text(
        f"شكراً {full_name}!\n\n"
        "يرجى إدخال رقم هاتفك (اختياري):",
        reply_markup=cancel_kb()
    )
    
    return WAITING_FOR_PHONE

# معالجة رقم الهاتف وإنهاء التسجيل
async def handle_user_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة رقم الهاتف وإنهاء التسجيل (مع الموافقة التلقائية)"""
    user = update.effective_user
    phone = update.message.text.strip()
    full_name = context.user_data.get('full_name', 'بدون اسم')
    
    # إنشاء سجل المستخدم الجديد في قاعدة البيانات
    try:
        with SessionLocal() as s:
            # التحقق من عدم وجود المستخدم مسبقاً
            existing = s.query(Translator).filter_by(tg_user_id=user.id).first()
            if not existing:
                # ✅ الموافقة التلقائية مفعّلة
                new_translator = Translator(
                    tg_user_id=user.id,
                    full_name=full_name,
                    phone_number=phone,
                    is_active=True,
                    is_approved=True  # ✅ الموافقة التلقائية
                )
                s.add(new_translator)
                s.commit()
                print(f"✅ تم إنشاء مستخدم جديد تلقائياً: {full_name} - ID: {user.id}")
        
        # إشعار بنجاح التسجيل (بدون انتظار الموافقة)
        await update.message.reply_text(
            f"✅ تم تسجيلك بنجاح!\n\n"
            f"👤 الاسم: {full_name}\n"
            f"📱 الهاتف: {phone}\n\n"
            f"يمكنك الآن استخدام النظام مباشرة 🎉",
            reply_markup=user_main_kb()
        )
    except Exception as e:
        print(f"❌ خطأ في إنشاء المستخدم: {e}")
        await update.message.reply_text(
            "❌ حدث خطأ أثناء التسجيل. يرجى المحاولة مرة أخرى.",
            reply_markup=user_main_kb()
        )
    
    return ConversationHandler.END

# إلغاء التسجيل
async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء عملية التسجيل"""
    await update.message.reply_text(
        "❌ تم إلغاء عملية التسجيل.",
        reply_markup=user_main_kb()
    )
    return ConversationHandler.END

# 🧩 تسجيل الهاندلرز الخاصة بالمستخدم
# ⚠️ معطّل - تم نقل /start إلى bot/handlers/user/user_start.py
def register_user_handlers(app):
    # ConversationHandler لتسجيل المستخدم الجديد
    registration_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🚀 أبدا استخدام النظام$"), start_registration)
        ],
        states={
            WAITING_FOR_NAME: [
                MessageHandler(filters.TEXT & ~filters.Regex("^❌ إلغاء العملية الحالية$"), handle_user_name)
            ],
            WAITING_FOR_PHONE: [
                MessageHandler(filters.TEXT & ~filters.Regex("^❌ إلغاء العملية الحالية$"), handle_user_phone)
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ إلغاء العملية الحالية$"), cancel_registration)
        ],
        name="user_registration_conv",
        per_chat=True,
        per_user=True,
    )
    
    # ❌ تم تعطيل هذا - استخدم bot/handlers/user/user_start.py بدلاً منه
    # app.add_handler(CommandHandler("start", user_start))
    app.add_handler(registration_conv)

