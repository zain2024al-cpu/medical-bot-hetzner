# services/error_digest.py
# مراقب السجلات: يلتقط كل خطأ يقع في البوت، ويرسل للأدمن آخر اليوم ملفاً
# واحداً يلخّص ما حدث.
#
# ── لماذا معالِج logging واحد لا استدعاءات متفرّقة ──────────────────────────────
#
# الالتقاط يتم عبر `logging.Handler` مركَّب على الجذر، فيلتقط **كل** ما
# يُسجَّل بمستوى ERROR أو أعلى من أي ملف في المشروع — سواء
# `logger.error(...)` في كود الوحدات أو `logger.exception(...)` أو معالِج
# أخطاء PTB. البديل (استدعاء دالة تسجيل يدوياً في كل موضع) يعني مئات
# المواضع، وأي موضع يُنسى يبقى خطؤه غير مرئي — وهو نفس نمط الخطأ المتكرر
# في هذا المشروع.
#
# ── لماذا ملف على القرص لا ذاكرة ──────────────────────────────────────────────
#
# ErrorMonitor.error_history يحتفظ بآخر 100 خطأ **في الذاكرة**، فتضيع كلها
# عند إعادة التشغيل — وإعادة التشغيل نفسها من أكثر ما نحتاج تقريره. لذلك
# يُكتب كل خطأ فوراً سطراً في ملف اليوم، فيبقى التقرير صحيحاً مهما أُعيد
# تشغيل البوت.
#
# ── الخصوصية ──────────────────────────────────────────────────────────────────
#
# **لا يُخزَّن نص ما كتبه المستخدم إطلاقاً** (قد يحوي اسم مريض أو تشخيصاً).
# يُخزَّن ما يكفي للتشخيص فقط: نوع الخطأ، موضعه في الكود، المستخدم، والزر
# المضغوط. انظر `_redact`.

from __future__ import annotations

import json
import logging
import os
import threading
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

LOGS_DIR = Path("logs")
_LOCK = threading.Lock()


def _today_local() -> date:
    """
    "اليوم" بتوقيت TIMEZONE المُعدّ (افتراضياً Asia/Kolkata) — لا `date.today()`
    الساذجة التي تقرأ توقيت نظام السيرفر مباشرة.

    ⚠️ سبب وجود هذه الدالة: خادم الاستضافة بتوقيت أوروبي (CEST، +2)، بينما
    مهمة الإرسال اليومية مجدولة عبر `app.job_queue.run_daily` بتوقيت
    Asia/Kolkata (+5:30) الساعة 23:55 — أي 20:25 بتوقيت السيرفر. لو استُخدمت
    `date.today()` الساذجة هنا (كما كانت)، يبقى "اليوم" بتوقيت السيرفر ولا
    يتبدّل إلى اليوم التالي إلا عند منتصف ليل CEST — أي بعد الإرسال بأكثر
    من 3 ساعات ونصف. أي خطأ يقع في تلك الفجوة (20:25–23:59 بتوقيت السيرفر)
    يُسجَّل في ملف "اليوم" **بعد** أن أُرسل تقريره فعلاً، فلا يظهر في تقرير
    اليوم نفسه (أُرسل قبله) ولا تقرير الغد (يقرأ ملف الغد لا اليوم) — يضيع
    نهائياً. هذا بالضبط ما أنتج "لا أخطاء، لا إرسال" في 2026-08-10 و
    2026-08-11 رغم وجود أخطاء فعلية مسجَّلة في ملفَي ذلك اليوم بتوقيت لاحق.
    """
    try:
        import pytz
        from config.settings import TIMEZONE
        return datetime.now(pytz.timezone(TIMEZONE)).date()
    except Exception:
        # احتياط: توقيت السيرفر الساذج أفضل من انهيار كامل للالتقاط/الإرسال.
        return date.today()

# سجلّات لا قيمة تشخيصية لها وتتكرر بكثافة — تُستبعَد حتى لا تُغرق التقرير
_IGNORE_SUBSTRINGS = (
    "terminated by other getUpdates",
    "Conflict",
    "httpx",
    "timed out",
    "NetworkError",
)


