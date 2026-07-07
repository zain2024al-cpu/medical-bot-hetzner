# services/pharmacy_evacuation_excel.py
# Excel لـ"🖨️ طباعة مسير إخلاء الأدوية والمستلزمات الطبية".
# نفس نمط openpyxl + rightToLeft المُثبت في bot/handlers/admin/admin_evaluation.py.
# نفس ترتيب أعمدة PDF بالضبط: م | المبلغ | الاسم | رقم الفاتورة | بند الصرف | البيان | التاريخ
#
# ✅ ملاحظة مهمة حول تنسيق التواريخ: بعض تطبيقات الجداول (WPS، إكسل على
# الجوال، Google Sheets) تُعيد اكتشاف أي نص يُشبه تاريخاً عند فتح الملف
# وتُعيد تنسيقه حسب اللغة/المنطقة الخاصة بها — حتى لو كانت الخلية
# مُخزَّنة فعلياً كنص صرف (data_type='s') في ملف openpyxl. لذلك كل خلية
# تحتوي نصاً يُشبه تاريخاً يجب أن تحمل number_format='@' (نص) صراحة
# لمنع أي تطبيق من إعادة تفسيرها كرقم/تاريخ (وهو السبب الشائع لظهور
# التاريخ كأرقام متلاصقة بلا فواصل مثل "20260621").

import io
import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)

_TEXT_FORMAT = "@"


