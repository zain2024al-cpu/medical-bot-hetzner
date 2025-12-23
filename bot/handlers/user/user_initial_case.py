# ================================================
# bot/handlers/user/user_initial_case.py
# 📋 عرض التقرير الأولي للمرضى
# ================================================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    InlineQueryHandler,
    ChosenInlineResultHandler,
    filters,
)
from db.session import SessionLocal
from db.models import Patient, InitialCase
# لا نحتاج استيراد render_patient_selection و show_patient_list
# سننشئ نسخ مخصصة تعرض فقط المرضى الذين لديهم تقرير أولي
from bot.shared_auth import is_user_approved
import logging

logger = logging.getLogger(__name__)

# States
INITIAL_CASE_SELECT_PATIENT = "initial_case_select_patient"
INITIAL_CASE_VIEW = "initial_case_view"


async def start_initial_case_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء البحث عن التقرير الأولي"""
    query = update.callback_query
    if query:
        await query.answer()
    
    user = update.effective_user
    if not is_user_approved(user.id):
        if query:
            await query.edit_message_text(
                "⏳ **بانتظار الموافقة**\n\n"
                "طلبك قيد المراجعة من قبل الإدارة.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "⏳ **بانتظار الموافقة**\n\n"
                "طلبك قيد المراجعة من قبل الإدارة.",
                parse_mode="Markdown"
            )
        return ConversationHandler.END
    
    # تهيئة البيانات - وضع علامة أننا في وضع التقرير الأولي
    context.user_data["initial_case_search"] = {"active": True}
    
    # عرض قائمة المرضى الذين لديهم تقرير أولي فقط
    message = query.message if query else update.message
    await render_initial_case_patient_selection(message, context)
    
    return INITIAL_CASE_SELECT_PATIENT


async def handle_initial_case_patient_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار المريض للبحث عن التقرير الأولي"""
    query = update.callback_query
    if query:
        await query.answer()
    
    # معالجة اختيار المريض من القائمة
    if query and query.data.startswith("patient_idx:"):
        try:
            patient_id = int(query.data.split(":")[1])
            
            with SessionLocal() as s:
                patient = s.query(Patient).filter_by(id=patient_id).first()
                if not patient:
                    await query.edit_message_text(
                        "❌ **خطأ**\n\n"
                        "لم يتم العثور على المريض.",
                        parse_mode="Markdown"
                    )
                    return INITIAL_CASE_SELECT_PATIENT
                
                # البحث عن التقرير الأولي للمريض (تقرير واحد فقط)
                # البحث باستخدام patient_id أو patient_name
                initial_case = s.query(InitialCase).filter(
                    (InitialCase.patient_id == patient_id) | 
                    (InitialCase.patient_name == patient.full_name)
                ).first()
                
                if not initial_case:
                    await query.edit_message_text(
                        f"❌ **لا يوجد تقرير أولي**\n\n"
                        f"👤 **المريض:** {patient.full_name}\n\n"
                        f"⚠️ لم يتم العثور على تقرير أولي لهذا المريض.\n\n"
                        f"💡 يمكن للإدارة إضافة تقرير أولي من لوحة الإدارة.",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔙 رجوع", callback_data="initial_case:back")]
                        ])
                    )
                    return INITIAL_CASE_VIEW
                
                # عرض التقرير الأولي
                await display_initial_case(query, initial_case, patient)
                return INITIAL_CASE_VIEW
                
        except (ValueError, IndexError) as e:
            logger.error(f"❌ Error parsing patient ID: {e}")
            await query.answer("⚠️ خطأ في اختيار المريض", show_alert=True)
            return INITIAL_CASE_SELECT_PATIENT
    
    return INITIAL_CASE_SELECT_PATIENT


async def display_initial_case(query, initial_case, patient):
    """عرض التقرير الأولي للمريض (من callback query)"""
    text = _build_initial_case_text(initial_case, patient)
    
    # أزرار التنقل
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع للبحث", callback_data="initial_case:back")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="user_action:back_main")]
    ])
    
    await query.edit_message_text(
        text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def display_initial_case_message(message, initial_case, patient):
    """عرض التقرير الأولي للمريض (من message)"""
    text = _build_initial_case_text(initial_case, patient)
    
    # أزرار التنقل
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع للبحث", callback_data="initial_case:back")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="user_action:back_main")]
    ])
    
    await message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


