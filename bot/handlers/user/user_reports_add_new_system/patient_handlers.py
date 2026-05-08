# =============================
# patient_handlers.py
# معالجات اختيار المريض + Inline Query Handler
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown
import logging
import sys

from .states import STATE_SELECT_PATIENT, STATE_SELECT_HOSPITAL, R_PATIENT
from .navigation import nav_push
from .managers import PatientDataManager
from .utils import MONTH_NAMES_AR


logger = logging.getLogger(__name__)

# Imports المشتركة
try:
    from db.session import SessionLocal
except ImportError:
    SessionLocal = None

try:
    from db.models import Patient
except ImportError:
    Patient = None


async def patient_inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler منفصل للبحث عن المرضى - يقرأ من قاعدة البيانات مباشرة"""
    query_text = update.inline_query.query.strip() if update.inline_query.query else ""
    logger.info("="*80)
    logger.info("🔍🔍🔍 PATIENT_INLINE_QUERY_HANDLER CALLED! 🔍🔍🔍")
    logger.info(f"🔍 Query text: '{query_text}'")
    logger.info(f"🔍 _current_search_type: {context.user_data.get('_current_search_type', 'NOT SET')}")
    logger.info(f"🔍 report_tmp exists: {bool(context.user_data.get('report_tmp'))}")
    logger.info(f"🔍 SessionLocal available: {SessionLocal is not None}")
    logger.info(f"🔍 Patient model available: {Patient is not None}")
    logger.info("="*80)

    results = []

    # ✅ قراءة من قاعدة البيانات مباشرة أو استخدام قائمة مؤقتة محفوظة في السياق كنسخة احتياطية
    try:
        if SessionLocal and Patient:
            logger.info("🔍 محاولة الاتصال بقاعدة البيانات...")
            with SessionLocal() as s:
                logger.info("✅ تم الاتصال بقاعدة البيانات")

                if query_text:
                    logger.info(f"🔍 البحث عن المرضى بالاستعلام: '{query_text}'")
                    patients = s.query(Patient).filter(
                        Patient.full_name.isnot(None),
                        Patient.full_name != "",
                        Patient.full_name.ilike(f"%{query_text}%")
                    ).order_by(Patient.full_name).limit(50).all()
                else:
                    logger.info("🔍 عرض جميع المرضى (بدون استعلام)")
                    patients = s.query(Patient).filter(
                        Patient.full_name.isnot(None),
                        Patient.full_name != ""
                    ).order_by(Patient.full_name).limit(50).all()

                logger.info(f"✅ تم العثور على {len(patients)} مريض في قاعدة البيانات")

                for patient in patients:
                    if not patient.full_name:
                        continue

                    title = f"👤 {patient.full_name}"
                    if len(title) > 64:
                        title = f"👤 {patient.full_name[:60]}..."

                    result = InlineQueryResultArticle(
                        id=f"patient_{patient.id}",
                        title=title,
                        description=f"👤 {patient.full_name}",
                        input_message_content=InputTextMessageContent(
                            message_text=f"__PATIENT_SELECTED__:{patient.id}:{patient.full_name}"
                        )
                    )
                    results.append(result)

                logger.info(f"✅ patient_inline_query_handler: تم إنشاء {len(results)} نتيجة من قاعدة البيانات")
        else:
            # سلوك احتياطي: استخدام قائمة أسماء المرضى المخزنة في context.user_data إن وجدت
            logger.warning("⚠️ SessionLocal أو نموذج Patient غير متاح؛ استخدام قائمة مؤقتة من context.user_data إذا كانت متوفرة")
            cached = context.user_data.get("report_tmp", {}).get("_patient_names_list", [])
            if cached:
                logger.info(f"🔁 استخدام {len(cached)} اسمًا من القائمة المؤقتة")
                # تصفية القائمة حسب الاستعلام
                filtered = [n for n in cached if query_text.lower() in n.lower()] if query_text else cached[:50]

                class SimplePatient:
                    def __init__(self, id_, full_name):
                        self.id = id_
                        self.full_name = full_name

                for i, name in enumerate(filtered[:50]):
                    p = SimplePatient(i + 1, name)
                    title = f"👤 {p.full_name}"
                    if len(title) > 64:
                        title = f"👤 {p.full_name[:60]}..."

                    result = InlineQueryResultArticle(
                        id=f"patient_cached_{i}",
                        title=title,
                        description=f"👤 {p.full_name}",
                        input_message_content=InputTextMessageContent(
                            message_text=f"__PATIENT_SELECTED__:{p.id}:{p.full_name}"
                        )
                    )
                    results.append(result)
                logger.info(f"✅ patient_inline_query_handler: تم إنشاء {len(results)} نتيجة من القائمة المؤقتة")
            else:
                logger.error("❌ لا يمكن الوصول لقاعدة البيانات ولا توجد قائمة مؤقتة في السياق")
                raise Exception("SessionLocal أو Patient غير متاح ولا توجد قائمة مؤقتة")

    except Exception as db_error:
        logger.error(f"❌ خطأ في البحث عن المرضى: {db_error}", exc_info=True)
        import traceback
        traceback.print_exc()
        error_result = InlineQueryResultArticle(
            id="patient_db_error",
            title="❌ خطأ في البحث عن المرضى",
            description=f"حدث خطأ: {str(db_error)[:100]}",
            input_message_content=InputTextMessageContent(
                message_text="__PATIENT_SELECTED__:0:خطأ"
            )
        )
        results.append(error_result)

    # إرسال النتائج - دائماً إرسال شيء حتى لو كانت النتائج فارغة
    if not results:
        logger.warning("⚠️ لا توجد نتائج - إرسال رسالة 'لا توجد نتائج'")
        result = InlineQueryResultArticle(
            id="patient_no_results",
            title="❌ لا توجد نتائج",
            description="لم يتم العثور على مرضى في قاعدة البيانات",
            input_message_content=InputTextMessageContent(
                message_text="__PATIENT_SELECTED__:0:لا يوجد"
            )
        )
        results.append(result)

    try:
        await update.inline_query.answer(results, cache_time=1)
        logger.info(f"✅ patient_inline_query_handler: تم إرسال {len(results)} نتيجة بنجاح")
    except Exception as answer_error:
        logger.error(f"❌ خطأ في إرسال النتائج: {answer_error}", exc_info=True)
        import traceback
        traceback.print_exc()


async def render_patient_selection(message, context):
    """عرض شاشة اختيار المريض - rendering فقط"""
    # ✅ ضبط نوع البحث على 'patient' لضمان عمل البحث بشكل صحيح
    context.user_data['_current_search_type'] = 'patient'
    
    keyboard = []

    # ✅ صف الأزرار الرئيسية: عرض القائمة + البحث
    keyboard.append([
        InlineKeyboardButton(
            "📋 عرض جميع الأسماء",
            callback_data="patient:show_list:0"
        ),
        InlineKeyboardButton(
                "🔍 بحث عن مريض",
                switch_inline_query_current_chat=""
        )
    ])

    # أزرار التنقل - استخدام زر الرجوع العادي
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="go_to_date_selection"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = "👤 **اسم المريض** (الخطوة 2 من 5)\n\n"
    text += "**اختر طريقة البحث:**\n"
    text += "• 📋 **عرض جميع الأسماء** - لعرض قائمة كاملة\n"
    text += "• 🔍 **بحث عن مريض** - للبحث السريع بالاسم\n\n"
    text += "💡 **نصيحة:** استخدم زر البحث للعثور على مريض بسرعة!"

    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def show_patient_selection(message, context, search_query=""):
    """Navigation wrapper - يحدث state ثم يستدعي rendering"""
    # ✅ تحديث last_valid_state
    context.user_data['last_valid_state'] = 'patient_selection'
    context.user_data['_conversation_state'] = STATE_SELECT_PATIENT
    # ✅ ضبط نوع البحث على 'patient' لضمان عمل البحث بشكل صحيح (قبل render_patient_selection)
    context.user_data['_current_search_type'] = 'patient'
    
    # استدعاء rendering function
    await render_patient_selection(message, context)


# Forward declarations to avoid circular imports
async def show_hospitals_menu(message, context):
    from .hospital_handlers import show_hospitals_menu as actual_show_hospitals_menu
    return await actual_show_hospitals_menu(message, context)


async def show_patient_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """عرض قائمة المرضى - مع pagination وعرض اسمين في كل صف"""
    
    query = update.callback_query
    if query:
        await query.answer()
    
    try:
        items_per_page = 10  # عدد الأسماء في كل صفحة (10 أسماء = 5 صفوف لأن كل صف يحتوي على اسمين)
        
        # ✅ دائماً جلب الأسماء مباشرة من قاعدة البيانات (لتضمين الأسماء الجديدة)
        # لا نعتمد على القائمة المحفوظة لأنها قد تكون قديمة
        patient_names = []
        if not SessionLocal:
            logger.error("❌ SessionLocal غير متاح في show_patient_list")
            raise Exception("SessionLocal غير متاح")
        if not Patient:
            logger.error("❌ Patient model غير متاح في show_patient_list")
            raise Exception("Patient model غير متاح")

        with SessionLocal() as s:
            # ✅ جلب جميع المرضى من قاعدة البيانات مباشرة (أحدث البيانات)
            all_patients = s.query(Patient).filter(
                Patient.full_name.isnot(None),
                Patient.full_name != ""
            ).order_by(Patient.full_name).all()
            patient_names = [p.full_name.strip() for p in all_patients if p.full_name and p.full_name.strip()]
            logger.info(f"✅ تم تحميل {len(patient_names)} اسم من قاعدة البيانات مباشرة في show_patient_list")
        
        # التحقق من وجود أسماء
        if not patient_names:
            error_text = "⚠️ **لا توجد أسماء مرضى**\n\n"
            error_text += "لم يتم العثور على أسماء مرضى في قاعدة البيانات."
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data="patient:back_to_menu")]
            ])
            
            if query:
                await query.edit_message_text(error_text, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await update.message.reply_text(error_text, reply_markup=keyboard, parse_mode="Markdown")
            return
        
        # إزالة التكرارات
        seen = set()
        unique_names = []
        for name in patient_names:
            name_clean = name.strip()
            if name_clean and name_clean not in seen:
                seen.add(name_clean)
                unique_names.append(name_clean)
        
        # ✅ ترتيب الأسماء أبجدياً من الألف إلى الياء
        unique_names.sort()
        
        # ✅ تحديث قائمة الأسماء في context.user_data (للاستخدام لاحقاً في نفس الجلسة)
        all_patient_names = unique_names
        context.user_data.setdefault("report_tmp", {})["_patient_names_list"] = all_patient_names
        
        total = len(all_patient_names)
        total_pages = max(1, (total + items_per_page - 1) // items_per_page)
        page = max(0, min(page, total_pages - 1))
        
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, total)
        patients_page = all_patient_names[start_idx:end_idx]
        
        keyboard = []
        
        # ✅ إضافة أزرار المرضى - عرض اسمين في كل صف
        for i in range(0, len(patients_page), 2):
            row = []
            for j in range(2):  # اسمين في كل صف
                if i + j >= len(patients_page):
                    break  # إذا انتهت القائمة
                
                patient_name = patients_page[i + j]
                
                # ✅ عرض الاسم كاملاً (بدون تقصير إذا أمكن)
                button_text = f"👤 {patient_name}"
                # تقصير النص فقط إذا كان طويلاً جداً (حد Telegram هو 64 حرف، لكن نحن نضع اسمين في صف واحد، لذا نستخدم 32 حرف)
                if len(button_text) > 32:
                    # محاولة عرض أكبر قدر ممكن من الاسم
                    max_name_length = 28  # 32 - 4 (👤 + مسافة)
                    button_text = f"👤 {patient_name[:max_name_length]}..."
                
                # حساب الفهرس الصحيح في القائمة الكاملة
                global_index = start_idx + i + j
                
                row.append(InlineKeyboardButton(
                    button_text,
                    callback_data=f"patient_idx:{global_index}"
                ))
            keyboard.append(row)
        
        # أزرار التنقل بين الصفحات
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"patient:show_list:{page-1}"))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"patient:show_list:{page+1}"))
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        # زر الرجوع
        keyboard.append([
            InlineKeyboardButton("🔙 رجوع", callback_data="patient:back_to_menu")
        ])
        
        text = f"👤 **قائمة المرضى**\n\n"
        text += f"📊 **العدد الإجمالي:** {total} مريض\n"
        text += f"📄 **الصفحة:** {page + 1} من {total_pages}\n\n"
        text += "اختر المريض من القائمة (مرتبة أبجدياً):"
        
        if query:
            try:
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"❌ خطأ في تعديل الرسالة: {e}")
                try:
                    await query.message.reply_text(
                        text.replace("**", ""),
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except Exception as e2:
                    logger.error(f"❌ خطأ في المحاولة الثانية: {e2}")
        else:
            await update.message.reply_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            
    except Exception as e:
        logger.error(f"❌ خطأ في show_patient_list: {e}", exc_info=True)
        error_text = f"❌ **حدث خطأ غير متوقع**\n\n{str(e)}\n\nيرجى المحاولة مرة أخرى."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="patient:back_to_menu")]
        ])
        
        try:
            if query:
                await query.edit_message_text(error_text, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await update.message.reply_text(error_text, reply_markup=keyboard, parse_mode="Markdown")
        except Exception as send_error:
            logger.error(f"❌ خطأ في إرسال رسالة الخطأ: {send_error}", exc_info=True)
    
    return STATE_SELECT_PATIENT


async def handle_patient_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة callbacks قائمة المرضى"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("patient:show_list:"):
        try:
            page = int(query.data.split(":")[-1])
            return await show_patient_list(update, context, page)
        except (ValueError, IndexError) as e:
            logger.error(f"❌ Error parsing page number: {e}")
            await query.answer("⚠️ خطأ في رقم الصفحة", show_alert=True)
            return STATE_SELECT_PATIENT
    elif query.data == "patient:back_to_menu":
        await render_patient_selection(query.message, context)
        return STATE_SELECT_PATIENT
    
    return STATE_SELECT_PATIENT


async def handle_patient_selection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار المريض من القائمة"""
    query = update.callback_query
    await query.answer()

    # معالجة callbacks قائمة المرضى
    if query.data.startswith("patient:show_list:") or query.data == "patient:back_to_menu":
        return await handle_patient_list_callback(update, context)
    
    # ✅ معالجة اختيار المريض من القائمة (باستخدام الفهرس)
    if query.data.startswith("patient_idx:"):
        try:
            # استخراج الفهرس
            index_str = query.data.split(":", 1)[1]
            global_index = int(index_str)
            
            # استرجاع قائمة الأسماء من context.user_data
            patient_names_list = context.user_data.get("report_tmp", {}).get("_patient_names_list", [])

            if not patient_names_list:
                # Snapshot wiped (PM2 restart) — re-render list directly so user picks from
                # a fresh authority state. Do NOT rebuild-and-resolve against stale index.
                logger.warning(
                    "_patient_names_list snapshot missing for user %s — re-rendering patient list",
                    getattr(query.from_user, "id", "?"),
                )
                await show_patient_list(update, context, page=0)
                return STATE_SELECT_PATIENT

            if global_index < 0 or global_index >= len(patient_names_list):
                logger.error(f"❌ فهرس غير صالح: {global_index}, القائمة تحتوي على {len(patient_names_list)} عنصر")
                await query.answer("⚠️ حدث خطأ في اختيار المريض", show_alert=True)
                return STATE_SELECT_PATIENT
            
            # استخدام الفهرس مباشرة (لأن القائمة مرتبة أبجدياً بالفعل)
            patient_name = patient_names_list[global_index]
            
            # حفظ اسم المريض
            context.user_data.setdefault("report_tmp", {})["patient_name"] = patient_name
            context.user_data["report_tmp"].setdefault("step_history", []).append(STATE_SELECT_PATIENT)
            
            # محاولة العثور على المريض في قاعدة البيانات (إن وجد)
            try:
                with SessionLocal() as s:
                    patient = s.query(Patient).filter_by(full_name=patient_name).first()
                    if patient:
                        context.user_data["report_tmp"]["patient_id"] = patient.id
            except Exception as e:
                logger.error(f"❌ خطأ في البحث عن المريض في قاعدة البيانات: {e}")
            
            patient_name_escaped = escape_markdown(patient_name, version=1)
            
            await query.edit_message_text(
                f"✅ **تم اختيار المريض**\n\n"
                f"👤 **المريض:**\n"
                f"{patient_name_escaped}",
                parse_mode="Markdown"
            )
            
            # تنظيف البيانات المؤقتة
            context.user_data.get("report_tmp", {}).pop("_patient_names_list", None)
            
            # الانتقال إلى اختيار المستشفى
            await show_hospitals_menu(query.message, context)
            return STATE_SELECT_HOSPITAL
        except (ValueError, IndexError) as e:
            logger.error(f"❌ خطأ في معالجة اختيار المريض (فهرس): {e}", exc_info=True)
            await query.answer("⚠️ حدث خطأ في اختيار المريض", show_alert=True)
            return STATE_SELECT_PATIENT
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة اختيار المريض: {e}", exc_info=True)
            await query.answer("⚠️ حدث خطأ في اختيار المريض", show_alert=True)
            return STATE_SELECT_PATIENT
    
    # ✅ معالجة اختيار المريض من القائمة (الطريقة القديمة - للتوافق)
    if query.data.startswith("patient_name:"):
        try:
            import base64
            name_encoded = query.data.split(":", 1)[1]
            # محاولة فك التشفير من Base64
            try:
                patient_name = base64.b64decode(name_encoded.encode('utf-8')).decode('utf-8')
            except Exception:
                # إذا فشل فك التشفير، استخدم الاسم كما هو (للتوافق مع البيانات القديمة)
                patient_name = name_encoded
            
            # حفظ اسم المريض
            context.user_data.setdefault("report_tmp", {})["patient_name"] = patient_name
            context.user_data["report_tmp"].setdefault("step_history", []).append(STATE_SELECT_PATIENT)
            
            # محاولة العثور على المريض في قاعدة البيانات (إن وجد)
            try:
                with SessionLocal() as s:
                    patient = s.query(Patient).filter_by(full_name=patient_name).first()
                    if patient:
                        context.user_data["report_tmp"]["patient_id"] = patient.id
            except Exception as e:
                logger.error(f"❌ خطأ في البحث عن المريض في قاعدة البيانات: {e}")
            
            patient_name_escaped = escape_markdown(patient_name, version=1)
            
            await query.edit_message_text(
                f"✅ **تم اختيار المريض**\n\n"
                f"👤 **المريض:**\n"
                f"{patient_name_escaped}",
                parse_mode="Markdown"
            )
            
            # الانتقال إلى اختيار المستشفى
            await show_hospitals_menu(query.message, context)
            return STATE_SELECT_HOSPITAL
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة اختيار المريض: {e}", exc_info=True)
            await query.answer("⚠️ حدث خطأ في اختيار المريض", show_alert=True)
            return STATE_SELECT_PATIENT

    # اختيار من القائمة (الطريقة القديمة)
    try:
        patient_id = int(query.data.split(":", 1)[1])

        # جلب اسم المريض من قاعدة البيانات
        with SessionLocal() as s:
            patient = s.query(Patient).filter_by(id=patient_id).first()
            if patient:
                patient_name = patient.full_name
                context.user_data["report_tmp"]["patient_name"] = patient_name
                context.user_data["report_tmp"].setdefault("step_history", []).append(R_PATIENT)
                context.user_data["report_tmp"].pop("patient_search_mode", None)

                await query.edit_message_text(
                    f"✅ **تم اختيار المريض**\n\n"
                    f"👤 **المريض:**\n"
                    f"{patient_name}"
                )
                await show_hospitals_menu(query.message, context)
                return STATE_SELECT_HOSPITAL
            else:
                await query.answer("⚠️ خطأ: لم يتم العثور على المريض", show_alert=True)
                await show_patient_selection(query.message, context)
                return STATE_SELECT_PATIENT
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة اختيار المريض: {e}", exc_info=True)
        await query.answer("⚠️ حدث خطأ في اختيار المريض", show_alert=True)
        return STATE_SELECT_PATIENT


