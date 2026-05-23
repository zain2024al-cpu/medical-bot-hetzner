# modules/healthcare/medical_followup/review_handlers.py
# Interactive Review Editor — routing table and step dispatcher.
#
# REVIEW_EDIT_ROUTES maps each edit button action (hcfu:edit_*) to the
# session step it opens.  open_edit_step() sets edit_from_review=True,
# advances the session to the target step, and delegates rendering to
# flow._route_to_edit_step() via a local import (avoids circular deps).

from modules.healthcare.medical_followup.session import (
    STEP_DEPARTMENT,
    STEP_PROC_TYPE,
    STEP_COMPLAINT,
    STEP_VITALS_TEMP,
    STEP_MEDS_SUPPLY,
    STEP_IMAGES,
    STEP_NOTES,
    STEP_SPECIALIST,
)

# ── Routing table ─────────────────────────────────────────────────────────────

REVIEW_EDIT_ROUTES: dict[str, str] = {
    "edit_dept":       STEP_DEPARTMENT,
    "edit_proc":       STEP_PROC_TYPE,
    "edit_complaint":  STEP_COMPLAINT,
    "edit_vitals":     STEP_VITALS_TEMP,
    "edit_meds":       STEP_MEDS_SUPPLY,
    "edit_images":     STEP_IMAGES,
    "edit_notes":      STEP_NOTES,
    "edit_specialist": STEP_SPECIALIST,
}


# ── Dispatcher ────────────────────────────────────────────────────────────────

async def open_edit_step(
    action:  str,
    session,
    update,
    context,
) -> None:
    """
    Entry point for every edit_* button on the review screen.

    Sets edit_from_review=True, advances session.step to the target, then
    delegates rendering to flow._route_to_edit_step().
    The late import of `flow` inside this function breaks the circular dependency
    (flow imports REVIEW_EDIT_ROUTES from this module at module level).
    """
    step = REVIEW_EDIT_ROUTES.get(action)
    if step is None:
        return

    session.edit_from_review = True
    session.step = step
    session.save(context.user_data)

    # Late import — flow.py is fully loaded by the time this function is called.
    from modules.healthcare.medical_followup import flow as _flow
    await _flow._route_to_edit_step(session, step, update, context)
