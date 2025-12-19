from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from db.models import Report, Patient, InitialCase
from services.pdf_generator import generate_pdf_report
from bot.shared_utils import format_datetime, parse_date
from datetime import datetime


# ================================================
# 🎨 الحالة الأولى المحسّنة — إدخال بيانات التقرير الأولية
# ================================================

ASK_PATIENT_NAME, ASK_AGE, ASK_MAIN_COMPLAINT, ASK_CURRENT_HISTORY, ASK_NOTES, ASK_PREVIOUS_PROCEDURES, ASK_HAS_TESTS, ASK_TEST_DETAILS, CONFIRM_SAVE = range(9)

# دالة مساعدة للأزرار الأساسية
def _get_navigation_buttons(show_back=False, show_skip=False, show_preview=False):
    """إنشاء أزرار التنقل الأساسية"""
    buttons = []
    
    row1 = []
    if show_back:
        row1.append(InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"))
    if show_skip:
        row1.append(InlineKeyboardButton("⏭️ تخطي", callback_data="nav:skip"))
    if row1:
        buttons.append(row1)
    
    if show_preview:
        buttons.append([InlineKeyboardButton("👁️ مراجعة المُدخل", callback_data="nav:preview")])
    
    buttons.append([InlineKeyboardButton("❌ إلغاء العملية", callback_data="nav:cancel")])
    
    return InlineKeyboardMarkup(buttons)

async def start_add_case(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # التحقق من أن المستخدم أدمن
    from bot.shared_auth import is_admin
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
        return ConversationHandler.END

    context.user_data.clear()
    
    # بدء مباشر - بدون مقدمات
    first_question = """
📝 **الخطوة 1 من 7**

👤 **اسم المريض:**

💡 مثال: محمد أحمد علي
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])
    
    await update.message.reply_text(first_question, reply_markup=keyboard)
    return ASK_PATIENT_NAME

async def ask_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() in ['إلغاء', 'الغاء', 'cancel']:
        return await cancel(update, context)
    
    context.user_data["patient_name"] = text
    
    age_text = f"""
✅ **تم حفظ:** {text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 **الخطوة 2 من 7**

🎂 **عمر المريض:**
أدخل عمر المريض بالسنوات

💡 مثال: 45 أو 3 سنوات
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="back:patient_name")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])
    
    await update.message.reply_text(age_text, reply_markup=keyboard)
    return ASK_AGE

async def ask_main_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() in ['إلغاء', 'الغاء', 'cancel']:
        return await cancel(update, context)
    
    context.user_data["patient_age"] = text
    
    complaint_text = f"""
✅ **تم حفظ:** {text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 **الخطوة 3 من 7**

🩺 **الشكوى الرئيسية:**
ما هو السبب الرئيسي للزيارة؟

💡 مثال: ألم في الصدر، صداع مستمر، ضيق تنفس
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="back:age")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])
    
    await update.message.reply_text(complaint_text, reply_markup=keyboard)
    return ASK_MAIN_COMPLAINT

async def ask_current_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() in ['إلغاء', 'الغاء', 'cancel']:
        return await cancel(update, context)
    
    context.user_data["main_complaint"] = text
    
    history_text = f"""
✅ **تم حفظ:** {text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 **الخطوة 4 من 7**

📋 **القصة المرضية الحالية:**
تفاصيل الحالة والأعراض الحالية

💡 مثال: بدأت الأعراض منذ أسبوعين، ألم متقطع يزداد ليلاً...
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="back:complaint")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])
    
    await update.message.reply_text(history_text, reply_markup=keyboard)
    return ASK_CURRENT_HISTORY

