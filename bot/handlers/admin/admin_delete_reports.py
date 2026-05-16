# ================================================
# bot/handlers/admin/admin_delete_reports.py
# 🗑️ نظام حذف التقارير للأدمن
# - اختيار التاريخ (سنة، شهر، يوم)
# - عرض التقارير
# - حذف فردي أو جماعي
# ================================================

import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, MessageHandler, CallbackQueryHandler, filters
)
from bot.shared_auth import is_admin
from bot.keyboards import admin_main_kb
from db.session import SessionLocal
from db.models import Report
try:
    from config.settings import ADMIN_IDS
except Exception:
    ADMIN_IDS = []

logger = logging.getLogger(__name__)


def _ist_now() -> datetime:
    """الوقت الحالي بتوقيت IST (UTC+5:30) بدون tzinfo — يطابق طريقة حفظ report_date."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)
    except Exception:
        from datetime import timezone
        ist = timezone(timedelta(hours=5, minutes=30))
        return datetime.now(timezone.utc).astimezone(ist).replace(tzinfo=None)


def _day_range_ist(year: int, month: int, day: int):
    """
    يُرجع (start, end) بتوقيت IST ليوم واحد.
    day=0 يعني كل الشهر.
    """
    if day == 0:
        start = datetime(year, month, 1)
        if month == 12:
            end = datetime(year + 1, 1, 1)
        else:
            end = datetime(year, month + 1, 1)
    else:
        start = datetime(year, month, day)
        end = start + timedelta(days=1)
    return start, end

# ============================================
# الأيقونات والثوابت
# ============================================
ITEMS_PER_PAGE = 8  # عدد التقارير في كل صفحة


# ============================================
# 1. زر حذف التقارير - نقطة البداية
# ============================================
async def start_delete_reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بداية مسار حذف التقارير - عرض السنوات"""
    user = update.effective_user
    if not is_admin(user.id):
        from bot.handlers.user.user_reports_delete import start_delete_reports as user_start_delete_reports
        return await user_start_delete_reports(update, context)

    # مسح بيانات الحذف السابقة
    context.user_data.pop('delete_reports', None)

    # عرض اختيار السنة
    await _show_year_selection(update.message, context)


