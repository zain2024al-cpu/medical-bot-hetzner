# =============================
# action_type_handlers.py
# معالجات اختيار نوع الإجراء
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging

from .states import R_ACTION_TYPE
from ..user_reports_add_helpers import PREDEFINED_ACTIONS

logger = logging.getLogger(__name__)


def _get_action_routing():
    """الحصول على ربط أنواع الإجراءات بالمسارات - يتم استدعاؤه بعد تعريف الدوال"""
    # استيراد من stub_flows.py (الذي يستورد من الملف الأصلي مؤقتاً)
    try:
        from .flows.stub_flows import (
            start_new_consultation_flow,
            start_followup_flow,
            start_periodic_followup_flow,
            start_emergency_flow,
            start_admission_flow,
            start_operation_flow,
            start_surgery_consult_flow,
            start_final_consult_flow,
            start_discharge_flow,
            start_rehab_flow,
            start_radiology_flow,
            start_reschedule_flow,
            start_radiation_therapy_flow,
            start_endoscopy_flow,
            start_chemo_flow,
            start_targeted_flow,
            start_immuno_flow,
            start_dialysis_flow,
        )
        logger.debug(f"✅ start_radiation_therapy_flow imported successfully: {start_radiation_therapy_flow}")
    except ImportError as e:
        logger.error(f"❌ Error importing flow functions: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    from .states import (
        NEW_CONSULT_COMPLAINT, FOLLOWUP_COMPLAINT, EMERGENCY_COMPLAINT,
        ADMISSION_REASON, OPERATION_DETAILS_AR, SURGERY_CONSULT_DIAGNOSIS,
        FINAL_CONSULT_DIAGNOSIS, DISCHARGE_TYPE, REHAB_TYPE, RADIOLOGY_TYPE,
        APP_RESCHEDULE_REASON, RADIATION_THERAPY_TYPE, ENDOSCOPY_COMPLAINT,
        CHEMO_MODE_CHOICE, TREATMENT_PLAN_SETUP,
    )
    
    routing_dict = {
        "استشارة جديدة": {
            "state": NEW_CONSULT_COMPLAINT,
            "flow": start_new_consultation_flow,
            "pre_process": None
        },
        "متابعة في الرقود": {
            "state": FOLLOWUP_COMPLAINT,
            "flow": start_followup_flow,
            "pre_process": None
        },
        "مراجعة / عودة دورية": {
            "state": FOLLOWUP_COMPLAINT,
            "flow": start_periodic_followup_flow,
            "pre_process": None
        },
        "استشارة مع قرار عملية": {
            "state": SURGERY_CONSULT_DIAGNOSIS,
            "flow": start_surgery_consult_flow,
            "pre_process": None
        },
        "طوارئ": {
            "state": EMERGENCY_COMPLAINT,
            "flow": start_emergency_flow,
            "pre_process": None
        },
        "عملية": {
            "state": OPERATION_DETAILS_AR,
            "flow": start_operation_flow,
            "pre_process": None
        },
        "استشارة أخيرة": {
            "state": FINAL_CONSULT_DIAGNOSIS,
            "flow": start_final_consult_flow,
            "pre_process": lambda context: context.user_data.setdefault("report_tmp", {}).update({"complaint_text": ""})
        },
        "علاج طبيعي وإعادة تأهيل": {
            "state": REHAB_TYPE,
            "flow": start_rehab_flow,
            "pre_process": None
        },
        "ترقيد": {
            "state": ADMISSION_REASON,
            "flow": start_admission_flow,
            "pre_process": None
        },
        "خروج من المستشفى": {
            "state": DISCHARGE_TYPE,
            "flow": start_discharge_flow,
            "pre_process": None
        },
        "أشعة وفحوصات": {
            "state": RADIOLOGY_TYPE,
            "flow": start_radiology_flow,
            "pre_process": None
        },
        "تأجيل موعد": {
            "state": APP_RESCHEDULE_REASON,
            "flow": start_reschedule_flow,
            "pre_process": None
        },
        "جلسة إشعاعي": {
            "state": RADIATION_THERAPY_TYPE,
            "flow": start_radiation_therapy_flow,
            "pre_process": None
        },
        "المناظير": {
            "state": ENDOSCOPY_COMPLAINT,
            "flow": start_endoscopy_flow,
            "pre_process": None
        },
        "العلاج الكيماوي": {
            "state": CHEMO_MODE_CHOICE,
            "flow": start_chemo_flow,
            "pre_process": None
        },
        "العلاج الموجه": {
            "state": TREATMENT_PLAN_SETUP,
            "flow": start_targeted_flow,
            "pre_process": None
        },
        "العلاج المناعي": {
            "state": TREATMENT_PLAN_SETUP,
            "flow": start_immuno_flow,
            "pre_process": None
        },
        "جلسات غسيل الكلى": {
            "state": TREATMENT_PLAN_SETUP,
            "flow": start_dialysis_flow,
            "pre_process": None
        },
    }

    return routing_dict


