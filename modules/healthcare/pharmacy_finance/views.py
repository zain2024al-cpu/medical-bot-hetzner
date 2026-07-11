# modules/healthcare/pharmacy_finance/views.py
# Pure view builders لتدفق "💰 التقرير المالي".

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from modules.healthcare.pharmacy_finance.session import PharmacyFinanceSession
from modules.healthcare.views import format_arabic_date

HCPHFIN = "hcphfin"

_DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
_THIN    = "─────────────────────"

_SOURCE_LABEL = {"medication": "💊 صرف أدوية", "supplies": "🏥 مستلزمات طبية"}


def _row_label(r) -> str:
    """تسمية زر صف واحد في أي قائمة حالات — تُظهر رقم الفاتورة إن وُجد
    حتى يُميَّز السجل المطلوب تعديله بسرعة."""
    mark = "✅" if r.has_financial else "🆕"
    label = f"{mark} {_SOURCE_LABEL.get(r.source_type, '')} — {r.patient_name}"
    if getattr(r, "invoice_number", ""):
        label += f" (🧾{r.invoice_number})"
    return label[:64]


def build_list_prompt(rows, page: int, total_pages: int, total: int) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER,
        "💰  **التقرير المالي — اختر حالة**",
        "",
        f"العدد الإجمالي (صرف من الصيدلية): {total}",
        _THIN,
    ]
    if not rows:
        lines.append("لا توجد حالات صرف من الصيدلية بعد.")

    kb_rows = [[InlineKeyboardButton("📅 تعديل تقرير بتاريخ", callback_data=f"{HCPHFIN}:datesearch")]]
    for r in rows:
        kb_rows.append([InlineKeyboardButton(
            _row_label(r), callback_data=f"{HCPHFIN}:pick:{r.source_type}:{r.source_record_id}"
        )])

    nav = []
    if total_pages > 1 and page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"{HCPHFIN}:page:{page - 1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data=f"{HCPHFIN}:noop"))
    if total_pages > 1 and page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"{HCPHFIN}:page:{page + 1}"))
    if nav:
        kb_rows.append(nav)

    kb_rows.append([InlineKeyboardButton("❌ إغلاق", callback_data=f"{HCPHFIN}:cancel")])
    return "\n".join(lines), InlineKeyboardMarkup(kb_rows)


def build_date_list_prompt(rows, target_date) -> tuple[str, InlineKeyboardMarkup]:
    """قائمة الحالات ليوم واحد محدَّد — شاشة 'تعديل تقرير بتاريخ'."""
    from datetime import datetime as _dt
    date_label = format_arabic_date(_dt.combine(target_date, _dt.min.time()))
    lines = [
        _DIVIDER,
        "📅  **تعديل تقرير — حسب التاريخ**",
        "",
        f"التاريخ: {date_label}",
        f"عدد الحالات: {len(rows)}",
        _THIN,
    ]
    if not rows:
        lines.append("لا توجد حالات صرف من الصيدلية في هذا التاريخ.")

    kb_rows = []
    for r in rows:
        kb_rows.append([InlineKeyboardButton(
            _row_label(r), callback_data=f"{HCPHFIN}:pick:{r.source_type}:{r.source_record_id}"
        )])
    kb_rows.append([InlineKeyboardButton("📆 تاريخ آخر", callback_data=f"{HCPHFIN}:datesearch")])
    kb_rows.append([InlineKeyboardButton("🔙 رجوع للقائمة الكاملة", callback_data=f"{HCPHFIN}:page:0")])
    return "\n".join(lines), InlineKeyboardMarkup(kb_rows)


def _source_header(session: PharmacyFinanceSession) -> list[str]:
    return [
        f"👤 المريض: {session.patient_name}",
        f"📦 العدد: {session.item_count}",
        f"🏪 جهة الصرف: الصيدلية",
    ]


def build_item_count_prompt(session: PharmacyFinanceSession, *, error: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER, "📦  **عدد الأصناف**", "",
        f"👤 المريض: {session.patient_name}",
        _THIN, "",
    ]
    if error:
        lines += ["⚠️ *الرجاء إرسال نص غير فارغ.*", ""]
    lines.append(f"العدد/التفاصيل الحالية: {session.item_count}")
    lines.append("")
    lines.append("أرسل العدد أو التفاصيل الجديدة (مثال: بنادول 3، شاش 2):")
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCPHFIN}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCPHFIN}:cancel"),
    ]])
    return "\n".join(lines), kb