async def _year_keyboard() -> InlineKeyboardMarkup:
    """بناء لوحة أزرار السنوات من السنوات الموجودة فعلاً في DB."""
    from sqlalchemy import extract
    with SessionLocal() as s:
        db_years = [
            int(r[0]) for r in
            s.query(extract('year', Report.report_date))
             .filter(Report.report_date.isnot(None))
             .group_by(extract('year', Report.report_date))
             .order_by(extract('year', Report.report_date).desc())
             .all()
        ]
    if not db_years:
        db_years = [_ist_now().year]

    buttons = []
    row = []
    for year in db_years:
        row.append(InlineKeyboardButton(f"📅 {year}", callback_data=f"delrep:year:{year}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="delrep:cancel")])
    return InlineKeyboardMarkup(buttons)


async def _show_year_selection(message, context):
    """عرض أزرار اختيار السنة"""
    await message.reply_text(
        "🗑️ **حذف التقارير**\n\nاختر السنة:",
        reply_markup=await _year_keyboard(),
        parse_mode="Markdown"
    )


# ============================================
# 2. اختيار السنة → عرض الأشهر
# ============================================
async def handle_year_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار السنة وعرض الأشهر"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not is_admin(user.id):
        await query.edit_message_text("🚫 غير مصرح.")
        return

    year = int(query.data.split(":")[2])
    context.user_data.setdefault('delete_reports', {})['year'] = year

    months_ar = [
        "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
        "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
    ]

    buttons = []
    for i in range(0, 12, 3):
        row = []
        for j in range(3):
            month_num = i + j + 1
            row.append(InlineKeyboardButton(
                f"{months_ar[month_num - 1]}",
                callback_data=f"delrep:month:{month_num}"
            ))
        buttons.append(row)

    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="delrep:back_to_year")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="delrep:cancel")])

    await query.edit_message_text(
        f"🗑️ **حذف التقارير**\n\n"
        f"📅 السنة: **{year}**\n\n"
        f"اختر الشهر:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


# ============================================
# 3. اختيار الشهر → عرض الأيام
# ============================================
async def handle_month_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار الشهر وعرض الأيام"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not is_admin(user.id):
        await query.edit_message_text("🚫 غير مصرح.")
        return

    month = int(query.data.split(":")[2])
    year = context.user_data.get('delete_reports', {}).get('year', _ist_now().year)
    context.user_data.setdefault('delete_reports', {})['month'] = month

    months_ar = [
        "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
        "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
    ]

    # حساب عدد أيام الشهر
    if month == 12:
        days_in_month = (datetime(year + 1, 1, 1) - datetime(year, month, 1)).days
    else:
        days_in_month = (datetime(year, month + 1, 1) - datetime(year, month, 1)).days

    # خيار "كل الشهر"
    buttons = [[InlineKeyboardButton("📋 كل الشهر", callback_data="delrep:day:0")]]

    # أزرار الأيام (7 أيام في كل صف)
    row = []
    for day in range(1, days_in_month + 1):
        row.append(InlineKeyboardButton(str(day), callback_data=f"delrep:day:{day}"))
        if len(row) == 7:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="delrep:back_to_month")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="delrep:cancel")])

    await query.edit_message_text(
        f"🗑️ **حذف التقارير**\n\n"
        f"📅 التاريخ: **{months_ar[month - 1]} {year}**\n\n"
        f"اختر اليوم (أو كل الشهر):",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


# ============================================
# 4. اختيار اليوم → عرض التقارير
# ============================================
async def handle_day_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار اليوم وعرض التقارير"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not is_admin(user.id):
        await query.edit_message_text("🚫 غير مصرح.")
        return

    day = int(query.data.split(":")[2])
    data = context.user_data.get('delete_reports', {})
    year = data.get('year', _ist_now().year)
    month = data.get('month', _ist_now().month)
    context.user_data.setdefault('delete_reports', {})['day'] = day
    context.user_data['delete_reports']['page'] = 0

    await _show_reports_page(query, context, year, month, day, page=0)


async def _show_reports_page(query, context, year, month, day, page=0):
    """عرض صفحة من التقارير"""
    months_ar = [
        "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
        "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
    ]

    start_date, end_date = _day_range_ist(year, month, day)
    date_label = f"{months_ar[month - 1]} {year}" if day == 0 else f"{day} {months_ar[month - 1]} {year}"

    with SessionLocal() as session:
        # بناء الفلتر — report_date مخزّن بـ IST لذا الحدود بـ IST أيضاً
        q = session.query(Report).filter(
            Report.report_date >= start_date,
            Report.report_date < end_date
        ).order_by(Report.report_date.desc())

        total_count = q.count()
        reports = q.offset(page * ITEMS_PER_PAGE).limit(ITEMS_PER_PAGE).all()

        if total_count == 0:
            buttons = [
                [InlineKeyboardButton("🔙 رجوع", callback_data="delrep:back_to_day")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="delrep:cancel")]
            ]
            await query.edit_message_text(
                f"🗑️ **حذف التقارير**\n\n"
                f"📅 التاريخ: **{date_label}**\n\n"
                f"⚠️ لا توجد تقارير في هذا التاريخ.",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown"
            )
            return

        total_pages = (total_count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

        # بناء النص
        text = (
            f"🗑️ **حذف التقارير**\n\n"
            f"📅 التاريخ: **{date_label}**\n"
            f"📊 عدد التقارير: **{total_count}**\n"
            f"📄 الصفحة: **{page + 1}/{total_pages}**\n\n"
        )

        # عرض التقارير
        buttons = []
        for report in reports:
            # بناء وصف مختصر
            patient = report.patient_name or "غير محدد"
            action = report.medical_action or "غير محدد"
            hospital = report.hospital_name or ""
            time_str = report.report_date.strftime("%H:%M") if report.report_date else ""
            translator = report.translator_name or ""

            label = f"🔸 {patient} | {action}"
            if hospital:
                label += f" | {hospital}"

            text += (
                f"📌 **#{report.id}** - {time_str}\n"
                f"   👤 {patient} | 📋 {action}\n"
                f"   🏥 {hospital} | 👨‍⚕️ {report.doctor_name or '-'}\n"
                f"   🌐 {translator}\n\n"
            )

            buttons.append([InlineKeyboardButton(
                f"🗑️ حذف #{report.id} - {patient[:15]}",
                callback_data=f"delrep:delete:{report.id}"
            )])

        # أزرار التنقل بين الصفحات
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀️ السابق", callback_data=f"delrep:page:{page - 1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("التالي ▶️", callback_data=f"delrep:page:{page + 1}"))
        if nav_row:
            buttons.append(nav_row)

        # زر حذف الكل
        if total_count > 0:
            buttons.append([InlineKeyboardButton(
                f"⚠️ حذف الكل ({total_count} تقرير)",
                callback_data="delrep:confirm_all"
            )])

        buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="delrep:back_to_day")])
        buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="delrep:cancel")])

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown"
        )