async def ask_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() in ['إلغاء', 'الغاء', 'cancel']:
        return await cancel(update, context)
    
    context.user_data["current_history"] = text
    
    notes_text = """
✅ **تم حفظ القصة المرضية**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 **الخطوة 5 من 7** (اختياري)

📝 **ملاحظات إضافية:**
أي ملاحظات مهمة أخرى؟

💡 مثال: حساسية من البنسلين، مريض سكري...
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="back:history"), InlineKeyboardButton("⏭️ تخطي", callback_data="skip:notes")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])
    
    await update.message.reply_text(notes_text, reply_markup=keyboard)
    return ASK_NOTES

async def handle_skip_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة تخطي الملاحظات"""
    query = update.callback_query
    await query.answer()
    
    context.user_data["notes"] = "لا توجد ملاحظات"
    
    procedures_text = """
✅ **تم التخطي**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 **الخطوة 6 من 7** (اختياري)

🔬 **الإجراءات السابقة:**
هل تمت للمريض إجراءات أو عمليات سابقة؟

💡 مثال: عملية قلب مفتوح 2020، منظار 2023...
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data="back:notes"), InlineKeyboardButton("⏭️ تخطي", callback_data="skip:procedures")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])
    
    await query.edit_message_text(procedures_text, reply_markup=keyboard)
    return ASK_PREVIOUS_PROCEDURES

async def ask_previous_procedures(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """طلب الإجراءات السابقة بعد حفظ الملاحظات"""
    text = update.message.text.strip()
    if text.lower() in ['إلغاء', 'الغاء', 'cancel']:
        return await cancel(update, context)
    
    # حفظ الملاحظات بشكل صحيح
    context.user_data["notes"] = text
    
    procedures_text = f"""
✅ **تم حفظ الملاحظات**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 **الخطوة 6 من 7** (اختياري)

🔬 **الإجراءات السابقة:**
هل تمت للمريض إجراءات أو عمليات سابقة؟

💡 مثال: عملية قلب مفتوح 2020، منظار 2023...
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💡 اقتراحات (عربي/إنجليزي)", callback_data="proc:suggestions")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back:notes"), InlineKeyboardButton("⏭️ تخطي", callback_data="skip:procedures")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])
    
    await update.message.reply_text(procedures_text, reply_markup=keyboard)
    return ASK_PREVIOUS_PROCEDURES

async def handle_skip_procedures(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة تخطي الإجراءات السابقة"""
    query = update.callback_query
    await query.answer()
    
    context.user_data["previous_procedures"] = "لا توجد إجراءات سابقة"
    
    tests_text = """
✅ **تم التخطي**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 **الخطوة 7 من 7** (اختياري)

📊 **الفحوصات والأشعة:**
هل يوجد مع المريض أشعة أو تحاليل سابقة؟
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ نعم، يوجد", callback_data="has_tests:yes"), InlineKeyboardButton("❌ لا يوجد", callback_data="has_tests:no")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back:procedures")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])
    
    await query.edit_message_text(tests_text, reply_markup=keyboard)
    return ASK_HAS_TESTS

async def show_procedure_suggestions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض اقتراحات العمليات والإجراءات"""
    query = update.callback_query
    await query.answer()
    
    # استيراد الاقتراحات
    from services.medical_procedures_suggestions import MEDICAL_PROCEDURES
    
    # عرض أول 15 اقتراح
    suggestions = MEDICAL_PROCEDURES[:15]
    
    keyboard = []
    for proc in suggestions:
        # تقصير النص للعرض
        display_text = proc if len(proc) <= 50 else proc[:47] + "..."
        keyboard.append([InlineKeyboardButton(
            f"💉 {display_text}", 
            callback_data=f"proc_select:{proc[:40]}"
        )])
    
    # أزرار إضافية
    keyboard.append([
        InlineKeyboardButton("🔍 بحث", callback_data="proc:search"),
        InlineKeyboardButton("✏️ إدخال يدوي", callback_data="proc:manual")
    ])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="proc:back")])
    
    suggestions_text = """
💡 **اقتراحات الإجراءات والعمليات**

اختر من القائمة أو ابحث:
"""
    
    await query.edit_message_text(
        suggestions_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ASK_PREVIOUS_PROCEDURES

async def handle_procedure_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار إجراء من الاقتراحات"""
    query = update.callback_query
    await query.answer()
    
    # استخراج الإجراء المختار
    selected = query.data.replace("proc_select:", "")
    
    # البحث عن الإجراء الكامل
    from services.medical_procedures_suggestions import MEDICAL_PROCEDURES
    full_procedure = None
    for proc in MEDICAL_PROCEDURES:
        if proc.startswith(selected):
            full_procedure = proc
            break
    
    if not full_procedure:
        full_procedure = selected
    
    # حفظ الإجراء
    context.user_data["previous_procedures"] = full_procedure
    
    confirmation_text = f"""
✅ **تم الاختيار:**

{full_procedure}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 **الخطوة 7 من 7** (اختياري)

📊 **الفحوصات والأشعة:**
هل يوجد مع المريض أشعة أو تحاليل سابقة؟
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ نعم، يوجد", callback_data="has_tests:yes"), InlineKeyboardButton("❌ لا يوجد", callback_data="has_tests:no")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back:procedures")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])
    
    await query.edit_message_text(confirmation_text, reply_markup=keyboard)
    return ASK_HAS_TESTS

async def handle_procedure_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """طلب البحث في الإجراءات"""
    query = update.callback_query
    await query.answer()
    
    search_text = """