def build_invoice_number_prompt(session: PharmacyFinanceSession) -> tuple[str, InlineKeyboardMarkup]:
    lines = [_DIVIDER, "🧾  **رقم الفاتورة**", "", *_source_header(session), _THIN, "", "أرسل رقم الفاتورة:"]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCPHFIN}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCPHFIN}:cancel"),
    ]])
    return "\n".join(lines), kb


def build_expense_item_prompt(session: PharmacyFinanceSession) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER, "📋  **بند الصرف**", "",
        *_source_header(session),
        f"🧾 رقم الفاتورة: {session.invoice_number}",
        _THIN, "", "أرسل بند الصرف:",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCPHFIN}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCPHFIN}:cancel"),
    ]])
    return "\n".join(lines), kb


def build_invoice_total_prompt(session: PharmacyFinanceSession, *, error: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER, "💰  **إجمالي الفاتورة**", "",
        *_source_header(session),
        f"🧾 رقم الفاتورة: {session.invoice_number}",
        f"📋 بند الصرف: {session.expense_item}",
        _THIN, "",
    ]
    if error:
        lines += ["⚠️ *الرجاء إدخال رقم صحيح وموجب.* (مثال: 1500 أو 1500.50)", ""]
    lines.append("أرسل إجمالي مبلغ الفاتورة:")
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCPHFIN}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCPHFIN}:cancel"),
    ]])
    return "\n".join(lines), kb


def build_discount_percent_prompt(session: PharmacyFinanceSession, *, error: bool = False) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _DIVIDER, "🏷️  **نسبة التخفيض %**", "",
        *_source_header(session),
        f"💰 إجمالي الفاتورة: {session.invoice_total:.2f}",
        _THIN, "",
    ]
    if error:
        lines += ["⚠️ *الرجاء إدخال نسبة بين 0 و100.* (مثال: 10 أو 0 إن لا يوجد تخفيض)", ""]
    lines.append("أرسل نسبة التخفيض % (أرسل 0 إن لم يوجد تخفيض):")
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCPHFIN}:back"),
        InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCPHFIN}:cancel"),
    ]])
    return "\n".join(lines), kb


def build_review(session: PharmacyFinanceSession) -> tuple[str, InlineKeyboardMarkup]:
    title = "✏️ تعديل بيانات مالية" if session.is_edit else "💰 مراجعة البيانات المالية"
    lines = [
        title, "",
        *_source_header(session),
        "─────────────────────",
        f"🧾 رقم الفاتورة: {session.invoice_number}",
        f"📋 بند الصرف: {session.expense_item}",
        f"💰 إجمالي الفاتورة: {session.invoice_total:.2f}",
        f"🏷️ نسبة التخفيض: {session.discount_percent:.1f}%",
        f"💵 مبلغ الخصم: {session.discount_amount:.2f}",
        f"💳 صافي المبلغ: {session.net_amount:.2f}",
        "",
        "هل تريد الحفظ؟",
    ]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💾 حفظ", callback_data=f"{HCPHFIN}:confirm"),
         InlineKeyboardButton("❌ إلغاء", callback_data=f"{HCPHFIN}:cancel")],
        [InlineKeyboardButton("✏️ عدد الأصناف", callback_data=f"{HCPHFIN}:edit_item_count"),
         InlineKeyboardButton("✏️ رقم الفاتورة", callback_data=f"{HCPHFIN}:edit_invoice_number")],
        [InlineKeyboardButton("✏️ بند الصرف", callback_data=f"{HCPHFIN}:edit_expense_item"),
         InlineKeyboardButton("✏️ إجمالي الفاتورة", callback_data=f"{HCPHFIN}:edit_invoice_total")],
        [InlineKeyboardButton("✏️ نسبة التخفيض", callback_data=f"{HCPHFIN}:edit_discount_percent")],
    ])
    return "\n".join(lines), kb


def build_success(net_amount: float, patient_name: str) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        "✅ **تم حفظ البيانات المالية بنجاح**", "",
        f"👤 {patient_name}", f"💳 صافي المبلغ: {net_amount:.2f}",
    ]
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 قائمة أخرى", callback_data=f"{HCPHFIN}:page:0")]])
    return "\n".join(lines), kb


def build_cancelled() -> tuple[str, InlineKeyboardMarkup]:
    return "✅ تم الإلغاء.", InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCPHFIN}:page:0")]])


def build_error(message: str) -> tuple[str, InlineKeyboardMarkup]:
    return f"❌ {message}", InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=f"{HCPHFIN}:page:0")]])