def _day_file(day: date) -> Path:
    return LOGS_DIR / f"errors-{day.isoformat()}.jsonl"


def _redact(record: logging.LogRecord) -> dict:
    """
    يحوّل سجل logging إلى قيد مُنقّى.

    ⚠️ لا يُنسخ نص رسالة المستخدم هنا بأي حال — الحقل الوحيد الذي قد يحمل
    ما كتبه المستخدم هو نص السجل نفسه، وهو من تأليف الكود لا من إدخاله.
    """
    try:
        msg = record.getMessage()
    except Exception:
        msg = str(record.msg)

    tb = ""
    if record.exc_info:
        try:
            tb = "".join(traceback.format_exception(*record.exc_info))
        except Exception:
            tb = ""

    return {
        "ts": datetime.fromtimestamp(record.created).isoformat(timespec="seconds"),
        "level": record.levelname,
        "logger": record.name,
        "func": record.funcName,
        "where": f"{os.path.basename(record.pathname)}:{record.lineno}",
        "msg": msg[:400],
        "exc": (record.exc_info[0].__name__ if record.exc_info and record.exc_info[0] else ""),
        "tb": tb[-2000:],
    }


class _DigestHandler(logging.Handler):
    """يكتب كل ERROR فأعلى سطراً في ملف اليوم. best-effort بالكامل."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.levelno < logging.ERROR:
                return
            # لا نُسجّل أخطاء هذه الوحدة نفسها — تفادياً للارتداد اللانهائي
            if record.name == __name__:
                return
            # ⚠️ يجب فحص الرسالة **بعد دمج المعاملات** ونوع الاستثناء معاً —
            # لا `record.msg` الخام. سبب ذلك (رُصِد في تقريرَي 2026-08-18/19،
            # 14 خطأ شبكة تسرّب رغم وجودها في قائمة التجاهل):
            #   • PTB يسجّل `_LOGGER.exception("Error while getting Updates: %s", exc)`
            #     فيبقى `record.msg` قالباً خاماً ("...: %s") والقيمة الحقيقية
            #     ("httpx.ReadError") في `record.args` — فلا تراها المطابقة أبداً.
            #   • بعض السجلات ("Exception happened while polling for updates.")
            #     لا تحوي أي كلمة مفتاحية في نصها إطلاقاً، والدليل الوحيد على
            #     كونها ضجيج شبكة هو **نوع الاستثناء** (NetworkError) في exc_info.
            try:
                formatted = record.getMessage()
            except Exception:
                formatted = str(record.msg)
            exc_name = (
                record.exc_info[0].__name__
                if record.exc_info and record.exc_info[0] else ""
            )
            text = f"{record.name} {formatted} {exc_name}"
            if any(s.lower() in text.lower() for s in _IGNORE_SUBSTRINGS):
                return
            entry = _redact(record)
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            line = json.dumps(entry, ensure_ascii=False)
            with _LOCK:
                with open(_day_file(_today_local()), "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception:
            # معالِج تسجيل لا يجوز أن يُسقط التطبيق مهما حدث
            pass


def install() -> None:
    """يركّب المراقب على الجذر مرة واحدة."""
    root = logging.getLogger()
    if any(isinstance(h, _DigestHandler) for h in root.handlers):
        return
    h = _DigestHandler()
    h.setLevel(logging.ERROR)
    root.addHandler(h)
    logger.info("[error_digest] installed — capturing ERROR+ to logs/errors-YYYY-MM-DD.jsonl")


# ── التقرير ───────────────────────────────────────────────────────────────────

def read_day(day: date) -> list[dict]:
    p = _day_file(day)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def build_report_text(day: date, entries: list[dict]) -> str:
    """تقرير نصّي مقروء: تجميع حسب (النوع + الموضع) لا سرد خام."""
    lines = [
        "=" * 66,
        f"تقرير أخطاء البوت — {day.isoformat()}",
        "=" * 66,
        "",
    ]
    if not entries:
        lines += ["✅ لم يُسجَّل أي خطأ اليوم."]
        return "\n".join(lines)

    groups: dict[tuple, list[dict]] = {}
    for e in entries:
        groups.setdefault((e.get("exc") or e.get("level"), e.get("where", "?")), []).append(e)

    ordered = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    lines += [
        f"الإجمالي: {len(entries)} خطأ   •   أنواع مختلفة: {len(ordered)}",
        "",
        "─" * 66,
        "الملخّص (الأكثر تكراراً أولاً):",
        "",
    ]
    for i, ((exc, where), items) in enumerate(ordered, 1):
        lines.append(f"{i:>2}. [{len(items):>3}×]  {exc or 'ERROR'}  @ {where}")
        lines.append(f"     أول مرة: {items[0]['ts']}   آخر مرة: {items[-1]['ts']}")
        lines.append(f"     {items[0].get('msg','')[:150]}")
        lines.append("")

    lines += ["─" * 66, "التفاصيل (أثر واحد لكل نوع):", ""]
    for (exc, where), items in ordered:
        e = items[0]
        lines += [
            "═" * 66,
            f"{exc or 'ERROR'}  @ {where}   ({len(items)}× اليوم)",
            f"المُسجِّل: {e.get('logger')}   الدالة: {e.get('func')}",
            f"الرسالة: {e.get('msg','')}",
            "",
        ]
        if e.get("tb"):
            lines += [e["tb"], ""]

    lines += [
        "=" * 66,
        "ملاحظة: لا يحتوي هذا التقرير على نص ما كتبه المستخدمون — حُجب عمداً",
        "لأنه قد يتضمّن أسماء مرضى أو تشخيصات.",
    ]
    return "\n".join(lines)


def build_report_file(day: date) -> tuple[Path | None, int]:
    """(مسار الملف, عدد الأخطاء). يعيد (None, 0) إن لم يقع أي خطأ."""
    entries = read_day(day)
    if not entries:
        return None, 0
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    out = LOGS_DIR / f"error-report-{day.isoformat()}.txt"
    out.write_text(build_report_text(day, entries), encoding="utf-8")
    return out, len(entries)


async def send_daily_error_report(application, day: date | None = None) -> None:
    """يُرسل تقرير اليوم للأدمن. صامت تماماً لو لم يقع خطأ."""
    from config.settings import ADMIN_IDS

    day = day or _today_local()
    path, count = build_report_file(day)
    if path is None:
        logger.info(f"[error_digest] {day} — لا أخطاء، لا إرسال")
        return

    caption = (
        f"🧾 **تقرير أخطاء البوت — {day.isoformat()}**\n\n"
        f"عدد الأخطاء: {count}\n"
        f"الملف يحوي ملخّصاً بالأكثر تكراراً ثم التفاصيل."
    )
    sent = 0
    for admin_id in ADMIN_IDS:
        try:
            with open(path, "rb") as f:
                await application.bot.send_document(
                    chat_id=admin_id,
                    document=f,
                    filename=path.name,
                    caption=caption,
                    parse_mode="Markdown",
                )
            sent += 1
        except Exception as exc:
            logger.warning(f"[error_digest] فشل الإرسال للأدمن {admin_id}: {exc}")

    logger.info(f"[error_digest] أُرسل تقرير {day} إلى {sent}/{len(ADMIN_IDS)} أدمن  ({count} خطأ)")


def cleanup_old(days: int = 30) -> int:
    """يحذف ملفات الأخطاء الأقدم من `days` حتى لا تتراكم بلا حد."""
    if not LOGS_DIR.exists():
        return 0
    cutoff = _today_local() - timedelta(days=days)
    removed = 0
    for p in LOGS_DIR.glob("errors-*.jsonl"):
        try:
            d = date.fromisoformat(p.stem.replace("errors-", ""))
        except Exception:
            continue
        if d < cutoff:
            try:
                p.unlink()
                removed += 1
            except Exception:
                logger.debug(f"تعذّر حذف {p}", exc_info=True)
    return removed