🔍 **بحث في الإجراءات**

أدخل كلمة البحث (عربي أو إنجليزي):

💡 مثال: "ECG" أو "قلب" أو "تحاليل"
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع للاقتراحات", callback_data="proc:suggestions")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])
    
    await query.edit_message_text(search_text, reply_markup=keyboard, parse_mode="Markdown")
    
    # تعيين حالة بحث
    context.user_data["searching_procedures"] = True
    return ASK_PREVIOUS_PROCEDURES

async def handle_procedure_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة نتائج البحث"""
    if not context.user_data.get("searching_procedures"):
        return await ask_has_tests(update, context)
    
    search_query = update.message.text.strip()
    context.user_data["searching_procedures"] = False
    
    # البحث
    from services.medical_procedures_suggestions import get_procedure_suggestions
    results = get_procedure_suggestions(search_query)
    
    if not results:
        no_results_text = f"""
❌ **لم يتم العثور على نتائج لـ:** {search_query}

جرّب كلمة أخرى أو أدخل يدوياً:
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💡 عرض الاقتراحات", callback_data="proc:suggestions")],
            [InlineKeyboardButton("✏️ إدخال يدوي", callback_data="proc:manual")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ])
        await update.message.reply_text(no_results_text, reply_markup=keyboard, parse_mode="Markdown")
        return ASK_PREVIOUS_PROCEDURES
    
    # عرض النتائج
    keyboard = []
    for proc in results[:10]:
        display_text = proc if len(proc) <= 50 else proc[:47] + "..."
        keyboard.append([InlineKeyboardButton(
            f"💉 {display_text}",
            callback_data=f"proc_select:{proc[:40]}"
        )])
    
    keyboard.append([
        InlineKeyboardButton("🔍 بحث جديد", callback_data="proc:search"),
        InlineKeyboardButton("✏️ يدوي", callback_data="proc:manual")
    ])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="proc:back")])
    
    results_text = f"""
✅ **نتائج البحث عن:** {search_query}

وُجد {len(results)} نتيجة:
"""
    
    await update.message.reply_text(
        results_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ASK_PREVIOUS_PROCEDURES

async def handle_procedure_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إدخال يدوي للإجراء"""
    query = update.callback_query
    await query.answer()
    
    manual_text = """
✏️ **إدخال يدوي**

أدخل اسم الإجراء أو العملية (عربي أو إنجليزي):

💡 مثال: عملية قلب مفتوح 2020
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💡 رجوع للاقتراحات", callback_data="proc:suggestions")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])
    
    await query.edit_message_text(manual_text, reply_markup=keyboard, parse_mode="Markdown")
    return ASK_PREVIOUS_PROCEDURES

async def handle_procedure_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرجوع من الاقتراحات"""
    query = update.callback_query
    await query.answer()
    
    procedures_text = """
📝 **الخطوة 6 من 7** (اختياري)

🔬 **الإجراءات السابقة:**
هل تمت للمريض إجراءات أو عمليات سابقة؟

💡 مثال: عملية قلب مفتوح 2020، منظار 2023...
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💡 اقتراحات (عربي/إنجليزي)", callback_data="proc:suggestions")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back:notes"), InlineKeyboardButton("⏭️ تخطي", callback_data="skip:procedures")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])
    
    await query.edit_message_text(procedures_text, reply_markup=keyboard, parse_mode="Markdown")
    return ASK_PREVIOUS_PROCEDURES

