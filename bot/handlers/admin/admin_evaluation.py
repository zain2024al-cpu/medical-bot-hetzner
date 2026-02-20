# ================================================
# bot/handlers/admin/admin_evaluation.py
# نظام تقييم المترجمين - يعتمد على services/stats_service.py فقط
# ================================================

import logging
import io
import os
import sys
import calendar
from datetime import datetime, date, timedelta
from sqlalchemy import text
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, CommandHandler, filters
)
from telegram.constants import ParseMode
from db.session import SessionLocal
from db.models import MonthlyEvaluation
from bot.shared_auth import is_admin
from services.stats_service import get_monthly_stats, get_translator_stats, ALL_ACTION_TYPES
from services.inline_calendar import MONTHS_AR, DAYS_AR, format_date_arabic

logger = logging.getLogger(__name__)

# ════════════════════════════════════════
# حالات المحادثة
# ════════════════════════════════════════
(
    EVAL_SELECT_YEAR,
    EVAL_SELECT_MONTH,
    EVAL_SELECT_PERIOD,
    EVAL_SELECT_DAY,
    EVAL_SELECT_FORMAT,
) = range(5)

MONTH_NAMES = {
    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
    5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس",
    9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"
}


# ════════════════════════════════════════
# أدوات مساعدة
# ════════════════════════════════════════

def _rating_label(percentage):
    """4 مستويات: ممتاز - جيد - مقبول - ضعيف"""
    if percentage >= 80:
        return "ممتاز", "🟢", "⭐⭐⭐⭐"
    elif percentage >= 60:
        return "جيد", "🟡", "⭐⭐⭐"
    elif percentage >= 40:
        return "مقبول", "🟠", "⭐⭐"
    else:
        return "ضعيف", "🔴", "⭐"


def _medal(rank):
    if rank == 1: return "🥇"
    elif rank == 2: return "🥈"
    elif rank == 3: return "🥉"
    return f"#{rank}"


def _report_label(count: int) -> str:
    return "تقرير" if count == 1 else "تقارير"


def _get_daily_counts(session, translator_id, start_date, end_date):
    if not translator_id:
        return []
    sql = text("""
        SELECT DATE(COALESCE(r.report_date, r.created_at)) as day, COUNT(*) as count
        FROM reports r
        WHERE COALESCE(r.report_date, r.created_at) >= :start
        AND COALESCE(r.report_date, r.created_at) < :end
        AND r.status = 'active'
        AND r.translator_id = :translator_id
        GROUP BY day
        ORDER BY day
    """)
    rows = session.execute(sql, {"start": start_date, "end": end_date, "translator_id": translator_id}).fetchall()
    return [(str(r[0]), int(r[1])) for r in rows]


