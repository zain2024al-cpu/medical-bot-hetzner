# tests/test_rbac_smoke.py
# Smoke tests for the RBAC / module-access layer.
# Uses an in-memory SQLite database — no production DB touched.
# No Telegram, no PTB context required.

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Patch DB to use in-memory SQLite for tests ────────────────────────────────
import db.session as _db_session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base

_test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
Base.metadata.create_all(bind=_test_engine)
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
_db_session.engine = _test_engine
_db_session.SessionLocal = _TestSessionLocal

# ── Bootstrap the registry ────────────────────────────────────────────────────
from core.modules_bootstrap import bootstrap_all
bootstrap_all()

# ── Imports under test ────────────────────────────────────────────────────────
from core.access.access_service import (
    get_user_modules,
    user_has_module,
    grant_module,
    revoke_module,
    list_user_module_access,
)
from core.routing.registry import registry
from db.models import User, UserModuleAccess, TranslatorDirectory

_TG_USER = 9_000_001   # synthetic Telegram user ID
_TG_APPROVED = 9_000_002
_TG_SUSPENDED = 9_000_003


def _seed_user(tg_id: int, approved: bool, suspended: bool = False):
    with _TestSessionLocal() as s:
        u = User(
            tg_user_id=tg_id,
            full_name="Test User",
            is_approved=approved,
            is_suspended=suspended,
            is_active=True,
        )
        s.add(u)
        s.commit()


# ── Registry: keyboard_rows ───────────────────────────────────────────────────

def test_registry_keyboard_rows():
    reg = registry.get("user_reports")
    assert reg is not None
    assert reg.keyboard_rows, "user_reports must have keyboard_rows"
    flat = [btn for row in reg.keyboard_rows for btn in row]
    assert "📝 إضافة تقرير جديد" in flat
    assert "✏️ تعديل التقارير" in flat

    hc = registry.get("healthcare")
    assert hc is not None
    assert hc.keyboard_rows
    assert ("▶️ ابدأ الآن",) in hc.keyboard_rows
    print("registry keyboard_rows OK")


# ── No records, unapproved user ───────────────────────────────────────────────

def test_no_modules_unapproved():
    mods = get_user_modules(_TG_USER)
    assert mods == [], f"Unapproved user should have no modules, got {mods}"
    assert not user_has_module(_TG_USER, "user_reports")
    print("no modules for unapproved user OK")


# ── Lazy migration for approved translator ────────────────────────────────────

def test_lazy_migration_approved_translator():
    _seed_user(_TG_APPROVED, approved=True)
    mods = get_user_modules(_TG_APPROVED)
    assert "user_reports" in mods, f"Expected 'user_reports' after lazy migration, got {mods}"
    # Second call should read from DB (not re-insert)
    mods2 = get_user_modules(_TG_APPROVED)
    assert mods2 == mods
    print(f"lazy migration OK - modules={mods}")


def test_lazy_migration_translator_directory_identity():
    tg = 9_000_090
    with _TestSessionLocal() as s:
        if not s.query(TranslatorDirectory).filter_by(translator_id=tg).first():
            s.add(TranslatorDirectory(translator_id=tg, name="Directory User"))
            s.commit()

    mods = get_user_modules(tg)
    assert "user_reports" in mods, f"Expected legacy directory user to get default module, got {mods}"
    print("lazy migration for translator directory identity OK")


# ── Lazy migration skipped for suspended users ────────────────────────────────

def test_no_lazy_migration_suspended():
    _seed_user(_TG_SUSPENDED, approved=True, suspended=True)
    mods = get_user_modules(_TG_SUSPENDED)
    assert mods == [], f"Suspended user must not be lazily migrated, got {mods}"
    print("no lazy migration for suspended user OK")


# ── Grant / revoke ────────────────────────────────────────────────────────────

