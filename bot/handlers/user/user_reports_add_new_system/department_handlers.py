# =============================
# department_handlers.py
# معالجات اختيار القسم
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
import logging

from .states import STATE_SELECT_DEPARTMENT, STATE_SELECT_DOCTOR, R_SUBDEPARTMENT, R_DEPARTMENT
from .navigation import nav_push
from ..user_reports_add_helpers import PREDEFINED_DEPARTMENTS, DIRECT_DEPARTMENTS
from .ui_primitives import paginate, pagination_buttons

logger = logging.getLogger(__name__)


def _build_departments_keyboard(page=0, search_query="", context=None):
    """بناء لوحة مفاتيح الأقسام مع بحث - يعرض الأقسام الرئيسية فقط"""
    items_per_page = 8

    # جمع الأقسام الرئيسية فقط (بدون الفروع) - بترتيب محدد
    all_departments = []
    
    # ترتيب محدد للأقسام الرئيسية:
    priority_departments = [
        "الجراحة | Surgery",
        "الباطنية | Internal Medicine",
        "طب الأطفال | Pediatrics",
        "طب وجراحة العيون | Ophthalmology"
    ]
    
    # إضافة الأقسام ذات الأولوية أولاً
    for priority_dept in priority_departments:
        if priority_dept in PREDEFINED_DEPARTMENTS:
            all_departments.append(priority_dept)
    
    # إضافة بقية الأقسام الرئيسية (إذا لم تكن في قائمة الأولوية)
    for main_dept in PREDEFINED_DEPARTMENTS.keys():
        if main_dept not in all_departments:
            all_departments.append(main_dept)

    # إضافة الأقسام المباشرة (التي لا تحتوي على فروع)
    all_departments.extend(DIRECT_DEPARTMENTS)

    # إزالة التكرار (لكن نحافظ على الترتيب)
    seen = set()
    unique_departments = []
    for dept in all_departments:
        if dept not in seen:
            seen.add(dept)
            unique_departments.append(dept)
    all_departments = unique_departments

    # تصفية الأقسام إذا كان هناك بحث
    if search_query:
        search_lower = search_query.lower()
        filtered_depts = []
        for dept in all_departments:
            if search_lower in dept.lower():
                filtered_depts.append(dept)
        all_departments = filtered_depts

    total = len(all_departments)
    page_items, page, total_pages = paginate(all_departments, page, per_page=items_per_page)

    if context:
        context.user_data.setdefault("report_tmp", {})["departments_list"] = all_departments
        context.user_data["report_tmp"]["departments_page"] = page

    keyboard = []
    start_idx = page * items_per_page
    for i, dept_name in enumerate(page_items):
        has_subdepartments = dept_name in PREDEFINED_DEPARTMENTS
        if has_subdepartments:
            display = f"📁 {dept_name[:22]}..." if len(dept_name) > 22 else f"📁 {dept_name}"
        else:
            display = f"🏷️ {dept_name[:22]}..." if len(dept_name) > 22 else f"🏷️ {dept_name}"
        keyboard.append([InlineKeyboardButton(
            display,
            callback_data=f"dept_idx:{start_idx + i}"
        )])

    nav_row = pagination_buttons(page, total_pages, "dept_page")
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="go_to_hospital_selection"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    text = (
        f"🏷️ **اختيار القسم** (الخطوة 4 من 5)\n\n"
        f"📋 **العدد:** {total} قسم"
    )
    if search_query:
        text += f"\n🔍 **البحث:** {search_query}"
    text += f"\n📄 **الصفحة:** {page + 1} من {total_pages}\n\nاختر القسم:"

    return text, InlineKeyboardMarkup(keyboard), search_query


async def render_department_selection(message, context):
    """عرض شاشة اختيار القسم - rendering فقط"""
    text, keyboard, search = _build_departments_keyboard(0, "", context)
    context.user_data.setdefault("report_tmp", {})["departments_search"] = search

    try:
        if hasattr(message, 'delete') and message.chat_id:
            await message.delete()
    except Exception:
        pass

    await message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")


async def show_departments_menu(message, context, page=0, search_query=""):
    """Navigation wrapper - يحدث state ثم يستدعي rendering"""
    context.user_data['last_valid_state'] = 'department_selection'
    context.user_data['_conversation_state'] = STATE_SELECT_DEPARTMENT
    await render_department_selection(message, context)