async def _send_text_chunks(message, text):
    lines = text.splitlines()
    chunk = ""
    for line in lines:
        if len(chunk) + len(line) + 1 > 3500:
            try:
                await message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                await message.reply_text(chunk)
            chunk = ""
        chunk += (line + "\n")
    if chunk.strip():
        try:
            await message.reply_text(chunk.strip(), parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await message.reply_text(chunk.strip())


def _compute_rating(stats_results):
    """
    إضافة التقييم (النسبة + المستوى) على نتائج stats_service.

    التقييم يعتمد على 3 عوامل:
    - الإنتاجية: عدد التقارير مقارنة بالمتوسط (50%)
    - الانتظام: أيام العمل / أيام الفترة (30%)
    - الالتزام: التقارير قبل 8 مساءً / إجمالي التقارير (20%)
    """
    if not stats_results:
        return []

    # حساب متوسط التقارير (للمقارنة النسبية)
    avg_reports = sum(r['total_reports'] for r in stats_results) / len(stats_results)

    results = []
    for s in stats_results:
        total = s['total_reports']
        work_days = s['work_days']            # أيام العمل الرسمية (بدون الجمعة)
        attendance_days = s['attendance_days']  # أيام الحضور الفعلي
        late = s['late_reports']

        # 1) الإنتاجية: نسبة للمتوسط (cap 100%)
        if avg_reports > 0:
            productivity = min((total / avg_reports) * 100, 100)
        else:
            productivity = 100 if total > 0 else 0

        # 2) الانتظام: أيام الحضور / أيام العمل الرسمية
        if work_days > 0:
            regularity = min((attendance_days / work_days) * 100, 100)
        else:
            regularity = 100

        # 3) الالتزام الزمني: قبل 8 مساءً
        if total > 0:
            punctuality = ((total - late) / total) * 100
        else:
            punctuality = 100

        # النتيجة النهائية
        final_score = round(
            productivity * 0.50 +
            regularity * 0.30 +
            punctuality * 0.20
        , 1)

        level, color, stars = _rating_label(final_score)

        results.append({
            **s,  # كل البيانات من stats_service
            'final_score': final_score,
            'level': level,
            'color': color,
            'stars': stars,
        })

    results.sort(key=lambda x: (-x['final_score'], -x['total_reports']))
    return results


# ════════════════════════════════════════
# توليد ملف PDF (reportlab على Windows)
# ════════════════════════════════════════

def _generate_pdf(results, period_label, year, month, start_date_str=None, end_date_str=None):
    """توليد تقرير PDF - بطاقة لكل مترجم"""

    total_reports = sum(r['total_reports'] for r in results)
    total_late = sum(r['late_reports'] for r in results)

    if not start_date_str or not end_date_str:
        if month == "all" or month == 0:
            start_date_str = f"01/01/{year}"
            end_date_str = f"31/12/{year}"
        else:
            m = int(month)
            start_date_str = f"01/{m:02d}/{year}"
            if m == 12:
                end_date_str = f"31/12/{year}"
            else:
                last_day = (datetime(year, m + 1, 1) - timedelta(days=1)).day
                end_date_str = f"{last_day}/{m:02d}/{year}"

    # ─── محاولة استخدام reportlab ───
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_RIGHT, TA_CENTER
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from arabic_reshaper import reshape
        from bidi.algorithm import get_display
    except Exception as e:
        logger.warning(f"فشل تحميل مكتبات PDF: {e}")
        return _generate_html_fallback(results, period_label, year, month, start_date_str, end_date_str, total_reports, total_late), "html"

    # تسجيل خط عربي
    font_name = "Helvetica"
    font_options = [
        ("C:\\Windows\\Fonts\\tahoma.ttf", "Tahoma"),
        ("C:\\Windows\\Fonts\\arial.ttf", "Arial"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans"),
    ]
    for font_path, font_alias in font_options:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont(font_alias, font_path))
                font_name = font_alias
                break
            except Exception:
                continue

    def r(text_val):
        value = "" if text_val is None else str(text_val)
        return get_display(reshape(value))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)

    styles = getSampleStyleSheet()
    base_style = ParagraphStyle("base", parent=styles["Normal"], fontName=font_name, fontSize=11, leading=14, alignment=TA_RIGHT)
    title_style = ParagraphStyle("title", parent=styles["Title"], fontName=font_name, fontSize=16, leading=20, alignment=TA_CENTER)
    subtitle_style = ParagraphStyle("subtitle", parent=styles["Heading2"], fontName=font_name, fontSize=12, leading=16, alignment=TA_CENTER)
    section_style = ParagraphStyle("section", parent=styles["Heading3"], fontName=font_name, fontSize=12, leading=16, alignment=TA_RIGHT)

    story = []
    story.append(Paragraph(r("تقرير تقييم أداء المترجمين"), title_style))
    story.append(Paragraph(r(f"من {start_date_str} إلى {end_date_str}"), subtitle_style))
    story.append(Spacer(1, 12))

    summary_table = Table(
        [
            [r("تقارير بعد 8 مساءً"), r("إجمالي التقارير"), r("عدد المترجمين")],
            [str(total_late), str(total_reports), str(len(results))]
        ],
        colWidths=[150, 150, 150]
    )
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
    ]))
    summary_table.hAlign = "RIGHT"
    story.append(summary_table)
    story.append(Spacer(1, 16))

    for i, item in enumerate(results, 1):
        # اسم المترجم + التقييم
        level = item.get('level', '-')
        score = item.get('final_score', 0)
        stars = item.get('stars', '')
        story.append(Paragraph(r(f"{_medal(i)} {item['translator_name']} - {level} ({score}%) {stars}"), section_style))
        story.append(Spacer(1, 6))

        info_table = Table(
            [
                [str(item["total_reports"]), r("إجمالي التقارير")],
                [str(item["work_days"]), r("أيام العمل")],
                [str(item["late_reports"]), r("تقارير بعد 8 مساءً")],
                [f"{score}% - {r(level)}", r("التقييم")],
            ],
            colWidths=[140, 270]
        )
        info_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e3f2fd")),
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        info_table.hAlign = "RIGHT"
        story.append(info_table)
        story.append(Spacer(1, 10))

        # جدول تفصيل الإجراءات
        action_breakdown = item.get("action_breakdown", {})
        action_rows_data = [[r("النسبة"), r("العدد"), r("نوع الإجراء")]]
        for action_name, count in sorted(action_breakdown.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                pct = (count / item["total_reports"] * 100) if item["total_reports"] > 0 else 0
                action_rows_data.append([f"{pct:.0f}%", str(count), r(action_name)])
        if len(action_rows_data) > 1:
            action_table = Table(action_rows_data, colWidths=[80, 80, 220])
            action_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a237e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ]))
            action_table.hAlign = "RIGHT"
            story.append(action_table)
            story.append(Spacer(1, 10))

        # جدول تفصيل الأيام
        item_start = item.get("start_date")
        item_end = item.get("end_date")
        if item_start and item_end:
            try:
                from db.session import SessionLocal
                with SessionLocal() as pdf_session:
                    daily = _get_daily_counts(pdf_session, item.get("translator_id"), item_start, item_end)
                if daily:
                    day_rows = [[r("التقارير"), r("التاريخ")]]
                    for day_str, count in daily:
                        day_rows.append([str(count), r(day_str)])
                    day_table = Table(day_rows, colWidths=[80, 220])
                    day_table.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2e7d32")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, -1), font_name),
                        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ]))
                    day_table.hAlign = "RIGHT"
                    story.append(Paragraph(r("تفصيل الأيام"), base_style))
                    story.append(Spacer(1, 4))
                    story.append(day_table)
            except Exception as e:
                logger.warning(f"خطأ في تفصيل الأيام للـ PDF: {e}")

        if i < len(results):
            story.append(PageBreak())

    doc.build(story)
    return buffer.getvalue(), "pdf"


