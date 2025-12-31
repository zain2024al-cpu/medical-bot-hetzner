# =============================
# inline_query.py
# معالجات Inline Query - البحث الذكي
# =============================

from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes
import logging

from .patient_handlers import patient_inline_query_handler

logger = logging.getLogger(__name__)

# Imports المشتركة
try:
    from db.session import SessionLocal
except ImportError:
    SessionLocal = None

try:
    from db.models import Translator, Doctor
except ImportError:
    Translator = Doctor = None


async def doctor_inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler بسيط للبحث عن الأطباء مع فلترة حسب المستشفى والقسم"""
    from services.doctors_smart_search import search_doctors
    
    logger.info("🎯 DOCTOR SEARCH STARTED")
    try:
        query_text = update.inline_query.query.strip() if update.inline_query.query else ""
        report_tmp = context.user_data.get("report_tmp", {})
        hospital_name = report_tmp.get("hospital_name", "").strip()
        department_name = report_tmp.get("department_name", "").strip()

        # تحويل أسماء المستشفيات المختصرة إلى الأسماء الكاملة
        hospital_mapping = {
            "Aster CMI": "Aster CMI Hospital, Bangalore",
            "Aster RV": "Aster RV Hospital, Bangalore",
            "Aster Whitefield": "Aster Whitefield Hospital, Bangalore",
            "Manipal Hospital - Old Airport Road": "Manipal Hospital, Old Airport Road, Bangalore",
            "Manipal Hospital - Millers Road": "Manipal Hospital, Millers Road, Bangalore",
            "Manipal Hospital - Whitefield": "Manipal Hospital, Whitefield, Bangalore",
            "Manipal Hospital - Yeshwanthpur": "Manipal Hospital, Yeshwanthpur, Bangalore",
            "Manipal Hospital - Sarjapur Road": "Manipal Hospital, Sarjapur Road, Bangalore",
        }

        full_hospital_name = hospital_mapping.get(hospital_name, hospital_name)

        # استخدام دالة البحث الذكية (ليست async)
        doctors_results = search_doctors(
            query=query_text if query_text else "",
            hospital=full_hospital_name if full_hospital_name else None,
            department=department_name if department_name else None,
            limit=20
        )

        results = []
        for idx, doctor in enumerate(doctors_results):
            name = doctor.get('name', 'طبيب بدون اسم')
            doctor_hospital = doctor.get('hospital', 'مستشفى غير محدد')
            department_display = doctor.get('department_ar', doctor.get('department_en', 'قسم غير محدد'))

            result = InlineQueryResultArticle(
                id=f"doc_{idx}",
                title=f"👨‍⚕️ {name}",
                description=f"🏥 {doctor_hospital[:30]} | 📋 {department_display[:30]}",
                input_message_content=InputTextMessageContent(
                    message_text=f"__DOCTOR_SELECTED__:{idx}:{name}"
                )
            )
            results.append(result)

        if not results:
            result = InlineQueryResultArticle(
                id="doctor_no_results",
                title="❌ لا توجد نتائج",
                description="لم يتم العثور على أطباء",
                input_message_content=InputTextMessageContent(
                    message_text="__DOCTOR_SELECTED__:0:غير محدد"
                )
            )
            results.append(result)

        await update.inline_query.answer(results, cache_time=1)
        logger.info(f"✅ doctor_inline_query_handler: Sent {len(results)} results")

    except Exception as e:
        logger.error(f"❌ خطأ في doctor_inline_query_handler: {e}", exc_info=True)
        error_result = InlineQueryResultArticle(
            id="doctor_error",
            title="❌ خطأ في البحث",
            description=f"حدث خطأ: {str(e)[:100]}",
            input_message_content=InputTextMessageContent(
                message_text="__DOCTOR_SELECTED__:0:خطأ"
            )
        )
        await update.inline_query.answer([error_result], cache_time=1)


async def translator_inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler منفصل للبحث عن المترجمين فقط"""
    query_text = update.inline_query.query.strip() if update.inline_query.query else ""
    logger.info(f"🔍 translator_inline_query_handler: Searching translators with query='{query_text}'")

    results = []

    try:
        if SessionLocal and Translator:
            with SessionLocal() as s:
                if query_text:
                    translators = s.query(Translator).filter(
                        Translator.is_approved == True,
                        Translator.is_active == True,
                        Translator.full_name.isnot(None),
                        Translator.full_name != "",
                        Translator.tg_user_id.is_(None),
                        Translator.full_name.ilike(f"%{query_text}%")
                    ).order_by(Translator.full_name).limit(50).all()
                else:
                    translators = s.query(Translator).filter(
                        Translator.is_approved == True,
                        Translator.is_active == True,
                        Translator.full_name.isnot(None),
                        Translator.full_name != "",
                        Translator.tg_user_id.is_(None)
                    ).order_by(Translator.full_name).limit(50).all()

                for translator in translators:
                    result = InlineQueryResultArticle(
                        id=f"translator_{translator.id}",
                        title=f"👤 {translator.full_name}",
                        description=f"اختر هذا المترجم",
                        input_message_content=InputTextMessageContent(
                            message_text=f"__TRANSLATOR_SELECTED__:{translator.id}:{translator.full_name}"
                        )
                    )
                    results.append(result)

            logger.info(f"translator_inline_query_handler: Found {len(results)} translators from database")

    except Exception as db_error:
        logger.error(f"❌ خطأ في البحث عن المترجمين من قاعدة البيانات: {db_error}")

    if not results:
        result = InlineQueryResultArticle(
            id="translator_no_results",
            title="❌ لا توجد نتائج",
            description="لم يتم العثور على مترجمين",
            input_message_content=InputTextMessageContent(
                message_text="__TRANSLATOR_SELECTED__:0:غير محدد"
            )
        )
        results.append(result)
    
    await update.inline_query.answer(results, cache_time=1)
    logger.info(f"translator_inline_query_handler: Sent {len(results)} results to Telegram")