def _build_initial_case_text(initial_case, patient):
    """بناء نص التقرير الأولي"""
    text = f"""
╔══════════════════════════════════╗
║    📋 التقرير الأولي للمريض      ║
╚══════════════════════════════════╝

👤 **اسم المريض:** {patient.full_name}
"""
    
    # التحقق من الحقول المتاحة في InitialCase
    # قد تكون الحقول مختلفة حسب النموذج الفعلي
    if hasattr(initial_case, 'patient_age') and initial_case.patient_age:
        text += f"🎂 **العمر:** {initial_case.patient_age} سنة\n"
    
    if hasattr(initial_case, 'main_complaint') and initial_case.main_complaint:
        text += f"\n💬 **الشكوى الرئيسية:**\n{initial_case.main_complaint}\n"
    elif hasattr(initial_case, 'case_details') and initial_case.case_details:
        # استخدام case_details إذا كان موجوداً
        text += f"\n💬 **تفاصيل الحالة:**\n{initial_case.case_details}\n"
    
    if hasattr(initial_case, 'current_history') and initial_case.current_history:
        text += f"\n📖 **التاريخ الحالي:**\n{initial_case.current_history}\n"
    
    if hasattr(initial_case, 'previous_procedures') and initial_case.previous_procedures:
        text += f"\n🏥 **الإجراءات السابقة:**\n{initial_case.previous_procedures}\n"
    
    if hasattr(initial_case, 'test_details') and initial_case.test_details:
        text += f"\n🔬 **تفاصيل الفحوصات:**\n{initial_case.test_details}\n"
    
    if hasattr(initial_case, 'notes') and initial_case.notes:
        text += f"\n📝 **ملاحظات:**\n{initial_case.notes}\n"
    
    if initial_case.created_at:
        from datetime import datetime
        created_date = initial_case.created_at.strftime('%Y-%m-%d %H:%M') if isinstance(initial_case.created_at, datetime) else str(initial_case.created_at)
        text += f"\n📅 **تاريخ الإنشاء:** {created_date}\n"
    
    text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    return text


async def handle_initial_case_patient_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة callbacks قائمة المرضى (pagination)"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("patient:show_list:"):
        try:
            page = int(query.data.split(":")[-1])
            # استخدام show_initial_case_patient_list
            await show_initial_case_patient_list(update, context, page)
            return INITIAL_CASE_SELECT_PATIENT
        except (ValueError, IndexError) as e:
            logger.error(f"❌ Error parsing page number: {e}")
            await query.answer("⚠️ خطأ في رقم الصفحة", show_alert=True)
            return INITIAL_CASE_SELECT_PATIENT
    elif query.data == "patient:back_to_menu":
        # العودة إلى شاشة اختيار المريض الرئيسية
        await render_initial_case_patient_selection(query.message, context)
        return INITIAL_CASE_SELECT_PATIENT
    
    return INITIAL_CASE_SELECT_PATIENT


async def handle_initial_case_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة إلى البحث عن مريض آخر"""
    query = update.callback_query
    await query.answer()
    
    # العودة إلى شاشة اختيار المريض
    await render_initial_case_patient_selection(query.message, context)
    return INITIAL_CASE_SELECT_PATIENT

async def handle_back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة إلى القائمة الرئيسية"""
    query = update.callback_query
    if query:
        await query.answer()
    
    # مسح بيانات المحادثة
    context.user_data.clear()
    
    # إرسال القائمة الرئيسية
    from bot.keyboards import user_main_kb
    if query:
        await query.message.reply_text(
            "📋 اختر العملية المطلوبة:",
            reply_markup=user_main_kb()
        )
    else:
        await update.message.reply_text(
            "📋 اختر العملية المطلوبة:",
            reply_markup=user_main_kb()
        )
    
    # إنهاء ConversationHandler
    return ConversationHandler.END