async def ask_has_tests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """طلب الفحوصات والأشعة بعد حفظ الإجراءات السابقة"""
    text = update.message.text.strip()
    if text.lower() in ['إلغاء', 'الغاء', 'cancel']:
        return await cancel(update, context)
    
    # حفظ الإجراءات السابقة بشكل صحيح
    context.user_data["previous_procedures"] = text
    
    tests_text = f"""
✅ **تم حفظ الإجراءات السابقة**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 **الخطوة 7 من 7** (اختياري)

📊 **الفحوصات والأشعة:**
هل يوجد مع المريض أشعة أو تحاليل سابقة؟
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ نعم، يوجد", callback_data="has_tests:yes"), InlineKeyboardButton("❌ لا يوجد", callback_data="has_tests:no")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back:procedures")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
    ])
    
    await update.message.reply_text(tests_text, reply_markup=keyboard)
    return ASK_HAS_TESTS

async def handle_tests_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    choice = query.data.split(":")[1]
    
    if choice == "yes":
        tests_details_text = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **تفاصيل الفحوصات والأشعة:**

أدخل تفاصيل الأشعة والتحاليل السابقة

💡 مثال:
• أشعة صدر 2024/10/15: طبيعية
• تحليل دم شامل: نسبة السكر 180
• أشعة مقطعية للرأس: سليمة
"""
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="back:has_tests")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ])
        
        await query.edit_message_text(tests_details_text, reply_markup=keyboard)
        return ASK_TEST_DETAILS
    else:
        # إذا لم تكن هناك فحوصات، انتقل مباشرة للتأكيد
        context.user_data["test_details"] = "لا توجد فحوصات سابقة"
        await query.edit_message_text("⏳ **جاري إعداد الملخص...**")
        return await show_summary(update, context)

async def ask_test_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() in ['إلغاء', 'الغاء', 'cancel']:
        return await cancel(update, context)
    
    context.user_data["test_details"] = text
    await update.message.reply_text("⏳ **جاري إعداد الملخص...**")
    
    # عرض ملخص البيانات - منسق بشكل احترافي
    data = context.user_data
    summary = f"""
╔══════════════════════════════════╗
║     📋 ملخص الحالة الأولية      ║
╚══════════════════════════════════╝

**معلومات المريض:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 **الاسم:** {data.get('patient_name', 'غير محدد')}
🎂 **العمر:** {data.get('patient_age', 'غير محدد')} سنة

**التفاصيل الطبية:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🩺 **الشكوى الرئيسية:**
   {data.get('main_complaint', 'غير محدد')}

📋 **القصة المرضية:**
   {data.get('current_history', 'غير محدد')}

📝 **الملاحظات:**
   {data.get('notes', 'لا توجد')}

🔬 **الإجراءات السابقة:**
   {data.get('previous_procedures', 'لا توجد')}

📊 **الفحوصات والأشعة:**
   {data.get('test_details', 'لا توجد')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 **التاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

**هل تريد حفظ هذه الحالة؟**
"""
    
    # أزرار احترافية مع زر رجوع
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💾 حفظ وإرسال للجميع", callback_data="action:save")],
        [InlineKeyboardButton("🔙 رجوع للتعديل", callback_data="back:has_tests")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="action:cancel")]
    ])
    
    await update.message.reply_text(summary, reply_markup=keyboard, parse_mode="Markdown")
    return CONFIRM_SAVE

async def show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # عرض ملخص البيانات - احترافي
    data = context.user_data
    summary = f"""
╔══════════════════════════════════╗
║     📋 ملخص الحالة الأولية      ║
╚══════════════════════════════════╝

**معلومات المريض:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 **الاسم:** {data.get('patient_name', 'غير محدد')}
🎂 **العمر:** {data.get('patient_age', 'غير محدد')} سنة

**التفاصيل الطبية:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🩺 **الشكوى الرئيسية:**
   {data.get('main_complaint', 'غير محدد')}

📋 **القصة المرضية:**
   {data.get('current_history', 'غير محدد')}

📝 **الملاحظات:**
   {data.get('notes', 'لا توجد')}

🔬 **الإجراءات السابقة:**
   {data.get('previous_procedures', 'لا توجد')}

📊 **الفحوصات والأشعة:**
   {data.get('test_details', 'لا توجد')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 **التاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

**هل تريد حفظ هذه الحالة؟**
"""
    
    # أزرار التأكيد احترافية مع زر رجوع
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💾 حفظ وإرسال للجميع", callback_data="action:save")],
        [InlineKeyboardButton("🔙 رجوع للتعديل", callback_data="back:has_tests")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="action:cancel")]
    ])
    
    # إرسال الملخص كرسالة جديدة
    await update.callback_query.message.reply_text(summary, reply_markup=keyboard, parse_mode="Markdown")
    return CONFIRM_SAVE

async def handle_confirm_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action = query.data.split(":")[1]
    
    if action == "save":
        return await save_case(update, context)
    else:  # cancel
        context.user_data.clear()
        await query.edit_message_text(
            "❌ **تم إلغاء العملية**\n\n"
            "لم يتم حفظ أي بيانات."
        )
        return ConversationHandler.END
    