# ✅ تصنيف أزرار نوع الإجراء في قوائم فرعية (تنظيم بصري بحت — لا يغيّر أي
# منطق أو توجيه أو نموذج أو تقرير: كل زر فرعي يحتفظ بنفس callback_data
# =action_idx:{idx} السابق تماماً، فيُعالَج بنفس handle_action_type_choice).
# كل تصنيف: (مفتاح, عنوان, [(اسم الإجراء الفعلي, أيقونة العرض, تسمية العرض)]).
ACTION_CATEGORIES = [
    ("consult", "🩺 الاستشارات", [
        ("استشارة جديدة",         "🆕", "استشارة جديدة"),
        ("مراجعة / عودة دورية",    "🔄", "عودة دورية"),
        ("استشارة أخيرة",         "✅", "استشارة أخيرة"),
        ("استشارة مع قرار عملية",  "📄", "استشارة مع قرار عملية"),
    ]),
    ("admission", "🏥 الترقيد والعمليات", [
        ("ترقيد",                "🛏️", "ترقيد"),
        ("عملية",                "🔪", "عملية"),
        ("متابعة في الرقود",      "🏥", "متابعة في الرقود"),
        ("خروج من المستشفى",      "✅", "خروج من المستشفى"),
    ]),
]

# ✅ "💉 جلسات العلاج" — تصنيف مُتشعِّب على مستويين: يفتح على قسمين
# (🎗️ جلسات الأورام تتوسّع لأربعة أنواع، 🩸 جلسات غسيل الكلى يبدأ مباشرة
# بلا قائمة فرعية إضافية لأنه نوع وحيد). نفس مبدأ action_idx القديم تماماً
# لكل الأزرار الفعلية — تنظيم بصري فقط.
TREATMENT_SESSIONS_KEY = "treatment"
TREATMENT_SESSIONS_LABEL = "💉 الجلسات"
ONCOLOGY_KEY = "oncology"
ONCOLOGY_LABEL = "🎗️ جلسات الأورام"
ONCOLOGY_SUBS = [
    ("جلسة إشعاعي",       "☢️", "العلاج الإشعاعي"),
    ("العلاج الكيماوي",    "💉", "العلاج الكيماوي"),
    ("العلاج الموجه",      "🎯", "العلاج الموجه"),
    ("العلاج المناعي",     "🧬", "العلاج المناعي"),
]
DIALYSIS_LEAF = ("جلسات غسيل الكلى", "🩸", "جلسات غسيل الكلى")

# الأزرار التي تبقى مباشرة في القائمة الرئيسية (غير مصنّفة ضمن قائمة فرعية).
# ✅ الترتيب مقصود لصفوف منتظمة: تُرصَّ زوجين في الصف، و"علاج طبيعي وإعادة
# تأهيل" (تسمية طويلة) في الأخير ليأخذ صفاً كاملاً مستقلاً بدل أن يُقرَن بزرّ
# قصير فيظهر الصف غير متوازن.
_TOP_LEVEL_ACTIONS = [
    ("طوارئ",                    "🚨"),
    ("أشعة وفحوصات",             "📷"),
    ("المناظير",                 "🔬"),
    ("تأجيل موعد",               "📅"),
    ("علاج طبيعي وإعادة تأهيل",   "🏃"),
]