async def handle_unhandled_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة النصوص غير المعالجة - العودة لشاشة اختيار المريض"""
    # العودة إلى شاشة اختيار المريض
    await render_initial_case_patient_selection(update.message, context)
    return INITIAL_CASE_SELECT_PATIENT


async def render_initial_case_patient_selection(message, context):
    """عرض شاشة اختيار المريض - فقط المرضى الذين لديهم تقرير أولي"""
    keyboard = []

    # زر البحث الذكي (inline search) - فقط المرضى الذين لديهم تقرير أولي
    keyboard.append([InlineKeyboardButton(
        "🔍 بحث عن مريض",
        switch_inline_query_current_chat=""
    )])
    
    # زر عرض قائمة كاملة مع pagination
    keyboard.append([InlineKeyboardButton(
        "📋 عرض جميع الأسماء",
        callback_data="patient:show_list:0"
    )])

    # أزرار التنقل
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="nav:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = "👤 **اختيار المريض**\n\n"
    text += "**خيارات البحث:**\n"
    text += "• 🔍 **بحث عن مريض:** للبحث السريع (فقط المرضى الذين لديهم تقرير أولي)\n"
    text += "• 📋 **عرض جميع الأسماء:** لعرض جميع المرضى الذين لديهم تقرير أولي\n\n"
    text += "💡 **ملاحظة:** سيتم عرض فقط المرضى الذين تم إضافة تقرير أولي لهم من لوحة الإدارة."

    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def show_initial_case_patient_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """عرض قائمة المرضى الذين لديهم تقرير أولي مع pagination"""
    query = update.callback_query
    if query:
        await query.answer()
    
    items_per_page = 10  # 10 أسماء في كل صفحة
    
    with SessionLocal() as s:
        # استخدام استعلام SQL مباشر آمن للتعامل مع الأعمدة المفقودة
        from sqlalchemy import text
        
        try:
            # محاولة جلب الأعمدة الموجودة في الجدول
            inspector_result = s.execute(text("PRAGMA table_info(initial_cases)"))
            columns_info = inspector_result.fetchall()
            existing_columns = [col[1] for col in columns_info]  # col[1] هو اسم العمود
            
            logger.info(f"📋 Existing columns in initial_cases: {existing_columns}")
            
            # بناء استعلام SQL ديناميكي بناءً على الأعمدة الموجودة
            select_fields = ["id"]
            where_conditions = []
            
            if 'patient_id' in existing_columns:
                select_fields.append("patient_id")
                where_conditions.append("patient_id IS NOT NULL")
            
            if 'patient_name' in existing_columns:
                select_fields.append("patient_name")
                if not where_conditions:
                    where_conditions.append("patient_name IS NOT NULL")
                else:
                    where_conditions[0] = f"({where_conditions[0]} OR patient_name IS NOT NULL)"
            
            # بناء الاستعلام
            if where_conditions:
                sql_query = f"SELECT DISTINCT {', '.join(select_fields)} FROM initial_cases WHERE {where_conditions[0]}"
            else:
                # إذا لم توجد أعمدة patient_id أو patient_name، نستخدم id فقط
                sql_query = "SELECT DISTINCT id FROM initial_cases"
            
            logger.info(f"🔍 Executing SQL: {sql_query}")
            result = s.execute(text(sql_query))
            initial_cases_data = result.fetchall()
            
            # جمع معرفات المرضى وأسمائهم
            patient_ids = set()
            patient_names = set()
            
            for row in initial_cases_data:
                # row هو tuple، نحتاج للتحقق من الفهرس
                row_dict = {}
                for idx, col_name in enumerate(select_fields):
                    if idx < len(row):
                        row_dict[col_name] = row[idx]
                
                if 'patient_id' in row_dict and row_dict['patient_id']:
                    patient_ids.add(row_dict['patient_id'])
                if 'patient_name' in row_dict and row_dict['patient_name']:
                    patient_names.add(row_dict['patient_name'])
            
            logger.info(f"📊 Found {len(patient_ids)} patient IDs and {len(patient_names)} patient names")
            
        except Exception as e:
            logger.error(f"❌ Error querying initial_cases: {e}", exc_info=True)
            patient_ids = set()
            patient_names = set()
        
        # جلب المرضى - فقط الذين لديهم تقرير أولي (من جدول initial_cases)
        # هذا يضمن أننا نعرض فقط المرضى الذين تم إضافتهم من زر "إضافة حالة أولية"
        all_patients = []
        
        if patient_ids:
            # جلب المرضى باستخدام patient_id
            patients_by_id = s.query(Patient).filter(Patient.id.in_(patient_ids)).all()
            all_patients.extend(patients_by_id)
            logger.info(f"📊 Found {len(patients_by_id)} patients by ID")
        
        if patient_names:
            # جلب المرضى باستخدام patient_name (فقط إذا لم يكن موجوداً بالفعل)
            existing_ids = {p.id for p in all_patients}
            if existing_ids:
                from sqlalchemy import not_
                patients_by_name = s.query(Patient).filter(
                    Patient.full_name.in_(patient_names),
                    not_(Patient.id.in_(existing_ids))
                ).all()
            else:
                patients_by_name = s.query(Patient).filter(
                    Patient.full_name.in_(patient_names)
                ).all()
            all_patients.extend(patients_by_name)
            logger.info(f"📊 Found {len(patients_by_name)} additional patients by name")
        
        # إزالة التكرارات
        seen_ids = set()
        unique_patients = []
        for patient in all_patients:
            if patient.id not in seen_ids:
                seen_ids.add(patient.id)
                unique_patients.append(patient)
        
        all_patients = unique_patients
        # ترتيب المرضى حسب الاسم
        all_patients.sort(key=lambda p: p.full_name or "")
        logger.info(f"📊 Total unique patients with initial cases: {len(all_patients)}")
        total = len(all_patients)
        total_pages = max(1, (total + items_per_page - 1) // items_per_page)
        page = max(0, min(page, total_pages - 1))
        
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, total)
        patients_page = all_patients[start_idx:end_idx]
        
        keyboard = []
        
        # إضافة أزرار المرضى
        for patient in patients_page:
            keyboard.append([InlineKeyboardButton(
                f"📋 {patient.full_name}",
                callback_data=f"patient_idx:{patient.id}"
            )])
        
        # أزرار التنقل بين الصفحات
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"patient:show_list:{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"patient:show_list:{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        # أزرار إضافية
        keyboard.append([
            InlineKeyboardButton("🔍 بحث سريع", switch_inline_query_current_chat=""),
            InlineKeyboardButton("🔙 رجوع", callback_data="patient:back_to_menu")
        ])
        
        text = f"📋 **قائمة المرضى (تقرير أولي)**\n\n"
        text += f"📊 **العدد الإجمالي:** {total} مريض لديهم تقرير أولي\n"
        text += f"📄 **الصفحة:** {page + 1} من {total_pages}\n\n"
        text += "اختر المريض من القائمة:"
        
        if query:
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        return INITIAL_CASE_SELECT_PATIENT


async def handle_initial_case_nav_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر الرجوع"""
    query = update.callback_query
    if query:
        await query.answer()
    
    # إنهاء المحادثة والعودة للقائمة الرئيسية
    from bot.keyboards import user_main_kb
    
    # تنظيف البيانات
    context.user_data.pop("initial_case_search", None)
    
    if query:
        await query.edit_message_text(
            "❌ **تم إلغاء العملية**\n\n"
            "يمكنك البدء مرة أخرى من القائمة الرئيسية.",
            parse_mode="Markdown"
        )
        await query.message.reply_text(
            "📋 اختر العملية المطلوبة:",
            reply_markup=user_main_kb()
        )
    else:
        await update.message.reply_text(
            "📋 اختر العملية المطلوبة:",
            reply_markup=user_main_kb()
        )
    
    return ConversationHandler.END


