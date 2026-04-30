# ================================================
# bot/handlers/admin/admin_hospitals_management.py
# 🔹 إدارة المستشفيات
# ================================================

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode
import logging
from db.session import SessionLocal, get_db
from db.models import Hospital
from bot.shared_auth import is_admin
from services.hospitals_service import (
    add_hospital as service_add_hospital,
    delete_hospital as service_delete_hospital,
    update_hospital as service_update_hospital,
    reload_hospitals as service_reload_hospitals
)

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
        with get_db() as s:
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
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_schedule")]
    ])
    
    await query.edit_message_text(
        f"🏥 **إدارة المستشفيات**\n\n"
        f"📊 **عدد المستشفيات:** {hospitals_count}\n\n"
        f"اختر العملية:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_view_hospitals(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    """عرض جميع المستشفيات مع صفحات"""
    query = update.callback_query
    await query.answer()
    
    # استخراج رقم الصفحة من callback_data إذا موجود
    if query.data.startswith("view_hospitals_page:"):
        page = int(query.data.split(":")[1])
    
    # قراءة المستشفيات من قاعدة البيانات
    try:
        with get_db() as s:
            hospitals = s.query(Hospital).order_by(Hospital.name).all()
            names = [h.name for h in hospitals if h.name]
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل المستشفيات: {e}")
        names = []
    
    if not names:
        text = "📋 **قائمة المستشفيات**\n\n⚠️ لا توجد مستشفيات مسجلة\n\nاستخدم 'مزامنة من القائمة الثابتة' لإضافة المستشفيات الافتراضية"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]
        ])
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # ترتيب المستشفيات أبجدياً
        names_sorted = sorted(names, key=lambda x: x.strip())
        
        # إعدادات الصفحات
        items_per_page = 15
        total = len(names_sorted)
        total_pages = max(1, (total + items_per_page - 1) // items_per_page)
        page = max(0, min(page, total_pages - 1))
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, total)
        
        text = f"📋 **قائمة المستشفيات**\n\n"
        text += f"📊 **العدد:** {total}\n"
        text += f"📄 **الصفحة:** {page + 1} من {total_pages}\n\n"
        
        for i in range(start_idx, end_idx):
            text += f"{i + 1}. 🏥 {names_sorted[i]}\n"
        
        # أزرار التنقل
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"view_hospitals_page:{page - 1}"))
        nav_buttons.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("➡️ التالي", callback_data=f"view_hospitals_page:{page + 1}"))
        
        keyboard = []
        if nav_buttons:
            keyboard.append(nav_buttons)
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_add_hospital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء إضافة مستشفى جديد"""
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_hospital_input")]
    ])

    await query.edit_message_text(
        "➕ **إضافة مستشفى جديد**\n\n"
        "📝 اكتب اسم المستشفى:\n"
        "مثال: Manipal Hospital - Whitefield",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return "ADD_HOSPITAL_NAME"

async def handle_hospital_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم المستشفى الجديد"""
    name = update.message.text.strip()
    
    if not name or len(name) < 3:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_hospital_input")]
        ])
        await update.message.reply_text(
            "⚠️ **خطأ:** الاسم قصير جداً\n\n"
            "يرجى إدخال اسم صحيح (3 حروف على الأقل):",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return "ADD_HOSPITAL_NAME"
    
    # إضافة المستشفى لقاعدة البيانات
    try:
        with get_db() as s:
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
            # get_db() context manager يقوم بالـ commit تلقائياً عند الخروج
            logger.info(f"✅ تم إضافة المستشفى '{name}' إلى قاعدة البيانات")

        # مزامنة مع خدمة المستشفيات (ملف JSON) حتى يظهر في واجهة المستخدم
        try:
            service_add_hospital(name)
            logger.info(f"✅ تم مزامنة المستشفى '{name}' مع خدمة المستشفيات")
        except Exception as sync_err:
            logger.warning(f"⚠️ فشل مزامنة المستشفى مع خدمة المستشفيات: {sync_err}")

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
        import traceback
        traceback.print_exc()
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
        with get_db() as s:
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
    
    # حفظ المستشفيات في context
    hospitals_dict = {h.id: h.name for h in hospitals}
    context.user_data['delete_hospitals_dict'] = hospitals_dict
    
    # استخراج رقم الصفحة
    page = 0
    if query.data.startswith("delete_hosp_page:"):
        page = int(query.data.split(":")[1])
    
    # إعدادات الصفحات
    hospitals_list = list(hospitals)
    items_per_page = 10
    total = len(hospitals_list)
    total_pages = max(1, (total + items_per_page - 1) // items_per_page)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total)
    
    # عرض المستشفيات مع أزرار حذف
    keyboard = []
    for i in range(start_idx, end_idx):
        hospital = hospitals_list[i]
        display_name = hospital.name[:30] + "..." if len(hospital.name) > 30 else hospital.name
        keyboard.append([InlineKeyboardButton(
            f"🗑️ {display_name}",
            callback_data=f"confirm_delete_hosp:{hospital.id}"  # ID فقط
        )])
    
    # أزرار التنقل
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"delete_hosp_page:{page - 1}"))
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("➡️ التالي", callback_data=f"delete_hosp_page:{page + 1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")])
    
    await query.edit_message_text(
        f"🗑️ **حذف مستشفى**\n\n"
        f"📊 **العدد:** {total}\n"
        f"📄 **الصفحة:** {page + 1} من {total_pages}\n\n"
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
    if len(parts) < 2:
        await query.edit_message_text("❌ خطأ: طلب حذف غير صالح.")
        return
    
    try:
        hospital_id = int(parts[1])
    except ValueError:
        await query.edit_message_text("❌ خطأ: معرف المستشفى غير صالح.")
        return
    
    # حذف من قاعدة البيانات
    try:
        session = SessionLocal()
        try:
            hospital = session.query(Hospital).filter_by(id=hospital_id).first()
            if hospital:
                full_name = hospital.name
                session.delete(hospital)
                session.commit()
                logger.info(f"✅ تم حذف المستشفى '{full_name}' من قاعدة البيانات (ID: {hospital_id})")

                # مزامنة الحذف مع خدمة المستشفيات (ملف JSON)
                try:
                    service_delete_hospital(full_name)
                    logger.info(f"✅ تم مزامنة حذف المستشفى '{full_name}' مع خدمة المستشفيات")
                except Exception as sync_err:
                    logger.warning(f"⚠️ فشل مزامنة حذف المستشفى: {sync_err}")

                # عد المستشفيات المتبقية
                remaining = session.query(Hospital).count()
                
                await query.edit_message_text(
                    f"✅ **تم حذف المستشفى:** {full_name}\n\n"
                    f"📊 **عدد المستشفيات المتبقية:** {remaining}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]]),
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await query.edit_message_text(
                    f"⚠️ **المستشفى غير موجود (ID: {hospital_id})**",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")]]),
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
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
        with get_db() as s:
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
    
    # استخراج رقم الصفحة
    page = 0
    if query.data.startswith("edit_hosp_page:"):
        page = int(query.data.split(":")[1])
    
    # إعدادات الصفحات
    hospitals_list = list(hospitals)
    items_per_page = 10
    total = len(hospitals_list)
    total_pages = max(1, (total + items_per_page - 1) // items_per_page)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total)
    
    # عرض المستشفيات مع أزرار تعديل
    keyboard = []
    for i in range(start_idx, end_idx):
        hospital = hospitals_list[i]
        display_name = hospital.name[:30] + "..." if len(hospital.name) > 30 else hospital.name
        keyboard.append([InlineKeyboardButton(
            f"✏️ {display_name}",
            callback_data=f"select_edit_hosp:{hospital.id}"  # ID فقط
        )])
    
    # أزرار التنقل
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"edit_hosp_page:{page - 1}"))
    if total_pages > 1:
        nav_buttons.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("➡️ التالي", callback_data=f"edit_hosp_page:{page + 1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="manage_hospitals")])
    
    await query.edit_message_text(
        f"✏️ **تعديل مستشفى**\n\n"
        f"📊 **العدد:** {total}\n"
        f"📄 **الصفحة:** {page + 1} من {total_pages}\n\n"
        f"اختر المستشفى المراد تعديله:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_select_edit_hospital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار مستشفى للتعديل"""
    query = update.callback_query
    await query.answer()
    
    # استخراج البيانات
    parts = query.data.split(':')
    if len(parts) < 2:
        await query.edit_message_text("❌ خطأ: طلب تعديل غير صالح.")
        return ConversationHandler.END
    
    try:
        hospital_id = int(parts[1])
    except ValueError:
        await query.edit_message_text("❌ خطأ: معرف المستشفى غير صالح.")
        return ConversationHandler.END
    
    # جلب الاسم الكامل من قاعدة البيانات
    try:
        session = SessionLocal()
        try:
            hospital = session.query(Hospital).filter_by(id=hospital_id).first()
            if hospital:
                old_name = hospital.name
            else:
                await query.edit_message_text("❌ خطأ: المستشفى غير موجود.")
                return ConversationHandler.END
        finally:
            session.close()
    except Exception as e:
        logger.error(f"❌ خطأ في جلب المستشفى: {e}")
        await query.edit_message_text("❌ خطأ في جلب بيانات المستشفى.")
        return ConversationHandler.END
    
    # حفظ في context
    context.user_data['edit_hospital_id'] = hospital_id
    context.user_data['edit_hospital_old_name'] = old_name
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_hospital_input")]
    ])

    await query.edit_message_text(
        f"✏️ **تعديل اسم المستشفى**\n\n"
        f"🏥 **الاسم الحالي:** {old_name}\n\n"
        f"اكتب الاسم الجديد:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

    return "EDIT_HOSPITAL_INPUT"

async def handle_edit_hospital_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال الاسم الجديد للمستشفى"""
    new_name = update.message.text.strip()
    
    if not new_name or len(new_name) < 3:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_hospital_input")]
        ])
        await update.message.reply_text(
            "⚠️ **خطأ:** الاسم قصير جداً\n\n"
            "يرجى إدخال اسم صحيح (3 حروف على الأقل):",
            reply_markup=keyboard,
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
        with get_db() as s:
            hospital = s.query(Hospital).filter_by(id=hospital_id).first()
            if hospital:
                hospital.name = new_name
                # get_db() context manager يقوم بالـ commit تلقائياً عند الخروج
                logger.info(f"✅ تم تعديل اسم المستشفى من '{old_name}' إلى '{new_name}'")

        # مزامنة التعديل مع خدمة المستشفيات (ملف JSON)
        try:
            service_update_hospital(old_name, new_name)
            logger.info(f"✅ تم مزامنة تعديل المستشفى مع خدمة المستشفيات")
        except Exception as sync_err:
            logger.warning(f"⚠️ فشل مزامنة تعديل المستشفى: {sync_err}")

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
        import traceback
        traceback.print_exc()
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
        with get_db() as s:
            for name in PREDEFINED_HOSPITALS:
                # التحقق من وجود المستشفى
                existing = s.query(Hospital).filter_by(name=name).first()
                if not existing:
                    new_hospital = Hospital(name=name)
                    s.add(new_hospital)
                    added_count += 1
            
            # get_db() context manager يقوم بالـ commit تلقائياً عند الخروج
            total = s.query(Hospital).count()

        # إعادة تحميل خدمة المستشفيات لتشمل المستشفيات الجديدة في ملف JSON
        try:
            for name in PREDEFINED_HOSPITALS:
                service_add_hospital(name)
            service_reload_hospitals()
            logger.info("✅ تم مزامنة المستشفيات مع خدمة المستشفيات (JSON)")
        except Exception as sync_err:
            logger.warning(f"⚠️ فشل مزامنة المستشفيات مع خدمة المستشفيات: {sync_err}")

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


async def handle_cancel_hospital_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء عملية إضافة/تعديل مستشفى"""
    query = update.callback_query
    await query.answer()

    # مسح البيانات المؤقتة
    context.user_data.pop('edit_hospital_id', None)
    context.user_data.pop('edit_hospital_old_name', None)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة مستشفى جديد", callback_data="add_hospital")],
        [InlineKeyboardButton("📋 عرض جميع المستشفيات", callback_data="view_hospitals")],
        [InlineKeyboardButton("✏️ تعديل مستشفى", callback_data="edit_hospital")],
        [InlineKeyboardButton("🗑️ حذف مستشفى", callback_data="delete_hospital")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_schedule")]
    ])

    try:
        with get_db() as s:
            hospitals_count = s.query(Hospital).count()
    except Exception:
        hospitals_count = 0

    await query.edit_message_text(
        f"❌ **تم إلغاء العملية**\n\n"
        f"🏥 **إدارة المستشفيات**\n"
        f"📊 **عدد المستشفيات:** {hospitals_count}\n\n"
        f"اختر العملية:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END


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
                CallbackQueryHandler(handle_cancel_hospital_input, pattern="^cancel_hospital_input$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_hospital_input)
            ],
            "ADD_HOSPITAL_NAME": [
                CallbackQueryHandler(handle_cancel_hospital_input, pattern="^cancel_hospital_input$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_hospital_name_input)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(handle_cancel_hospital_input, pattern="^cancel_hospital_input$"),
            CallbackQueryHandler(handle_manage_hospitals, pattern="^manage_hospitals$")
        ],
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=True,
        name="hospitals_conv"
    )
    
    # تسجيل الهاندلرز
    app.add_handler(hospitals_conv)
    app.add_handler(CallbackQueryHandler(handle_manage_hospitals, pattern="^manage_hospitals$"))
    app.add_handler(CallbackQueryHandler(handle_view_hospitals, pattern="^view_hospitals$"))
    app.add_handler(CallbackQueryHandler(handle_view_hospitals, pattern="^view_hospitals_page:"))  # صفحات المستشفيات
    app.add_handler(CallbackQueryHandler(handle_delete_hospital, pattern="^delete_hospital$"))
    app.add_handler(CallbackQueryHandler(handle_delete_hospital, pattern="^delete_hosp_page:"))  # صفحات الحذف
    app.add_handler(CallbackQueryHandler(handle_confirm_delete_hospital, pattern="^confirm_delete_hosp:\\d+$"))  # ID فقط
    app.add_handler(CallbackQueryHandler(handle_edit_hospital, pattern="^edit_hospital$"))
    app.add_handler(CallbackQueryHandler(handle_edit_hospital, pattern="^edit_hosp_page:"))  # صفحات التعديل
    # ⚠️ تم تعطيل مزامنة القائمة الثابتة لضمان أن DB هي المصدر الوحيد للحقيقة.