def _generate_html_fallback(results, period_label, year, month, start_date_str, end_date_str, total_reports, total_late):
    """HTML fallback إذا فشل reportlab"""
    translator_pages = ""
    for i, item in enumerate(results, 1):
        actions_rows = ""
        for action_name, count in sorted(item.get('action_breakdown', {}).items(), key=lambda x: x[1], reverse=True):
            pct = (count / item['total_reports'] * 100) if item['total_reports'] > 0 else 0
            color = "" if count > 0 else ' style="color:#bbb;"'
            actions_rows += f'<tr{color}><td style="text-align:right;padding:5px 10px;">{action_name}</td><td style="text-align:center;padding:5px 10px;">{count}</td><td style="text-align:center;padding:5px 10px;">{pct:.0f}%</td></tr>'
        translator_pages += f'''<div style="page-break-before:always;"><h2>{_medal(i)} {item["translator_name"]}</h2>
        <p>إجمالي التقارير: <b>{item["total_reports"]}</b> | أيام العمل: <b>{item["work_days"]}</b> | بعد 8 مساءً: <b>{item["late_reports"]}</b></p>
        <table border="1" cellpadding="5"><tr><th>نوع الإجراء</th><th>العدد</th><th>النسبة</th></tr>{actions_rows}</table></div>'''

    html = f'<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="UTF-8"></head><body><h1>تقرير تقييم المترجمين</h1><p>{period_label} | مترجمين: {len(results)} | تقارير: {total_reports} | بعد 8 مساءً: {total_late}</p>{translator_pages}</body></html>'
    return html.encode("utf-8")


# ════════════════════════════════════════
# توليد ملف Excel
# ════════════════════════════════════════

def _generate_excel(results, period_label, year, month):
    """توليد تقرير Excel - ملخص + تفصيل الإجراءات"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.properties import PageSetupProperties

    wb = Workbook()

    # ─── الورقة 1: ملخص ───
    ws = wb.active
    ws.title = "ملخص التقييمات"
    ws.sheet_view.rightToLeft = True
    ws.page_setup.orientation = 'landscape'
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.print_options.horizontalCentered = True

    header_font = Font(name='Arial', bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='1A237E', end_color='1A237E', fill_type='solid')
    title_font = Font(name='Arial', bold=True, size=14, color='1A237E')
    bold_font = Font(name='Arial', bold=True, size=11)
    normal_font = Font(name='Arial', size=11)
    center_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    right_align = Alignment(horizontal='right', vertical='center', wrap_text=True)
    thin_border = Border(
        left=Side(style='thin', color='CCCCCC'),
        right=Side(style='thin', color='CCCCCC'),
        top=Side(style='thin', color='CCCCCC'),
        bottom=Side(style='thin', color='CCCCCC'),
    )
    level_fills = {
        'ممتاز': PatternFill(start_color='E8F5E9', end_color='E8F5E9', fill_type='solid'),
        'جيد': PatternFill(start_color='FFF8E1', end_color='FFF8E1', fill_type='solid'),
        'مقبول': PatternFill(start_color='FFF3E0', end_color='FFF3E0', fill_type='solid'),
        'ضعيف': PatternFill(start_color='FFEBEE', end_color='FFEBEE', fill_type='solid'),
    }

    ws.merge_cells('A1:G1')
    ws['A1'] = f"تقرير تقييم أداء المترجمين - {period_label}"
    ws['A1'].font = title_font
    ws['A1'].alignment = center_align

    ws.merge_cells('A2:G2')
    ws['A2'] = f"تاريخ الإصدار: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    ws['A2'].font = Font(name='Arial', size=10, color='777777')
    ws['A2'].alignment = center_align

    headers = ['الترتيب', 'المترجم', 'إجمالي التقارير', 'أيام العمل', 'بعد 8 مساءً', 'النسبة %', 'التقييم']

    row = 4
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border

    for i, item in enumerate(results, 1):
        row = i + 4
        medal = ""
        if i == 1: medal = "🥇 "
        elif i == 2: medal = "🥈 "
        elif i == 3: medal = "🥉 "

        values = [
            i,
            f"{medal}{item['translator_name']}",
            item['total_reports'],
            item['work_days'],
            item['late_reports'],
            item.get('final_score', 0),
            item.get('level', '-'),
        ]

        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row, column=col, value=val)
            cell.font = bold_font if col == 2 else normal_font
            cell.alignment = center_align if col != 2 else right_align
            cell.border = thin_border
            # تلوين خلية التقييم حسب المستوى
            if col == 7:
                level_fill = level_fills.get(str(val))
                if level_fill:
                    cell.fill = level_fill

    col_widths = [8, 25, 15, 12, 14, 10, 12]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ─── الورقة 2: تفصيل الإجراءات ───
    ws2 = wb.create_sheet("تفصيل الإجراءات")
    ws2.sheet_view.rightToLeft = True
    ws2.page_setup.orientation = 'landscape'
    ws2.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws2.print_options.horizontalCentered = True

    total_cols = 1 + len(ALL_ACTION_TYPES) + 2
    end_col_letter = get_column_letter(total_cols)
    ws2.merge_cells(f'A1:{end_col_letter}1')
    ws2['A1'] = f"تفصيل التقارير حسب نوع الإجراء - {period_label}"
    ws2['A1'].font = title_font
    ws2['A1'].alignment = center_align

    detail_headers = ['المترجم'] + ALL_ACTION_TYPES + ['المجموع', 'بعد 8 مساءً']

    row = 3
    for col, header in enumerate(detail_headers, 1):
        cell = ws2.cell(row=row, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border

    for i, item in enumerate(results, 1):
        row = i + 3
        action_breakdown = item.get('action_breakdown', {})
        values = [item['translator_name']]
        for action_type in ALL_ACTION_TYPES:
            values.append(action_breakdown.get(action_type, 0))
        values.append(item['total_reports'])
        values.append(item['late_reports'])

        for col, val in enumerate(values, 1):
            cell = ws2.cell(row=row, column=col, value=val)
            cell.font = normal_font
            cell.alignment = center_align if col != 1 else right_align
            cell.border = thin_border

    ws2.column_dimensions['A'].width = 25
    for col_idx in range(2, total_cols + 1):
        ws2.column_dimensions[get_column_letter(col_idx)].width = 16

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()


# ════════════════════════════════════════
# Handlers
# ════════════════════════════════════════

async def start_evaluation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نقطة الدخول - اختيار السنة"""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("هذه الخاصية مخصصة للأدمن فقط.")
        return ConversationHandler.END

    context.user_data.pop('eval_data', None)

    current_year = date.today().year
    keyboard = [
        [InlineKeyboardButton(f"📅 {current_year}", callback_data=f"eval:year:{current_year}")],
        [InlineKeyboardButton(f"📅 {current_year - 1}", callback_data=f"eval:year:{current_year - 1}")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="eval:cancel")],
    ]

    await update.message.reply_text(
        "╔══════════════════════════════════╗\n"
        "     📊 **تقييم أداء المترجمين**\n"
        "╚══════════════════════════════════╝\n\n"
        "📌 **التقرير يتضمن:**\n"
        "├ 👤 اسم المترجم\n"
        "├ 📅 الفترة (من - إلى)\n"
        "├ 📄 إجمالي التقارير\n"
        "├ 📋 تفصيل حسب نوع الإجراء\n"
        "├ 📅 عدد أيام العمل\n"
        "├ 🕐 تقارير بعد 8 مساءً\n"
        "└ ⭐ نسبة الأداء العملي\n\n"
        "اختر السنة:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )
    return EVAL_SELECT_YEAR


def _build_day_calendar(year, month):
    today = date.today()
    keyboard = []
    keyboard.append([InlineKeyboardButton(f"{MONTHS_AR[month]} {year}", callback_data="noop")])
    keyboard.append([InlineKeyboardButton(day, callback_data="noop") for day in DAYS_AR])

    for week in calendar.monthcalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="noop"))
                continue
            day_date = date(year, month, day)
            if day_date > today:
                row.append(InlineKeyboardButton(f"·{day}·", callback_data="noop"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                row.append(InlineKeyboardButton(str(day), callback_data=f"evalday:select:{date_str}"))
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="eval:back_period")])
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="eval:cancel")])
    return InlineKeyboardMarkup(keyboard)