async def handle_initial_case_nav_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر الإلغاء"""
    query = update.callback_query
    if query:
        await query.answer()
    
    # تنظيف البيانات - إزالة علامة التقرير الأولي
    context.user_data.pop("initial_case_search", None)
    
    # إنهاء المحادثة
    if query:
        await query.edit_message_text(
            "❌ **تم إلغاء العملية**\n\n"
            "يمكنك البدء مرة أخرى من القائمة الرئيسية.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "❌ **تم إلغاء العملية**\n\n"
            "يمكنك البدء مرة أخرى من القائمة الرئيسية.",
            parse_mode="Markdown"
        )
    
    return ConversationHandler.END


async def handle_initial_case_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة البحث السريع عن المرضى الذين لديهم تقرير أولي فقط (inline query)"""
    # ✅ التحقق أولاً: هل المستخدم فعلاً في وضع التقرير الأولي؟
    initial_case_search = context.user_data.get("initial_case_search")
    report_tmp = context.user_data.get("report_tmp", {})
    
    # ✅ هذا الـ handler يتم استدعاؤه فقط من unified_inline_query_handler
    # عندما يكون المستخدم في وضع التقرير الأولي
    # لذلك لا نحتاج التحقق من report_tmp أو initial_case_search هنا
    
    query_text = update.inline_query.query.strip() if update.inline_query.query else ""
    logger.info(f"🔍 initial_case_inline_query: Searching patients with initial case, query='{query_text}'")
    
    results = []
    
    try:
        with SessionLocal() as s:
            # استخدام استعلام مباشر آمن
            from sqlalchemy import text
            
            if query_text:
                # البحث عن المرضى الذين لديهم تقرير أولي واسمهم يطابق البحث
                sql = text("""
                    SELECT DISTINCT ic.patient_id, ic.patient_name 
                    FROM initial_cases ic
                    WHERE (ic.patient_id IS NOT NULL OR ic.patient_name IS NOT NULL)
                    AND (ic.patient_name LIKE :query OR EXISTS (
                        SELECT 1 FROM patients p 
                        WHERE (p.id = ic.patient_id OR p.full_name = ic.patient_name)
                        AND p.full_name LIKE :query
                    ))
                    LIMIT 50
                """)
                initial_cases_data = s.execute(sql, {"query": f"%{query_text}%"}).fetchall()
            else:
                # عرض آخر 50 حالة أولية
                sql = text("""
                    SELECT DISTINCT patient_id, patient_name 
                    FROM initial_cases 
                    WHERE patient_id IS NOT NULL OR patient_name IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 50
                """)
                initial_cases_data = s.execute(sql).fetchall()
            
            for row in initial_cases_data:
                patient_id = row[0]
                patient_name = row[1]
                
                # جلب بيانات المريض
                patient = None
                if patient_id:
                    patient = s.query(Patient).filter_by(id=patient_id).first()
                if not patient and patient_name:
                    patient = s.query(Patient).filter_by(full_name=patient_name).first()
                
                if patient:
                    result = InlineQueryResultArticle(
                        id=f"initial_case_{patient.id}",
                        title=f"📋 {patient.full_name}",
                        description="✅ تقرير أولي متاح - اضغط للعرض",
                        input_message_content=InputTextMessageContent(
                            message_text=f"__INITIAL_CASE_SELECTED__:{patient.id}:{patient.full_name}"
                        )
                    )
                    results.append(result)
        
        logger.info(f"initial_case_inline_query: Found {len(results)} patients with initial cases")
        
    except Exception as e:
        logger.error(f"❌ خطأ في البحث عن المرضى: {e}", exc_info=True)
    
    # إرسال النتائج
    await update.inline_query.answer(results, cache_time=1)


