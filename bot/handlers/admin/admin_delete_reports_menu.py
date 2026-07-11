# bot/handlers/admin/admin_delete_reports_menu.py
#
# قائمة حذف التقارير الموحدة
# تتيح حذف:
# - تقارير المترجمين (User Reports)
# - تقارير الرعاية الصحية (Healthcare Reports)
# - تقارير الخدمات العامة (General Services Reports)

from __future__ import annotations

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler,
    filters
)

from bot.shared_auth import is_admin
from bot.handlers.admin.decorators import require_admin

logger = logging.getLogger(__name__)

# ── States ─────────────────────────────────────────────────────────────────────
(
    SHOW_MENU,
) = range(1)

_PFX = "del_menu"


# ✅ زر "🗑️ حذف التقارير" مستخدَم بنفس النص بالضبط في قائمتي الأدمن والمستخدم
# العادي (bot/keyboards.py: admin_main_kb() و user_main_kb()) — وكلاهما
# ConversationHandler مسجَّل بدون group صريح (أي المجموعة 0 الافتراضية).
# بدون هذا الفلتر، كان هذا الـConversationHandler (المسجَّل أولاً في
# handlers_registry.py) يعترض الضغطة لأي مستخدم (حتى غير الأدمن)، وينهي
# المحادثة فوراً بلا أي رسالة — فلا تصل الضغطة إطلاقاً لمعالج المترجمين
# الحقيقي في user_reports_delete.py المسجَّل بعده بنفس المجموعة. بإضافة
# هذا الفلتر، فحص المطابقة (check_update) يعيد False لغير الأدمن، فينتقل
# PTB تلقائياً للمعالج التالي في نفس المجموعة (معالج المترجمين).
class _IsAdminFilter(filters.MessageFilter):
    def filter(self, message):
        user = message.from_user
        return bool(user and is_admin(user.id))


_is_admin_filter = _IsAdminFilter()


# ── Keyboards ──────────────────────────────────────────────────────────────────