async def handle_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار السنة"""
    q = update.callback_query
    await q.answer()

    if q.data == "eval:cancel":
        await q.edit_message_text("✅ تم إلغاء التقييم.")
        return ConversationHandler.END

    year = int(q.data.split(":")[2])
    context.user_data.setdefault('eval_data', {})['year'] = year

    keyboard = []
    for i in range(0, 12, 3):
        row = []
        for j in range(3):
            m = i + j + 1
            row.append(InlineKeyboardButton(
                MONTH_NAMES[m], callback_data=f"eval:month:{m}"
            ))
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("📄 كل الشهور", callback_data="eval:month:all")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="eval:back_year")])
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="eval:cancel")])

    await q.edit_message_text(
        f"📊 **تقييم أداء المترجمين**\n\n"
        f"📅 السنة: **{year}**\n\n"
        f"اختر الشهر:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )
    return EVAL_SELECT_MONTH


async def handle_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار الشهر"""
    q = update.callback_query
    await q.answer()

    if q.data == "eval:cancel":
        await q.edit_message_text("✅ تم إلغاء التقييم.")
        return ConversationHandler.END

    if q.data == "eval:back_year":
        current_year = date.today().year
        keyboard = [
            [InlineKeyboardButton(f"📅 {current_year}", callback_data=f"eval:year:{current_year}")],
            [InlineKeyboardButton(f"📅 {current_year - 1}", callback_data=f"eval:year:{current_year - 1}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="eval:cancel")],
        ]
        await q.edit_message_text(
            "📊 **تقييم أداء المترجمين**\n\nاختر السنة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )
        return EVAL_SELECT_YEAR

    month_val = q.data.split(":")[2]
    eval_data = context.user_data.setdefault('eval_data', {})
    eval_data['month'] = month_val
    eval_data.pop('day', None)
    eval_data.pop('period_type', None)

    year = eval_data.get('year', date.today().year)
    month_label = "كل الشهور" if month_val == "all" else MONTH_NAMES.get(int(month_val), month_val)

    if month_val == "all":
        eval_data['period_type'] = "full"
        keyboard = [
            [InlineKeyboardButton("📄 PDF", callback_data="eval:format:pdf")],
            [InlineKeyboardButton("📊 Excel", callback_data="eval:format:excel")],
            [InlineKeyboardButton("📄 PDF + 📊 Excel", callback_data="eval:format:both")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="eval:back_month")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="eval:cancel")],
        ]

        await q.edit_message_text(
            f"📊 **تقييم أداء المترجمين**\n\n"
            f"📅 الفترة: **{month_label} {year}**\n\n"
            f"اختر صيغة الملف:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )
        return EVAL_SELECT_FORMAT

    keyboard = [
        [InlineKeyboardButton("📅 الشهر كامل", callback_data="eval:period:full")],
        [InlineKeyboardButton("📆 يوم محدد", callback_data="eval:period:day")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="eval:back_month")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="eval:cancel")],
    ]

    await q.edit_message_text(
        f"📊 **تقييم أداء المترجمين**\n\n"
        f"📅 الشهر: **{month_label} {year}**\n\n"
        f"اختر نوع الفترة:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )
    return EVAL_SELECT_PERIOD


async def handle_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "eval:cancel":
        await q.edit_message_text("✅ تم إلغاء التقييم.")
        return ConversationHandler.END

    if q.data == "eval:back_month":
        year = context.user_data.get('eval_data', {}).get('year', date.today().year)
        keyboard = []
        for i in range(0, 12, 3):
            row = []
            for j in range(3):
                m = i + j + 1
                row.append(InlineKeyboardButton(
                    MONTH_NAMES[m], callback_data=f"eval:month:{m}"
                ))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("📄 كل الشهور", callback_data="eval:month:all")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="eval:back_year")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="eval:cancel")])
        await q.edit_message_text(
            f"📊 **تقييم أداء المترجمين**\n\n📅 السنة: **{year}**\n\nاختر الشهر:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )
        return EVAL_SELECT_MONTH

    eval_data = context.user_data.setdefault('eval_data', {})
    year = eval_data.get('year', date.today().year)
    month = eval_data.get('month')
    if not month or month == "all":
        return EVAL_SELECT_MONTH

    if q.data == "eval:period:full":
        eval_data['period_type'] = "full"
        month_label = MONTH_NAMES.get(int(month), month)
        keyboard = [
            [InlineKeyboardButton("📄 PDF", callback_data="eval:format:pdf")],
            [InlineKeyboardButton("📊 Excel", callback_data="eval:format:excel")],
            [InlineKeyboardButton("📄 PDF + 📊 Excel", callback_data="eval:format:both")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="eval:back_month")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="eval:cancel")],
        ]
        await q.edit_message_text(
            f"📊 **تقييم أداء المترجمين**\n\n"
            f"📅 الفترة: **{month_label} {year}**\n\n"
            f"اختر صيغة الملف:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )
        return EVAL_SELECT_FORMAT

    if q.data == "eval:period:day":
        eval_data['period_type'] = "day"
        month_int = int(month)
        await q.edit_message_text(
            f"📊 **تقييم أداء المترجمين**\n\n"
            f"📅 اختر يوماً من شهر **{MONTH_NAMES.get(month_int)} {year}**:",
            reply_markup=_build_day_calendar(year, month_int),
            parse_mode=ParseMode.MARKDOWN,
        )
        return EVAL_SELECT_DAY

    return EVAL_SELECT_PERIOD


async def handle_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "eval:cancel":
        await q.edit_message_text("✅ تم إلغاء التقييم.")
        return ConversationHandler.END

    if q.data == "eval:back_period":
        eval_data = context.user_data.get('eval_data', {})
        year = eval_data.get('year', date.today().year)
        month = eval_data.get('month')
        if not month or month == "all":
            return EVAL_SELECT_MONTH
        month_label = MONTH_NAMES.get(int(month), month)
        keyboard = [
            [InlineKeyboardButton("📅 الشهر كامل", callback_data="eval:period:full")],
            [InlineKeyboardButton("📆 يوم محدد", callback_data="eval:period:day")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="eval:back_month")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="eval:cancel")],
        ]
        await q.edit_message_text(
            f"📊 **تقييم أداء المترجمين**\n\n"
            f"📅 الشهر: **{month_label} {year}**\n\n"
            f"اختر نوع الفترة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )
        return EVAL_SELECT_PERIOD

    if q.data.startswith("evalday:select:"):
        date_str = q.data.split(":")[-1]
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        eval_data = context.user_data.setdefault('eval_data', {})
        month = eval_data.get('month')
        year = eval_data.get('year')
        if month and year:
            if selected_date.month != int(month) or selected_date.year != int(year):
                await q.answer("اختر يوماً من نفس الشهر", show_alert=True)
                await q.edit_message_text(
                    f"📊 **تقييم أداء المترجمين**\n\n"
                    f"📅 اختر يوماً من شهر **{MONTH_NAMES.get(int(month))} {year}**:",
                    reply_markup=_build_day_calendar(int(year), int(month)),
                    parse_mode=ParseMode.MARKDOWN,
                )
                return EVAL_SELECT_DAY

        eval_data['day'] = selected_date
        period_label = format_date_arabic(selected_date)
        keyboard = [
            [InlineKeyboardButton("📄 PDF", callback_data="eval:format:pdf")],
            [InlineKeyboardButton("📊 Excel", callback_data="eval:format:excel")],
            [InlineKeyboardButton("📄 PDF + 📊 Excel", callback_data="eval:format:both")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="eval:back_month")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="eval:cancel")],
        ]
        await q.edit_message_text(
            f"📊 **تقييم أداء المترجمين**\n\n"
            f"📅 الفترة: **{period_label}**\n\n"
            f"اختر صيغة الملف:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )
        return EVAL_SELECT_FORMAT

    return EVAL_SELECT_DAY


async def handle_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار التنسيق وتوليد التقرير"""
    q = update.callback_query
    await q.answer()

    if q.data == "eval:cancel":
        await q.edit_message_text("✅ تم إلغاء التقييم.")
        return ConversationHandler.END

    if q.data == "eval:back_month":
        eval_data = context.user_data.get('eval_data', {})
        year = eval_data.get('year', date.today().year)
        month = eval_data.get('month')
        period_type = eval_data.get('period_type')
        if month and month != "all" and period_type in ("full", "day"):
            month_label = MONTH_NAMES.get(int(month), month)
            keyboard = [
                [InlineKeyboardButton("📅 الشهر كامل", callback_data="eval:period:full")],
                [InlineKeyboardButton("📆 يوم محدد", callback_data="eval:period:day")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="eval:back_month")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="eval:cancel")],
            ]
            await q.edit_message_text(
                f"📊 **تقييم أداء المترجمين**\n\n"
                f"📅 الشهر: **{month_label} {year}**\n\n"
                f"اختر نوع الفترة:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN,
            )
            return EVAL_SELECT_PERIOD
        keyboard = []
        for i in range(0, 12, 3):
            row = []
            for j in range(3):
                m = i + j + 1
                row.append(InlineKeyboardButton(
                    MONTH_NAMES[m], callback_data=f"eval:month:{m}"
                ))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("📄 كل الشهور", callback_data="eval:month:all")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="eval:back_year")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="eval:cancel")])
        await q.edit_message_text(
            f"📊 **تقييم أداء المترجمين**\n\n📅 السنة: **{year}**\n\nاختر الشهر:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )
        return EVAL_SELECT_MONTH

    fmt = q.data.split(":")[2]  # pdf, excel, both
    data = context.user_data.get('eval_data', {})
    year = data.get('year', date.today().year)
    month = data.get('month', 'all')
    period_type = data.get('period_type', 'full')

    if period_type == "day" and data.get('day'):
        day_date = data.get('day')
        period_label = format_date_arabic(day_date)
        start_date = day_date
        end_date = day_date
        start_date_str = day_date.strftime("%d/%m/%Y")
        end_date_str = day_date.strftime("%d/%m/%Y")
    else:
        month_label = "كل الشهور" if month == "all" else MONTH_NAMES.get(int(month), month)
        period_label = f"{month_label} {year}"
        start_date = None
        end_date = None
        start_date_str = None
        end_date_str = None

    await q.edit_message_text(
        f"⏳ **جاري إعداد تقرير التقييم...**\n\n"
        f"📅 الفترة: {period_label}\n"
        f"📄 الصيغة: {'PDF' if fmt == 'pdf' else 'Excel' if fmt == 'excel' else 'PDF + Excel'}",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        with SessionLocal() as session:
            logger.info(f"📊 EVAL: period_type={period_type}, start={start_date}, end={end_date}, year={year}, month={month}")
            if period_type == "day" and start_date and end_date:
                raw_stats = get_translator_stats(session, start_date, end_date)
            else:
                raw_stats = get_monthly_stats(session, year, month)

            logger.info(f"📊 EVAL: raw_stats returned {len(raw_stats)} translators, total_reports={sum(r['total_reports'] for r in raw_stats)}")
            for i, rs in enumerate(raw_stats):
                logger.info(f"   ├ [{i+1}] tid={rs['translator_id']}, name={rs['translator_name']}, reports={rs['total_reports']}")

            if not raw_stats:
                await q.edit_message_text(
                    f"⚠️ **لا توجد تقارير في الفترة:** {period_label}\n\n"
                    "لا يمكن إنشاء تقييم بدون تقارير.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return ConversationHandler.END

            # إضافة التقييم فوق الإحصائيات
            results = _compute_rating(raw_stats)

            # حفظ في قاعدة البيانات
            if period_type != "day":
                _save_evaluations_to_db(session, results, year, month)

            # إرسال ملخص نصي
            total_reports = sum(r['total_reports'] for r in results)
            total_late = sum(r['late_reports'] for r in results)

            # ═══ رسالة تشخيصية للأدمن ═══
            diag_lines = [f"🔍 **تشخيص:** وجدت {len(results)} مترجم، {total_reports} تقرير"]
            try:
                from sqlalchemy import text as sa_text
                from datetime import timedelta as td2

                # حساب النطاق الزمني
                if period_type == "day" and start_date:
                    s_str = start_date.strftime("%Y-%m-%d") if hasattr(start_date, 'strftime') else str(start_date)
                    e_date = start_date + td2(days=1) if hasattr(start_date, 'strftime') else None
                    e_str = e_date.strftime("%Y-%m-%d") if e_date else str(end_date)
                else:
                    if month == "all" or month == 0:
                        s_str = f"{year}-01-01"
                        e_str = f"{year + 1}-01-01"
                    else:
                        m = int(month)
                        s_str = f"{year}-{m:02d}-01"
                        e_str = f"{year}-{m+1:02d}-01" if m < 12 else f"{year+1}-01-01"

                diag_lines.append(f"📅 النطاق: {s_str} → {e_str}")

                # تقارير بدون translator_id
                no_tid = session.execute(sa_text(
                    "SELECT COUNT(*) FROM reports WHERE COALESCE(report_date, created_at) >= :s AND COALESCE(report_date, created_at) < :e AND status='active' AND translator_id IS NULL"
                ), {"s": s_str, "e": e_str}).scalar() or 0
                if no_tid > 0:
                    diag_lines.append(f"⚠️ بدون مترجم: **{no_tid}**")

                # تقارير ليست active
                not_active = session.execute(sa_text(
                    "SELECT COUNT(*) FROM reports WHERE COALESCE(report_date, created_at) >= :s AND COALESCE(report_date, created_at) < :e AND (status != 'active' OR status IS NULL)"
                ), {"s": s_str, "e": e_str}).scalar() or 0
                if not_active > 0:
                    diag_lines.append(f"⚠️ غير نشطة: **{not_active}**")

                # تقارير اليوم السابق (بسبب UTC)
                if period_type == "day" and start_date:
                    prev_s = (start_date - td2(days=1)).strftime("%Y-%m-%d")
                    prev_count = session.execute(sa_text(
                        "SELECT COUNT(*) FROM reports WHERE COALESCE(report_date, created_at) >= :s AND COALESCE(report_date, created_at) < :e AND status='active' AND translator_id IS NOT NULL"
                    ), {"s": prev_s, "e": s_str}).scalar() or 0
                    # تقارير created_at في نفس اليوم لكن report_date في يوم سابق
                    mismatched = session.execute(sa_text(
                        "SELECT COUNT(*) FROM reports WHERE DATE(created_at) >= :target AND DATE(created_at) < :next_day AND DATE(report_date) < :target AND status='active' AND translator_id IS NOT NULL"
                    ), {"target": s_str, "next_day": e_str}).scalar() or 0
                    if mismatched > 0:
                        diag_lines.append(f"⚠️ تقارير created\\_at={s_str} لكن report\\_date قبله: **{mismatched}**")
                    # تقارير created في هذا اليوم بغض النظر عن report_date
                    by_created = session.execute(sa_text(
                        "SELECT COUNT(*) FROM reports WHERE DATE(created_at) >= :s AND DATE(created_at) < :e AND status='active' AND translator_id IS NOT NULL"
                    ), {"s": s_str, "e": e_str}).scalar() or 0
                    diag_lines.append(f"📊 حسب created\\_at: **{by_created}** تقرير")
                    by_report_date = session.execute(sa_text(
                        "SELECT COUNT(*) FROM reports WHERE DATE(report_date) >= :s AND DATE(report_date) < :e AND status='active' AND translator_id IS NOT NULL"
                    ), {"s": s_str, "e": e_str}).scalar() or 0
                    diag_lines.append(f"📊 حسب report\\_date: **{by_report_date}** تقرير")

            except Exception as diag_err:
                logger.warning(f"Diagnostic query error: {diag_err}")

            await q.message.reply_text("\n".join(diag_lines), parse_mode=ParseMode.MARKDOWN)

            header = (
                f"╔══════════════════════════════════╗\n"
                f"  ✅ **تم إعداد تقرير التقييم**\n"
                f"╚══════════════════════════════════╝\n\n"
                f"📅 الفترة: **{period_label}**\n"
                f"👥 المترجمين: **{len(results)}**\n"
                f"📄 إجمالي التقارير: **{total_reports}**\n"
                f"🕐 تقارير بعد 8 مساءً: **{total_late}**\n"
            )
            await q.message.reply_text(header, parse_mode=ParseMode.MARKDOWN)

            # إرسال تفاصيل كل مترجم
            for i, item in enumerate(results, 1):
                medal = _medal(i)
                detail = f"{medal} **{item['translator_name']}**\n"
                detail += f"├ ⭐ التقييم: **{item.get('level', '-')}** ({item.get('final_score', 0)}%) {item.get('stars', '')}\n"
                detail += f"├ 📄 إجمالي التقارير: **{item['total_reports']}**\n"
                detail += f"├ 📅 أيام العمل: **{item['work_days']}** يوم\n"
                detail += f"├ 🕐 بعد 8 مساءً: **{item['late_reports']}**\n"

                # تفصيل الإجراءات (غير الصفرية فقط)
                non_zero = {k: v for k, v in item.get('action_breakdown', {}).items() if v > 0}
                if non_zero:
                    detail += "├ 📋 **التقارير حسب النوع:**\n"
                    for action_name, count in sorted(non_zero.items(), key=lambda x: x[1], reverse=True):
                        detail += f"│   • {action_name}: **{count}**\n"

                item_start = item.get("start_date")
                item_end = item.get("end_date")
                daily_counts = _get_daily_counts(session, item.get("translator_id"), item_start, item_end)
                if daily_counts:
                    detail += "├ 📆 **تفصيل الأيام:**\n"
                    for day, count in daily_counts:
                        detail += f"│   • {day}: **{count}** {_report_label(count)}\n"

                detail += "\n"

                await _send_text_chunks(q.message, detail)

            # توليد وإرسال الملفات
            file_prefix = f"تقييم_المترجمين_{year}"
            if period_type == "day" and data.get('day'):
                file_prefix += f"_{data['day'].strftime('%Y_%m_%d')}"
            elif month != "all":
                file_prefix += f"_{month}"

            if fmt in ('pdf', 'both'):
                try:
                    file_bytes, file_ext = _generate_pdf(results, period_label, year, month, start_date_str, end_date_str)
                    file_obj = io.BytesIO(file_bytes)
                    file_obj.name = f"{file_prefix}.{file_ext}"
                    await q.message.reply_document(
                        document=file_obj,
                        caption=f"📄 تقرير تقييم المترجمين - {period_label}",
                    )
                    if file_ext != "pdf":
                        await q.message.reply_text("⚠️ تم إرسال HTML لأن PDF غير متوفر.")
                except Exception as e:
                    logger.error(f"خطأ في PDF: {e}", exc_info=True)
                    await q.message.reply_text(f"⚠️ خطأ في إنشاء PDF: {str(e)[:200]}")

            if fmt in ('excel', 'both'):
                try:
                    excel_bytes = _generate_excel(results, period_label, year, month)
                    excel_file = io.BytesIO(excel_bytes)
                    excel_file.name = f"{file_prefix}.xlsx"
                    await q.message.reply_document(
                        document=excel_file,
                        caption=f"📊 تقرير تقييم المترجمين - {period_label}",
                    )
                except Exception as e:
                    logger.error(f"خطأ في Excel: {e}", exc_info=True)
                    await q.message.reply_text(f"⚠️ خطأ في إنشاء Excel: {str(e)[:200]}")

    except Exception as e:
        logger.error(f"خطأ في التقييم: {e}", exc_info=True)
        # لا تستخدم Markdown هنا لأن نص الاستثناء قد يحتوي رموزًا تكسر parse entities.
        safe_error = str(e).replace("\n", " ").strip()[:300]
        await q.message.reply_text(f"❌ حدث خطأ: {safe_error}")

    return ConversationHandler.END


def _save_evaluations_to_db(session, results, year, month):
    """حفظ نتائج التقييم في قاعدة البيانات"""
    month_int = 0 if month == "all" else int(month)
    for res in results:
        try:
            existing = session.query(MonthlyEvaluation).filter_by(
                translator_name=res['translator_name'],
                year=year,
                month=month_int,
            ).first()

            if existing:
                existing.total_reports = res['total_reports']
                existing.work_days = res['work_days']
                existing.late_reports = res['late_reports']
                existing.total_points = res['final_score']
                existing.final_rating = int(res['final_score'] / 20)
                existing.performance_level = res['level']
                existing.updated_at = datetime.utcnow()
            else:
                ev = MonthlyEvaluation(
                    translator_id=res.get('translator_id'),
                    translator_name=res['translator_name'],
                    year=year,
                    month=month_int,
                    total_reports=res['total_reports'],
                    work_days=res['work_days'],
                    late_reports=res['late_reports'],
                    total_points=res['final_score'],
                    final_rating=int(res['final_score'] / 20),
                    performance_level=res['level'],
                )
                session.add(ev)
        except Exception as e:
            logger.warning(f"خطأ في حفظ تقييم {res['translator_name']}: {e}")
    try:
        session.commit()
    except Exception as e:
        logger.error(f"خطأ في حفظ التقييمات: {e}")
        session.rollback()


# ════════════════════════════════════════
# تسجيل الهاندلرز
# ════════════════════════════════════════

async def _cancel_evaluation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء التقييم من زر inline"""
    query = update.callback_query
    if query:
        try:
            await query.answer()
        except Exception:
            pass
        try:
            await query.edit_message_text("✅ تم إلغاء التقييم.")
        except Exception:
            pass
    context.user_data.pop('eval_data', None)
    return ConversationHandler.END


async def _cancel_evaluation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء التقييم من أمر /cancel"""
    context.user_data.pop('eval_data', None)
    if update.message:
        await update.message.reply_text("✅ تم إلغاء التقييم.")
    return ConversationHandler.END


async def start_evaluation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نقطة دخول من زر inline (admin:evaluation)"""
    query = update.callback_query
    if query:
        await query.answer()

    user = update.effective_user
    if not is_admin(user.id):
        if query:
            await query.edit_message_text("هذه الخاصية مخصصة للأدمن فقط.")
        return ConversationHandler.END

    context.user_data.pop('eval_data', None)

    current_year = date.today().year
    keyboard = [
        [InlineKeyboardButton(f"📅 {current_year}", callback_data=f"eval:year:{current_year}")],
        [InlineKeyboardButton(f"📅 {current_year - 1}", callback_data=f"eval:year:{current_year - 1}")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="eval:cancel")],
    ]

    text = (
        "╔══════════════════════════════════╗\n"
        "     📊 **تقييم أداء المترجمين**\n"
        "╚══════════════════════════════════╝\n\n"
        "📌 **التقرير يتضمن:**\n"
        "├ 👤 اسم المترجم\n"
        "├ 📅 الفترة (من - إلى)\n"
        "├ 📄 إجمالي التقارير\n"
        "├ 📋 تفصيل حسب نوع الإجراء\n"
        "├ 📅 عدد أيام العمل\n"
        "├ 🕐 تقارير بعد 8 مساءً\n"
        "└ ⭐ نسبة الأداء العملي\n\n"
        "اختر السنة:"
    )

    if query:
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )
    return EVAL_SELECT_YEAR