async def handle_department_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج اختيار القسم"""
    query = update.callback_query
    await query.answer()

    if query.data.startswith("dept_search"):
        await query.edit_message_text(
            "🔍 **البحث عن القسم**\n\n"
            "يرجى إدخال كلمة البحث:",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")]]),
            parse_mode="Markdown"
        )
        context.user_data.setdefault("report_tmp", {})["departments_search_mode"] = True
        return STATE_SELECT_DEPARTMENT

    # استخدام index بدلاً من الاسم الكامل
    if query.data.startswith("dept_idx:"):
        dept_index = int(query.data.split(":", 1)[1])
        departments_list = context.user_data.get("report_tmp", {}).get("departments_list", [])

        if not departments_list:
            # Snapshot wiped (PM2 restart) — re-render so user picks from fresh list.
            logger.warning(
                "departments_list snapshot missing for user %s — re-rendering department selection",
                getattr(query.from_user, "id", "?"),
            )
            await query.answer()
            await render_department_selection(query.message, context)
            return STATE_SELECT_DEPARTMENT

        if 0 <= dept_index < len(departments_list):
            dept = departments_list[dept_index]
        else:
            logger.error("dept_idx %d out of range (list len %d)", dept_index, len(departments_list))
            await query.answer("⚠️ خطأ في اختيار القسم، يرجى المحاولة مرة أخرى.", show_alert=True)
            return STATE_SELECT_DEPARTMENT
    else:
        dept = query.data.split(":", 1)[1]

    report_tmp = context.user_data.setdefault("report_tmp", {})
    report_tmp.pop("departments_search", None)
    report_tmp.pop("departments_search_mode", None)
    report_tmp.pop("departments_list", None)

    # ✅ تم نقل "أشعة وفحوصات" إلى قائمة أنواع الإجراءات
    # لا حاجة لمعالج خاص هنا - يجب اختيارها من قائمة أنواع الإجراءات

    # التحقق إذا كان القسم المختار هو قسم رئيسي يحتوي على فروع
    if dept in PREDEFINED_DEPARTMENTS:
        context.user_data.setdefault("report_tmp", {})["main_department"] = dept
        await query.edit_message_text(
            f"✅ **تم اختيار القسم الرئيسي**\n\n"
            f"🏷️ **القسم:**\n"
            f"{dept}\n\n"
            f"يرجى اختيار التخصص الفرعي:"
        )
        await show_subdepartment_options(query.message, context, dept)
        return R_SUBDEPARTMENT
    else:
        from .doctor_handlers import show_doctor_input
        report_tmp = context.user_data.setdefault("report_tmp", {})
        report_tmp["department_name"] = dept
        report_tmp.setdefault("step_history", []).append(R_DEPARTMENT)
        
        # ✅ تحديث state إلى STATE_SELECT_DOCTOR قبل الانتقال
        nav_push(context, STATE_SELECT_DOCTOR)
        context.user_data['_conversation_state'] = STATE_SELECT_DOCTOR

        await query.edit_message_text(
            f"✅ **تم اختيار القسم**\n\n"
            f"🏷️ **القسم:**\n"
            f"{dept}"
        )
        await show_doctor_input(query.message, context)
        return STATE_SELECT_DOCTOR


async def handle_department_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج التنقل بين صفحات الأقسام"""
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":", 1)[1])
    search = context.user_data.get("report_tmp", {}).get("departments_search", "")
    text, keyboard, search = _build_departments_keyboard(page, search, context)
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    return STATE_SELECT_DEPARTMENT


