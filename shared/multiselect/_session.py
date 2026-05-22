# shared/multiselect/_session.py
# Typed session state for the multiselect engine.
#
# State is stored under a single namespaced key in user_data so it never
# collides with module drafts, legacy keys, or the patient selector.
#
# IDX SNAPSHOT PROTOCOL (same doctrine as patient_selector):
#   - Options snapshot is written at open() time and never mutated.
#   - Toggle callbacks resolve against the snapshot by index.
#   - If snapshot is missing (session cleared): route None — the engine
#     cannot reconstruct caller-supplied options from first principles.
#
# selected_ids is a Python set for O(1) toggle; serialized as a list
# in user_data (JSON-compatible).

from dataclasses import dataclass, field  # noqa: F401 (field used in auto_confirm_ids default)

_KEY = "_msel"


@dataclass
class MultiSelectState:
    return_to: str           # result_router key
    title: str               # screen title (shown in header)
    icon: str                # screen icon emoji
    options: list[dict]      # snapshot: [{"id":str, "label":str, "icon":str}, ...]
    selected_ids: set[str]   # mutable set of selected option ids
    page: int = 0
    min_select: int = 0      # 0 = no minimum enforced
    max_select: int = 0      # 0 = no maximum enforced
    auto_confirm_ids: frozenset = field(default_factory=frozenset)
    # When a toggled-ON option id is in auto_confirm_ids, the engine
    # immediately auto-confirms the selection (no manual ✅ needed).
    # Use for "أخرى" / free-text options that should open text input instantly.


def save(user_data: dict, state: MultiSelectState) -> None:
    user_data[_KEY] = {
        "return_to":       state.return_to,
        "title":           state.title,
        "icon":            state.icon,
        "options":         state.options,           # already list[dict]
        "selected_ids":    list(state.selected_ids),
        "page":            state.page,
        "min_select":      state.min_select,
        "max_select":      state.max_select,
        "auto_confirm_ids": list(state.auto_confirm_ids),
    }


def load(user_data: dict) -> MultiSelectState | None:
    raw = user_data.get(_KEY)
    if not raw:
        return None
    return MultiSelectState(
        return_to=raw.get("return_to", ""),
        title=raw.get("title", ""),
        icon=raw.get("icon", "☑️"),
        options=raw.get("options", []),
        selected_ids=set(raw.get("selected_ids", [])),
        page=raw.get("page", 0),
        min_select=raw.get("min_select", 0),
        max_select=raw.get("max_select", 0),
        auto_confirm_ids=frozenset(raw.get("auto_confirm_ids", [])),
    )


def clear(user_data: dict) -> None:
    user_data.pop(_KEY, None)
