# services/pharmacy_evacuation_excel.py
# Excel لـ"🖨️ طباعة مسير إخلاء الأدوية والمستلزمات الطبية".
# نفس نمط openpyxl + rightToLeft المُثبت في bot/handlers/admin/admin_evaluation.py.
# نفس ترتيب أعمدة PDF بالضبط: م | المبلغ | الاسم | رقم الفاتورة | بند الصرف | البيان | التاريخ

import io
import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)


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
    title_font = Font(name="Arial", bold=True, size=14, color="1A237E")
    normal_font = Font(name="Arial", size=10)
    total_font = Font(name="Arial", bold=True, size=11, color="FFFFFF")
    total_fill = PatternFill(start_color="1565C0", end_color="1565C0", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    right_align = Alignment(horizontal="right", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"), right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"), bottom=Side(style="thin", color="CCCCCC"),
    )

    headers = ["م", "المبلغ", "الاسم", "رقم الفاتورة", "بند الصرف", "البيان", "التاريخ"]

    ws.merge_cells(f"A1:{get_column_letter(len(headers))}1")
    ws["A1"] = "مسير إخلاء الأدوية والمستلزمات الطبية"
    ws["A1"].font = title_font
    ws["A1"].alignment = center_align

    ws.merge_cells(f"A2:{get_column_letter(len(headers))}2")
    ws["A2"] = f"الفترة: من {start_date.strftime('%Y-%m-%d')} إلى {end_date.strftime('%Y-%m-%d')}"
    ws["A2"].font = Font(name="Arial", size=10, color="777777")
    ws["A2"].alignment = center_align

    header_row_idx = 4
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
            cell.alignment = center_align if col in (1, 2, 4, 7) else right_align

    total_row_idx = header_row_idx + len(rows) + 1
    ws.merge_cells(f"A{total_row_idx}:{get_column_letter(len(headers) - 1)}{total_row_idx}")
    ws.cell(row=total_row_idx, column=1, value="إجمالي المبلغ").font = total_font
    ws.cell(row=total_row_idx, column=1).fill = total_fill
    ws.cell(row=total_row_idx, column=1).alignment = center_align
    total_cell = ws.cell(row=total_row_idx, column=len(headers), value=f"{total_amount:,.2f}")
    total_cell.font = total_font
    total_cell.fill = total_fill
    total_cell.alignment = center_align

    col_widths = [6, 12, 22, 16, 18, 26, 14]
    for i, width in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    logger.info(f"[pharmacy_evacuation_excel] built  rows={len(rows)}  size={output.getbuffer().nbytes:,}")
    return output