def _build_action_type_keyboard(page=0):
    """القائمة الرئيسية لنوع الإجراء: أزرار التصنيفات + الأزرار غير المصنّفة."""
    idx_map = {name: i for i, name in enumerate(PREDEFINED_ACTIONS)}

    keyboard = []

    # صف/صفوف أزرار التصنيفات (توسيع لقائمة فرعية عند الضغط)
    row = []
    for cat_key, cat_label, _subs in ACTION_CATEGORIES:
        row.append(InlineKeyboardButton(cat_label, callback_data=f"action_cat:{cat_key}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    row.append(InlineKeyboardButton(TREATMENT_SESSIONS_LABEL, callback_data=f"action_cat:{TREATMENT_SESSIONS_KEY}"))
    if len(row) == 2:
        keyboard.append(row)
        row = []
    if row:
        keyboard.append(row)

    # الأزرار غير المصنّفة — نفس callback القديم تماماً
    row = []
    for action_name, icon in _TOP_LEVEL_ACTIONS:
        idx = idx_map.get(action_name)
        if idx is None:
            continue
        row.append(InlineKeyboardButton(f"{icon} {action_name}", callback_data=f"action_idx:{idx}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="go_to_search_doctor_screen"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = "⚕️ **نوع الإجراء** (الخطوة 6 من 6)\n\nاختر نوع الإجراء:"
    return text, InlineKeyboardMarkup(keyboard), 1


def _build_leaves_keyboard(subs, back_target: str):
    """يبني لوحة أزرار قابلة لإعادة الاستخدام لأي قائمة إجراءات نهائية
    (action_idx) — تُستخدَم لتصنيفات القائمة الرئيسية وللمستوى الفرعي
    داخل "جلسات العلاج" على حدٍّ سواء."""
    idx_map = {name: i for i, name in enumerate(PREDEFINED_ACTIONS)}
    keyboard = []
    row = []
    for action_name, icon, display in subs:
        idx = idx_map.get(action_name)
        if idx is None:
            continue
        row.append(InlineKeyboardButton(f"{icon} {display}", callback_data=f"action_idx:{idx}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع للقائمة", callback_data=f"action_cat:{back_target}"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])
    return keyboard


def _build_category_submenu(cat_key):
    """القائمة الفرعية لتصنيف معيّن — أزرار الإجراءات بنفس callback القديم."""
    cat = next((c for c in ACTION_CATEGORIES if c[0] == cat_key), None)
    if not cat:
        return _build_action_type_keyboard()
    _key, cat_label, subs = cat
    keyboard = _build_leaves_keyboard(subs, back_target="main")
    text = f"⚕️ **{cat_label}**\n\nاختر نوع الإجراء:"
    return text, InlineKeyboardMarkup(keyboard), 1


def _build_treatment_sessions_menu():
    """المستوى الأول داخل "💉 جلسات العلاج": 🎗️ جلسات الأورام (يتوسّع أكثر)
    + 🩸 جلسات غسيل الكلى (زر مباشر بلا قائمة فرعية إضافية)."""
    idx_map = {name: i for i, name in enumerate(PREDEFINED_ACTIONS)}
    keyboard = [[InlineKeyboardButton(ONCOLOGY_LABEL, callback_data=f"action_cat:{ONCOLOGY_KEY}")]]

    dialysis_name, dialysis_icon, dialysis_display = DIALYSIS_LEAF
    idx = idx_map.get(dialysis_name)
    if idx is not None:
        keyboard.append([InlineKeyboardButton(f"{dialysis_icon} {dialysis_display}", callback_data=f"action_idx:{idx}")])

    keyboard.append([
        InlineKeyboardButton("🔙 رجوع للقائمة", callback_data="action_cat:main"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])
    text = f"⚕️ **{TREATMENT_SESSIONS_LABEL}**\n\nاختر القسم:"
    return text, InlineKeyboardMarkup(keyboard), 1


def _build_oncology_submenu():
    """المستوى الثاني: أنواع علاج الأورام الأربعة."""
    keyboard = _build_leaves_keyboard(ONCOLOGY_SUBS, back_target=TREATMENT_SESSIONS_KEY)
    text = f"⚕️ **{ONCOLOGY_LABEL}**\n\nاختر نوع الإجراء:"
    return text, InlineKeyboardMarkup(keyboard), 1


async def handle_action_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """توسيع/طي تصنيفات نوع الإجراء — تنظيم بصري فقط (بلا أي تغيير في المنطق)."""
    query = update.callback_query
    if not query:
        return R_ACTION_TYPE
    await query.answer()
    cat_key = query.data.split(":", 1)[1]
    context.user_data['_conversation_state'] = R_ACTION_TYPE
    if cat_key == "main":
        text, keyboard, _ = _build_action_type_keyboard()
    elif cat_key == TREATMENT_SESSIONS_KEY:
        text, keyboard, _ = _build_treatment_sessions_menu()
    elif cat_key == ONCOLOGY_KEY:
        text, keyboard, _ = _build_oncology_submenu()
    else:
        text, keyboard, _ = _build_category_submenu(cat_key)
    try:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"HANDLE_ACTION_CATEGORY: error rendering '{cat_key}': {e}", exc_info=True)
    return R_ACTION_TYPE


async def show_action_type_menu(message, context, page=0, query=None):
    """عرض قائمة أنواع الإجراءات المتاحة - جميع الأزرار في صفحة واحدة.
    query: إذا مُمرَّر يُعدَّل الرسالة الحالية (للرجوع). وإلا ترسل رسالة جديدة.
    """
    context.user_data['_current_search_type'] = 'action_type'
    context.user_data['last_valid_state'] = 'action_type_selection'
    context.user_data['_conversation_state'] = R_ACTION_TYPE

    logger.info("SHOW_ACTION_TYPE_MENU: Function called")
    logger.info(f"SHOW_ACTION_TYPE_MENU: Total actions = {len(PREDEFINED_ACTIONS)}")

    text, keyboard, total_pages = _build_action_type_keyboard(0)

    if query:
        try:
            await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
            logger.info("SHOW_ACTION_TYPE_MENU: Message edited successfully (restore path)")
            return
        except Exception:
            pass

    try:
        await message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
        logger.info("SHOW_ACTION_TYPE_MENU: Message sent successfully")
    except Exception as e:
        logger.error(f"SHOW_ACTION_TYPE_MENU: Error sending message: {e}", exc_info=True)
        raise


async def handle_action_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل بين صفحات أنواع الإجراءات"""
    query = update.callback_query
    if not query:
        logger.error("HANDLE_ACTION_PAGE: No callback_query in update!")
        return R_ACTION_TYPE

    await query.answer()
    
    try:
        page = int(query.data.split(":", 1)[1])
        text, keyboard, total_pages = _build_action_type_keyboard(page)
        
        if page < 0 or page >= total_pages:
            await query.answer("⚠️ رقم الصفحة غير صحيح", show_alert=True)
            return R_ACTION_TYPE
        
        context.user_data['_conversation_state'] = R_ACTION_TYPE
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
        logger.info(f"HANDLE_ACTION_PAGE: Successfully navigated to page {page}")
        return R_ACTION_TYPE
    except (ValueError, IndexError) as e:
        logger.error(f"HANDLE_ACTION_PAGE: Error parsing page number: {e}", exc_info=True)
        await query.answer("⚠️ خطأ في قراءة رقم الصفحة", show_alert=True)
        return R_ACTION_TYPE
    except Exception as e:
        logger.error(f"HANDLE_ACTION_PAGE: Error in handle_action_page: {e}", exc_info=True)
        await query.answer("⚠️ خطأ في التنقل", show_alert=True)
        return R_ACTION_TYPE


async def handle_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج لزر noop (لا يفعل شيئاً - يستخدم لعرض معلومات فقط)"""
    query = update.callback_query
    if query:
        await query.answer()
    return R_ACTION_TYPE


async def handle_stale_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج للـ callbacks القديمة من حالات سابقة"""
    query = update.callback_query
    if not query:
        return None
    
    current_state = context.user_data.get('_conversation_state', None)
    
    # ✅ إذا كان callback هو doctor_idx: وكان state = STATE_SELECT_DOCTOR، استدعاء handle_doctor_selection مباشرة
    if query.data and query.data.startswith("doctor_idx:") and current_state == STATE_SELECT_DOCTOR:
        from .doctor_handlers import handle_doctor_selection
        logger.info(f"✅ handle_stale_callback: Redirecting doctor_idx: callback to handle_doctor_selection (state={current_state})")
        return await handle_doctor_selection(update, context)
    
    try:
        await query.answer("⚠️ هذه القائمة لم تعد نشطة. يرجى استخدام القائمة الحالية.", show_alert=False)
    except Exception as e:
        logger.warning(f"⚠️ خطأ في إجابة stale callback: {e}")
    
    try:
        await query.message.delete()
    except Exception as e:
        logger.debug(f"⚠️ لا يمكن حذف الرسالة القديمة: {e}")
    
    try:
        from .hospital_handlers import show_hospitals_menu
        from .department_handlers import show_departments_menu
        from .doctor_handlers import show_doctor_input
        from .states import STATE_SELECT_HOSPITAL, STATE_SELECT_DEPARTMENT, STATE_SELECT_DOCTOR
        
        if current_state == STATE_SELECT_HOSPITAL:
            await show_hospitals_menu(query.message, context)
            return STATE_SELECT_HOSPITAL
        elif current_state == STATE_SELECT_DEPARTMENT:
            await show_departments_menu(query.message, context)
            return STATE_SELECT_DEPARTMENT
        elif current_state == STATE_SELECT_DOCTOR:
            await show_doctor_input(query.message, context)
            return STATE_SELECT_DOCTOR
        elif current_state == R_ACTION_TYPE:
            await show_action_type_menu(query.message, context)
            return R_ACTION_TYPE
    except Exception as e:
        logger.error(f"❌ خطأ في إعادة عرض القائمة: {e}", exc_info=True)
    
    return current_state if current_state is not None else R_ACTION_TYPE


async def handle_action_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار نوع الإجراء - جميع المسارات"""
    from telegram.ext import ConversationHandler
    
    query = update.callback_query
    if not query:
        logger.error("ACTION_TYPE_CHOICE: CRITICAL - No callback_query in update!")
        return R_ACTION_TYPE

    current_state = context.user_data.get('_conversation_state', 'NOT SET')
    
    logger.info(f"ACTION_TYPE_CHOICE: Callback data = {query.data}")
    logger.info(f"ACTION_TYPE_CHOICE: Current state = {current_state}")

    if query.data and query.data.startswith("action_page:"):
        return None

    if not query.data or not query.data.startswith("action_idx:"):
        logger.warning(f"ACTION_TYPE_CHOICE: Received unexpected callback data: {query.data}")
        await query.answer("⚠️ نوع بيانات غير متوقع", show_alert=True)
        return R_ACTION_TYPE

    try:
        await query.answer()
        logger.info("ACTION_TYPE_CHOICE: Callback answered successfully")
    except Exception as e:
        logger.error(f"ACTION_TYPE_CHOICE: Error answering callback: {e}", exc_info=True)

    try:
        action_idx = int(query.data.split(":", 1)[1])
        logger.info(f"ACTION_TYPE_CHOICE: Extracted action_idx = {action_idx}")

        if action_idx < 0 or action_idx >= len(PREDEFINED_ACTIONS):
            logger.error(f"ACTION_TYPE_CHOICE: Invalid action index: {action_idx}")
            await query.answer("نوع الإجراء غير صحيح", show_alert=True)
            return R_ACTION_TYPE

        action_name = PREDEFINED_ACTIONS[action_idx]
        logger.info(f"ACTION_TYPE_CHOICE: Selected action = '{action_name}' (index: {action_idx})")

        # حفظ نوع الإجراء
        context.user_data.setdefault("report_tmp", {})["medical_action"] = action_name
        context.user_data["report_tmp"]["action_type"] = action_name
        context.user_data["report_tmp"].setdefault("step_history", []).append(R_ACTION_TYPE)

        # حفظ flow_type
        action_to_flow_type = {
            "استشارة جديدة": "new_consult",
            "متابعة في الرقود": "followup",
            "مراجعة / عودة دورية": "periodic_followup",
            "استشارة مع قرار عملية": "surgery_consult",
            "طوارئ": "emergency",
            "عملية": "operation",
            "استشارة أخيرة": "final_consult",
            "علاج طبيعي وإعادة تأهيل": "rehab_physical",
            "ترقيد": "admission",
            "خروج من المستشفى": "discharge",
            "أشعة وفحوصات": "radiology",
            "تأجيل موعد": "appointment_reschedule",
            "جلسة إشعاعي": "radiation_therapy",
            "المناظير": "endoscopy",
            "العلاج الكيماوي": "treatment_chemo",
            "العلاج الموجه": "treatment_targeted",
            "العلاج المناعي": "treatment_immuno",
            "جلسات غسيل الكلى": "treatment_dialysis",
        }

        flow_type = action_to_flow_type.get(action_name, "new_consult")
        context.user_data["report_tmp"]["current_flow"] = flow_type
        logger.info(f"ACTION_TYPE_CHOICE: Flow type = '{flow_type}' for action '{action_name}'")

        # Clear nav stack — fresh flow starts here
        context.user_data['_nav_stack'] = []

        message_target = query.message if query.message else None
        if not message_target:
            logger.error("ACTION_TYPE_CHOICE: No message target available")
            await query.edit_message_text(f"تم اختيار نوع الإجراء\n\nالنوع:\n{action_name}")
            return R_ACTION_TYPE

        # البحث عن المسار المناسب
        action_routing = _get_action_routing()
        logger.info(f"ACTION_TYPE_CHOICE: Available actions in routing: {list(action_routing.keys())}")
        routing = action_routing.get(action_name)
        
        if not routing:
            logger.error(f"ACTION_TYPE_CHOICE: Unknown action type: '{action_name}'")
            logger.error(f"ACTION_TYPE_CHOICE: Available actions: {list(action_routing.keys())}")
            logger.warning(f"ACTION_TYPE_CHOICE: Using default flow (استشارة جديدة)")
            routing = action_routing.get("استشارة جديدة")
            if not routing:
                logger.error("ACTION_TYPE_CHOICE: CRITICAL - Default routing also not found!")
                await query.answer("خطأ: نوع الإجراء غير مدعوم", show_alert=True)
                return R_ACTION_TYPE
        else:
            logger.info(f"ACTION_TYPE_CHOICE: Found routing for '{action_name}': state={routing.get('state')}, flow={routing.get('flow')}")

        # تنفيذ pre_process إذا كان موجوداً
        if routing.get("pre_process"):
            logger.info(f"ACTION_TYPE_CHOICE: Executing pre_process for action: {action_name}")
            try:
                routing["pre_process"](context)
                logger.info("ACTION_TYPE_CHOICE: pre_process completed successfully")
            except Exception as e:
                logger.error(f"ACTION_TYPE_CHOICE: Error in pre_process: {e}", exc_info=True)

        try:
            await query.edit_message_text(f"تم اختيار نوع الإجراء\n\nالنوع:\n{action_name}")
            logger.info("ACTION_TYPE_CHOICE: Message updated successfully")
        except Exception as e:
            logger.error(f"ACTION_TYPE_CHOICE: Error updating message: {e}", exc_info=True)

        # استدعاء دالة بدء المسار
        try:
            flow_function = routing["flow"]
            target_state = routing["state"]
            logger.info(f"ACTION_TYPE_CHOICE: Calling flow function: {flow_function.__name__}")
            result = await flow_function(message_target, context)
            logger.info(f"ACTION_TYPE_CHOICE: Flow function returned: {result}")
            return result if result is not None else target_state
        except Exception as e:
            logger.error(f"ACTION_TYPE_CHOICE: Error calling flow function: {e}", exc_info=True)
            await query.answer("خطأ في بدء المسار", show_alert=True)
            return R_ACTION_TYPE

    except (ValueError, IndexError) as e:
        logger.error(f"ACTION_TYPE_CHOICE: Error parsing action index: {e}", exc_info=True)
        await query.answer("⚠️ خطأ في قراءة نوع الإجراء", show_alert=True)
        return R_ACTION_TYPE
    except Exception as e:
        logger.error(f"ACTION_TYPE_CHOICE: Error in handle_action_type_choice: {e}", exc_info=True)
        await query.answer("⚠️ خطأ في معالجة اختيار نوع الإجراء", show_alert=True)
        return R_ACTION_TYPE



async def handle_restart_from_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إعادة تعيين كاملة والعودة لشاشة البداية."""
    from telegram.ext import ConversationHandler
    try:
        context.user_data.clear()
    except Exception:
        pass
    try:
        from bot.handlers.user.user_start import user_start
        await user_start(update, context)
    except Exception:
        if update.message:
            await update.message.reply_text("✅ تم إعادة البدء. اختر العملية المطلوبة.")
    return ConversationHandler.END


async def handle_restart_from_start_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إعادة تعيين كاملة والعودة للقائمة الرئيسية."""
    from telegram.ext import ConversationHandler
    try:
        context.user_data.clear()
    except Exception:
        pass
    try:
        from bot.handlers.user.user_start import handle_start_main_menu
        await handle_start_main_menu(update, context)
    except Exception:
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text("✅ تم إعادة البدء. اختر العملية المطلوبة.")
    return ConversationHandler.END
