# tests/test_edit_field_markdown_safety.py
# 🛡️ حارس دائم: شاشات «تعديل قبل النشر» لا تنهار عند اختيار أي حقل.
#
# ⚠️ لماذا هذا الاختبار: كل ملف تعديل كان يحمل قاموس أسماء عرض خاصاً به
# ويعود للمفتاح الخام حين يغيب الحقل عنه. والمفتاح `complaint_text` أو
# `translator_name` فيه شرطة سفلية، وهي في Markdown v1 تفتح كياناً مائلاً
# لا يُغلَق ⇒ `Can't parse entities` ⇒ تسقط الشاشة كلها. قِيس: ٥٧ حالة
# (معالج × مسار × حقل) كانت تنهار، وتعود كلما أُضيف حقل إلى
# `field_registry` ونُسي قاموس معالجه — ولا يكشفها إلا تقرير أخطاء يومي.
#
# المحلّل أدناه يحاكي قاعدة تليجرام (كيان مفتوح بلا إغلاق ⇒ خطأ عند بايت
# فتحه) وقد طابق الخطأ الحقيقي بالبايت (٢٩) حين قُورن بتقرير الإنتاج.

import asyncio
import glob
import importlib
import inspect
import os
import re

import pytest

os.environ.setdefault("BOT_TOKEN", "1:x")

telegram_error = pytest.importorskip("telegram.error")
BadRequest = telegram_error.BadRequest

_PKG = "bot.handlers.user.user_reports_add_new_system"
_BP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "bot", "handlers", "user", "user_reports_add_new_system",
    "edit_handlers", "before_publish",
)

# مسارات الملف المشترك للعلاج/المناظير: لا تُشتَقّ من نص الدالة (flow_type
# يأتي من callback_data لا من ثابت).
_TREATMENT_FLOWS = [
    "treatment_chemo", "treatment_targeted", "treatment_immuno",
    "treatment_dialysis", "treatment_combined", "endoscopy", "transplant",
]


def first_unclosed_entity(text: str):
    """إزاحة البايت لأول كيان Markdown v1 لا إغلاق له، أو None إن سلم النص."""
    b = 0
    open_ch, open_off = None, None
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            b += len(ch.encode()) + len(text[i + 1].encode())
            i += 2
            continue
        if ch in "*_`":
            if open_ch is None:
                open_ch, open_off = ch, b
            elif open_ch == ch:
                open_ch, open_off = None, None
        b += len(ch.encode())
        i += 1
    return open_off if open_ch is not None else None


def test_parser_matches_the_production_failure():
    """المحلّل يعيد البايت ٢٩ كما في تقرير الإنتاج 2026-09-19 — وإلا فالحارس بلا قيمة."""
    msg = "✏️ **تعديل complaint_text**\n\n**القيمة الحالية:**\nx"
    assert first_unclosed_entity(msg) == 29
    assert first_unclosed_entity("✏️ **تعديل 💬 شكوى المريض**\n\nx") is None
    assert first_unclosed_entity("a\\_b\\*c") is None      # المهرَّب سليم


class _Query:
    def __init__(self, data):
        self.data = data
        self.error_offset = None
        self.from_user = type("U", (), {"id": 7})()
        self.message = type("M", (), {"chat_id": 5, "message_id": 1})()

    async def answer(self, *a, **k):
        pass

    async def edit_message_text(self, text, **k):
        if k.get("parse_mode") in ("Markdown", "MarkdownV1"):
            off = first_unclosed_entity(text)
            if off is not None:
                self.error_offset = off
                raise BadRequest(
                    f"Can't parse entities: can't find end of the entity starting at byte offset {off}")

    async def edit_message_reply_markup(self, **k):
        pass


class _Update:
    def __init__(self, data):
        self.callback_query = _Query(data)
        self.effective_user = self.callback_query.from_user
        self.effective_chat = type("C", (), {"id": 5})()
        self.effective_message = self.callback_query.message
        self.message = None


def _context(key):
    ctx = type("C", (), {})()
    ctx.user_data = {"report_tmp": {key: "قيمة تجريبية", "medical_action": "x"}}
    ctx.bot = type("B", (), {"send_message": staticmethod(lambda *a, **k: None)})()
    return ctx


async def _press(handler, flow, key):
    upd = _Update(f"edit_field:{flow}:{key}")
    try:
        await handler(upd, _context(key))
    except Exception as exc:                       # noqa: BLE001
        return f"exception {type(exc).__name__}: {exc}"
    off = upd.callback_query.error_offset
    return None if off is None else f"Markdown غير مغلق عند البايت {off}"


def _fields(flow):
    from bot.handlers.user.user_reports_add_new_system.flows.shared import (
        get_editable_fields_by_flow_type,
    )
    try:
        return get_editable_fields_by_flow_type(flow)
    except Exception:                              # noqa: BLE001
        return []


def _selection_handlers():
    """[(اسم الملف، الدالة، مساراتها)] لكل معالج اختيار حقل قبل النشر."""
    out = []
    for path in sorted(glob.glob(os.path.join(_BP_DIR, "*_edit.py"))):
        modname = os.path.basename(path)[:-3]
        mod = importlib.import_module(f"{_PKG}.edit_handlers.before_publish.{modname}")
        for name, fn in inspect.getmembers(mod, inspect.iscoroutinefunction):
            if "edit_field_selection" not in name or fn.__module__ != mod.__name__:
                continue
            flows = sorted(set(re.findall(
                r'flow_type\s*=\s*["\']([a-z_]+)["\']', inspect.getsource(fn))))
            if not flows and "treatment_endoscopy" in name:
                flows = _TREATMENT_FLOWS
            out.append((modname, fn, flows))
    return out


def test_no_edit_field_selection_crashes_on_markdown():
    handlers = _selection_handlers()
    assert len(handlers) >= 15, f"وُجد {len(handlers)} معالجاً فقط — تغيّر هيكل الملفات؟"

    async def _run():
        failures, total = [], 0
        for modname, fn, flows in handlers:
            for flow in flows:
                for key, _label in _fields(flow):
                    total += 1
                    problem = await _press(fn, flow, key)
                    if problem:
                        failures.append(f"{modname} · {flow} · {key}: {problem}")
        return total, failures

    total, failures = asyncio.run(_run())
    assert total >= 100, f"اختُبر {total} حالة فقط — الاكتشاف تعطّل؟"
    assert not failures, (
        f"{len(failures)} من {total} حالة تنهار عند اختيار الحقل:\n  " + "\n  ".join(failures[:20])
        + "\n\nالسبب المعتاد: حقل في field_registry بلا اسم عرض في قاموس المعالج، "
          "والمفتاح الخام فيه شرطة سفلية. الإصلاح في utils.edit_field_display_name.")
