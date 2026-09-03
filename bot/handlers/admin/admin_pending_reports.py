# bot/handlers/admin/admin_pending_reports.py
#
# 📋 شاشة "التقارير المعلقة" — متابعة يدوية من داخل "🛠️ إدارة النظام"
# بديل/مكمّل لتنبيه الساعة 9 مساءً التلقائي: يعرض كل الحالات المعلقة
# فعلياً (يعتمد على نفس services/pending_reports_service.py المستخدَمة
# في التنبيه اليومي — بلا أي تكرار للمنطق) مع عدد أيام الانتظار، بترقيم
# صفحات إن كانت القائمة طويلة.
#
# ✅ بدون ConversationHandler (نفس نمط admin_system_menu.py وغيره هذه
# الجلسة) — CallbackQueryHandler مستقل دائم التفعيل.

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from bot.shared_auth import is_admin

logger = logging.getLogger(__name__)


def _ist_now() -> datetime:
    """الوقت الحالي بتوقيت IST (UTC+5:30) — نفس التوقيت المعروض في بقية الشاشات."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)
    except Exception:
        return datetime.utcnow() + timedelta(hours=5, minutes=30)

_PFX = "pndrep"
_PER_PAGE = 8


# عتبة الإغلاق الجماعي — «قديم» يعني تجاوز هذه المدة.
_BULK_DAYS = 30


def _list_kb(page: int, total_pages: int, items=None, total_old: int = 0
             ) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if total_pages > 1 and page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"{_PFX}:page:{page - 1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data=f"{_PFX}:noop"))
    if total_pages > 1 and page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"{_PFX}:page:{page + 1}"))

    rows: list[list[InlineKeyboardButton]] = []
    if nav:
        rows.append(nav)
    # ✅ زرّ إغلاق لكل تقرير معروض — الشاشة كانت للقراءة فقط، فالتقرير
    # الذي تعذّر على المترجم إغلاقه (استقال، أو أُدخِل خطأً) يبقى فيها
    # إلى الأبد بلا أي سبيل للتخلّص منه.
    for p in (items or []):
        rid = p.get("report_id")
        if not rid:
            continue
        nm = str(p.get("patient_name") or "—")[:20]
        rows.append([InlineKeyboardButton(
            f"✅ إغلاق: {nm} ({p.get('days_waiting', 0)}ي)",
            callback_data=f"{_PFX}:close:{rid}:{page}")])

    if total_old:
        rows.append([InlineKeyboardButton(
            f"🧹 إغلاق كل ما تجاوز {_BULK_DAYS} يوماً ({total_old})",
            callback_data=f"{_PFX}:bulkask:{page}")])

    rows.append([InlineKeyboardButton("🕘 آخر ما أُغلِق (تراجع)",
                                      callback_data=f"{_PFX}:recent")])
    rows.append([InlineKeyboardButton("🔄 تحديث", callback_data=f"{_PFX}:page:{page}")])
    rows.append([InlineKeyboardButton("🔙 رجوع", callback_data="sys_menu:back")])
    return InlineKeyboardMarkup(rows)


def _urgency_emoji(days_waiting: int) -> str:
    if days_waiting >= 3:
        return "🔴"
    if days_waiting >= 1:
        return "🟡"
    return "🟢"


def _render_item_text(p: dict) -> str:
    reason = (p.get("no_report_reason") or "—").strip()
    action = (p.get("medical_action") or "—").strip()
    # ✅ التفصيل الدقيق (مثال: "فحص دم شامل") إن وُجد — وإلا النوع العام
    # (مثال: "ترقيد"، "استشارة جديدة") لبقية أنواع الإجراءات غير الأشعة.
    exam_detail = (p.get("exam_detail") or "").strip()
    detail = exam_detail or action

    expected = int(p.get("expected_count") or 1)
    uploaded = int(p.get("uploaded_count") or 0)
    progress_line = f"   📊 التقدّم: {uploaded}/{expected} فحص\n" if expected > 1 else ""

    return (
        f"{_urgency_emoji(p['days_waiting'])} {p['patient_name']}\n"
        f"   🩺 نوع الفحص: {detail}\n"
        f"{progress_line}"
        f"   🏢 القسم: {p['department']}\n"
        f"   👤 المترجم: {p['translator_name']}\n"
        f"   📝 السبب: {reason}\n"
        f"   ⏳ منتظر منذ: {p['days_waiting']} يوم"
    )


_NOT_READY_REASON = "🟡 لم يجهز بعد"


async def _render_list(query, page: int, answered: bool = False) -> None:
    from services.pending_reports_service import get_pending_reports

    # ✅ هذه الشاشة مخصَّصة حصراً لحالة "🟡 لم يجهز بعد" — العلامة الثابتة
    # التي يضعها flows/shared.py عند هذا الاختيار فقط (انظر add_pending_report
    # call site). أي سجل آخر (بيانات قديمة سابقة لهذا التصميم، أو أي مسار
    # مستقبلي) لا يجب أن يظهر هنا حتى لو دخل جدول pending_reports بطريقة ما.
    items = [
        p for p in get_pending_reports()
        if (p.get("no_report_reason") or "").strip() == _NOT_READY_REASON
    ]
    items.sort(key=lambda x: x["days_waiting"], reverse=True)
    total = len(items)

    # ⚠️ سطر وقت التحديث ليس تجميلاً: زر "🔄 تحديث" كان يبدو **معطَّلاً
    # تماماً** بدونه. السبب أن تيليجرام يرفض edit_message_text إن كان
    # المحتوى مطابقاً حرفياً للحالي، والمعالِج يكون قد استهلك
    # query.answer() أصلاً في أعلاه — وanswerCallbackQuery مسموح **مرة
    # واحدة فقط** لكل استعلام، فمحاولة الردّ بـ"القائمة محدَّثة" تفشل
    # صامتة ولا يرى الأدمن أي استجابة إطلاقاً (تحقّقنا عملياً).
    # الطابع الزمني يجعل المحتوى مختلفاً دائماً فينجح التعديل، ويرى
    # الأدمن دليلاً مرئياً على أن التحديث تمّ فعلاً.
    stamp = _ist_now().strftime("%H:%M:%S")

    if not items:
        try:
            await query.edit_message_text(
                "📋 التقارير الطبية المعلقة\n\n"
                "✅ لا توجد تقارير معلقة حالياً — جميع التقارير جاهزة!\n\n"
                f"🔄 آخر تحديث: {stamp}",
                reply_markup=_list_kb(0, 1),
            )
            if not answered:
                await _answer_once(query, "✅ تم التحديث.")
        except Exception as exc:
            await _handle_render_error(query, exc, page=0)
        return

    # عدد المتجاوز للعتبة — يُحسب من **كل** القائمة لا من الصفحة الحالية،
    # وإلا اختلف رقم زرّ الإغلاق الجماعي بين الصفحات وهو عملية واحدة.
    total_old = sum(1 for p in items if int(p.get("days_waiting") or 0) >= _BULK_DAYS)

    per_page = _PER_PAGE
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    page_items = items[page * per_page: (page + 1) * per_page]

    lines = [
        "📋 التقارير الطبية المعلقة",
        f"العدد الإجمالي: {total}",
        f"🔄 آخر تحديث: {stamp}",
        "",
    ]
    lines.extend(_render_item_text(p) + "\n" for p in page_items)

    try:
        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=_list_kb(page, total_pages, page_items, total_old),
        )
        if not answered:
            await _answer_once(query, "✅ تم التحديث.")
    except Exception as exc:
        await _handle_render_error(query, exc, page=page)


async def _render_recent(query, answered: bool = False) -> None:
    """شاشة «آخر ما أُغلِق» — ماذا أُغلِق، ومن أين يُعاد فتحه."""
    from services.pending_reports_service import get_recently_closed

    items = get_recently_closed(10)
    rows: list[list[InlineKeyboardButton]] = []
    if not items:
        body = ["🕘 آخر ما أُغلِق", "", "لم يُغلَق أي تقرير بعد."]
    else:
        body = ["🕘 آخر ما أُغلِق", "",
                "اضغط على أي تقرير لإعادة فتحه كما كان.", ""]
        for it in items:
            when = it["closed_at"].strftime("%Y-%m-%d %H:%M") if it["closed_at"] else "—"
            body.append(f"• {it['patient_name']}  ·  {it['translator_name']}")
            body.append(f"   ⏳ كان منتظراً {it['days_waited']} يوماً  ·  أُغلِق {when}")
            if it.get("report_id"):
                rows.append([InlineKeyboardButton(
                    f"↩️ إعادة فتح: {str(it['patient_name'])[:20]}",
                    callback_data=f"{_PFX}:reopen:{it['report_id']}")])
    rows.append([InlineKeyboardButton("⬅️ رجوع للقائمة",
                                      callback_data=f"{_PFX}:page:0")])
    try:
        await query.edit_message_text("\n".join(body),
                                      reply_markup=InlineKeyboardMarkup(rows))
    except Exception as exc:
        await _handle_render_error(query, exc, page=0)
        return
    if not answered:
        await _answer_once(query)


async def _answer_once(query, text: str | None = None) -> None:
    """الردّ على الاستعلام مرة واحدة — تيليجرام لا يسمح بأكثر من ردّ."""
    try:
        await query.answer(text)
    except Exception:
        logger.debug("تم تجاهل استثناء في _answer_once", exc_info=True)


async def _handle_render_error(query, exc: Exception, page: int) -> None:
    """تيليجرام يرفض edit_message_text إن كان المحتوى الجديد مطابقاً
    تماماً للحالي (مثال: ضغط 'تحديث' مرّتين في نفس الثانية) — هذا سلوك
    طبيعي متوقَّع وليس خطأ، فنعرض تنبيهاً خفيفاً بدل تسجيله كـERROR."""
    if "message is not modified" in str(exc).lower():
        await _answer_once(query, "✅ القائمة محدَّثة بالفعل.")
        return
    await _answer_once(query, "⚠️ تعذّر التحديث — حاول مرة أخرى.")
    logger.error(f"[pndrep] Failed to render list (page={page}): {exc}")


async def handle_pending_reports_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    query = update.callback_query

    data = query.data or ""
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    # ⚠️ لا يُستدعى query.answer() هنا لمسار "page" عمداً: تيليجرام يسمح
    # بالردّ على الاستعلام **مرة واحدة فقط**، وكان الردّ الفارغ في هذا
    # الموضع يستهلك تلك الفرصة — فحين يفشل التعديل لاحقاً بـ"message is
    # not modified" (ضغط 🔄 تحديث مرّتين في نفس الثانية) تفشل محاولة
    # عرض "✅ القائمة محدَّثة" صامتة، فيبدو الزر معطَّلاً تماماً بلا أي
    # استجابة. مسار العرض أدناه هو من يملك الردّ الآن ويستدعيه مرة واحدة.
    if action == "noop":
        try:
            await query.answer()
        except Exception:
            logger.debug("تم تجاهل استثناء في handle_pending_reports_callback", exc_info=True)
        return

    if action == "page":
        try:
            page = int(parts[2])
        except (IndexError, ValueError):
            page = 0
        await _render_list(query, page)
        return

    # ── إغلاق تقرير واحد ───────────────────────────────────────────────
    if action == "close":
        from services.pending_reports_service import close_pending_report
        try:
            report_id = int(parts[2])
            page = int(parts[3]) if len(parts) > 3 else 0
        except (IndexError, ValueError):
            await _answer_once(query, "⚠️ بيانات غير صالحة.")
            return
        ok, uploaded, expected = close_pending_report(report_id, performed_by=user.id)
        # ⚠️ الردّ **قبل** إعادة الرسم: `_render_list` يستهلك فرصة الردّ
        # الوحيدة، فلو أُخِّر لضاعت نتيجة العملية بلا أن يراها الأدمن.
        await _answer_once(
            query,
            f"✅ أُغلِق ({uploaded}/{expected})" if ok else "⚠️ تعذّر الإغلاق.")
        await _render_list(query, page, answered=True)
        return

    # ── آخر ما أُغلِق + إعادة الفتح ────────────────────────────────────
    if action == "recent":
        await _render_recent(query)
        return

    if action == "reopen":
        from services.pending_reports_service import reopen_pending_report
        try:
            report_id = int(parts[2])
        except (IndexError, ValueError):
            await _answer_once(query, "⚠️ بيانات غير صالحة.")
            return
        ok = reopen_pending_report(report_id, performed_by=user.id)
        await _answer_once(query, "↩️ أُعيد فتحه." if ok else "⚠️ تعذّرت إعادة الفتح.")
        # ⚠️ **لا يُعدَّل `query.data` ولا يُستدعى المعالِج نفسه**: كائن
        # `CallbackQuery` في PTB غير قابل للتعديل، فالإسناد يرمي استثناءً
        # في الإنتاج بينما يمرّ صامتاً في الاختبار بـMagicMock. تُستدعى
        # دالة الشاشة مباشرةً بدل ذلك.
        await _render_recent(query, answered=True)
        return

    # ── إغلاق جماعي: تأكيد ثم تنفيذ ───────────────────────────────────
    if action == "bulkask":
        from services.pending_reports_service import get_pending_reports
        try:
            page = int(parts[2])
        except (IndexError, ValueError):
            page = 0
        n = sum(1 for p in get_pending_reports()
                if (p.get("no_report_reason") or "").strip() == _NOT_READY_REASON
                and int(p.get("days_waiting") or 0) >= _BULK_DAYS)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"✅ نعم، أغلِق الـ{n}",
                                  callback_data=f"{_PFX}:bulkdo:{page}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:page:{page}")],
        ])
        _txt = "\n".join([
            "🧹 تأكيد الإغلاق الجماعي",
            "",
            f"سيُغلَق {n} تقريراً معلَّقاً تجاوز عمره {_BULK_DAYS} يوماً.",
            "",
            "يختفي كلٌّ منها من هذه الشاشة ومن قائمة المترجم معاً،",
            "ويبقى سجلّها محفوظاً للمراجعة.",
            "",
            "⚠️ لا تُلغى العملية بضغطة — تابع فقط إن كنت متأكداً.",
        ])
        await query.edit_message_text(_txt, reply_markup=kb)
        await _answer_once(query)
        return

    if action == "bulkdo":
        from services.pending_reports_service import close_pending_older_than
        try:
            page = int(parts[2])
        except (IndexError, ValueError):
            page = 0
        done, failed = close_pending_older_than(
            _BULK_DAYS, performed_by=user.id, reason_filter=_NOT_READY_REASON)
        msg = f"✅ أُغلِق {done}" + (f" · تعذّر {failed}" if failed else "")
        await _answer_once(query, msg)
        await _render_list(query, page, answered=True)
        return

    try:
        await query.answer()
    except Exception:
        logger.debug("تم تجاهل استثناء في handle_pending_reports_callback", exc_info=True)


# ── Registration ───────────────────────────────────────────────────────────────

def register(app) -> None:
    """تسجيل شاشة التقارير المعلقة (بدون ConversationHandler)."""
    app.add_handler(
        CallbackQueryHandler(handle_pending_reports_callback, pattern=rf"^{_PFX}:")
    )
    logger.info("[pndrep] Pending reports screen handlers registered")
