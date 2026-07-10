# bot/handlers/admin/admin_patient_report.py
#
# Patient report handler — single patient with multiselect filters.
#
# Dialog flow:
#   👤 Patient Report selected in admin_reports_menu
#       ↓  show_patient_search()
#   ✏️ Type patient name
#       ↓  handle_patient_search()
#   Pick patient from results
#       ↓  handle_patient_picked()
#   📅 Select departments (all or specific)
#       ↓  handle_depts_picked()
#   📋 Select procedure types (all or specific)
#       ↓  handle_actions_picked()
#   📅 Select period
#       ↓  handle_period_picked()
#   Generate & send professional PDF
#
# Callback prefix: pr:
# States: PR_SEARCH → PR_PICK → PR_DEPTS → PR_ACTIONS → PR_PERIOD → END
#
from __future__ import annotations

import logging
from datetime import datetime, timedelta, date

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters,
)

from bot.shared_auth import is_admin
from bot.handlers.admin.decorators import require_admin

logger = logging.getLogger(__name__)

# ── ConversationHandler states ────────────────────────────────────────────────
PR_SEARCH  = 700
PR_PICK    = 701
PR_DEPTS   = 702
PR_ACTIONS = 703
PR_PERIOD  = 704

_PFX = "pr"   # callback prefix


# ── Keyboards ─────────────────────────────────────────────────────────────────

def _cancel_kb(back_cb: str | None = None) -> InlineKeyboardMarkup:
    row = []
    if back_cb:
        row.append(InlineKeyboardButton("⬅️ رجوع", callback_data=back_cb))
    row.append(InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel"))
    return InlineKeyboardMarkup([row])


def _depts_kb() -> InlineKeyboardMarkup:
    """Departments selection."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ كل الأقسام", callback_data=f"{_PFX}:depts:all")],
        [InlineKeyboardButton("🔍 اختيار محدد", callback_data=f"{_PFX}:depts:select")],
        [InlineKeyboardButton("⬅️ رجوع",       callback_data=f"{_PFX}:back_patient")],
        [InlineKeyboardButton("❌ إلغاء",       callback_data=f"{_PFX}:cancel")],
    ])


def _actions_kb() -> InlineKeyboardMarkup:
    """Procedure types selection."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ كل الإجراءات", callback_data=f"{_PFX}:actions:all")],
        [InlineKeyboardButton("🔍 اختيار محدد", callback_data=f"{_PFX}:actions:select")],
        [InlineKeyboardButton("⬅️ رجوع",         callback_data=f"{_PFX}:back_depts")],
        [InlineKeyboardButton("❌ إلغاء",         callback_data=f"{_PFX}:cancel")],
    ])


def _period_kb(patient_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 كل التقارير",    callback_data=f"{_PFX}:period:{patient_id}:all")],
        [InlineKeyboardButton("📅 آخر 3 أشهر",    callback_data=f"{_PFX}:period:{patient_id}:3m")],
        [InlineKeyboardButton("📅 آخر شهر",        callback_data=f"{_PFX}:period:{patient_id}:1m")],
        [InlineKeyboardButton("⬅️ رجوع",           callback_data=f"{_PFX}:back_actions")],
        [InlineKeyboardButton("❌ إلغاء",           callback_data=f"{_PFX}:cancel")],
    ])


# ── Entry — show search prompt ─────────────────────────────────────────────────

