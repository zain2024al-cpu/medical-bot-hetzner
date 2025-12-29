# ================================================
# bot/handlers/admin/admin_hospitals_management.py
# 🔹 إدارة المستشفيات
# ================================================

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode
import logging
from db.session import SessionLocal
from db.models import Hospital
from bot.shared_auth import is_admin

logger = logging.getLogger(__name__)

# ================================================
# إدارة المستشفيات
# ================================================

async def handle_manage_hospitals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدارة المستشفيات"""
    query = update.callback_query
    await query.answer()
    
    # التحقق من صلاحيات الأدمن
    if not is_admin(update.effective_user.id):
        await query.edit_message_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
        return ConversationHandler.END
    
    # قراءة المستشفيات من قاعدة البيانات
    try:
        with SessionLocal() as s:
            hospitals = s.query(Hospital).order_by(Hospital.name).all()
            hospitals_count = len(hospitals)
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل المستشفيات: {e}")
        hospitals_count = 0
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة مستشفى جديد", callback_data="add_hospital")],
        [InlineKeyboardButton("📋 عرض جميع المستشفيات", callback_data="view_hospitals")],
        [InlineKeyboardButton("✏️ تعديل مستشفى", callback_data="edit_hospital")],
        [InlineKeyboardButton("🗑️ حذف مستشفى", callback_data="delete_hospital")],
        [InlineKeyboardButton("🔄 مزامنة من القائمة الثابتة", callback_data="sync_hospitals")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_schedule")]
    ])
    
    await query.edit_message_text(
        f"🏥 **إدارة المستشفيات**\n\n"
        f"📊 **عدد المستشفيات:** {hospitals_count}\n\n"
        f"اختر العملية:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_view_hospitals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض جميع المستشفيات"""
    query = update.callback_query
    await query.answer()
    
    # قراءة المستشفيات من قاعدة البيانات
    try:
        with SessionLocal() as s:
            hospitals = s.query(Hospital).order_by(Hospital.name).all()
            names = [h.name for h in hospitals if h.name]
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل المستشفيات: {e}")
        names = []
    
    if not names:
        text = "📋 **قائمة المستشفيات**\n\n⚠️ لا توجد مستشفيات مسجلة\n\nاستخدم 'مزامنة من القائمة الثابتة' لإضافة المستشفيات الافتراضية"
    else:
        text = f"📋 **قائمة المستشفيات**\n\n📊 **العدد:** {len(names)}\n\n"
        for i, name in enumerate(names[:25], 1):  # أول 25 مستشفى
            text += f"{i}. 🏥 {name}\n"
        
        if len(names) > 25:
            text += f"\n... و {len(names) - 25} مستشفى آخر"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]
    ])
    
    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_add_hospital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إضافة مستشفى جديد"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "➕ **إضافة مستشفى جديد**\n\n"
        "📝 اكتب اسم المستشفى:\n"
        "مثال: Manipal Hospital - Whitefield",
        parse_mode=ParseMode.MARKDOWN
    )
    return "ADD_HOSPITAL_NAME"