def build_evacuation_excel(rows: list[dict], start_date: date, end_date: date) -> io.BytesIO:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "مسير الإخلاء"
    ws.sheet_view.rightToLeft = True

    header_font = Font(name="Arial", bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="1565C0", end_color="1565C0", fill_type="solid")
    bismillah_font = Font(name="Arial", bold=True, size=13, color="1A237E")
    title_font = Font(name="Arial", bold=True, size=16, color="1565C0")
    band_font = Font(name="Arial", size=10, color="1A237E")
    band_fill = PatternFill(start_color="F0F4F8", end_color="F0F4F8", fill_type="solid")
    period_font = Font(name="Arial", size=10, color="777777")
    normal_font = Font(name="Arial", size=10)
    total_font = Font(name="Arial", bold=True, size=11, color="FFFFFF")
    total_fill = PatternFill(start_color="1565C0", end_color="1565C0", fill_type="solid")
    footer_font = Font(name="Arial", bold=True, size=10, color="1A237E")
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"), right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"), bottom=Side(style="thin", color="CCCCCC"),
    )

    headers = ["م", "المبلغ", "الاسم", "رقم الفاتورة", "بند الصرف", "البيان", "التاريخ"]
    last_col = get_column_letter(len(headers))

    # ── بسم الله الرحمن الرحيم ────────────────────────────────────────────────
    ws.merge_cells(f"A1:{last_col}1")
    ws["A1"] = "بسم الله الرحمن الرحيم"
    ws["A1"].font = bismillah_font
    ws["A1"].alignment = center_align
    ws.row_dimensions[1].height = 22

    # فراغ فاصل واضح قبل العنوان
    ws.row_dimensions[2].height = 8

    # ── العنوان الرئيسي ───────────────────────────────────────────────────────
    ws.merge_cells(f"A3:{last_col}3")
    ws["A3"] = "مسير إخلاء الأدوية والمستلزمات الطبية"
    ws["A3"].font = title_font
    ws["A3"].alignment = center_align
    ws.row_dimensions[3].height = 26

    # ── صف واحد مظلَّل يجمع الحقول الثلاثة (سطر كامل مضلَّل، تُملأ يدوياً) ─────
    ws.merge_cells(f"A4:{last_col}4")
    band_cell = ws["A4"]
    band_cell.value = "رقم سند الصرف: ________________          رقم القيد: ________________          تاريخ تسليم المسير: ________________"
    band_cell.font = band_font
    band_cell.alignment = center_align
    ws.row_dimensions[4].height = 20
    for col in range(1, len(headers) + 1):
        ws.cell(row=4, column=col).fill = band_fill

    ws.row_dimensions[5].height = 6

    # ── الفترة ────────────────────────────────────────────────────────────────
    ws.merge_cells(f"A6:{last_col}6")
    period_cell = ws["A6"]
    period_cell.value = f"الفترة: من {start_date.strftime('%Y-%m-%d')} إلى {end_date.strftime('%Y-%m-%d')}"
    period_cell.font = period_font
    period_cell.alignment = center_align
    period_cell.number_format = _TEXT_FORMAT

    header_row_idx = 8
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=header_row_idx, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border

    total_amount = 0.0
    for i, r in enumerate(rows, start=1):
        row_idx = header_row_idx + i
        date_str = r["date"].strftime("%Y-%m-%d") if isinstance(r["date"], date) else str(r["date"])
        values = [i, f'{r["amount"]:.2f}', r["name"], r["invoice_number"], r["expense_item"], r["statement"], date_str]
        total_amount += r["amount"]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col, value=val)
            cell.font = normal_font
            cell.border = thin_border
            cell.alignment = center_align  # ✅ كل الأعمدة موسَّطة الآن لمظهر أفضل وأكثر اتساقاً
            if col == len(headers):  # عمود التاريخ — نصّ صرف دائماً، لا يُعاد تفسيره كرقم
                cell.number_format = _TEXT_FORMAT

    # ✅ قيمة الإجمالي تظهر تحت عمود "المبلغ" (العمود 2) تحديداً فقط —
    # لا تمتد عبر الجدول كاملاً. عمود "م" (1) يُترك فارغاً بنفس التظليل،
    # والتسمية "إجمالي المبلغ" تمتد من "الاسم" حتى "التاريخ" (الأعمدة 3-7).
    total_row_idx = header_row_idx + len(rows) + 1

    empty_cell = ws.cell(row=total_row_idx, column=1, value="")
    empty_cell.fill = total_fill

    amount_cell = ws.cell(row=total_row_idx, column=2, value=f"{total_amount:,.2f}")
    amount_cell.font = total_font
    amount_cell.fill = total_fill
    amount_cell.alignment = center_align

    ws.merge_cells(f"C{total_row_idx}:{last_col}{total_row_idx}")
    label_cell = ws.cell(row=total_row_idx, column=3, value="إجمالي المبلغ")
    label_cell.font = total_font
    label_cell.fill = total_fill
    label_cell.alignment = center_align
    for col in range(4, len(headers) + 1):
        ws.cell(row=total_row_idx, column=col).fill = total_fill

    # ── صف تذييل التوقيعات (فارغ دائماً) ──────────────────────────────────────
    # ✅ العمود 1 (A) يظهر أقصى يمين الشاشة تلقائياً بفضل rightToLeft=True —
    # لذا تُوزَّع التسميات بترتيبها الطبيعي بدءاً من العمود 1 (وليس معكوسة
    # كما في PDF، حيث لا يوجد انعكاس تلقائي مماثل)، فيظهر "مستلم العهدة"
    # في أقصى اليمين تلقائياً بلا أي حساب عكسي.
    footer_row_idx = total_row_idx + 3
    footer_labels_rtl = ["مستلم العهدة", "المراجعة", "المسؤول المالي", "مسؤول العمليات"]
    n = len(headers)
    cols_per_label = n / 4
    col_ranges = []
    for i in range(4):
        start = int(round(i * cols_per_label)) + 1
        end = int(round((i + 1) * cols_per_label))
        col_ranges.append((start, max(start, end)))
    for label, (c_start, c_end) in zip(footer_labels_rtl, col_ranges):
        if c_end > c_start:
            ws.merge_cells(start_row=footer_row_idx, start_column=c_start, end_row=footer_row_idx, end_column=c_end)
        cell = ws.cell(row=footer_row_idx, column=c_start, value=label)
        cell.font = footer_font
        cell.alignment = center_align
        cell.border = Border(bottom=Side(style="thin", color="999999"))
    ws.row_dimensions[footer_row_idx + 1].height = 24  # فراغ فارغ للتوقيع الفعلي

    col_widths = [6, 12, 22, 16, 18, 26, 14]
    for i, width in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    logger.info(f"[pharmacy_evacuation_excel] built  rows={len(rows)}  size={output.getbuffer().nbytes:,}")
    return output