def test_grant_and_revoke():
    tg = 9_000_010
    # Grant a module that doesn't require user presence in DB
    result = grant_module(tg, "healthcare", granted_by=1)
    assert result is True

    mods = get_user_modules(tg)
    assert "healthcare" in mods

    # Second grant is a no-op (already active)
    result2 = grant_module(tg, "healthcare", granted_by=1)
    assert result2 is False

    # Revoke
    rev = revoke_module(tg, "healthcare", revoked_by=1)
    assert rev is True

    mods_after = get_user_modules(tg)
    assert "healthcare" not in mods_after

    # Revoke again → no record → False
    rev2 = revoke_module(tg, "healthcare", revoked_by=1)
    assert rev2 is False

    print("grant / revoke OK")


# ── Re-grant after revoke ─────────────────────────────────────────────────────

def test_regrant_after_revoke():
    tg = 9_000_020
    grant_module(tg, "user_reports", granted_by=1)
    revoke_module(tg, "user_reports", revoked_by=1)
    # Re-grant should re-activate the existing row
    result = grant_module(tg, "user_reports", granted_by=1)
    assert result is True
    assert user_has_module(tg, "user_reports")
    print("re-grant after revoke OK")


# ── list_user_module_access ───────────────────────────────────────────────────

def test_list_user_module_access():
    tg = 9_000_030
    grant_module(tg, "user_reports", granted_by=5)
    grant_module(tg, "healthcare", granted_by=5)
    revoke_module(tg, "healthcare", revoked_by=5)

    records = list_user_module_access(tg)
    assert len(records) == 2

    active_keys = [r["module_key"] for r in records if r["is_active"]]
    assert "user_reports" in active_keys
    assert "healthcare" not in active_keys

    revoked = [r for r in records if r["module_key"] == "healthcare"][0]
    assert revoked["revoked_by"] == 5
    assert revoked["revoked_at"] is not None
    print("list_user_module_access OK")


# ── dynamic_user_kb ───────────────────────────────────────────────────────────

def test_dynamic_user_kb_builds_rows():
    from bot.keyboards import dynamic_user_kb, user_main_kb
    from telegram import ReplyKeyboardMarkup

    tg = 9_000_040
    grant_module(tg, "user_reports", granted_by=1)
    grant_module(tg, "healthcare", granted_by=1)

    kb = dynamic_user_kb(tg)
    assert isinstance(kb, ReplyKeyboardMarkup)
    flat = [btn.text for row in kb.keyboard for btn in row]
    assert "📝 إضافة تقرير جديد" in flat
    assert "▶️ ابدأ الآن" in flat
    print(f"dynamic_user_kb OK - button count={len(flat)}")


def test_dynamic_user_kb_no_modules_fallback():
    """A user with no modules gets the static fallback keyboard."""
    from bot.keyboards import dynamic_user_kb, user_main_kb
    from telegram import ReplyKeyboardMarkup

    tg = 9_000_050  # unknown user, no records, unapproved
    kb = dynamic_user_kb(tg)
    assert isinstance(kb, ReplyKeyboardMarkup)
    # Static fallback should still have at least one button
    flat = [btn.text for row in kb.keyboard for btn in row]
    assert len(flat) > 0
    print(f"dynamic_user_kb fallback OK - button count={len(flat)}")


def test_dynamic_user_kb_single_module():
    """Healthcare-only user sees only healthcare buttons."""
    from bot.keyboards import dynamic_user_kb

    tg = 9_000_060
    grant_module(tg, "healthcare", granted_by=1)

    kb = dynamic_user_kb(tg)
    flat = [btn.text for row in kb.keyboard for btn in row]
    assert "▶️ ابدأ الآن" in flat
    assert "📝 إضافة تقرير جديد" not in flat
    print(f"dynamic_user_kb single-module OK - button count={len(flat)}")


# ── DB schema: UserModuleAccess ───────────────────────────────────────────────

