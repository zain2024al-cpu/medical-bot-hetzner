# tests/test_uploads_smoke.py
# Smoke test for shared/uploads — no Telegram, no DB, no PTB context.

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.uploads._models import UploadedFile, UploadResult
from shared.uploads._session import UploadSession, save, load, clear
from shared.uploads._validation import validate_incoming, ValidationError
from shared.uploads._view import (
    build_waiting, build_collecting, build_min_warning,
    build_session_lost, build_error, CB,
)
from shared.uploads._hooks import register as hook_register, get as hook_get, clear as hook_clear


# ── UploadedFile ──────────────────────────────────────────────────────────────

def test_model():
    f = UploadedFile(
        file_id="abc123",
        file_unique_id="uniq1",
        mime_type="image/jpeg",
        file_size=512 * 1024,
        width=1280,
        height=720,
    )
    assert f.is_photo
    assert not f.is_pdf
    assert abs(f.size_mb - 0.5) < 0.01

    d = f.to_dict()
    f2 = UploadedFile.from_dict(d)
    assert f == f2
    print("UploadedFile OK")


def test_result():
    r = UploadResult.cancelled_result()
    assert r.cancelled
    assert r.is_empty()

    f = UploadedFile("id", "uid", "image/jpeg", 1000)
    r2 = UploadResult.confirmed([f])
    assert not r2.cancelled
    assert r2.count == 1
    assert r2.files[0] == f
    print("UploadResult OK")


# ── Session ───────────────────────────────────────────────────────────────────

def test_session():
    ud: dict = {}
    f = UploadedFile("id1", "uid1", "image/jpeg", 100_000, width=800, height=600)
    session = UploadSession(
        return_to="mod.step",
        title="ارفع صور",
        icon="📎",
        allowed_types=["photo"],
        min_files=1,
        max_files=5,
        max_file_size_mb=10,
        collected=[f.to_dict()],
        seen_unique_ids=["uid1"],
        ui_message_id=42,
        ui_chat_id=99,
    )
    save(ud, session)
    assert "_upl" in ud

    s2 = load(ud)
    assert s2 is not None
    assert s2.count == 1
    assert s2.ui_message_id == 42
    assert s2.get_files()[0] == f

    clear(ud)
    assert load(ud) is None
    print("session OK")


# ── Validation ────────────────────────────────────────────────────────────────

def _make_args(**overrides):
    defaults = dict(
        mime_type="image/jpeg",
        file_size=200_000,
        file_unique_id="uniq1",
        is_photo=True,
        is_document=False,
        allowed_types=["photo"],
        max_file_size_mb=0,
        max_files=0,
        current_count=0,
        seen_unique_ids=[],
    )
    defaults.update(overrides)
    return defaults


def test_validation_pass():
    result = validate_incoming(**_make_args())
    assert result is None
    print("validation pass OK")


def test_validation_duplicate():
    args = _make_args(seen_unique_ids=["uniq1"])
    err = validate_incoming(**args)
    assert err is not None
    assert err.code == "duplicate"
    print("validation duplicate OK")


def test_validation_max():
    args = _make_args(max_files=3, current_count=3)
    err = validate_incoming(**args)
    assert err is not None
    assert err.code == "max_reached"
    print("validation max_reached OK")


def test_validation_wrong_type():
    args = _make_args(
        mime_type="application/pdf",
        is_photo=False,
        is_document=True,
        allowed_types=["photo"],
    )
    err = validate_incoming(**args)
    assert err is not None
    assert err.code == "wrong_type"
    print("validation wrong_type OK")


def test_validation_pdf_allowed():
    args = _make_args(
        mime_type="application/pdf",
        is_photo=False,
        is_document=True,
        allowed_types=["pdf"],
    )
    err = validate_incoming(**args)
    assert err is None
    print("validation pdf allowed OK")


def test_validation_too_large():
    args = _make_args(
        mime_type="application/pdf",
        is_photo=False,
        is_document=True,
        allowed_types=["pdf"],
        file_size=25 * 1024 * 1024,   # 25 MB
        max_file_size_mb=20,
    )
    err = validate_incoming(**args)
    assert err is not None
    assert err.code == "too_large"
    print("validation too_large OK")


