# ================================================
# bot/handlers/user/user_patient_search_inline.py
# 🔍 نظام بحث منفصل عن المرضى باستخدام Inline Query
# مربوط بقاعدة البيانات مباشرة - يعرض الأسماء المضافة حديثاً
# ================================================

from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import ContextTypes, InlineQueryHandler
from telegram.helpers import escape_markdown
import logging

# Imports قاعدة البيانات
try:
    from db.session import SessionLocal
    from db.models import Patient
except ImportError as e:
    logging.error(f"❌ خطأ في استيراد قاعدة البيانات: {e}")
    SessionLocal = None
    Patient = None

logger = logging.getLogger(__name__)


async def patient_search_inline_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    🔍 Handler منفصل للبحث عن المرضى باستخدام Inline Query
    - مربوط بقاعدة البيانات مباشرة
    - يعرض جميع الأسماء المضافة (حتى المضافة حديثاً من الأدمن)
    - بسيط وسريع
    """
    try:
        query_text = update.inline_query.query.strip() if update.inline_query.query else ""
        # إزالة "بحث: " أو "بحث:" من بداية النص إذا كان موجوداً
        if query_text.startswith("بحث: "):
            query_text = query_text[5:].strip()
        elif query_text.startswith("بحث:"):
            query_text = query_text[4:].strip()
        elif query_text.startswith("بحث "):
            query_text = query_text[4:].strip()
        elif query_text == "بحث":
            query_text = ""
        user_id = update.inline_query.from_user.id if update.inline_query.from_user else None

        logger.info("=" * 80)
        logger.info("🎯🎯🎯 PATIENT_SEARCH_INLINE_HANDLER TRIGGERED! 🎯🎯🎯")
        logger.info(f"🔍 patient_search_inline_handler: تم استدعاء البحث - النص: '{query_text}' للمستخدم {user_id}")
        logger.info(f"🔍 Query object: {update.inline_query.query if update.inline_query.query else 'None'}")
        logger.info(f"🔍 SessionLocal available: {SessionLocal is not None}")
        logger.info(f"🔍 Patient model available: {Patient is not None}")
        logger.info("=" * 80)
        
        # التحقق من توفر قاعدة البيانات
        if not SessionLocal or not Patient:
            logger.error("❌ SessionLocal أو Patient غير متاح")
            error_result = InlineQueryResultArticle(
                id="error_db",
                title="❌ خطأ في قاعدة البيانات",
                description="غير متاح حالياً",
                input_message_content=InputTextMessageContent(
                    message_text="__PATIENT_SEARCH_ERROR__:قاعدة البيانات غير متاحة"
                )
            )
            await update.inline_query.answer([error_result], cache_time=1)
            return
        
        results = []

        # ✅ نوع ظهور المريض في نتائج البحث inline: يعتمد بالكامل على جلسة
        # مُنتقي المرضى المشترك النشطة (نفس قاعدة _type_visible المستخدَمة
        # في القائمة العادية) — حتى لا يختلف ما يظهر عبر "🔍 بحث" عمّا يظهر
        # في القائمة المرقَّمة لنفس الشاشة (كانت include_companions/
        # only_companion_flow مفقودتين هنا تماماً سابقاً، فيسرّب البحث
        # مرضى "general" لشاشات مقيَّدة مثل الخدمات العامة).
        include_pharmacy = False
        include_companions = False
        only_companion_flow = False
        try:
            from shared.selectors.patient_selector._session import load as _sel_load
            _sel_state = _sel_load(context.user_data)
            if _sel_state is not None:
                include_pharmacy = _sel_state.include_pharmacy
                include_companions = _sel_state.include_companions
                only_companion_flow = _sel_state.only_companion_flow
        except Exception:
            pass

        # ✅ البحث مباشرة من قاعدة البيانات
        with SessionLocal() as s:
            try:
                if query_text:
                    # ✅ البحث عن الأسماء التي تحتوي على النص المدخل
                    patients = s.query(Patient).filter(
                        Patient.full_name.isnot(None),
                        Patient.full_name != "",
                        Patient.full_name.ilike(f"%{query_text}%")
                    ).order_by(Patient.full_name).limit(50).all()

                    logger.info(f"✅ تم العثور على {len(patients)} مريض بالبحث: '{query_text}'")
                else:
                    # ✅ إذا لم يتم إدخال نص، عرض آخر 50 مريض (الأحدث أولاً)
                    patients = s.query(Patient).filter(
                        Patient.full_name.isnot(None),
                        Patient.full_name != ""
                    ).order_by(Patient.created_at.desc(), Patient.full_name).limit(50).all()

                    logger.info(f"✅ عرض آخر {len(patients)} مريض (بدون بحث)")

                from shared.selectors.patient_selector._data import _type_visible
                patients = [
                    p for p in patients
                    if _type_visible(p.patient_type, include_pharmacy, include_companions, only_companion_flow)
                ]

                # ✅ إنشاء النتائج
                for idx, patient in enumerate(patients):
                    if not patient.full_name or not patient.full_name.strip():
                        continue

                    patient_name = patient.full_name.strip()

                    # ✅ إعداد العنوان
                    title = f"👤 {patient_name}"
                    if len(title) > 64:
                        title = f"👤 {patient_name[:60]}..."

                    # ✅ إضافة معلومات إضافية في الوصف (إن وجدت)
                    description_parts = []
                    if patient.file_number:
                        description_parts.append(f"📄 {patient.file_number}")
                    if patient.phone_number:
                        description_parts.append(f"📱 {patient.phone_number}")
                    if patient.age:
                        description_parts.append(f"🎂 {patient.age} سنة")

                    description = " | ".join(description_parts) if description_parts else "اضغط للاختيار"
                    if len(description) > 200:
                        description = description[:197] + "..."

                    # ✅ إنشاء النتيجة
                    result = InlineQueryResultArticle(
                        id=f"patient_search_{patient.id}",
                        title=title,
                        description=description,
                        input_message_content=InputTextMessageContent(
                            message_text=f"__PATIENT_SELECTED__:{patient.id}:{patient_name}"
                        )
                    )
                    results.append(result)

                logger.info(f"✅ تم إنشاء {len(results)} نتيجة للبحث")

            except Exception as db_error:
                logger.error(f"❌ خطأ في البحث من قاعدة البيانات: {db_error}", exc_info=True)
                error_result = InlineQueryResultArticle(
                    id="error_search",
                    title="❌ خطأ في البحث",
                    description=f"حدث خطأ: {str(db_error)[:100]}",
                    input_message_content=InputTextMessageContent(
                        message_text="__PATIENT_SEARCH_ERROR__:خطأ في البحث"
                    )
                )
                results.append(error_result)

        # ✅ إرسال النتائج
        if not results:
            # ✅ إذا لم توجد نتائج، إرسال رسالة توضيحية
            no_results = InlineQueryResultArticle(
                id="no_results",
                title="❌ لا توجد نتائج",
                description=f"لم يتم العثور على مرضى باسم '{query_text}'" if query_text else "لا توجد مرضى في قاعدة البيانات",
                input_message_content=InputTextMessageContent(
                    message_text="__PATIENT_SEARCH_NO_RESULTS__"
                )
            )
            results.append(no_results)
        
        # ✅ إرسال النتائج مع cache_time=1 (لا تخزين مؤقت)
        await update.inline_query.answer(results, cache_time=1)
        logger.info(f"✅ تم إرسال {len(results)} نتيجة بنجاح")
        
    except Exception as e:
        logger.error(f"❌ خطأ عام في patient_search_inline_handler: {e}", exc_info=True)
        error_result = InlineQueryResultArticle(
            id="error_general",
            title="❌ خطأ غير متوقع",
            description=f"حدث خطأ: {str(e)[:100]}",
            input_message_content=InputTextMessageContent(
                message_text="__PATIENT_SEARCH_ERROR__:خطأ غير متوقع"
            )
        )
        try:
            await update.inline_query.answer([error_result], cache_time=1)
        except:
            pass


def register(app):
    """
    تسجيل InlineQueryHandler للبحث عن المرضى
    - منفصل تماماً عن باقي النظام
    - لا يتعارض مع أي handlers أخرى
    """
    try:
        logger.info("=" * 80)
        logger.info("🎯 بدء تسجيل InlineQueryHandler للبحث عن المرضى...")
        logger.info("=" * 80)

        # ✅ تسجيل InlineQueryHandler
        # pattern=None يعني أنه سيعمل مع أي inline query
        # لكن سنستخدم switch_inline_query_current_chat في الزر
        app.add_handler(InlineQueryHandler(
            patient_search_inline_handler,
            pattern=None  # يقبل أي inline query
        ))

        logger.info("=" * 80)
        logger.info("✅ تم تسجيل user_patient_search_inline بنجاح")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ خطأ في تسجيل user_patient_search_inline: {e}", exc_info=True)

