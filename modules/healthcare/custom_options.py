# modules/healthcare/custom_options.py
# Persistent custom "أخرى" option storage for all healthcare multiselects.
#
# When a user types a free-text value after selecting "أخرى", it is saved here.
# Next time the same multiselect opens, saved values appear as ready-made buttons
# at the top of the list — no need to type the same value again.
#
# All DB calls are wrapped in try/except — errors never crash the flow.

import logging
from shared.multiselect import Option

logger = logging.getLogger(__name__)

# ── Context keys (one per multiselect that has an "أخرى" option) ──────────────
CTX_HC_DEPARTMENT  = "hc_department"   # shared by woundcare + followup departments
CTX_WC_SUPPLIES    = "wc_supplies"     # woundcare medical supplies
CTX_FU_COMPLAINT   = "fu_complaint"    # followup chief complaint
CTX_FU_MEDS_SUPPLY = "fu_meds_supply"  # followup medications & supplies


def save_custom_option(context: str, label: str) -> None:
    """
    Save a user-entered custom option label for the given context.

    If the same (context, label) already exists → increments use_count.
    If it is new → inserts with use_count=1.
    Silently ignores empty labels and DB errors.
    """
    label = (label or "").strip()
    if not label:
        return
    try:
        from db.session import get_db
        from db.models import CustomOption
        with get_db() as db:
            existing = (
                db.query(CustomOption)
                .filter_by(context=context, label=label)
                .first()
            )
            if existing:
                existing.use_count = (existing.use_count or 0) + 1
            else:
                db.add(CustomOption(context=context, label=label, use_count=1))
        logger.debug(f"[custom_options] saved  ctx={context!r}  label={label!r}")
    except Exception as exc:
        logger.warning(
            f"[custom_options] save failed  ctx={context!r}  label={label!r}: {exc}"
        )


def load_custom_options(context: str, icon: str = "✏️") -> list[Option]:
    """
    Return saved custom options for the given context, most-used first.

    IDs are prefixed with "co_" to distinguish them from built-in option IDs.
    Returns an empty list on DB errors — graceful degradation.
    """
    try:
        from db.session import get_db
        from db.models import CustomOption
        with get_db() as db:
            rows = (
                db.query(CustomOption)
                .filter_by(context=context)
                .order_by(CustomOption.use_count.desc(), CustomOption.id)
                .all()
            )
            return [
                Option(id=f"co_{row.id}", label=row.label, icon=icon)
                for row in rows
            ]
    except Exception as exc:
        logger.warning(f"[custom_options] load failed  ctx={context!r}: {exc}")
        return []