def _menu_kb() -> InlineKeyboardMarkup:
    """Delete menu options."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👨‍⚕️ تقارير المترجمين", callback_data=f"{_PFX}:translators")],
        [InlineKeyboardButton("🏥 تقارير الرعاية الصحية", callback_data=f"{_PFX}:healthcare")],
        [InlineKeyboardButton("🛠️ تقارير الخدمات العامة", callback_data=f"{_PFX}:services")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")],
    ])


# ── Handlers ───────────────────────────────────────────────────────────────────

async def start_delete_reports_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Show delete menu."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return ConversationHandler.END

    context.user_data.clear()

    try:
        await update.message.reply_text(
            "🗑️ *حذف التقارير*\n\n"
            "اختر نوع التقارير المراد حذفها:",
            reply_markup=_menu_kb(),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[del_menu] Failed to show menu: {exc}")

    return SHOW_MENU


@require_admin
async def handle_menu_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle delete choice - delegate to appropriate handler."""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ""

    if data == f"{_PFX}:cancel":
        try:
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
        context.user_data.clear()
        return ConversationHandler.END

    # Mark which type of reports to delete
    if data == f"{_PFX}:translators":
        context.user_data["_delete_type"] = "translators"
        type_label = "تقارير المترجمين"
    elif data == f"{_PFX}:healthcare":
        context.user_data["_delete_type"] = "healthcare"
        type_label = "تقارير الرعاية الصحية"
    elif data == f"{_PFX}:services":
        context.user_data["_delete_type"] = "services"
        type_label = "تقارير الخدمات العامة"
    else:
        return SHOW_MENU

    # Show confirmation message and delegate to appropriate handler
    try:
        await query.edit_message_text(
            f"جاري تحميل {type_label}...",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        pass

    # Delegate to the appropriate delete handler
    if context.user_data.get("_delete_type") == "translators":
        try:
            from bot.handlers.admin.admin_delete_reports import _year_keyboard, _show_year_selection

            # Call the year selection directly
            await query.edit_message_text("🗑️ *حذف تقارير المترجمين*\n\nاختر السنة:")
            await _show_year_selection(query.message, context)
        except Exception as exc:
            logger.error(f"[del_menu] Failed to delegate to delete reports: {exc}")
            try:
                await query.edit_message_text("❌ فشل تحميل حذف التقارير.\n\nحاول مرة أخرى.")
            except Exception:
                pass
    elif context.user_data.get("_delete_type") == "healthcare":
        await _delete_healthcare_reports(update, context)
    elif context.user_data.get("_delete_type") == "services":
        await _delete_services_reports(update, context)

    return ConversationHandler.END


def _healthcare_models():
    """جميع جداول الرعاية الصحية الخمسة (وليس فقط 'أخرى').

    ✅ نظام الرعاية الصحية يحفظ التقارير في 5 جداول منفصلة حسب نوع الإجراء
    (جروح / متابعة طبية / أدوية / مستلزمات / أخرى). أي عملية حذف أو عدّ
    يجب أن تمر على الخمسة معاً وإلا ستظهر تقارير "غير موجودة" رغم وجودها
    فعلياً في أحد الجداول الأخرى.
    """
    from db.models import (
        WoundRecord, MedicalFollowupRecord, MedicationRecord,
        SuppliesRecord, OtherHealthcareRecord,
    )
    return [WoundRecord, MedicalFollowupRecord, MedicationRecord, SuppliesRecord, OtherHealthcareRecord]


async def _delete_healthcare_reports(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Delete healthcare reports - show year selection."""
    query = update.callback_query
    from datetime import datetime
    from sqlalchemy import extract
    from db.session import SessionLocal

    try:
        # Get years across ALL healthcare tables (union)
        with SessionLocal() as s:
            years_set = set()
            for model in _healthcare_models():
                rows = (
                    s.query(extract('year', model.created_at))
                     .filter(model.created_at.isnot(None))
                     .group_by(extract('year', model.created_at))
                     .all()
                )
                for r in rows:
                    if r[0] is not None:
                        years_set.add(int(r[0]))

        db_years = sorted(years_set, reverse=True)

        if not db_years:
            db_years = [datetime.now().year]

        # Build year buttons
        buttons = []
        row = []
        for year in db_years:
            row.append(InlineKeyboardButton(f"📅 {year}", callback_data=f"del_hc:year:{year}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="del_hc:cancel")])

        await query.edit_message_text(
            "🏥 *حذف تقارير الرعاية الصحية*\n\n"
            "اختر السنة:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[del_menu] Healthcare year selection failed: {exc}")
        try:
            await query.edit_message_text("❌ خطأ في تحميل السنوات.")
        except Exception:
            pass


async def _delete_services_reports(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Delete services reports - show year selection."""
    query = update.callback_query
    from datetime import datetime
    from sqlalchemy import extract
    from db.session import SessionLocal
    from db.models import PublicServiceRecord

    try:
        # Get years from service records
        with SessionLocal() as s:
            db_years = [
                int(r[0]) for r in
                s.query(extract('year', PublicServiceRecord.created_at))
                 .filter(PublicServiceRecord.created_at.isnot(None))
                 .group_by(extract('year', PublicServiceRecord.created_at))
                 .order_by(extract('year', PublicServiceRecord.created_at).desc())
                 .all()
            ]

        if not db_years:
            db_years = [datetime.now().year]

        # Build year buttons
        buttons = []
        row = []
        for year in db_years:
            row.append(InlineKeyboardButton(f"📅 {year}", callback_data=f"del_svc:year:{year}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)

        buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="del_svc:cancel")])

        await query.edit_message_text(
            "🛠️ *حذف تقارير الخدمات العامة*\n\n"
            "اختر السنة:",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[del_menu] Services year selection failed: {exc}")
        try:
            await query.edit_message_text("❌ خطأ في تحميل السنوات.")
        except Exception:
            pass


@require_admin
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel handler."""
    query = update.callback_query
    if query:
        try:
            await query.answer()
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
    context.user_data.clear()
    return ConversationHandler.END


# ── Callback handlers for healthcare and services ────────────────────────────

_MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
              "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]

# رموز مختصرة لكل جدول رعاية صحية (تُستخدم داخل callback_data المحدود بـ 64 حرفاً)
_HC_TABLE_CODES = {
    "wr": ("👁️ جرح", "WoundRecord"),
    "mf": ("🩺 متابعة طبية", "MedicalFollowupRecord"),
    "md": ("💊 أدوية", "MedicationRecord"),
    "sp": ("📦 مستلزمات", "SuppliesRecord"),
    "oh": ("📁 أخرى", "OtherHealthcareRecord"),
}

_HC_ITEMS_PER_PAGE = 6


def _hc_model_by_code(code: str):
    """إرجاع الكلاس (model) المطابق لرمز الجدول المختصر."""
    from db.models import (
        WoundRecord, MedicalFollowupRecord, MedicationRecord,
        SuppliesRecord, OtherHealthcareRecord,
    )
    mapping = {
        "wr": WoundRecord,
        "mf": MedicalFollowupRecord,
        "md": MedicationRecord,
        "sp": SuppliesRecord,
        "oh": OtherHealthcareRecord,
    }
    return mapping.get(code)


async def _show_hc_months(query, year: int) -> None:
    """عرض قائمة الأشهر لسنة معينة (رعاية صحية)."""
    buttons = []
    months = list(range(1, 13))
    for i in range(0, len(months), 3):
        row = []
        for month in months[i:i + 3]:
            row.append(InlineKeyboardButton(
                _MONTHS_AR[month - 1], callback_data=f"del_hc:month:{year}:{month}"
            ))
        buttons.append(row)

    buttons.append([InlineKeyboardButton("🔙 رجوع للسنوات", callback_data="del_hc:back_year")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="del_hc:cancel")])

    try:
        await query.edit_message_text(
            f"🏥 *اختر الشهر* - {year}",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        pass


async def _show_hc_list(query, year: int, month: int, page: int = 0) -> None:
    """عرض قائمة التقارير التفصيلية لشهر معين (كل الجداول الخمسة مجمّعة) مع أزرار حذف فردية."""
    from db.session import SessionLocal
    from sqlalchemy import extract

    month_name = _MONTHS_AR[month - 1]

    items = []  # (code, id, created_at, patient_name, specialist_name, notes)
    with SessionLocal() as s:
        for code, (label, _) in _HC_TABLE_CODES.items():
            model = _hc_model_by_code(code)
            rows = s.query(model).filter(
                extract('year', model.created_at) == year,
                extract('month', model.created_at) == month,
            ).all()
            for r in rows:
                items.append({
                    "code": code,
                    "id": r.id,
                    "created_at": r.created_at,
                    "patient_name": getattr(r, "patient_name", None) or "غير محدد",
                    "specialist_name": getattr(r, "specialist_name", None) or "-",
                    "notes": (getattr(r, "notes", None) or "").strip(),
                })

    items.sort(key=lambda x: x["created_at"] or 0, reverse=True)
    total_count = len(items)

    if total_count == 0:
        buttons = [
            [InlineKeyboardButton("🔙 رجوع للأشهر", callback_data=f"del_hc:back_month:{year}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="del_hc:cancel")],
        ]
        try:
            await query.edit_message_text(
                f"🏥 *حذف تقارير الرعاية الصحية*\n\n"
                f"📅 {month_name} {year}\n\n"
                f"⚠️ لا توجد تقارير في هذا الشهر.",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass
        return

    total_pages = (total_count + _HC_ITEMS_PER_PAGE - 1) // _HC_ITEMS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    page_items = items[page * _HC_ITEMS_PER_PAGE: (page + 1) * _HC_ITEMS_PER_PAGE]

    text = (
        f"🏥 *حذف تقارير الرعاية الصحية*\n\n"
        f"📅 {month_name} {year}\n"
        f"📊 عدد التقارير: *{total_count}*\n"
        f"📄 الصفحة: {page + 1}/{total_pages}\n\n"
    )

    buttons = []
    for it in page_items:
        type_label = _HC_TABLE_CODES[it["code"]][0]
        time_str = it["created_at"].strftime("%d/%m %H:%M") if it["created_at"] else ""
        note_preview = (it["notes"][:30] + "…") if len(it["notes"]) > 30 else it["notes"]

        text += (
            f"📌 *#{it['id']}* ({type_label}) - {time_str}\n"
            f"   👤 {it['patient_name']} | 🧑‍⚕️ {it['specialist_name']}\n"
        )
        if note_preview:
            text += f"   📝 {note_preview}\n"
        text += "\n"

        buttons.append([InlineKeyboardButton(
            f"🗑️ حذف #{it['id']} - {it['patient_name'][:15]} ({type_label})",
            callback_data=f"del_hc:item:{it['code']}:{it['id']}:{year}:{month}:{page}",
        )])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ السابق", callback_data=f"del_hc:page:{year}:{month}:{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("التالي ▶️", callback_data=f"del_hc:page:{year}:{month}:{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(
        f"⚠️ حذف الكل ({total_count} تقرير)", callback_data=f"del_hc:delall:{year}:{month}"
    )])
    buttons.append([InlineKeyboardButton("🔙 رجوع للأشهر", callback_data=f"del_hc:back_month:{year}")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="del_hc:cancel")])

    try:
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.error(f"[del_menu] Failed to render healthcare list: {exc}")


@require_admin
async def handle_healthcare_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle healthcare deletion callbacks (del_hc:*)"""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ""

    if data == "del_hc:cancel":
        try:
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
        context.user_data.pop("_delete_type", None)
        context.user_data.pop("_hc_year", None)
        return

    if data == "del_hc:back_year":
        await _delete_healthcare_reports(update, context)
        return

    if data.startswith("del_hc:back_month:"):
        year = int(data.split(":")[2])
        await _show_hc_months(query, year)
        return

    if data.startswith("del_hc:year:"):
        # Year selected - show months
        year = int(data.split(":")[2])
        context.user_data["_hc_year"] = year
        await _show_hc_months(query, year)
        return

    if data.startswith("del_hc:month:"):
        # Month selected - show detailed report list (not just a count)
        parts = data.split(":")
        year = int(parts[2])
        month = int(parts[3])
        await _show_hc_list(query, year, month, page=0)
        return

    if data.startswith("del_hc:page:"):
        parts = data.split(":")
        year, month, page = int(parts[2]), int(parts[3]), int(parts[4])
        await _show_hc_list(query, year, month, page=page)
        return

    if data.startswith("del_hc:item:"):
        # Show confirmation for a single record
        parts = data.split(":")
        code, rec_id, year, month, page = parts[2], int(parts[3]), int(parts[4]), int(parts[5]), int(parts[6])

        from db.session import SessionLocal
        model = _hc_model_by_code(code)
        if model is None:
            try:
                await query.edit_message_text("❌ نوع تقرير غير معروف.")
            except Exception:
                pass
            return

        with SessionLocal() as s:
            rec = s.query(model).filter_by(id=rec_id).first()
            if not rec:
                try:
                    await query.edit_message_text("⚠️ التقرير غير موجود أو تم حذفه مسبقاً.")
                except Exception:
                    pass
                return
            patient = getattr(rec, "patient_name", None) or "غير محدد"
            specialist = getattr(rec, "specialist_name", None) or "غير محدد"
            date_str = rec.created_at.strftime("%Y-%m-%d %H:%M") if rec.created_at else "غير محدد"

        type_label = _HC_TABLE_CODES[code][0]
        buttons = [
            [
                InlineKeyboardButton("✅ نعم، احذف", callback_data=f"del_hc:idel:{code}:{rec_id}:{year}:{month}:{page}"),
                InlineKeyboardButton("❌ لا، رجوع", callback_data=f"del_hc:page:{year}:{month}:{page}"),
            ]
        ]
        try:
            await query.edit_message_text(
                f"⚠️ *تأكيد حذف تقرير*\n\n"
                f"📌 رقم التقرير: #{rec_id}\n"
                f"📋 النوع: {type_label}\n"
                f"👤 المريض: {patient}\n"
                f"🧑‍⚕️ الأخصائي: {specialist}\n"
                f"📅 التاريخ: {date_str}\n\n"
                f"⚠️ *هذا الإجراء لا يمكن التراجع عنه!*",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass
        return

    if data.startswith("del_hc:idel:"):
        # Execute single-record deletion then refresh the list
        parts = data.split(":")
        code, rec_id, year, month, page = parts[2], int(parts[3]), int(parts[4]), int(parts[5]), int(parts[6])

        from db.session import SessionLocal
        model = _hc_model_by_code(code)
        deleted_ok = False
        if model is not None:
            with SessionLocal() as s:
                rec = s.query(model).filter_by(id=rec_id).first()
                if rec:
                    s.delete(rec)
                    s.commit()
                    deleted_ok = True

        if deleted_ok:
            logger.info(f"[del_menu] Deleted healthcare record #{rec_id} (type={code})")
        else:
            try:
                await query.answer("⚠️ التقرير غير موجود أو تم حذفه مسبقاً.", show_alert=True)
            except Exception:
                pass

        await _show_hc_list(query, year, month, page=page)
        return

    if data.startswith("del_hc:delall:"):
        # Confirm bulk deletion for the whole month
        parts = data.split(":")
        year, month = int(parts[2]), int(parts[3])

        from db.session import SessionLocal
        from sqlalchemy import extract

        with SessionLocal() as s:
            count = 0
            for m in _healthcare_models():
                count += s.query(m).filter(
                    extract('year', m.created_at) == year,
                    extract('month', m.created_at) == month,
                ).count()

        month_name = _MONTHS_AR[month - 1]
        buttons = [
            [
                InlineKeyboardButton("✅ نعم، احذف الكل", callback_data=f"del_hc:confirm:{year}:{month}"),
                InlineKeyboardButton("❌ رجوع للقائمة", callback_data=f"del_hc:page:{year}:{month}:0"),
            ]
        ]
        try:
            await query.edit_message_text(
                f"⚠️ *تأكيد حذف كل تقارير الشهر*\n\n"
                f"📅 {month_name} {year}\n"
                f"📊 عدد التقارير: {count}\n\n"
                f"⚠️ هذا الإجراء **لا يمكن التراجع عنه!**",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass
        return

    if data.startswith("del_hc:confirm:"):
        # Confirm bulk deletion of the entire month across all tables
        parts = data.split(":")
        year = int(parts[2])
        month = int(parts[3])

        from db.session import SessionLocal
        from sqlalchemy import extract

        try:
            with SessionLocal() as s:
                deleted = 0
                for model in _healthcare_models():
                    deleted += s.query(model).filter(
                        extract('year', model.created_at) == year,
                        extract('month', model.created_at) == month,
                    ).delete(synchronize_session=False)
                s.commit()

            month_name = _MONTHS_AR[month - 1]
            buttons = [
                [InlineKeyboardButton("🔙 رجوع للأشهر", callback_data=f"del_hc:back_month:{year}")],
                [InlineKeyboardButton("❌ إنهاء", callback_data="del_hc:cancel")],
            ]

            await query.edit_message_text(
                f"✅ *تم الحذف بنجاح*\n\n"
                f"🏥 تقارير الرعاية الصحية\n"
                f"📅 {month_name} {year}\n"
                f"🗑️ عدد التقارير المحذوفة: {deleted}",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
            )

            logger.info(f"[del_menu] Deleted {deleted} healthcare records for {month}/{year}")
        except Exception as exc:
            logger.error(f"[del_menu] Healthcare deletion failed: {exc}")
            try:
                await query.edit_message_text("❌ فشل الحذف. حاول مرة أخرى.")
            except Exception:
                pass


@require_admin
async def handle_services_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle services deletion callbacks (del_svc:*)"""
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ""

    if data == "del_svc:cancel":
        try:
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
        context.user_data.pop("_delete_type", None)
        context.user_data.pop("_svc_year", None)
        return

    if data == "del_svc:back_year":
        await _delete_services_reports(update, context)
        return

    if data.startswith("del_svc:back_month:"):
        year = int(data.split(":")[2])
        data = f"del_svc:year:{year}"  # fall through to the year branch below to re-render months

    if data.startswith("del_svc:year:"):
        # Year selected - show months
        year = int(data.split(":")[2])
        context.user_data["_svc_year"] = year

        buttons = []
        months = list(range(1, 13))
        for i in range(0, len(months), 3):
            row = []
            for month in months[i:i+3]:
                month_name = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                             "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"][month-1]
                row.append(InlineKeyboardButton(f"{month_name[:3]}", callback_data=f"del_svc:month:{year}:{month}"))
            buttons.append(row)

        buttons.append([InlineKeyboardButton("🔙 رجوع للسنوات", callback_data="del_svc:back_year")])
        buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="del_svc:cancel")])

        try:
            await query.edit_message_text(
                f"🛠️ *اختر الشهر* - {year}",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    elif data.startswith("del_svc:month:"):
        # Month selected - confirm deletion
        parts = data.split(":")
        year = int(parts[2])
        month = int(parts[3])

        from db.session import SessionLocal
        from db.models import PublicServiceRecord
        from sqlalchemy import extract

        with SessionLocal() as s:
            count = s.query(PublicServiceRecord).filter(
                extract('year', PublicServiceRecord.created_at) == year,
                extract('month', PublicServiceRecord.created_at) == month,
            ).count()

        month_name = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                     "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"][month-1]

        buttons = [
            [
                InlineKeyboardButton("✅ نعم، احذف الكل", callback_data=f"del_svc:confirm:{year}:{month}"),
                InlineKeyboardButton("❌ رجوع", callback_data=f"del_svc:back_month:{year}")
            ]
        ]

        try:
            await query.edit_message_text(
                f"⚠️ *تأكيد حذف تقارير الخدمات*\n\n"
                f"📅 {month_name} {year}\n"
                f"📊 عدد التقارير: {count}\n\n"
                f"⚠️ هذا الإجراء **لا يمكن التراجع عنه!**",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    elif data.startswith("del_svc:confirm:"):
        # Confirm deletion
        parts = data.split(":")
        year = int(parts[2])
        month = int(parts[3])

        from db.session import SessionLocal
        from db.models import PublicServiceRecord
        from sqlalchemy import extract

        try:
            with SessionLocal() as s:
                deleted = s.query(PublicServiceRecord).filter(
                    extract('year', PublicServiceRecord.created_at) == year,
                    extract('month', PublicServiceRecord.created_at) == month,
                ).delete()
                s.commit()

            month_name = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
                         "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"][month-1]

            buttons = [
                [InlineKeyboardButton("🔙 رجوع للأشهر", callback_data=f"del_svc:back_month:{year}")],
                [InlineKeyboardButton("❌ إنهاء", callback_data="del_svc:cancel")],
            ]

            await query.edit_message_text(
                f"✅ *تم الحذف بنجاح*\n\n"
                f"🛠️ تقارير الخدمات العامة\n"
                f"📅 {month_name} {year}\n"
                f"🗑️ عدد التقارير المحذوفة: {deleted}",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN,
            )

            logger.info(f"[del_menu] Deleted {deleted} service records for {month}/{year}")
        except Exception as exc:
            logger.error(f"[del_menu] Services deletion failed: {exc}")
            try:
                await query.edit_message_text("❌ فشل الحذف. حاول مرة أخرى.")
            except Exception:
                pass


# ── Registration ───────────────────────────────────────────────────────────────

def register(app) -> None:
    """Register delete reports menu handler."""
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(r"^🗑️ حذف التقارير$") & _is_admin_filter,
                start_delete_reports_menu,
            ),
        ],
        states={
            SHOW_MENU: [
                CallbackQueryHandler(handle_menu_choice, pattern=rf"^{_PFX}:"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern=rf"^{_PFX}:cancel$"),
        ],
        name="delete_reports_menu_conv",
        per_chat=True,
        per_user=True,
        per_message=False,
    )

    app.add_handler(conv)

    # Register healthcare deletion callbacks
    app.add_handler(CallbackQueryHandler(handle_healthcare_callback, pattern=r"^del_hc:"))

    # Register services deletion callbacks
    app.add_handler(CallbackQueryHandler(handle_services_callback, pattern=r"^del_svc:"))

    logger.info("[del_menu] ConversationHandler registered for delete menu")
