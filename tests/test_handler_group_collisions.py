"""
حارس ضد تصادم معالِجات المجموعة الواحدة.

PTB ينفّذ **أول معالِج مطابق في كل مجموعة فقط** ثم ينتقل للمجموعة التالية.
فإذا قبِل معالِجان في المجموعة نفسها التحديثَ ذاته، صار الثاني كوداً ميتاً —
بلا استثناء ولا سجلّ ولا أي أثر ظاهر. وهذا العطب تكرّر ثلاث مرات في هذا
المشروع (woundcare ⇄ pharmacy_finance في group 0، ثم pharmacy_finance ⇄
arrivals في group 10 الذي عطّل إدخال عنوان السكن في الواصلين).

الاختبار يبني Application حقيقياً ويسجّل كل المعالِجات فعلياً، ثم يمرّر
تحديثات نموذجية ويتأكد أن كل واحد لا يقبله إلا معالِج واحد في كل مجموعة.
"""

from datetime import datetime

import pytest
from telegram import Chat, Document, Message, PhotoSize, Update, User
from telegram.ext import Application

from bot.handlers_registry import register_all_handlers

_UID = 999_000_111
_CHAT = Chat(id=_UID, type="private")
_USER = User(id=_UID, first_name="tester", is_bot=False)


def _msg(**kw) -> Message:
    return Message(message_id=1, date=datetime.now(), chat=_CHAT, from_user=_USER, **kw)


def _samples() -> dict[str, Update]:
    return {
        "text": Update(update_id=1, message=_msg(text="عنوان سكن تجريبي")),
        "photo": Update(update_id=2, message=_msg(
            photo=(PhotoSize(file_id="f", file_unique_id="u", width=1, height=1),))),
        "image_document": Update(update_id=3, message=_msg(
            document=Document(file_id="f", file_unique_id="u", mime_type="image/jpeg"))),
    }


@pytest.fixture(scope="module")
def registered_app() -> Application:
    app = Application.builder().token("1:x").build()
    register_all_handlers(app)
    return app


def _accepting(app: Application, group: int, update: Update) -> list[str]:
    names = []
    for h in app.handlers[group]:
        try:
            ok = h.check_update(update)
        except Exception:
            continue
        if ok is not False and ok is not None:
            cb = getattr(h, "callback", None)
            names.append(getattr(cb, "__module__", type(h).__name__) if cb else type(h).__name__)
    return names


@pytest.mark.parametrize("kind", list(_samples()))
def test_no_two_handlers_in_one_group_accept_the_same_update(registered_app, kind):
    update = _samples()[kind]
    clashes = {
        group: accepting
        for group in registered_app.handlers
        if len(accepting := _accepting(registered_app, group, update)) > 1
    }
    assert not clashes, (
        f"تصادم في تحديث من نوع {kind!r}: معالِجان أو أكثر في المجموعة نفسها "
        f"يقبلان التحديث ذاته، فلن يُنفَّذ إلا الأول وما بعده كودٌ ميت.\n"
        + "\n".join(
            f"  group {g}: ينفَّذ {mods[0]} — ولن يُنفَّذ {mods[1:]}"
            for g, mods in sorted(clashes.items())
        )
        + "\nالحل: انقل أحدهما إلى مجموعة حرّة خاصة به."
    )


def test_arrivals_text_handler_is_reachable(registered_app):
    """حارس مخصَّص للعطب الذي كشفه المستخدم: إدخال عنوان السكن اليدوي."""
    update = _samples()["text"]
    for group in sorted(registered_app.handlers):
        accepting = _accepting(registered_app, group, update)
        if any("general_services.arrivals" in m for m in accepting):
            assert accepting[0].endswith("arrivals.flow"), (
                f"معالِج نصوص الواصلين موجود في group {group} لكنه ليس الأول — "
                f"يسبقه {accepting[0]} فيبتلع الإدخال، ويبدو للمستخدم أن البوت "
                f"«لا يقبل الإدخال اليدوي» بينما زر تخطي يعمل."
            )
            return
    pytest.fail("معالِج نصوص الواصلين غير مسجَّل إطلاقاً.")
