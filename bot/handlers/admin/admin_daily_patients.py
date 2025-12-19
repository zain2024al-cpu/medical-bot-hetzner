# ================================================
# bot/handlers/admin/admin_daily_patients.py
# 🧍‍♂️ إدارة أسماء المرضى اليومية
# ================================================

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, CommandHandler, filters
)
from telegram.constants import ParseMode
from datetime import datetime, date
from db.session import SessionLocal
from db.models import DailyPatient, Translator, DailySchedule
from bot.shared_auth import is_admin

# حالات المحادثة
SELECT_ACTION, ADD_PATIENTS, CONFIRM_ADD, VIEW_PATIENTS = range(4)

async def start_daily_patients_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بداية إدارة أسماء المرضى اليومية"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("⚠️ هذه الميزة متاحة للإدارة فقط")
        return ConversationHandler.END
    
    today = date.today()
    
    # عرض القائمة الرئيسية
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة أسماء مرضى اليوم", callback_data="dp_add")],
        [InlineKeyboardButton("👀 عرض أسماء مرضى اليوم", callback_data="dp_view")],
        [InlineKeyboardButton("🗑️ حذف جميع أسماء اليوم", callback_data="dp_delete")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="dp_cancel")]
    ])
    
    text = "🧍‍♂️ **إدارة أسماء المرضى اليومية**\n\n"
    text += f"📅 **التاريخ:** {today.strftime('%Y-%m-%d')}\n\n"
    text += "اختر العملية المطلوبة:"
    
    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return SELECT_ACTION