async def handle_nav_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر الإلغاء من الأزرار Inline"""
    query = update.callback_query
    await query.answer()
    
    context.user_data.clear()
    await query.edit_message_text(
        "❌ **تم إلغاء العملية**\n\n"
        "لم يتم حفظ أي بيانات."
    )
    return ConversationHandler.END

async def handle_back_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر الرجوع"""
    query = update.callback_query
    await query.answer()
    
    back_to = query.data.split(":")[1]
    
    if back_to == "patient_name":
        # الرجوع لاسم المريض
        text = """
📝 **الخطوة 1 من 7**

👤 **اسم المريض:**

💡 مثال: محمد أحمد علي
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
        return ASK_PATIENT_NAME
    
    elif back_to == "age":
        # الرجوع للعمر
        text = f"""
📝 **الخطوة 2 من 7**

🎂 **عمر المريض:**

💡 مثال: 45 أو 3 سنوات
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="back:patient_name")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
        return ASK_AGE
    
    elif back_to == "complaint":
        # الرجوع للشكوى
        text = """
📝 **الخطوة 3 من 7**

🩺 **الشكوى الرئيسية:**

💡 مثال: ألم في الصدر، صداع مستمر
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="back:age")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
        return ASK_MAIN_COMPLAINT
    
    elif back_to == "history":
        # الرجوع للقصة المرضية
        text = """
📝 **الخطوة 4 من 7**

📋 **القصة المرضية الحالية:**

💡 مثال: بدأت الأعراض منذ أسبوعين...
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="back:complaint")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
        return ASK_CURRENT_HISTORY
    
    elif back_to == "notes":
        # الرجوع للملاحظات
        text = """
📝 **الخطوة 5 من 7** (اختياري)

📝 **ملاحظات إضافية:**

💡 مثال: حساسية من البنسلين...
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="back:history"), InlineKeyboardButton("⏭️ تخطي", callback_data="skip:notes")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
        return ASK_NOTES
    
    elif back_to == "procedures":
        # الرجوع للإجراءات
        text = """
📝 **الخطوة 6 من 7** (اختياري)

🔬 **الإجراءات السابقة:**

💡 مثال: عملية قلب 2020...
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="back:notes"), InlineKeyboardButton("⏭️ تخطي", callback_data="skip:procedures")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
        return ASK_PREVIOUS_PROCEDURES
    
    elif back_to == "has_tests":
        # الرجوع لسؤال الفحوصات
        text = """
📝 **الخطوة 7 من 7** (اختياري)

📊 **الفحوصات والأشعة:**
هل يوجد مع المريض أشعة أو تحاليل سابقة؟
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ نعم، يوجد", callback_data="has_tests:yes"), InlineKeyboardButton("❌ لا يوجد", callback_data="has_tests:no")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="back:procedures")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
        return ASK_HAS_TESTS

async def save_case(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    
    # ✅ حفظ البيانات في قاعدة البيانات
    from db.session import SessionLocal
    from db.models import Patient, InitialCase
    
    try:
        with SessionLocal() as s:
            # إنشاء أو العثور على المريض
            patient = s.query(Patient).filter_by(full_name=data.get('patient_name')).first()
            if not patient:
                patient = Patient(full_name=data.get('patient_name'))
                s.add(patient)
                s.commit()
                s.refresh(patient)
            
            # إنشاء الحالة الأولية في الجدول الجديد
            initial_case = InitialCase(
                patient_id=patient.id,
                patient_age=data.get('patient_age'),
                main_complaint=data.get('main_complaint'),
                current_history=data.get('current_history'),
                notes=data.get('notes'),
                previous_procedures=data.get('previous_procedures'),
                test_details=data.get('test_details'),
                created_by=update.effective_user.id,
                created_at=datetime.utcnow()
            )
            s.add(initial_case)
            s.commit()
            s.refresh(initial_case)
            
            print(f"تم حفظ الحالة الأولية ID: {initial_case.id} للمريض: {patient.full_name}")
            
            # بث الحالة الأولية لجميع المستخدمين والأدمن
            try:
                from services.broadcast_service import broadcast_initial_case
                
                # تحضير بيانات الحالة للبث
                case_broadcast_data = {
                    'patient_name': data.get('patient_name'),
                    'patient_age': data.get('patient_age'),
                    'main_complaint': data.get('main_complaint'),
                    'current_history': data.get('current_history'),
                    'notes': data.get('notes'),
                    'previous_procedures': data.get('previous_procedures'),
                    'test_details': data.get('test_details'),
                }
                
                await broadcast_initial_case(update.callback_query.bot, case_broadcast_data)
                print(f"تم بث الحالة الاولية للمريض {data.get('patient_name')}")
            except Exception as e:
                print(f"خطأ في بث الحالة الاولية: {e}")

        # ✅ تأكيد الحفظ - احترافي
        success_message = f"""