def test_validation_blocked():
    args = _make_args(
        mime_type="application/x-msdownload",
        is_photo=False,
        is_document=True,
        allowed_types=["document"],
    )
    err = validate_incoming(**args)
    assert err is not None
    assert err.code == "blocked"
    print("validation blocked OK")


# ── View ─────────────────────────────────────────────────────────────────────

def _session_dict(**overrides):
    base = {
        "return_to":        "mod.step",
        "title":            "ارفع صور الجرح",
        "icon":             "📎",
        "allowed_types":    ["photo", "pdf"],
        "min_files":        1,
        "max_files":        5,
        "max_file_size_mb": 10,
    }
    base.update(overrides)
    return base


def test_view_waiting():
    text, kb = build_waiting(_session_dict())
    assert "ارفع صور الجرح" in text
    assert "الصور" in text
    kb_str = str(kb)
    assert "إلغاء" in kb_str
    assert f"{CB}:cancel" in kb_str
    print("build_waiting OK")


def test_view_collecting():
    files = [
        {"file_id": "f1", "file_unique_id": "u1",
         "mime_type": "image/jpeg", "file_size": 300_000,
         "file_name": "", "width": 800, "height": 600},
        {"file_id": "f2", "file_unique_id": "u2",
         "mime_type": "application/pdf", "file_size": 1_500_000,
         "file_name": "report.pdf", "width": 0, "height": 0},
    ]
    text, kb = build_collecting(_session_dict(), files)
    assert "ارفع صور الجرح" in text
    assert "2" in text   # count
    kb_str = str(kb)
    assert f"{CB}:confirm" in kb_str
    assert f"{CB}:cancel" in kb_str
    assert f"{CB}:rm:0" in kb_str
    assert f"{CB}:rm:1" in kb_str
    print("build_collecting OK")


def test_view_min_warning():
    text, kb = build_min_warning(_session_dict(), [], min_files=2)
    assert "يجب رفع" in text
    print("build_min_warning OK")


def test_view_session_lost():
    text, kb = build_session_lost()
    assert "انتهت الجلسة" in text
    print("build_session_lost OK")


def test_view_error():
    text, kb = build_error("رسالة خطأ")
    assert "خطأ" in text
    assert "رسالة خطأ" in text
    print("build_error OK")


def test_view_max_files_shown():
    # >8 files: counter should mention overflow but not crash
    files = [
        {"file_id": f"f{i}", "file_unique_id": f"u{i}",
         "mime_type": "image/jpeg", "file_size": 100_000,
         "file_name": "", "width": 0, "height": 0}
        for i in range(12)
    ]
    text, kb = build_collecting(_session_dict(max_files=20), files)
    assert "12" in text
    print("build_collecting overflow OK")


# ── Hooks ────────────────────────────────────────────────────────────────────

async def _fake_processor(raw: bytes, meta: dict) -> bytes:
    return raw

def test_hooks():
    hook_clear()
    assert hook_get("enhance") is None
    hook_register("enhance", _fake_processor)
    assert hook_get("enhance") is _fake_processor
    hook_clear("enhance")
    assert hook_get("enhance") is None
    print("hooks OK")


# ── Wipe key coverage ─────────────────────────────────────────────────────────

def test_lifecycle_wipe_includes_upl():
    from core.conversation.lifecycle import wipe_session
    ud = {"_upl": "upload_state", "_msel": "msel_state", "_sel_patient": "sp_state",
          "report_tmp": "legacy", "other": "keep"}
    wipe_session(ud)
    assert "_upl" not in ud,        "_upl should be wiped"
    assert "_msel" not in ud,       "_msel should be wiped"
    assert "_sel_patient" not in ud,"_sel_patient should be wiped"
    assert "report_tmp" not in ud,  "report_tmp should be wiped"
    assert "other" in ud,           "unrelated keys should survive"
    print("lifecycle wipe coverage OK")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_model()
    test_result()
    test_session()
    test_validation_pass()
    test_validation_duplicate()
    test_validation_max()
    test_validation_wrong_type()
    test_validation_pdf_allowed()
    test_validation_too_large()
    test_validation_blocked()
    test_view_waiting()
    test_view_collecting()
    test_view_min_warning()
    test_view_session_lost()
    test_view_error()
    test_view_max_files_shown()
    test_hooks()
    test_lifecycle_wipe_includes_upl()
    print("\nALL TESTS PASSED")