async def show_patient_search(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Entry from admin_reports_menu. Show search prompt."""
    # NOTE: Called from admin_reports_menu via delegation, not as ConversationHandler entry
    query = update.callback_query
    try:
        await query.edit_message_text(
            "👤 *تقرير المريض*\n\n"
            "✏️ اكتب اسم المريض أو جزءاً منه للبحث:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_cancel_kb(),
        )
    except Exception:
        await query.message.reply_text(
            "👤 *تقرير المريض*\n\n"
            "✏️ اكتب اسم المريض أو جزءاً منه للبحث:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_cancel_kb(),
        )
    return PR_SEARCH


async def start_patient_report(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Deprecated: kept for backward compatibility. Use show_patient_search instead."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text(
        "👤 *تقرير المريض*\n\n"
        "✏️ اكتب اسم المريض أو جزءاً منه للبحث:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_cancel_kb(),
    )
    return PR_SEARCH


# ── State PR_SEARCH — user typed a name ──────────────────────────────────────

@require_admin
async def handle_patient_search(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """User typed a search query — show matching patients."""
    query_text = (update.message.text or "").strip()
    if not query_text:
        await update.message.reply_text(
            "⚠️ يرجى كتابة اسم المريض.",
            reply_markup=_cancel_kb(),
        )
        return PR_SEARCH

    context.user_data["pr_search"] = query_text

    patients = await _search_patients(query_text)

    if not patients:
        await update.message.reply_text(
            f"⚠️ لم يُعثر على مريض يطابق *{query_text}*\n\nجرّب جزءاً من الاسم:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_cancel_kb(),
        )
        return PR_SEARCH

    # Build patient selection keyboard (max 20 results)
    rows = []
    for p in patients[:20]:
        label = f"👤 {p['name']}"
        if p.get("report_count"):
            label += f"  ({p['report_count']} تقرير)"
        rows.append([InlineKeyboardButton(label, callback_data=f"{_PFX}:pick:{p['id']}")])

    if len(patients) > 20:
        rows.append([InlineKeyboardButton(
            f"⚠️ {len(patients)} نتيجة — دقّق البحث للحصول على نتائج أقل",
            callback_data=f"{_PFX}:noop",
        )])

    rows.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")])

    await update.message.reply_text(
        f"🔍 نتائج البحث عن *{query_text}*:\n"
        f"وُجد {min(len(patients), 20)} مريض — اختر:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(rows),
    )
    return PR_PICK


# ── State PR_PICK — user tapped a patient button ──────────────────────────────

@require_admin
async def handle_patient_picked(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data or ""

    if data == f"{_PFX}:cancel":
        await query.edit_message_text("✅ تم إلغاء العملية.")
        return ConversationHandler.END

    if data == f"{_PFX}:back_search":
        await query.edit_message_text(
            "✏️ اكتب اسم المريض:",
            reply_markup=_cancel_kb(),
        )
        return PR_SEARCH

    if data == f"{_PFX}:noop":
        return PR_PICK

    if not data.startswith(f"{_PFX}:pick:"):
        return PR_PICK

    patient_id = int(data.split(":")[-1])
    context.user_data["pr_patient_id"] = patient_id

    # Fetch patient name for display
    patient = await _get_patient_by_id(patient_id)
    patient_name = patient["name"] if patient else f"#{patient_id}"
    context.user_data["pr_patient_name"] = patient_name

    await query.edit_message_text(
        f"👤 *{patient_name}*\n\n"
        f"📋 اختر الأقسام المطلوبة:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_depts_kb(),
    )
    return PR_DEPTS


# ── State PR_DEPTS — user chose departments ───────────────────────────────────

@require_admin
async def handle_depts_picked(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """User selected departments (all or specific)."""
    query = update.callback_query
    await query.answer()

    data = query.data or ""

    if data == f"{_PFX}:cancel":
        await query.edit_message_text("✅ تم الإلغاء.")
        return ConversationHandler.END

    if data == f"{_PFX}:back_patient":
        await query.edit_message_text(
            "✏️ اكتب اسم المريض:",
            reply_markup=_cancel_kb(),
        )
        return PR_SEARCH

    if data == f"{_PFX}:depts:all":
        context.user_data["pr_depts"] = None  # None = all departments
        await query.edit_message_text(
            "✅ تم تحديد: كل الأقسام\n\n"
            "📋 اختر الإجراءات المطلوبة:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_actions_kb(),
        )
        return PR_ACTIONS

    if data == f"{_PFX}:depts:select":
        # TODO: implement multiselect UI for departments
        # For now, fallback to "all"
        context.user_data["pr_depts"] = None
        await query.edit_message_text(
            "⚠️ اختيار محدد - قريباً\n"
            "الآن: كل الأقسام\n\n"
            "📋 اختر الإجراءات:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_actions_kb(),
        )
        return PR_ACTIONS

    return PR_DEPTS


# ── State PR_ACTIONS — user chose procedure types ──────────────────────────────

@require_admin
async def handle_actions_picked(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """User selected procedure types (all or specific)."""
    query = update.callback_query
    await query.answer()

    data = query.data or ""

    if data == f"{_PFX}:cancel":
        await query.edit_message_text("✅ تم الإلغاء.")
        return ConversationHandler.END

    if data == f"{_PFX}:back_depts":
        await query.edit_message_text(
            "📋 اختر الأقسام:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_depts_kb(),
        )
        return PR_DEPTS

    patient_id = context.user_data.get("pr_patient_id")

    if data == f"{_PFX}:actions:all":
        context.user_data["pr_actions"] = None  # None = all actions
        await query.edit_message_text(
            "✅ تم تحديد: كل الإجراءات\n\n"
            "📅 اختر الفترة الزمنية:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_period_kb(patient_id),
        )
        return PR_PERIOD

    if data == f"{_PFX}:actions:select":
        # TODO: implement multiselect UI for actions
        # For now, fallback to "all"
        context.user_data["pr_actions"] = None
        await query.edit_message_text(
            "⚠️ اختيار محدد - قريباً\n"
            "الآن: كل الإجراءات\n\n"
            "📅 اختر الفترة:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_period_kb(patient_id),
        )
        return PR_PERIOD

    return PR_ACTIONS


# ── State PR_PERIOD — user chose a time range ─────────────────────────────────

@require_admin
async def handle_period_picked(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data or ""

    if data == f"{_PFX}:cancel":
        try:
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
        context.user_data.clear()
        return ConversationHandler.END

    if data == f"{_PFX}:back_actions":
        await query.edit_message_text(
            "📋 اختر الإجراءات:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_actions_kb(),
        )
        return PR_ACTIONS

    # pr:period:<patient_id>:<range>
    parts  = data.split(":")
    # parts = ['pr', 'period', '<id>', '<range>']
    if len(parts) < 4 or parts[1] != "period":
        return PR_PERIOD

    patient_id  = int(parts[2])
    period_code = parts[3]   # all | 3m | 1m

    await query.edit_message_text("⏳ جارٍ إعداد التقرير...")

    period_start = _resolve_period_start(period_code)
    period_label = _period_label(period_code)

    # Get filters from context
    depts   = context.user_data.get("pr_depts")    # None or list
    actions = context.user_data.get("pr_actions")  # None or list

    try:
        from services.reports_repository import get_reports
        from services.patient_report_pdf import build_patient_pdf

        # Fetch patient reports with filters
        reports = await get_reports(
            start=period_start,
            end=date.today(),
            patient_id=patient_id,
            depts=depts,
            actions=actions,
        )
        patient = await _get_patient_by_id(patient_id)

        if not reports:
            await query.edit_message_text(
                f"⚠️ لا توجد تقارير للمريض *{patient['name'] if patient else ''}*"
                f" في {period_label}.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=_period_kb(patient_id),
            )
            return PR_PERIOD

        # Build professional PDF
        pdf_buf = build_patient_pdf(patient, reports, depts, period_label)

        # Send PDF
        filename = f"Patient_{patient_id}_{period_code}.pdf"
        caption = (
            f"👤 *تقرير المريض*\n"
            f"📝 {patient['name']}\n"
            f"📅 {period_label}\n"
            f"📋 {len(reports)} تقرير"
        )

        try:
            await query.delete_message()
        except Exception:
            pass

        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buf,
            filename=filename,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
        )

        logger.info(
            f"[patient_report] PDF sent  patient_id={patient_id}  period={period_code}"
            f"  reports={len(reports)}"
        )

    except Exception as exc:
        logger.exception("[patient_report] PDF generation failed")
        try:
            await query.edit_message_text(
                "❌ حدث خطأ أثناء إعداد التقرير.",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    finally:
        context.user_data.clear()

    return ConversationHandler.END


# ── Cancel handler ─────────────────────────────────────────────────────────────

@require_admin
async def cancel_patient_report(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        try:
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
    context.user_data.clear()
    return ConversationHandler.END


# ── Report builder ─────────────────────────────────────────────────────────────

def _build_patient_report(
    patient: dict, reports: list[dict], period_code: str
) -> list[str]:
    """
    Build a professional Arabic patient report as a list of Telegram messages.
    Each message stays under 4000 chars to avoid splitting mid-paragraph.
    """
    name         = patient.get("name", "—")
    file_no      = patient.get("file_number") or patient.get("patient_file_number") or ""
    nationality  = patient.get("nationality") or patient.get("patient_nationality") or ""
    disease      = patient.get("disease") or patient.get("patient_disease") or ""
    period_label = _period_label(period_code)

    # Compute statistics
    total     = len(reports)
    hospitals = sorted({r["hospital_name"] for r in reports if r.get("hospital_name")})
    dates     = [r["report_date"] for r in reports if r.get("report_date")]
    first_dt  = min(dates) if dates else None
    last_dt   = max(dates) if dates else None
    date_range = (
        f"{_fmt_date(first_dt)} → {_fmt_date(last_dt)}"
        if first_dt else "—"
    )
    action_counts: dict[str, int] = {}
    for r in reports:
        a = (r.get("medical_action") or "غير محدد").strip()
        action_counts[a] = action_counts.get(a, 0) + 1

    # ── Header block ──────────────────────────────────────────────────────────
    header_lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "🏥  *التقرير الطبي للمريض*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"👤  *الاسم:*  {name}",
    ]
    if file_no:
        header_lines.append(f"📁  *رقم الملف:*  {file_no}")
    if nationality:
        header_lines.append(f"🌍  *الجنسية:*  {nationality}")
    if disease:
        header_lines.append(f"🦠  *الحالة:*  {disease}")

    header_lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📊  *الملخص — {period_label}*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📋  *إجمالي التقارير:*  {total}",
        f"🏥  *المستشفيات:*  {len(hospitals)}",
        f"📅  *الفترة:*  {date_range}",
    ]

    if action_counts:
        header_lines += ["", "*توزيع الإجراءات:*"]
        for action, cnt in sorted(action_counts.items(), key=lambda x: -x[1]):
            header_lines.append(f"  • {action}: {cnt}")

    if hospitals:
        header_lines += ["", "*المستشفيات:*"]
        for h in hospitals:
            header_lines.append(f"  • {h}")

    header_lines += ["", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", ""]

    # ── Individual reports ────────────────────────────────────────────────────
    report_blocks: list[str] = []
    for i, r in enumerate(sorted(reports, key=lambda x: x.get("report_date") or date.min), 1):
        lines = [f"*{i}.* 📅 {_fmt_date(r.get('report_date'))}"]

        hosp = r.get("hospital_name", "")
        dept = r.get("department", "")
        doc  = r.get("doctor_name", "")
        if hosp:
            lines.append(f"🏥 {hosp}" + (f"  ›  {dept}" if dept else ""))
        if doc:
            lines.append(f"👨‍⚕️ {doc}")

        action = r.get("medical_action", "")
        if action:
            lines.append(f"📋 *{action}*")

        complaint = r.get("complaint_text", "") or ""
        if complaint and len(complaint) <= 300:
            lines.append(f"💬 {complaint}")
        elif complaint:
            lines.append(f"💬 {complaint[:300]}…")

        decision = r.get("doctor_decision", "") or ""
        if decision and len(decision) <= 300:
            lines.append(f"✅ {decision}")
        elif decision:
            lines.append(f"✅ {decision[:300]}…")

        followup = r.get("followup_date")
        if followup:
            lines.append(f"📌 موعد المتابعة: {_fmt_date(followup)}")

        lines.append("")
        report_blocks.append("\n".join(lines))

    # ── Chunk into Telegram-safe messages ────────────────────────────────────
    header_text = "\n".join(header_lines)
    chunks = [header_text]

    current = ""
    for block in report_blocks:
        if len(current) + len(block) > 3800:
            chunks.append(current)
            current = block
        else:
            current += block
    if current:
        chunks.append(current)

    return [c for c in chunks if c.strip()]


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _search_patients(query_text: str) -> list[dict]:
    """Search patients by name fragment. Returns list of {id, name, report_count}."""
    import asyncio
    return await asyncio.to_thread(_search_patients_sync, query_text)


def _search_patients_sync(query_text: str) -> list[dict]:
    from db.session import SessionLocal
    from db.models import Patient
    from sqlalchemy import func

    q = query_text.strip().lower()
    results = []
    try:
        with SessionLocal() as s:
            # Query patients table
            try:
                patients = (
                    s.query(Patient)
                    .filter(func.lower(Patient.name).contains(q))
                    .order_by(Patient.name)
                    .limit(50)
                    .all()
                )
                for p in patients:
                    # Count reports for this patient
                    from db.models import Report
                    report_count = (
                        s.query(func.count(Report.id))
                        .filter(Report.patient_id == p.id)
                        .scalar() or 0
                    )
                    results.append({
                        "id": p.id,
                        "name": p.name or "—",
                        "report_count": report_count,
                    })
            except Exception:
                # Fallback: search in reports.patient_name directly
                from db.models import Report
                rows = (
                    s.query(Report.patient_id, Report.patient_name,
                            func.count(Report.id).label("cnt"))
                    .filter(func.lower(Report.patient_name).contains(q),
                            Report.patient_name.isnot(None))
                    .group_by(Report.patient_id, Report.patient_name)
                    .order_by(Report.patient_name)
                    .limit(50)
                    .all()
                )
                for row in rows:
                    results.append({
                        "id": row.patient_id or 0,
                        "name": row.patient_name or "—",
                        "report_count": row.cnt,
                    })
    except Exception as exc:
        logger.error(f"[patient_report] search failed: {exc}", exc_info=True)
    return results


async def _get_patient_by_id(patient_id: int) -> dict | None:
    import asyncio
    return await asyncio.to_thread(_get_patient_sync, patient_id)


def _get_patient_sync(patient_id: int) -> dict | None:
    from db.session import SessionLocal
    try:
        with SessionLocal() as s:
            from db.models import Patient
            p = s.query(Patient).filter(Patient.id == patient_id).first()
            if p:
                return {
                    "id": p.id, "name": p.name or "—",
                    "file_number": getattr(p, "file_number", "") or "",
                    "nationality": getattr(p, "nationality", "") or "",
                    "disease": getattr(p, "disease", "") or "",
                }
            # Fallback: get name from reports
            from db.models import Report
            r = (
                s.query(Report.patient_name, Report.patient_file_number,
                        Report.patient_nationality, Report.patient_disease)
                .filter(Report.patient_id == patient_id)
                .first()
            )
            if r:
                return {
                    "id": patient_id,
                    "name": r.patient_name or "—",
                    "file_number": r.patient_file_number or "",
                    "nationality": r.patient_nationality or "",
                    "disease": r.patient_disease or "",
                }
    except Exception as exc:
        logger.error(f"[patient_report] get_patient failed: {exc}", exc_info=True)
    return None


async def _fetch_patient_reports(patient_id: int, since: date | None) -> list[dict]:
    import asyncio
    return await asyncio.to_thread(_fetch_reports_sync, patient_id, since)


def _fetch_reports_sync(patient_id: int, since: date | None) -> list[dict]:
    from db.session import SessionLocal
    from db.models import Report
    results = []
    try:
        with SessionLocal() as s:
            q = s.query(Report).filter(Report.patient_id == patient_id)
            if since:
                q = q.filter(Report.report_date >= since)
            rows = q.order_by(Report.report_date.asc()).all()
            for r in rows:
                results.append({
                    "id":             r.id,
                    "report_date":    r.report_date.date() if r.report_date else None,
                    "hospital_name":  r.hospital_name or "",
                    "department":     r.department or "",
                    "doctor_name":    r.doctor_name or "",
                    "medical_action": r.medical_action or "",
                    "complaint_text": r.complaint_text or "",
                    "doctor_decision":r.doctor_decision or "",
                    "followup_date":  (
                        r.followup_date.date()
                        if r.followup_date else None
                    ),
                })
    except Exception as exc:
        logger.error(f"[patient_report] fetch_reports failed: {exc}", exc_info=True)
    return results


# ── Utilities ─────────────────────────────────────────────────────────────────

def _resolve_period_start(code: str) -> date:
    """Resolve period code to start date."""
    today = date.today()
    if code == "1m":
        return today - timedelta(days=30)
    if code == "3m":
        return today - timedelta(days=90)
    # "all" — return very old date
    return date(1900, 1, 1)


def _period_label(code: str) -> str:
    return {"all": "كل التقارير", "1m": "آخر شهر", "3m": "آخر 3 أشهر"}.get(code, "—")


def _fmt_date(d) -> str:
    if d is None:
        return "—"
    if hasattr(d, "strftime"):
        return d.strftime("%d/%m/%Y")
    return str(d)


# ── Registration ──────────────────────────────────────────────────────────────

def register(app) -> None:
    """
    Register patient report handler.

    NOTE: Entry point (message button) is in admin_reports_menu.
    This registers the full conversation flow for patient reports,
    delegated to from the menu.
    """
    conv = ConversationHandler(
        entry_points=[
            # Backward compatibility: allow direct message button (deprecated)
            MessageHandler(
                filters.Regex(r"^🖨️ طباعة التقارير$"),
                start_patient_report,
            ),
        ],
        states={
            PR_SEARCH: [
                CallbackQueryHandler(cancel_patient_report, pattern=rf"^{_PFX}:cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_patient_search),
            ],
            PR_PICK: [
                CallbackQueryHandler(handle_patient_picked, pattern=rf"^{_PFX}:(pick:|back_search|cancel|noop)"),
            ],
            PR_DEPTS: [
                CallbackQueryHandler(handle_depts_picked, pattern=rf"^{_PFX}:(depts:|back_patient|cancel)"),
            ],
            PR_ACTIONS: [
                CallbackQueryHandler(handle_actions_picked, pattern=rf"^{_PFX}:(actions:|back_depts|cancel)"),
            ],
            PR_PERIOD: [
                CallbackQueryHandler(handle_period_picked, pattern=rf"^{_PFX}:(period:|back_actions|cancel)"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_patient_report, pattern=rf"^{_PFX}:cancel$"),
        ],
        name="patient_report_conv",
        per_chat=True,
        per_user=True,
        per_message=False,
        allow_reentry=True,
    )
    app.add_handler(conv)
    logger.info("[patient_report] ConversationHandler registered  prefix=pr:")