async def handle_action_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار العملية"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "dp_cancel":
        await query.edit_message_text("❌ تم إلغاء العملية")
        return ConversationHandler.END
    
    if query.data == "dp_add":
        # إضافة أسماء جديدة
        text = "➕ **إضافة أسماء مرضى اليوم**\n\n"
        text += "📋 أرسل أسماء المرضى:\n\n"
        text += "**الطريقة 1:** أرسل كل اسم في سطر منفصل\n"
        text += "```\nمحمد أحمد علي\nفاطمة حسن محمد\nأحمد سالم عبدالله\n```\n\n"
        text += "**الطريقة 2:** أرسل الأسماء مفصولة بفاصلة\n"
        text += "```\nمحمد أحمد, فاطمة حسن, أحمد سالم\n```\n\n"
        text += "💡 يمكنك إضافة معلومات إضافية بعد الاسم:\n"
        text += "```\nمحمد أحمد | مستشفى الأطفال | د.أحمد\n```\n\n"
        text += "أو اكتب **'إلغاء'** للإلغاء"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ إلغاء", callback_data="dp_cancel")]
        ])
        
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return ADD_PATIENTS
    
    elif query.data == "dp_view":
        # عرض الأسماء الموجودة
        return await view_daily_patients(query, context)
    
    elif query.data == "dp_delete":
        # تأكيد الحذف
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ نعم، احذف الكل", callback_data="dp_confirm_delete")],
            [InlineKeyboardButton("❌ لا، إلغاء", callback_data="dp_cancel")]
        ])
        
        await query.edit_message_text(
            "⚠️ **تأكيد الحذف**\n\n"
            "هل أنت متأكد من حذف جميع أسماء مرضى اليوم؟\n\n"
            "⚠️ هذا الإجراء لا يمكن التراجع عنه!",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return SELECT_ACTION

async def handle_patients_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال أسماء المرضى"""
    text = update.message.text.strip()
    
    if text.lower() == "إلغاء":
        await update.message.reply_text("❌ تم إلغاء العملية")
        return ConversationHandler.END
    
    # معالجة النص
    patients_data = []
    
    # الطريقة 1: كل اسم في سطر
    if '\n' in text:
        lines = [line.strip() for line in text.split('\n') if line.strip()]
    # الطريقة 2: مفصولة بفاصلة
    elif ',' in text:
        lines = [line.strip() for line in text.split(',') if line.strip()]
    # اسم واحد
    else:
        lines = [text]
    
    # معالجة كل سطر
    for line in lines:
        if '|' in line:
            # يحتوي على معلومات إضافية
            parts = [p.strip() for p in line.split('|')]
            patient_name = parts[0] if len(parts) > 0 else ""
            hospital_name = parts[1] if len(parts) > 1 else None
            doctor_name = parts[2] if len(parts) > 2 else None
        else:
            # اسم فقط
            patient_name = line
            hospital_name = None
            doctor_name = None
        
        if patient_name:
            patients_data.append({
                'name': patient_name,
                'hospital': hospital_name,
                'doctor': doctor_name
            })
    
    if not patients_data:
        await update.message.reply_text(
            "⚠️ لم يتم العثور على أسماء صحيحة.\n\n"
            "حاول مرة أخرى أو اكتب 'إلغاء'"
        )
        return ADD_PATIENTS
    
    # حفظ البيانات مؤقتاً
    context.user_data['patients_data'] = patients_data
    
    # عرض ملخص
    text = "📋 **ملخص الأسماء المُدخلة**\n\n"
    text += f"📊 **العدد الإجمالي:** {len(patients_data)} مريض\n\n"
    
    for i, patient in enumerate(patients_data, 1):
        text += f"{i}. **{patient['name']}**"
        if patient['hospital']:
            text += f" - {patient['hospital']}"
        if patient['doctor']:
            text += f" - {patient['doctor']}"
        text += "\n"
    
    text += "\n\n**هل تريد حفظ هذه الأسماء؟**"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ نعم، احفظ", callback_data="dp_confirm_save")],
        [InlineKeyboardButton("❌ لا، إلغاء", callback_data="dp_cancel")]
    ])
    
    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return CONFIRM_ADD

async def handle_confirm_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد حفظ الأسماء"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "dp_cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ تم إلغاء العملية")
        return ConversationHandler.END
    
    if query.data == "dp_confirm_save":
        patients_data = context.user_data.get('patients_data', [])
        
        if not patients_data:
            await query.edit_message_text("⚠️ لا توجد بيانات لحفظها")
            return ConversationHandler.END
        
        # حفظ في قاعدة البيانات
        today = date.today()
        today_datetime = datetime.combine(today, datetime.min.time())
        
        with SessionLocal() as s:
            saved_count = 0
            
            for patient_data in patients_data:
                # التحقق من عدم وجود نفس الاسم اليوم
                existing = s.query(DailyPatient).filter(
                    DailyPatient.date >= today_datetime,
                    DailyPatient.patient_name == patient_data['name']
                ).first()
                
                if not existing:
                    daily_patient = DailyPatient(
                        date=today_datetime,
                        patient_name=patient_data['name'],
                        hospital_name=patient_data.get('hospital'),
                        doctor_name=patient_data.get('doctor'),
                        created_by=query.from_user.id
                    )
                    s.add(daily_patient)
                    saved_count += 1
            
            s.commit()
        
        # رسالة النجاح
        text = f"✅ **تم حفظ الأسماء بنجاح!**\n\n"
        text += f"📊 **تم حفظ:** {saved_count} اسم\n"
        text += f"📅 **التاريخ:** {today.strftime('%Y-%m-%d')}\n\n"
        text += "الآن المستخدمون يمكنهم اختيار هذه الأسماء عند إضافة تقرير جديد."
        
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
        
        context.user_data.clear()
        return ConversationHandler.END
    
    elif query.data == "dp_confirm_delete":
        # حذف جميع أسماء اليوم
        today = date.today()
        today_datetime = datetime.combine(today, datetime.min.time())
        
        with SessionLocal() as s:
            deleted_count = s.query(DailyPatient).filter(
                DailyPatient.date >= today_datetime
            ).delete()
            s.commit()
        
        await query.edit_message_text(
            f"✅ **تم حذف {deleted_count} اسم من أسماء اليوم**",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return ConversationHandler.END

async def back_to_schedule_from_patients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة لقائمة إدارة الجدول من أسماء المرضى"""
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 رفع جدول جديد", callback_data="upload_schedule")],
        [InlineKeyboardButton("📋 عرض الجدول الحالي", callback_data="view_schedule")],
        [InlineKeyboardButton("📊 تتبع التقارير اليومية", callback_data="track_reports")],
        [InlineKeyboardButton("🔔 إرسال تنبيهات", callback_data="send_notifications")],
        [InlineKeyboardButton("🧍‍♂️ أسماء المرضى اليومية", callback_data="daily_patients")],
        [InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="back_to_main")]
    ])

    await query.edit_message_text(
        "📅 **إدارة جدول المترجمين**\n\n"
        "اختر العملية المطلوبة:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    
    return ConversationHandler.END

async def view_daily_patients(query, context):
    """عرض أسماء مرضى اليوم"""
    today = date.today()
    today_datetime = datetime.combine(today, datetime.min.time())
    
    with SessionLocal() as s:
        patients = s.query(DailyPatient).filter(
            DailyPatient.date >= today_datetime
        ).order_by(DailyPatient.created_at).all()
        
        if not patients:
            await query.edit_message_text(
                f"📋 **لا توجد أسماء مرضى لليوم**\n\n"
                f"📅 التاريخ: {today.strftime('%Y-%m-%d')}\n\n"
                f"استخدم 'إضافة أسماء مرضى اليوم' لإضافة أسماء جديدة.",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        text = f"📋 **أسماء مرضى اليوم**\n\n"
        text += f"📅 التاريخ: {today.strftime('%Y-%m-%d')}\n"
        text += f"📊 العدد: {len(patients)} مريض\n\n"
        
        for i, patient in enumerate(patients, 1):
            text += f"{i}. **{patient.patient_name}**"
            
            if patient.hospital_name:
                text += f" - {patient.hospital_name}"
            if patient.doctor_name:
                text += f" - {patient.doctor_name}"
            
            if patient.is_processed:
                text += " ✅"
            
            text += "\n"
        
        if len(text) > 4000:
            # إذا كان النص طويلاً جداً، قسمه
            parts = []
            current = ""
            for line in text.split('\n'):
                if len(current) + len(line) < 4000:
                    current += line + '\n'
                else:
                    parts.append(current)
                    current = line + '\n'
            if current:
                parts.append(current)
            
            for part in parts:
                await query.message.reply_text(part, parse_mode=ParseMode.MARKDOWN)
            
            await query.edit_message_text("✅ تم عرض القائمة")
        else:
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
        
        return ConversationHandler.END

async def cancel_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء العملية"""
    context.user_data.clear()
    await update.message.reply_text("❌ تم إلغاء العملية")
    return ConversationHandler.END

# ============================================
# معالجات للوصول من إدارة الجدول
# ============================================

async def handle_dp_add_from_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إضافة أسماء من إدارة الجدول"""
    query = update.callback_query
    await query.answer()
    
    # إضافة أسماء جديدة
    text = "➕ **إضافة أسماء مرضى اليوم**\n\n"
    text += "📋 أرسل أسماء المرضى:\n\n"
    text += "**الطريقة 1:** أرسل كل اسم في سطر منفصل\n"
    text += "```\nمحمد أحمد علي\nفاطمة حسن محمد\nأحمد سالم عبدالله\n```\n\n"
    text += "**الطريقة 2:** أرسل الأسماء مفصولة بفاصلة\n"
    text += "```\nمحمد أحمد, فاطمة حسن, أحمد سالم\n```\n\n"
    text += "💡 يمكنك إضافة معلومات إضافية بعد الاسم:\n"
    text += "```\nمحمد أحمد | مستشفى الأطفال | د.أحمد\n```\n\n"
    text += "أو اكتب **'إلغاء'** للإلغاء"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 العودة لإدارة الجدول", callback_data="back_to_schedule")]
    ])
    
    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # حفظ الحالة
    context.user_data['waiting_for_patients'] = True
    context.user_data['from_schedule'] = True