async def handle_department_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج البحث في الأقسام"""
    if update.message:
        search_mode = context.user_data.get("report_tmp", {}).get("departments_search_mode", False)
        if search_mode:
            search_query = update.message.text.strip()
            report_tmp = context.user_data.setdefault("report_tmp", {})
            report_tmp["departments_search"] = search_query
            report_tmp["departments_search_mode"] = False
            text, keyboard, _ = _build_departments_keyboard(0, search_query, context)
            await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
            return STATE_SELECT_DEPARTMENT
        else:
            return STATE_SELECT_DEPARTMENT


async def show_subdepartment_options(message, context, main_dept, page=0):
    """عرض التخصصات الفرعية - مع إدارة State History"""
    from .states import STATE_SELECT_SUBDEPARTMENT
    nav_push(context, STATE_SELECT_SUBDEPARTMENT)
    context.user_data['_conversation_state'] = STATE_SELECT_SUBDEPARTMENT
    
    subdepts = PREDEFINED_DEPARTMENTS.get(main_dept, [])
    total = len(subdepts)
    page_items, page, total_pages = paginate(subdepts, page, per_page=8)

    report_tmp = context.user_data.setdefault("report_tmp", {})
    report_tmp["subdepartments_list"] = subdepts
    report_tmp["main_department"] = main_dept

    keyboard = []
    start_idx = page * 8
    for i, name in enumerate(page_items):
        keyboard.append([InlineKeyboardButton(
            f"🏥 {name}",
            callback_data=f"subdept_idx:{start_idx + i}"
        )])

    nav_row = pagination_buttons(page, total_pages, "subdept_page")
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton(
        "🔙 رجوع", callback_data="nav:back")])
    keyboard.append([InlineKeyboardButton(
        "❌ إلغاء", callback_data="nav:cancel")])

    await message.reply_text(
        f"🏥 **{main_dept}** (صفحة {page + 1}/{total_pages})\n\n"
        f"اختر التخصص الفرعي:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def handle_subdepartment_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار التخصص الفرعي"""
    from .doctor_handlers import show_doctor_input
    
    query = update.callback_query
    await query.answer()

    data_parts = query.data.split(":", 1)
    if len(data_parts) < 2:
        await query.answer("⚠️ خطأ في البيانات", show_alert=True)
        return R_SUBDEPARTMENT

    choice = data_parts[1]

    if choice == "back":
        await query.message.delete()
        await show_departments_menu(query.message, context)
        return STATE_SELECT_DEPARTMENT

    # subdept_idx: format (standard path) — resolve IDX against snapshot
    if query.data.startswith("subdept_idx:"):
        idx = int(query.data.split(":", 1)[1])
        report_tmp = context.user_data.get("report_tmp", {})
        subdepts = report_tmp.get("subdepartments_list", [])

        if not subdepts:
            # Snapshot wiped (PM2 restart) — cascaded recovery:
            # if main_department is known, re-render subdept screen;
            # otherwise fall back to department selection.
            main_dept = report_tmp.get("main_department", "")
            logger.warning(
                "subdepartments_list snapshot missing for user %s (main_dept=%r) — cascaded re-render",
                getattr(query.from_user, "id", "?"), main_dept,
            )
            await query.answer()
            if main_dept:
                await show_subdepartment_options(query.message, context, main_dept)
                return R_SUBDEPARTMENT
            else:
                await render_department_selection(query.message, context)
                return STATE_SELECT_DEPARTMENT

        if 0 <= idx < len(subdepts):
            choice = subdepts[idx]
        else:
            logger.error("subdept_idx %d out of range (list len %d)", idx, len(subdepts))
            await query.answer("⚠️ خطأ في الفهرس", show_alert=True)
            return R_SUBDEPARTMENT

    report_tmp = context.user_data.setdefault("report_tmp", {})
    report_tmp["department_name"] = choice
    report_tmp.setdefault("step_history", []).append(R_SUBDEPARTMENT)

    context.user_data['last_valid_state'] = 'search_doctor_screen'
    context.user_data['_conversation_state'] = STATE_SELECT_DOCTOR

    await query.edit_message_text(f"✅ تم اختيار القسم: {choice}")
    await show_doctor_input(query.message, context)

    return STATE_SELECT_DOCTOR


async def handle_subdepartment_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة التنقل بين صفحات التخصصات الفرعية"""
    query = update.callback_query
    await query.answer()

    page = int(query.data.split(":", 1)[1])
    main_dept = context.user_data.get("report_tmp", {}).get("main_department", "")

    if not main_dept:
        # main_department wiped (PM2 restart) — fall back to department selection
        logger.warning(
            "main_department missing during subdept page nav for user %s — re-rendering department selection",
            getattr(query.from_user, "id", "?"),
        )
        await render_department_selection(query.message, context)
        return STATE_SELECT_DEPARTMENT

    await query.message.delete()
    await show_subdepartment_options(query.message, context, main_dept, page)
    return R_SUBDEPARTMENT

