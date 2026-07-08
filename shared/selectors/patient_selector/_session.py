# shared/selectors/patient_selector/_session.py
# Typed state helpers — the selector's render context stored in user_data.
#
# The state lives under a single namespaced key (_KEY) so it never
# collides with any module's own draft data or legacy keys.
#
# Follows the IDX SNAPSHOT PROTOCOL from ui_primitives:
#   - snapshot is written at render time
#   - snapshot is read (and validated) at callback time
#   - if snapshot is missing: re-render, never resolve stale idx

from dataclasses import dataclass, field

_KEY = "_sel_patient"


@dataclass
class PatientSelectorState:
    return_to: str              # result_router key: e.g. "healthcare.woundcare.patient"
    page: int = 0               # current list page (0-based)
    search_query: str = ""      # active search filter (empty = no filter)
    # ✅ True فقط لزرّي صرف الأدوية/المستلزمات الطبية — يُظهر مرضى "pharmacy_only"
    # إضافةً لمرضى general. يُحفظ في الجلسة حتى تحترمه إعادة الجلب عند فقدان
    # الـsnapshot وبحث inline النشط.
    include_pharmacy: bool = False
    # names-only snapshot for idx resolution (avoids re-querying on every tap)
    snapshot: list[str] = field(default_factory=list)


def save(user_data: dict, state: PatientSelectorState) -> None:
    user_data[_KEY] = {
        "return_to":        state.return_to,
        "page":             state.page,
        "search_query":     state.search_query,
        "include_pharmacy": state.include_pharmacy,
        "snapshot":         state.snapshot,
    }


def load(user_data: dict) -> PatientSelectorState | None:
    raw = user_data.get(_KEY)
    if not raw:
        return None
    return PatientSelectorState(
        return_to=raw.get("return_to", ""),
        page=raw.get("page", 0),
        search_query=raw.get("search_query", ""),
        include_pharmacy=raw.get("include_pharmacy", False),
        snapshot=raw.get("snapshot", []),
    )


def clear(user_data: dict) -> None:
    user_data.pop(_KEY, None)