def register(app):
    """تسجيل نظام تقييم المترجمين"""
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📊 تقييم المترجمين$"), start_evaluation),
            CallbackQueryHandler(start_evaluation_callback, pattern=r"^(admin:evaluation|eval_translators|translator_evaluation)$"),
        ],
        states={
            EVAL_SELECT_YEAR: [
                CallbackQueryHandler(handle_year, pattern=r"^eval:"),
            ],
            EVAL_SELECT_MONTH: [
                CallbackQueryHandler(handle_month, pattern=r"^eval:"),
            ],
            EVAL_SELECT_PERIOD: [
                CallbackQueryHandler(handle_period, pattern=r"^eval:"),
            ],
            EVAL_SELECT_DAY: [
                CallbackQueryHandler(handle_day, pattern=r"^(evalday:|eval:)"),
            ],
            EVAL_SELECT_FORMAT: [
                CallbackQueryHandler(handle_format, pattern=r"^eval:"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", _cancel_evaluation_command),
            CallbackQueryHandler(_cancel_evaluation, pattern=r"^eval:cancel$"),
            MessageHandler(filters.Regex("^📊 تقييم المترجمين$"), start_evaluation),
            CallbackQueryHandler(start_evaluation_callback, pattern=r"^(admin:evaluation|eval_translators|translator_evaluation)$"),
        ],
        name="translator_evaluation_conv",
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=True,
    )
    app.add_handler(conv)
    logger.info("تم تسجيل نظام تقييم المترجمين")