# ============================================
# 5. التنقل بين الصفحات
# ============================================
async def handle_page_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """التنقل بين صفحات التقارير"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not is_admin(user.id):
        return

    page = int(query.data.split(":")[2])
    data = context.user_data.get('delete_reports', {})
    year = data.get('year', _ist_now().year)
    month = data.get('month', _ist_now().month)
    day = data.get('day', 0)
    context.user_data['delete_reports']['page'] = page

    await _show_reports_page(query, context, year, month, day, page)


# ============================================
# 6. حذف تقرير فردي
# ============================================
async def handle_delete_single(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد حذف تقرير فردي"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not is_admin(user.id):
        return

    report_id = int(query.data.split(":")[2])

    with SessionLocal() as session:
        report = session.query(Report).filter_by(id=report_id).first()
        if not report:
            await query.edit_message_text("⚠️ التقرير غير موجود.")
            return

        patient = report.patient_name or "غير محدد"
        action = report.medical_action or "غير محدد"
        hospital = report.hospital_name or "غير محدد"
        date_str = report.report_date.strftime("%Y-%m-%d %H:%M") if report.report_date else "غير محدد"

    buttons = [
        [
            InlineKeyboardButton("✅ نعم، احذف", callback_data=f"delrep:confirmed:{report_id}"),
            InlineKeyboardButton("❌ لا، رجوع", callback_data="delrep:back_to_list"),
        ]
    ]

    await query.edit_message_text(
        f"⚠️ **تأكيد الحذف**\n\n"
        f"هل تريد حذف هذا التقرير؟\n\n"
        f"📌 **رقم التقرير:** #{report_id}\n"
        f"👤 **المريض:** {patient}\n"
        f"📋 **الإجراء:** {action}\n"
        f"🏥 **المستشفى:** {hospital}\n"
        f"📅 **التاريخ:** {date_str}\n\n"
        f"⚠️ **هذا الإجراء لا يمكن التراجع عنه!**",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


# ============================================
# 7. تنفيذ الحذف الفردي
# ============================================
async def handle_confirmed_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ حذف تقرير فردي"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not is_admin(user.id):
        return

    report_id = int(query.data.split(":")[2])

    with SessionLocal() as session:
        report = session.query(Report).filter_by(id=report_id).first()
        if not report:
            await query.edit_message_text("⚠️ التقرير غير موجود أو تم حذفه مسبقاً.")
            return

        patient = report.patient_name or "غير محدد"
        session.delete(report)
        session.commit()
        logger.info(f"🗑️ Admin {user.id} deleted report #{report_id} (patient: {patient})")

    # عرض رسالة النجاح مع زر العودة
    buttons = [
        [InlineKeyboardButton("🔙 العودة للقائمة", callback_data="delrep:back_to_list")],
        [InlineKeyboardButton("❌ إنهاء", callback_data="delrep:cancel")]
    ]

    await query.edit_message_text(
        f"✅ **تم حذف التقرير بنجاح!**\n\n"
        f"📌 رقم التقرير: #{report_id}\n"
        f"👤 المريض: {patient}",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


# ============================================
# 8. تأكيد حذف الكل
# ============================================
async def handle_confirm_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأكيد حذف جميع تقارير الفترة"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not is_admin(user.id):
        return

    data = context.user_data.get('delete_reports', {})
    year = data.get('year', _ist_now().year)
    month = data.get('month', _ist_now().month)
    day = data.get('day', 0)

    months_ar = [
        "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
        "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
    ]

    if day == 0:
        date_label = f"{months_ar[month - 1]} {year}"
    else:
        date_label = f"{day} {months_ar[month - 1]} {year}"

    start_date, end_date = _day_range_ist(year, month, day)

    with SessionLocal() as session:
        count = session.query(Report).filter(
            Report.report_date >= start_date,
            Report.report_date < end_date
        ).count()

    buttons = [
        [
            InlineKeyboardButton(f"⚠️ نعم، احذف الكل ({count})", callback_data="delrep:delete_all_confirmed"),
            InlineKeyboardButton("❌ لا، رجوع", callback_data="delrep:back_to_list"),
        ]
    ]

    await query.edit_message_text(
        f"🚨 **تحذير: حذف جماعي!**\n\n"
        f"📅 الفترة: **{date_label}**\n"
        f"📊 عدد التقارير: **{count}**\n\n"
        f"⚠️ **سيتم حذف جميع التقارير في هذه الفترة!**\n"
        f"❌ **هذا الإجراء لا يمكن التراجع عنه!**\n\n"
        f"هل أنت متأكد؟",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


# ============================================
# 9. تنفيذ حذف الكل
# ============================================
async def handle_delete_all_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنفيذ حذف جميع التقارير"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not is_admin(user.id):
        return

    data = context.user_data.get('delete_reports', {})
    year = data.get('year', _ist_now().year)
    month = data.get('month', _ist_now().month)
    day = data.get('day', 0)

    start_date, end_date = _day_range_ist(year, month, day)

    with SessionLocal() as session:
        count = session.query(Report).filter(
            Report.report_date >= start_date,
            Report.report_date < end_date
        ).delete(synchronize_session=False)
        session.commit()

    logger.info(f"🗑️ Admin {user.id} bulk-deleted {count} reports for {year}-{month}-{day or 'all'}")

    months_ar = [
        "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
        "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
    ]
    if day == 0:
        date_label = f"{months_ar[month - 1]} {year}"
    else:
        date_label = f"{day} {months_ar[month - 1]} {year}"

    buttons = [
        [InlineKeyboardButton("🗑️ حذف تقارير أخرى", callback_data="delrep:restart")],
        [InlineKeyboardButton("❌ إنهاء", callback_data="delrep:cancel")]
    ]

    await query.edit_message_text(
        f"✅ **تم الحذف الجماعي بنجاح!**\n\n"
        f"📅 الفترة: **{date_label}**\n"
        f"🗑️ عدد التقارير المحذوفة: **{count}**",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


# ============================================
# 10. أزرار الرجوع والإلغاء
# ============================================
async def handle_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أزرار الرجوع والإلغاء"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if not is_admin(user.id):
        return

    action = query.data.replace("delrep:", "")

    if action == "cancel":
        context.user_data.pop('delete_reports', None)
        await query.edit_message_text(
            "✅ تم إلغاء عملية حذف التقارير.",
            reply_markup=None
        )
        # إرسال لوحة المفاتيح الرئيسية
        await query.message.reply_text(
            "👑 لوحة التحكم:",
            reply_markup=admin_main_kb()
        )

    elif action == "back_to_year":
        await query.edit_message_text(
            "🗑️ **حذف التقارير**\n\naختر السنة:",
            reply_markup=await _year_keyboard(),
            parse_mode="Markdown"
        )

    elif action == "back_to_month":
        # العودة لاختيار الشهر
        year = context.user_data.get('delete_reports', {}).get('year', _ist_now().year)
        # إعادة عرض الأشهر
        await _show_months(query, year)

    elif action == "back_to_day":
        # العودة لاختيار اليوم
        data = context.user_data.get('delete_reports', {})
        year = data.get('year', _ist_now().year)
        month = data.get('month', _ist_now().month)
        # إعادة عرض الأيام
        await _show_days(query, year, month)

    elif action == "back_to_list":
        # العودة لقائمة التقارير
        data = context.user_data.get('delete_reports', {})
        year = data.get('year', _ist_now().year)
        month = data.get('month', _ist_now().month)
        day = data.get('day', 0)
        page = data.get('page', 0)
        await _show_reports_page(query, context, year, month, day, page)

    elif action == "restart":
        context.user_data.pop('delete_reports', None)
        await query.edit_message_text(
            "🗑️ **حذف التقارير**\n\naختر السنة:",
            reply_markup=await _year_keyboard(),
            parse_mode="Markdown"
        )


async def _show_months(query, year):
    """عرض أزرار الأشهر"""
    months_ar = [
        "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
        "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
    ]

    buttons = []
    for i in range(0, 12, 3):
        row = []
        for j in range(3):
            month_num = i + j + 1
            row.append(InlineKeyboardButton(
                f"{months_ar[month_num - 1]}",
                callback_data=f"delrep:month:{month_num}"
            ))
        buttons.append(row)

    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="delrep:back_to_year")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="delrep:cancel")])

    await query.edit_message_text(
        f"🗑️ **حذف التقارير**\n\n"
        f"📅 السنة: **{year}**\n\n"
        f"اختر الشهر:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


async def _show_days(query, year, month):
    """عرض أزرار الأيام"""
    months_ar = [
        "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
        "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"
    ]

    if month == 12:
        days_in_month = (datetime(year + 1, 1, 1) - datetime(year, month, 1)).days
    else:
        days_in_month = (datetime(year, month + 1, 1) - datetime(year, month, 1)).days

    buttons = [[InlineKeyboardButton("📋 كل الشهر", callback_data="delrep:day:0")]]

    row = []
    for day in range(1, days_in_month + 1):
        row.append(InlineKeyboardButton(str(day), callback_data=f"delrep:day:{day}"))
        if len(row) == 7:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data="delrep:back_to_month")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="delrep:cancel")])

    await query.edit_message_text(
        f"🗑️ **حذف التقارير**\n\n"
        f"📅 التاريخ: **{months_ar[month - 1]} {year}**\n\n"
        f"اختر اليوم (أو كل الشهر):",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


# ============================================
# تسجيل الهاندلرز
# ============================================
def register(app):
    """تسجيل جميع handlers حذف التقارير للأدمن"""

    # زر لوحة المفاتيح الرئيسية
    app.add_handler(MessageHandler(
        filters.Regex("^🗑️ حذف التقارير$") & filters.User(user_id=ADMIN_IDS),
        start_delete_reports
    ))

    # اختيار السنة
    app.add_handler(CallbackQueryHandler(
        handle_year_selection, pattern=r"^delrep:year:\d+$"
    ))

    # اختيار الشهر
    app.add_handler(CallbackQueryHandler(
        handle_month_selection, pattern=r"^delrep:month:\d+$"
    ))

    # اختيار اليوم
    app.add_handler(CallbackQueryHandler(
        handle_day_selection, pattern=r"^delrep:day:\d+$"
    ))

    # التنقل بين الصفحات
    app.add_handler(CallbackQueryHandler(
        handle_page_navigation, pattern=r"^delrep:page:\d+$"
    ))

    # حذف فردي (عرض التأكيد)
    app.add_handler(CallbackQueryHandler(
        handle_delete_single, pattern=r"^delrep:delete:\d+$"
    ))

    # تنفيذ الحذف الفردي (بعد التأكيد)
    app.add_handler(CallbackQueryHandler(
        handle_confirmed_delete, pattern=r"^delrep:confirmed:\d+$"
    ))

    # تأكيد حذف الكل
    app.add_handler(CallbackQueryHandler(
        handle_confirm_all, pattern=r"^delrep:confirm_all$"
    ))

    # تنفيذ حذف الكل
    app.add_handler(CallbackQueryHandler(
        handle_delete_all_confirmed, pattern=r"^delrep:delete_all_confirmed$"
    ))

    # أزرار الرجوع والإلغاء والإعادة
    app.add_handler(CallbackQueryHandler(
        handle_navigation,
        pattern=r"^delrep:(cancel|back_to_year|back_to_month|back_to_day|back_to_list|restart)$"
    ))

    logger.info("✅ تم تسجيل نظام حذف التقارير للأدمن")