╔══════════════════════════════════╗
║        ✅ تم الحفظ بنجاح!        ║
╚══════════════════════════════════╝

📋 **تفاصيل الحالة المحفوظة:**

👤 **المريض:** {data.get('patient_name')}
🆔 **رقم الحالة:** #{initial_case.id}
📅 **التاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📢 **تم إرسال الحالة لجميع المستخدمين والأدمن**

✨ يمكن للمترجمين الآن البدء بإضافة التقارير لهذه الحالة!
"""
        
        await update.callback_query.edit_message_text(success_message)
        context.user_data.clear()
        
    except Exception as e:
        print(f"خطأ في حفظ الحالة الأولية: {e}")
        import traceback
        traceback.print_exc()
        await update.callback_query.edit_message_text(f"❌ حدث خطأ أثناء الحفظ: {e}")
    
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🚫 تم إلغاء العملية.")
    return ConversationHandler.END


def register(app):
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("add_case", start_add_case),
            MessageHandler(filters.Regex("^➕ إضافة حالة أولية$"), start_add_case)
        ],
        states={
            ASK_PATIENT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_age),
                CallbackQueryHandler(handle_nav_cancel, pattern="^nav:cancel$")
            ],
            ASK_AGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_main_complaint),
                CallbackQueryHandler(handle_back_button, pattern="^back:"),
                CallbackQueryHandler(handle_nav_cancel, pattern="^nav:cancel$")
            ],
            ASK_MAIN_COMPLAINT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_current_history),
                CallbackQueryHandler(handle_back_button, pattern="^back:"),
                CallbackQueryHandler(handle_nav_cancel, pattern="^nav:cancel$")
            ],
            ASK_CURRENT_HISTORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_notes),
                CallbackQueryHandler(handle_back_button, pattern="^back:"),
                CallbackQueryHandler(handle_nav_cancel, pattern="^nav:cancel$")
            ],
            ASK_NOTES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_previous_procedures),
                CallbackQueryHandler(handle_skip_notes, pattern="^skip:notes$"),
                CallbackQueryHandler(handle_back_button, pattern="^back:"),
                CallbackQueryHandler(handle_nav_cancel, pattern="^nav:cancel$")
            ],
            ASK_PREVIOUS_PROCEDURES: [
                CallbackQueryHandler(show_procedure_suggestions, pattern="^proc:suggestions$"),
                CallbackQueryHandler(handle_procedure_selection, pattern="^proc_select:"),
                CallbackQueryHandler(handle_procedure_search, pattern="^proc:search$"),
                CallbackQueryHandler(handle_procedure_manual, pattern="^proc:manual$"),
                CallbackQueryHandler(handle_procedure_back, pattern="^proc:back$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: handle_procedure_search_query(u, c) if c.user_data.get("searching_procedures") else ask_has_tests(u, c)),
                CallbackQueryHandler(handle_skip_procedures, pattern="^skip:procedures$"),
                CallbackQueryHandler(handle_back_button, pattern="^back:"),
                CallbackQueryHandler(handle_nav_cancel, pattern="^nav:cancel$")
            ],
            ASK_HAS_TESTS: [
                CallbackQueryHandler(handle_tests_choice, pattern="^has_tests:"),
                CallbackQueryHandler(handle_back_button, pattern="^back:"),
                CallbackQueryHandler(handle_nav_cancel, pattern="^nav:cancel$")
            ],
            ASK_TEST_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_test_details),
                CallbackQueryHandler(handle_back_button, pattern="^back:"),
                CallbackQueryHandler(handle_nav_cancel, pattern="^nav:cancel$")
            ],
            CONFIRM_SAVE: [
                CallbackQueryHandler(handle_confirm_action, pattern="^action:"),
                CallbackQueryHandler(handle_back_button, pattern="^back:")
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex("^إلغاء$|^الغاء$|^cancel$"), cancel),
            CallbackQueryHandler(handle_back_button, pattern="^back:"),
            CallbackQueryHandler(handle_nav_cancel, pattern="^nav:cancel$")
        ],
        name="admin_initial_case_conv",
        per_chat=True,
        per_user=True,
        per_message=False,
    )
    app.add_handler(conv)