async def handle_initial_case_chosen_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار مريض من inline query"""
    result_id = update.chosen_inline_result.result_id
    
    if result_id.startswith("initial_case_"):
        try:
            patient_id = int(result_id.split("_")[-1])
            context.user_data["initial_case_search"] = {"patient_id": patient_id}
        except (ValueError, IndexError):
            logger.error(f"❌ Error parsing patient ID from result_id: {result_id}")


async def handle_initial_case_inline_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار مريض من inline query (عند إرسال الرسالة)"""
    text = update.message.text.strip()
    
    if text.startswith("__INITIAL_CASE_SELECTED__:"):
        try:
            parts = text.split(":")
            patient_id = int(parts[1])
            patient_name = parts[2] if len(parts) > 2 else ""
            
            with SessionLocal() as s:
                patient = s.query(Patient).filter_by(id=patient_id).first()
                if not patient:
                    await update.message.reply_text(
                        "❌ **خطأ**\n\n"
                        "لم يتم العثور على المريض.",
                        parse_mode="Markdown"
                    )
                    return INITIAL_CASE_SELECT_PATIENT
                
                # البحث عن التقرير الأولي للمريض
                initial_case = s.query(InitialCase).filter(
                    (InitialCase.patient_id == patient_id) | 
                    (InitialCase.patient_name == patient.full_name)
                ).first()
                
                if not initial_case:
                    await update.message.reply_text(
                        f"❌ **لا يوجد تقرير أولي**\n\n"
                        f"👤 **المريض:** {patient.full_name}\n\n"
                        f"⚠️ لم يتم العثور على تقرير أولي لهذا المريض.\n\n"
                        f"💡 يمكن للإدارة إضافة تقرير أولي من لوحة الإدارة.",
                        parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔙 رجوع", callback_data="initial_case:back")]
                        ])
                    )
                    return INITIAL_CASE_VIEW
                
                # عرض التقرير الأولي
                await display_initial_case_message(update.message, initial_case, patient)
                return INITIAL_CASE_VIEW
                
        except (ValueError, IndexError) as e:
            logger.error(f"❌ Error parsing inline selection: {e}")
            await update.message.reply_text(
                "❌ **خطأ**\n\n"
                "حدث خطأ في معالجة الاختيار.",
                parse_mode="Markdown"
            )
            return INITIAL_CASE_SELECT_PATIENT
    
    return INITIAL_CASE_SELECT_PATIENT