async def unified_inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler موحد للبحث - يحدد النوع بناءً على علامة البحث"""
    query_text = update.inline_query.query.strip() if update.inline_query.query else ""
    logger.info("="*80)
    logger.info("🎯🎯🎯 UNIFIED_INLINE_QUERY_HANDLER TRIGGERED (FROM SEGMENTED FILES)! 🎯🎯🎯")
    logger.info("="*80)

    report_tmp = context.user_data.get("report_tmp", {})
    search_type = context.user_data.get('_current_search_type')
    initial_case_search = context.user_data.get("initial_case_search")
    
    if not search_type:
        search_type = 'patient'
        context.user_data['_current_search_type'] = 'patient'
        logger.info("🎯 Search type was not set, defaulting to 'patient'")
    
    logger.info(f"🎯 Report TMP exists: {bool(report_tmp)}")
    logger.info(f"🎯 Search type: {search_type}")
    logger.info(f"🎯 Initial case search: {initial_case_search}")
    logger.info(f"🎯 Query text: '{query_text}'")
    
    # التحقق: هل المستخدم في وضع التقرير الأولي فقط؟
    if initial_case_search is not None and initial_case_search.get("active") is True and not report_tmp:
        logger.info("🎯 User is in initial case search mode - calling initial case handler")
        from bot.handlers.user.user_initial_case import handle_initial_case_inline_query
        await handle_initial_case_inline_query(update, context)
        return

    # البحث عن الأطباء
    if search_type == 'doctor':
        if not report_tmp:
            logger.info("🎯 No report_tmp for doctor search, returning empty results")
            await update.inline_query.answer([], cache_time=1)
            return
        logger.info("🎯 Calling doctor search")
        await doctor_inline_query_handler(update, context)
        return
    
    # البحث عن المترجمين
    if search_type == 'translator':
        logger.info("🎯 Calling translator search")
        await translator_inline_query_handler(update, context)
        return
    
    # البحث عن المرضى (افتراضي)
    logger.info("🎯 Calling patient search (default or fallback)")
    logger.info("🎯 About to call patient_inline_query_handler from patient_handlers.py")
    try:
        await patient_inline_query_handler(update, context)
        logger.info("✅ patient_inline_query_handler completed successfully")
    except Exception as e:
        logger.error(f"❌ Error in patient_inline_query_handler: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        error_result = InlineQueryResultArticle(
            id="patient_error",
            title="❌ خطأ في البحث",
            description=f"حدث خطأ: {str(e)[:100]}",
            input_message_content=InputTextMessageContent(
                message_text="__PATIENT_SELECTED__:0:خطأ"
            )
        )
        await update.inline_query.answer([error_result], cache_time=1)
    return