async def handle_patient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم المريض يدوياً أو اختياره من inline query"""
    
    # التحقق أولاً إذا كان المريض تم اختياره بالفعل
    report_tmp = context.user_data.get("report_tmp", {})
    if report_tmp.get("patient_name"):
        # المريض تم اختياره بالفعل، الانتقال إلى خطوة المستشفى
        logger.info("handle_patient: Patient already selected, moving to hospital selection")
        await show_hospitals_menu(update.message, context)
        return STATE_SELECT_HOSPITAL

    text = update.message.text
    
    # التحقق إذا كانت الرسالة من اختيار inline query
    if text and text.startswith("__PATIENT_SELECTED__"):
        try:
            parts = text.split(":", 2) # Split into 3 parts: prefix, id, name
            patient_id = int(parts[1])
            patient_name = parts[2]

            # حفظ اسم المريض
            context.user_data.setdefault("report_tmp", {})["patient_name"] = patient_name
            context.user_data["report_tmp"]["patient_id"] = patient_id
            context.user_data["report_tmp"].setdefault("step_history", []).append(R_PATIENT)

            # حذف الرسالة الخاصة
            try:
                await update.message.delete()
            except:
                pass

            # إرسال رسالة تأكيد
            await update.message.reply_text(
                f"✅ **تم اختيار المريض**\n\n"
                f"👤 **المريض:**\n"
                f"{patient_name}",
                parse_mode="Markdown"
            )

            # الانتقال إلى خطوة المستشفى
            logger.info(f"handle_patient: Patient selected from inline query: {patient_name}, moving to hospital")
            await show_hospitals_menu(update.message, context)
            return STATE_SELECT_HOSPITAL
        except (ValueError, IndexError) as e:
            logger.error(f"handle_patient: Error parsing patient selection: {str(e)}")
            await update.message.reply_text("⚠️ خطأ في قراءة بيانات المريض")
            await show_patient_selection(update.message, context)
            return STATE_SELECT_PATIENT
    else:
        # تنسيق غير صحيح
        logger.warning(f"handle_patient: Invalid patient selection format: {text}")
        await show_patient_selection(update.message, context)
        return STATE_SELECT_PATIENT