# ================================================
# تسجيل المعالجات
# ================================================

def register(app):
    """تسجيل معالجات التقرير الأولي"""
    
    # ConversationHandler للبحث عن التقرير الأولي
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_initial_case_search, pattern="^user_action:initial_case$"),
            MessageHandler(filters.Regex("^📋 التقرير الأولي للمرضى$"), start_initial_case_search)
        ],
        states={
            INITIAL_CASE_SELECT_PATIENT: [
                CallbackQueryHandler(handle_initial_case_patient_selection, pattern="^patient_idx:"),
                CallbackQueryHandler(handle_initial_case_patient_list, pattern="^patient:(show_list|back_to_menu)"),
                CallbackQueryHandler(handle_initial_case_back, pattern="^initial_case:back"),
                CallbackQueryHandler(handle_initial_case_nav_back, pattern="^nav:back"),
                CallbackQueryHandler(handle_initial_case_nav_cancel, pattern="^nav:cancel"),
                CallbackQueryHandler(handle_back_to_main_menu, pattern="^user_action:back_main$"),
                MessageHandler(filters.TEXT & filters.Regex(r"^__INITIAL_CASE_SELECTED__:"), handle_initial_case_inline_selection),
            ],
            INITIAL_CASE_VIEW: [
                CallbackQueryHandler(handle_initial_case_back, pattern="^initial_case:back"),
                CallbackQueryHandler(handle_initial_case_nav_back, pattern="^nav:back"),
                CallbackQueryHandler(handle_initial_case_nav_cancel, pattern="^nav:cancel"),
                CallbackQueryHandler(handle_back_to_main_menu, pattern="^user_action:back_main$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handle_initial_case_back, pattern="^initial_case:back"),
            CallbackQueryHandler(handle_initial_case_nav_back, pattern="^nav:back"),
            CallbackQueryHandler(handle_initial_case_nav_cancel, pattern="^nav:cancel"),
            CallbackQueryHandler(handle_back_to_main_menu, pattern="^user_action:back_main$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unhandled_text),
        ],
        name="user_initial_case_conv",
    )
    
    app.add_handler(conv_handler)
    
    # Inline Query Handler للبحث السريع - مسجل في group=1 لضمان الأولوية
    # لكن unified_inline_query_handler سيتحقق من initial_case_search ويستدعيه إذا لزم الأمر
    # لذلك نترك unified_inline_query_handler يتعامل معه
    # app.add_handler(InlineQueryHandler(handle_initial_case_inline_query, pattern=".*"), group=1)
    
    # Chosen Inline Result Handler
    app.add_handler(ChosenInlineResultHandler(handle_initial_case_chosen_inline))