def test_admin_user_actions_exposes_module_access():
    from bot.handlers.admin.admin_users_management import _user_actions_kb

    kb = _user_actions_kb(
        user_id=123,
        approved=True,
        suspended=False,
        access_tg_user_id=9_123_456,
    )
    callbacks = [
        button.callback_data
        for row in kb.inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert callbacks.count("amod:list:9123456") == 1
    assert callbacks[-1] == "aum:home"
    print("admin user actions module-access button OK")


def test_admin_user_actions_skips_module_access_without_tg_id():
    from bot.handlers.admin.admin_users_management import _user_actions_kb

    kb = _user_actions_kb(
        user_id=123,
        approved=True,
        suspended=False,
        access_tg_user_id=None,
    )
    callbacks = [
        button.callback_data
        for row in kb.inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert not any(cb.startswith("amod:list:") for cb in callbacks)
    print("admin user actions missing-tg guard OK")


def test_access_identity_resolves_translator_directory_id():
    from core.access.access_service import resolve_tg_user_id

    row = TranslatorDirectory(translator_id=9_000_091, name="Directory Identity")
    assert resolve_tg_user_id(row) == 9_000_091
    print("access identity resolves translator directory id OK")


def test_schema_compatibility_backfills_users_from_translator_directory():
    tg = 9_000_092
    with _TestSessionLocal() as s:
        if not s.query(TranslatorDirectory).filter_by(translator_id=tg).first():
            s.add(TranslatorDirectory(translator_id=tg, name="Backfilled User"))
            s.commit()

    _db_session._ensure_schema_compatibility(_test_engine)

    with _TestSessionLocal() as s:
        user = s.query(User).filter_by(tg_user_id=tg).first()
        assert user is not None
        assert user.chat_id == tg
        assert user.full_name == "Backfilled User"
        assert user.is_approved is True
        assert user.is_active is True
    print("schema compatibility backfills users from translator directory OK")


def test_schema_compatibility_adds_missing_legacy_user_columns():
    from sqlalchemy import text

    legacy_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    with legacy_engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT)"))
        conn.execute(text("CREATE TABLE translators (translator_id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("INSERT INTO users (full_name) VALUES ('Existing Legacy User')"))
        conn.execute(text(
            "INSERT INTO translators (translator_id, name) VALUES (9000093, 'Legacy Directory User')"
        ))
        conn.execute(text(
            "INSERT INTO translators (translator_id, name) VALUES (9000094, 'Existing Legacy User')"
        ))

    _db_session._ensure_schema_compatibility(legacy_engine)

    with legacy_engine.connect() as conn:
        columns = {
            row[1]
            for row in conn.execute(text("PRAGMA table_info(users)")).fetchall()
        }
        assert "tg_user_id" in columns
        assert "chat_id" in columns
        assert "is_approved" in columns

        row = conn.execute(text(
            "SELECT tg_user_id, chat_id, full_name, is_approved "
            "FROM users WHERE tg_user_id = 9000093"
        )).fetchone()
        assert row is not None
        assert row[0] == 9000093
        assert row[1] == 9000093
        assert row[2] == "Legacy Directory User"
        assert row[3] == 1

        repaired = conn.execute(text(
            "SELECT tg_user_id, chat_id, is_approved "
            "FROM users WHERE full_name = 'Existing Legacy User'"
        )).fetchone()
        assert repaired is not None
        assert repaired[0] == 9000094
        assert repaired[1] == 9000094
        assert repaired[2] == 1
    print("schema compatibility adds missing legacy user columns OK")


def test_admin_user_management_registers_callbacks_in_integration_group():
    from telegram.ext import CallbackQueryHandler
    from bot.handlers.admin.admin_users_management import handle_callbacks, register

    class FakeApp:
        def __init__(self):
            self.handlers = []

        def add_handler(self, handler, group=0):
            self.handlers.append((handler, group))

    app = FakeApp()
    register(app)

    matches = [
        (handler, group)
        for handler, group in app.handlers
        if isinstance(handler, CallbackQueryHandler)
        and getattr(handler, "callback", None) is handle_callbacks
    ]
    assert len(matches) == 1

    handler, group = matches[0]
    pattern = getattr(handler, "pattern", None)
    pattern_text = getattr(pattern, "pattern", str(pattern))
    assert group == 1
    assert pattern_text == "^aum:"
    print("admin user management callback registration OK")


def test_admin_user_management_callbacks_are_known_to_fallback():
    from bot.handlers.shared.universal_fallback import is_known_callback

    callbacks = [
        "aum:list:all:0",
        "aum:list:all:4",
        "aum:home",
        "aum:close",
        "aum:user:123",
        "aum:act:suspend:123",
    ]
    for callback_data in callbacks:
        assert is_known_callback(callback_data), callback_data
    print("admin user management callbacks known to fallback OK")


def test_unique_constraint():
    """Duplicate (tg_user_id, module_key) is handled gracefully via grant idempotency."""
    tg = 9_000_070
    grant_module(tg, "user_reports", granted_by=1)
    # Second call should not raise; it returns False (no-op)
    result = grant_module(tg, "user_reports", granted_by=2)
    assert result is False
    print("unique constraint / idempotency OK")


# ── Landing resolver ──────────────────────────────────────────────────────────

def test_landing_translator_only():
    """User with only user_reports → translator landing."""
    from core.routing.landing import resolve_user_landing_interface
    tg = 9_001_001
    grant_module(tg, "user_reports", granted_by=1)
    assert resolve_user_landing_interface(tg) == "translator"
    print("landing translator_only OK")


def test_landing_healthcare_only():
    """User with only healthcare module → healthcare landing."""
    from core.routing.landing import resolve_user_landing_interface
    tg = 9_001_002
    grant_module(tg, "healthcare", granted_by=1)
    assert resolve_user_landing_interface(tg) == "healthcare"
    print("landing healthcare_only OK")


def test_landing_both_modules_translator_wins():
    """User with both modules → translator landing (translator takes priority)."""
    from core.routing.landing import resolve_user_landing_interface
    tg = 9_001_003
    grant_module(tg, "user_reports", granted_by=1)
    grant_module(tg, "healthcare", granted_by=1)
    assert resolve_user_landing_interface(tg) == "translator"
    print("landing both_modules translator_wins OK")


def test_landing_no_modules_public():
    """User with no modules → public landing."""
    from core.routing.landing import resolve_user_landing_interface
    tg = 9_001_004  # fresh, unknown user
    assert resolve_user_landing_interface(tg) == "public"
    print("landing no_modules_public OK")


def test_landing_user_main_kb_has_no_healthcare_button():
    """user_main_kb() fallback must NOT contain the healthcare ▶️ ابدأ الآن button."""
    from bot.keyboards import user_main_kb
    flat = [btn.text for row in user_main_kb().keyboard for btn in row]
    assert "▶️ ابدأ الآن" not in flat, (
        "healthcare button must not appear in the translator fallback keyboard"
    )
    print("user_main_kb no healthcare button OK")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_registry_keyboard_rows()
    test_no_modules_unapproved()
    test_lazy_migration_approved_translator()
    test_lazy_migration_translator_directory_identity()
    test_no_lazy_migration_suspended()
    test_grant_and_revoke()
    test_regrant_after_revoke()
    test_list_user_module_access()
    test_dynamic_user_kb_builds_rows()
    test_dynamic_user_kb_no_modules_fallback()
    test_dynamic_user_kb_single_module()
    test_admin_user_actions_exposes_module_access()
    test_admin_user_actions_skips_module_access_without_tg_id()
    test_access_identity_resolves_translator_directory_id()
    test_schema_compatibility_backfills_users_from_translator_directory()
    test_schema_compatibility_adds_missing_legacy_user_columns()
    test_admin_user_management_registers_callbacks_in_integration_group()
    test_admin_user_management_callbacks_are_known_to_fallback()
    test_unique_constraint()
    test_landing_translator_only()
    test_landing_healthcare_only()
    test_landing_both_modules_translator_wins()
    test_landing_no_modules_public()
    test_landing_user_main_kb_has_no_healthcare_button()
    print("\nALL RBAC TESTS PASSED")
