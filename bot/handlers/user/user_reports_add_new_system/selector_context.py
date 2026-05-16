# =============================
# selector_context.py
# Governed selector-context preservation for back-navigation continuity.
#
# DOCTRINE:
#   Every governed selector saves its render context into report_tmp
#   under a canonical key at render time.  The back-navigation path
#   reads that key and restores it before calling the render function,
#   so the user returns to the exact view state they came from —
#   not a default-initialised screen.
#
# Keys stored per selector (all under report_tmp):
#
#   _sel_ctx_hospital  : { page, search }
#   _sel_ctx_patient   : { page, search, list_open }
#   _sel_ctx_department: { page, search }
#   _sel_ctx_doctor    : { page }   (filtered by hosp/dept — always fresh)
#
# Usage pattern:
#
#   # At render time (save):
#   SelectorContext.save_hospital(context, page, search)
#
#   # At back-navigation time (restore):
#   ctx = SelectorContext.load_hospital(context)
#   await render_hospital_selection(message, context,
#                                   page=ctx.page, search=ctx.search, query=query)
# =============================

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class _SelCtx:
    """Immutable snapshot of one selector's render context."""
    page: int = 0
    search: str = ""
    list_open: bool = False    # patient list was shown (vs menu)
    list_page: int = 0         # pagination inside patient list


class SelectorContext:
    """
    Governs persistence and retrieval of selector render contexts
    inside report_tmp.

    All methods are pure class methods — no instance needed.
    """

    # ── internal keys (never leak outside this module) ──────────────
    _KEY_HOSPITAL   = "_sel_ctx_hospital"
    _KEY_PATIENT    = "_sel_ctx_patient"
    _KEY_DEPARTMENT = "_sel_ctx_department"
    _KEY_DOCTOR     = "_sel_ctx_doctor"

    # ── helpers ──────────────────────────────────────────────────────

    @classmethod
    def _report_tmp(cls, context) -> dict:
        return context.user_data.setdefault("report_tmp", {})

    @classmethod
    def _save(cls, context, key: str, page: int = 0, search: str = "",
              list_open: bool = False, list_page: int = 0) -> None:
        cls._report_tmp(context)[key] = {
            "page": page,
            "search": search,
            "list_open": list_open,
            "list_page": list_page,
        }

    @classmethod
    def _load(cls, context, key: str) -> _SelCtx:
        raw = cls._report_tmp(context).get(key) or {}
        return _SelCtx(
            page=raw.get("page", 0),
            search=raw.get("search", ""),
            list_open=raw.get("list_open", False),
            list_page=raw.get("list_page", 0),
        )

    # ── hospital ─────────────────────────────────────────────────────

    @classmethod
    def save_hospital(cls, context, page: int = 0, search: str = "") -> None:
        cls._save(context, cls._KEY_HOSPITAL, page=page, search=search)

    @classmethod
    def load_hospital(cls, context) -> _SelCtx:
        return cls._load(context, cls._KEY_HOSPITAL)

    # ── patient ──────────────────────────────────────────────────────

    @classmethod
    def save_patient(cls, context, page: int = 0, search: str = "",
                     list_open: bool = False, list_page: int = 0) -> None:
        cls._save(context, cls._KEY_PATIENT,
                  page=page, search=search,
                  list_open=list_open, list_page=list_page)

    @classmethod
    def load_patient(cls, context) -> _SelCtx:
        return cls._load(context, cls._KEY_PATIENT)

    # ── department ───────────────────────────────────────────────────

    @classmethod
    def save_department(cls, context, page: int = 0, search: str = "") -> None:
        cls._save(context, cls._KEY_DEPARTMENT, page=page, search=search)

    @classmethod
    def load_department(cls, context) -> _SelCtx:
        return cls._load(context, cls._KEY_DEPARTMENT)

    # ── doctor ───────────────────────────────────────────────────────
    # Doctor list is always derived from hospital+department — no search/page
    # to preserve beyond the current page position.

    @classmethod
    def save_doctor(cls, context, page: int = 0) -> None:
        cls._save(context, cls._KEY_DOCTOR, page=page)

    @classmethod
    def load_doctor(cls, context) -> _SelCtx:
        return cls._load(context, cls._KEY_DOCTOR)