async def handle_hospital_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم المستشفى الجديد"""
    name = update.message.text.strip()
    
    if not name or len(name) < 3:
        await update.message.reply_text(
            "⚠️ **خطأ:** الاسم قصير جداً\n\n"
            "يرجى إدخال اسم صحيح (3 حروف على الأقل):",
            parse_mode=ParseMode.MARKDOWN
        )
        return "ADD_HOSPITAL_NAME"
    
    # إضافة المستشفى لقاعدة البيانات
    try:
        with SessionLocal() as s:
            # التحقق من وجود المستشفى مسبقاً
            existing = s.query(Hospital).filter_by(name=name).first()
            if existing:
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]])
                await update.message.reply_text(
                    f"⚠️ **المستشفى موجود مسبقاً:** {name}",
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN
                )
                return ConversationHandler.END
            
            new_hospital = Hospital(name=name)
            s.add(new_hospital)
            s.commit()
            logger.info(f"✅ تم إضافة المستشفى '{name}' إلى قاعدة البيانات")
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]])
        
        await update.message.reply_text(
            f"✅ **تم إضافة المستشفى بنجاح:** {name}\n\n"
            f"🏥 سيظهر المستشفى عند إنشاء تقرير جديد",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"❌ خطأ في إضافة المستشفى: {e}")
        await update.message.reply_text(
            f"❌ **خطأ في الحفظ:** {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

async def handle_delete_hospital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """واجهة حذف مستشفى"""
    query = update.callback_query
    await query.answer()
    
    # قراءة المستشفيات من قاعدة البيانات
    try:
        with SessionLocal() as s:
            hospitals = s.query(Hospital).order_by(Hospital.name).all()
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل المستشفيات: {e}")
        await query.edit_message_text(
            "❌ **خطأ في تحميل المستشفيات**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]]),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if not hospitals:
        await query.edit_message_text(
            "⚠️ **لا توجد مستشفيات لحذفها**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]]),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # عرض المستشفيات مع أزرار حذف (أول 10 فقط)
    keyboard = []
    for hospital in hospitals[:10]:
        keyboard.append([InlineKeyboardButton(
            f"🗑️ {hospital.name}",
            callback_data=f"confirm_delete_hosp:{hospital.id}:{hospital.name[:30]}"
        )])
    
    if len(hospitals) > 10:
        keyboard.append([InlineKeyboardButton(
            f"⚠️ عرض {len(hospitals) - 10} مستشفى آخر...",
            callback_data="delete_hosp_page_2"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")])
    
    await query.edit_message_text(
        f"🗑️ **حذف مستشفى**\n\n"
        f"📊 **العدد:** {len(hospitals)}\n\n"
        f"اختر المستشفى المراد حذفه:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_confirm_delete_hospital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد حذف مستشفى"""
    query = update.callback_query
    await query.answer()
    
    # استخراج البيانات
    parts = query.data.split(':', 2)
    if len(parts) < 3:
        await query.edit_message_text("❌ خطأ: طلب حذف غير صالح.")
        return
    
    try:
        hospital_id = int(parts[1])
    except ValueError:
        await query.edit_message_text("❌ خطأ: معرف المستشفى غير صالح.")
        return
    
    hospital_name = parts[2]
    
    # حذف من قاعدة البيانات
    try:
        with SessionLocal() as s:
            hospital = s.query(Hospital).filter_by(id=hospital_id).first()
            if hospital:
                full_name = hospital.name
                s.delete(hospital)
                s.commit()
                logger.info(f"✅ تم حذف المستشفى '{full_name}' من قاعدة البيانات")
                
                # عد المستشفيات المتبقية
                remaining = s.query(Hospital).count()
                
                await query.edit_message_text(
                    f"✅ **تم حذف المستشفى:** {full_name}\n\n"
                    f"📊 **عدد المستشفيات المتبقية:** {remaining}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]]),
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await query.edit_message_text(
                    "⚠️ **المستشفى غير موجود**",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]]),
                    parse_mode=ParseMode.MARKDOWN
                )
    except Exception as e:
        logger.error(f"❌ خطأ في حذف المستشفى: {e}")
        await query.edit_message_text(
            f"❌ **خطأ في الحذف:** {str(e)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]]),
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_edit_hospital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """واجهة تعديل مستشفى"""
    query = update.callback_query
    await query.answer()
    
    # قراءة المستشفيات من قاعدة البيانات
    try:
        with SessionLocal() as s:
            hospitals = s.query(Hospital).order_by(Hospital.name).all()
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل المستشفيات: {e}")
        await query.edit_message_text(
            "❌ **خطأ في تحميل المستشفيات**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]]),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if not hospitals:
        await query.edit_message_text(
            "⚠️ **لا توجد مستشفيات لتعديلها**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]]),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # عرض المستشفيات مع أزرار تعديل (أول 10 فقط)
    keyboard = []
    for hospital in hospitals[:10]:
        keyboard.append([InlineKeyboardButton(
            f"✏️ {hospital.name}",
            callback_data=f"select_edit_hosp:{hospital.id}:{hospital.name[:30]}"
        )])
    
    if len(hospitals) > 10:
        keyboard.append([InlineKeyboardButton(
            f"⚠️ عرض {len(hospitals) - 10} مستشفى آخر...",
            callback_data="edit_hosp_page_2"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")])
    
    await query.edit_message_text(
        f"✏️ **تعديل مستشفى**\n\n"
        f"📊 **العدد:** {len(hospitals)}\n\n"
        f"اختر المستشفى المراد تعديله:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_select_edit_hospital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار مستشفى للتعديل"""
    query = update.callback_query
    await query.answer()
    
    # استخراج البيانات
    parts = query.data.split(':', 2)
    if len(parts) < 3:
        await query.edit_message_text("❌ خطأ: طلب تعديل غير صالح.")
        return ConversationHandler.END
    
    try:
        hospital_id = int(parts[1])
    except ValueError:
        await query.edit_message_text("❌ خطأ: معرف المستشفى غير صالح.")
        return ConversationHandler.END
    
    # جلب الاسم الكامل من قاعدة البيانات
    try:
        with SessionLocal() as s:
            hospital = s.query(Hospital).filter_by(id=hospital_id).first()
            if hospital:
                old_name = hospital.name
            else:
                await query.edit_message_text("❌ خطأ: المستشفى غير موجود.")
                return ConversationHandler.END
    except Exception as e:
        logger.error(f"❌ خطأ في جلب المستشفى: {e}")
        await query.edit_message_text("❌ خطأ في جلب بيانات المستشفى.")
        return ConversationHandler.END
    
    # حفظ في context
    context.user_data['edit_hospital_id'] = hospital_id
    context.user_data['edit_hospital_old_name'] = old_name
    
    await query.edit_message_text(
        f"✏️ **تعديل اسم المستشفى**\n\n"
        f"🏥 **الاسم الحالي:** {old_name}\n\n"
        f"اكتب الاسم الجديد:",
        parse_mode=ParseMode.MARKDOWN
    )
    
    return "EDIT_HOSPITAL_INPUT"

async def handle_edit_hospital_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال الاسم الجديد للمستشفى"""
    new_name = update.message.text.strip()
    
    if not new_name or len(new_name) < 3:
        await update.message.reply_text(
            "⚠️ **خطأ:** الاسم قصير جداً\n\n"
            "يرجى إدخال اسم صحيح (3 حروف على الأقل):",
            parse_mode=ParseMode.MARKDOWN
        )
        return "EDIT_HOSPITAL_INPUT"
    
    # الحصول على البيانات المحفوظة
    hospital_id = context.user_data.get('edit_hospital_id')
    old_name = context.user_data.get('edit_hospital_old_name')
    
    if hospital_id is None or old_name is None:
        await update.message.reply_text("❌ **خطأ:** لم يتم اختيار مستشفى للتعديل", parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    
    # تعديل في قاعدة البيانات
    try:
        with SessionLocal() as s:
            hospital = s.query(Hospital).filter_by(id=hospital_id).first()
            if hospital:
                hospital.name = new_name
                s.commit()
                logger.info(f"✅ تم تعديل اسم المستشفى من '{old_name}' إلى '{new_name}'")
        
        # مسح البيانات المحفوظة
        context.user_data.pop('edit_hospital_id', None)
        context.user_data.pop('edit_hospital_old_name', None)
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]])
        
        await update.message.reply_text(
            f"✅ **تم تعديل اسم المستشفى بنجاح**\n\n"
            f"🏥 **من:** {old_name}\n"
            f"🏥 **إلى:** {new_name}",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"❌ خطأ في تعديل المستشفى: {e}")
        await update.message.reply_text(
            f"❌ **خطأ في الحفظ:** {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

async def handle_sync_hospitals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مزامنة المستشفيات من القائمة الثابتة إلى قاعدة البيانات"""
    query = update.callback_query
    await query.answer()
    
    # القائمة الثابتة للمستشفيات
    PREDEFINED_HOSPITALS = [
        "Manipal Hospital - Old Airport Road",
        "Manipal Hospital - Millers Road",
        "Manipal Hospital - Whitefield",
        "Manipal Hospital - Yeshwanthpur",
        "Manipal Hospital - Sarjapur Road",
        "Aster CMI",
        "Aster RV",
        "Aster Whitefield",
        "Sakra World Hospital, Bangalore",
        "Fortis Hospital BG Road, Bangalore",
        "Apollo Hospital, Bannerghatta, Bangalore",
        "SPARSH Hospital, Infantry Road",
        "SPARSH Hospital, Hennur Road",
        "Sankara Eye Hospital, Bengaluru",
        "St John Hospital, Bangalore",
        "Trilife Hospital, Bangalore",
        "Silverline Diagnostics Kalyan Nagar",
        "M S Ramaiah Memorial Hospital, Bangalore",
        "Narayana Hospital, Bommasandra",
        "Gleneagles Global Hospital, Kengeri, Bangalore",
        "Rela Hospital, Chennai",
        "Rainbow Children's Hospital, Marathahalli",
        "HCG Hospital K R Road, Bangalore",
        "L V Prasad Eye Institute, Hyderabad",
        "NU Hospitals, Rajajinagar",
        "Zion Hospital, Kammanahalli",
        "Cura Hospital, Kammanahalli",
        "KIMS Hospital, Mahadevapura",
        "KARE Prosthetics & Orthotics, Bangalore",
        "Nueclear Diagnostics, Bangalore",
        "BLK-Max Super Specialty Hospital, Delhi",
        "Max Super Speciality Hospital, Saket, Delhi",
        "Artemis Hospital, Delhi",
        "Bhagwan Mahaveer Jain Hospital - Millers Road",
        "AIG Hospitals, Hyderabad"
    ]
    
    try:
        added_count = 0
        with SessionLocal() as s:
            for name in PREDEFINED_HOSPITALS:
                # التحقق من وجود المستشفى
                existing = s.query(Hospital).filter_by(name=name).first()
                if not existing:
                    new_hospital = Hospital(name=name)
                    s.add(new_hospital)
                    added_count += 1
            
            s.commit()
            total = s.query(Hospital).count()
        
        logger.info(f"✅ تم مزامنة {added_count} مستشفى جديد إلى قاعدة البيانات")
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]])
        
        await query.edit_message_text(
            f"✅ **تمت المزامنة بنجاح**\n\n"
            f"➕ **مستشفيات جديدة:** {added_count}\n"
            f"📊 **إجمالي المستشفيات:** {total}",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"❌ خطأ في مزامنة المستشفيات: {e}")
        await query.edit_message_text(
            f"❌ **خطأ في المزامنة:** {str(e)}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]]),
            parse_mode=ParseMode.MARKDOWN
        )


def register(app):
    """تسجيل الهاندلرز"""
    
    # ConversationHandler لإدارة المستشفيات (إضافة وتعديل)
    hospitals_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_select_edit_hospital, pattern="^select_edit_hosp:"),
            CallbackQueryHandler(handle_add_hospital, pattern="^add_hospital$")
        ],
        states={
            "EDIT_HOSPITAL_INPUT": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_hospital_input)
            ],
            "ADD_HOSPITAL_NAME": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_hospital_name_input)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(handle_manage_hospitals, pattern="^manage_hospitals$")
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
        name="hospitals_conv"
    )
    
    # تسجيل الهاندلرز
    app.add_handler(hospitals_conv)
    app.add_handler(CallbackQueryHandler(handle_manage_hospitals, pattern="^manage_hospitals$"))
    app.add_handler(CallbackQueryHandler(handle_view_hospitals, pattern="^view_hospitals$"))
    app.add_handler(CallbackQueryHandler(handle_delete_hospital, pattern="^delete_hospital$"))
    app.add_handler(CallbackQueryHandler(handle_confirm_delete_hospital, pattern="^confirm_delete_hosp:"))
    app.add_handler(CallbackQueryHandler(handle_edit_hospital, pattern="^edit_hospital$"))
    app.add_handler(CallbackQueryHandler(handle_sync_hospitals, pattern="^sync_hospitals$"))