async def handle_dp_view_from_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة عرض أسماء من إدارة الجدول"""
    query = update.callback_query
    await query.answer()
    
    today = date.today()
    today_datetime = datetime.combine(today, datetime.min.time())
    
    with SessionLocal() as s:
        patients = s.query(DailyPatient).filter(
            DailyPatient.date >= today_datetime
        ).order_by(DailyPatient.created_at).all()
        
        if not patients:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 العودة لإدارة الجدول", callback_data="back_to_schedule")]
            ])
            await query.edit_message_text(
                f"📋 **لا توجد أسماء مرضى لليوم**\n\n"
                f"📅 التاريخ: {today.strftime('%Y-%m-%d')}\n\n"
                f"استخدم 'إضافة أسماء مرضى اليوم' لإضافة أسماء جديدة.",
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        text = f"📋 **أسماء مرضى اليوم**\n\n"
        text += f"📅 التاريخ: {today.strftime('%Y-%m-%d')}\n"
        text += f"📊 العدد: {len(patients)} مريض\n\n"
        
        for i, patient in enumerate(patients, 1):
            text += f"{i}. **{patient.patient_name}**"
            
            if patient.hospital_name:
                text += f" - {patient.hospital_name}"
            if patient.doctor_name:
                text += f" - {patient.doctor_name}"
            
            if patient.is_processed:
                text += " ✅"
            
            text += "\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 العودة لإدارة الجدول", callback_data="back_to_schedule")]
        ])
        
        if len(text) > 4000:
            # إذا كان النص طويلاً جداً، قسمه
            parts = []
            current = ""
            for line in text.split('\n'):
                if len(current) + len(line) < 4000:
                    current += line + '\n'
                else:
                    parts.append(current)
                    current = line + '\n'
            if current:
                parts.append(current)
            
            for part in parts[:-1]:
                await query.message.reply_text(part, parse_mode=ParseMode.MARKDOWN)
            
            await query.edit_message_text(parts[-1], reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

async def handle_dp_delete_from_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة حذف أسماء من إدارة الجدول"""
    query = update.callback_query
    await query.answer()
    
    # تأكيد الحذف
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ نعم، احذف الكل", callback_data="dp_confirm_delete_from_schedule")],
        [InlineKeyboardButton("🔙 العودة لإدارة الجدول", callback_data="back_to_schedule")]
    ])
    
    await query.edit_message_text(
        "⚠️ **تأكيد الحذف**\n\n"
        "هل أنت متأكد من حذف جميع أسماء مرضى اليوم؟\n\n"
        "⚠️ هذا الإجراء لا يمكن التراجع عنه!",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_dp_confirm_delete_from_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد حذف أسماء من إدارة الجدول"""
    query = update.callback_query
    await query.answer()
    
    # حذف جميع أسماء اليوم
    today = date.today()
    today_datetime = datetime.combine(today, datetime.min.time())
    
    with SessionLocal() as s:
        deleted_count = s.query(DailyPatient).filter(
            DailyPatient.date >= today_datetime
        ).delete()
        s.commit()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 العودة لإدارة الجدول", callback_data="back_to_schedule")]
    ])
    
    await query.edit_message_text(
        f"✅ **تم حذف {deleted_count} اسم من أسماء اليوم**",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_text_input_for_patients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال نصي لأسماء المرضى (خارج ConversationHandler)"""
    if not context.user_data.get('waiting_for_patients'):
        return
    
    text = update.message.text.strip()
    
    if text.lower() == "إلغاء":
        context.user_data.clear()
        await update.message.reply_text("❌ تم إلغاء العملية")
        return
    
    # معالجة النص
    patients_data = []
    
    # الطريقة 1: كل اسم في سطر
    if '\n' in text:
        lines = [line.strip() for line in text.split('\n') if line.strip()]
    # الطريقة 2: مفصولة بفاصلة
    elif ',' in text:
        lines = [line.strip() for line in text.split(',') if line.strip()]
    # اسم واحد
    else:
        lines = [text]
    
    # معالجة كل سطر
    for line in lines:
        if '|' in line:
            # يحتوي على معلومات إضافية
            parts = [p.strip() for p in line.split('|')]
            patient_name = parts[0] if len(parts) > 0 else ""
            hospital_name = parts[1] if len(parts) > 1 else None
            doctor_name = parts[2] if len(parts) > 2 else None
        else:
            # اسم فقط
            patient_name = line
            hospital_name = None
            doctor_name = None
        
        if patient_name:
            patients_data.append({
                'name': patient_name,
                'hospital': hospital_name,
                'doctor': doctor_name
            })
    
    if not patients_data:
        await update.message.reply_text(
            "⚠️ لم يتم العثور على أسماء صحيحة.\n\n"
            "حاول مرة أخرى أو اكتب 'إلغاء'"
        )
        return
    
    # عرض ملخص
    summary_text = "📋 **ملخص الأسماء المُدخلة**\n\n"
    summary_text += f"📊 **العدد الإجمالي:** {len(patients_data)} مريض\n\n"
    
    for i, patient in enumerate(patients_data, 1):
        summary_text += f"{i}. **{patient['name']}**"
        if patient['hospital']:
            summary_text += f" - {patient['hospital']}"
        if patient['doctor']:
            summary_text += f" - {patient['doctor']}"
        summary_text += "\n"
    
    summary_text += "\n\n**هل تريد حفظ هذه الأسماء؟**"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ نعم، احفظ", callback_data="dp_save_from_schedule")],
        [InlineKeyboardButton("🔙 العودة لإدارة الجدول", callback_data="back_to_schedule")]
    ])
    
    await update.message.reply_text(
        summary_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # حفظ البيانات
    context.user_data['patients_data'] = patients_data
    context.user_data['waiting_for_patients'] = False

async def handle_dp_save_from_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حفظ الأسماء المدخلة"""
    query = update.callback_query
    await query.answer()
    
    patients_data = context.user_data.get('patients_data', [])
    
    if not patients_data:
        await query.edit_message_text("⚠️ لا توجد بيانات لحفظها")
        context.user_data.clear()
        return
    
    # حفظ في قاعدة البيانات
    today = date.today()
    today_datetime = datetime.combine(today, datetime.min.time())
    
    with SessionLocal() as s:
        saved_count = 0
        
        for patient_data in patients_data:
            # التحقق من عدم وجود نفس الاسم اليوم
            existing = s.query(DailyPatient).filter(
                DailyPatient.date >= today_datetime,
                DailyPatient.patient_name == patient_data['name']
            ).first()
            
            if not existing:
                daily_patient = DailyPatient(
                    date=today_datetime,
                    patient_name=patient_data['name'],
                    hospital_name=patient_data.get('hospital'),
                    doctor_name=patient_data.get('doctor'),
                    created_by=query.from_user.id
                )
                s.add(daily_patient)
                saved_count += 1
        
        s.commit()
    
    # رسالة النجاح
    text = f"✅ **تم حفظ الأسماء بنجاح!**\n\n"
    text += f"📊 **تم حفظ:** {saved_count} اسم\n"
    text += f"📅 **التاريخ:** {today.strftime('%Y-%m-%d')}\n\n"
    text += "الآن المستخدمون يمكنهم اختيار هذه الأسماء عند إضافة تقرير جديد."
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 العودة لإدارة الجدول", callback_data="back_to_schedule")]
    ])
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    
    context.user_data.clear()

def register(app):
    """تسجيل معالج إدارة أسماء المرضى اليومية"""
    
    # معالجات منفصلة للوصول من إدارة الجدول (خارج ConversationHandler)
    from bot.shared_auth import is_admin
    
    # معالج الإضافة
    app.add_handler(CallbackQueryHandler(
        handle_dp_add_from_schedule, 
        pattern="^dp_add_from_schedule$"
    ))
    
    # معالج العرض
    app.add_handler(CallbackQueryHandler(
        handle_dp_view_from_schedule, 
        pattern="^dp_view_from_schedule$"
    ))
    
    # معالج الحذف
    app.add_handler(CallbackQueryHandler(
        handle_dp_delete_from_schedule, 
        pattern="^dp_delete_from_schedule$"
    ))
    
    # معالج تأكيد الحذف
    app.add_handler(CallbackQueryHandler(
        handle_dp_confirm_delete_from_schedule, 
        pattern="^dp_confirm_delete_from_schedule$"
    ))
    
    # معالج الحفظ
    app.add_handler(CallbackQueryHandler(
        handle_dp_save_from_schedule, 
        pattern="^dp_save_from_schedule$"
    ))
    
    
    # معالج إدخال النص (منفصل عن ConversationHandler)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(📋 أسماء المرضى اليومية|❌ إلغاء العملية الحالية)$"),
        handle_text_input_for_patients
    ), group=10)
    
    # ConversationHandler الأصلي للوصول المباشر
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📋 أسماء المرضى اليومية$"), start_daily_patients_management),
            CallbackQueryHandler(handle_action_selection, pattern="^dp_")
        ],
        states={
            SELECT_ACTION: [
                CallbackQueryHandler(handle_action_selection, pattern="^dp_"),
                CallbackQueryHandler(handle_confirm_add, pattern="^dp_confirm_delete$")
            ],
            ADD_PATIENTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_patients_input),
                CallbackQueryHandler(handle_action_selection, pattern="^dp_cancel$")
            ],
            CONFIRM_ADD: [
                CallbackQueryHandler(handle_confirm_add, pattern="^dp_")
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ إلغاء العملية الحالية$"), cancel_management),
            CallbackQueryHandler(handle_action_selection, pattern="^dp_cancel$"),
            CallbackQueryHandler(back_to_schedule_from_patients, pattern="^back_to_schedule$")
        ],
        allow_reentry=True,
        per_chat=True,
        per_user=True,
        per_message=False,
    )
    
    app.add_handler(conv_handler)


