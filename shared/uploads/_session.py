# shared/uploads/_session.py
# Typed session state for the upload collector.
#
# State is stored under a single namespaced key (_upl) so it never
# collides with module drafts, core keys, or other shared selectors.
#
# collected    — list of UploadedFile.to_dict() snapshots
# seen_unique_ids — deduplication set, serialized as list
# ui_message_id / ui_chat_id — tracks the "collecting" message we edit
#   on each new file arrival; allows clean in-place updates even when
#   new photo messages arrive (which cannot call edit_message_text themselves).

from dataclasses import dataclass, field

from ._models import UploadedFile

_KEY = "_upl"


@dataclass
class UploadSession:
    return_to:        str
    title:            str
    icon:             str
    allowed_types:    list[str]   # "photo", "document", "pdf", "image_document"
    min_files:        int         # 0 = no minimum enforced
    max_files:        int         # 0 = no maximum enforced
    max_file_size_mb: int         # 0 = no limit (photos always server-compressed)
    collected:        list[dict]  # list[UploadedFile.to_dict()]
    seen_unique_ids:  list[str]   # for O(1)-ish dedup via list membership
    ui_message_id:    int | None = None
    ui_chat_id:       int | None = None

    @property
    def count(self) -> int:
        return len(self.collected)

    def get_files(self) -> list[UploadedFile]:
        return [UploadedFile.from_dict(d) for d in self.collected]


def save(user_data: dict, session: UploadSession) -> None:
    user_data[_KEY] = {
        "return_to":        session.return_to,
        "title":            session.title,
        "icon":             session.icon,
        "allowed_types":    session.allowed_types,
        "min_files":        session.min_files,
        "max_files":        session.max_files,
        "max_file_size_mb": session.max_file_size_mb,
        "collected":        session.collected,
        "seen_unique_ids":  session.seen_unique_ids,
        "ui_message_id":    session.ui_message_id,
        "ui_chat_id":       session.ui_chat_id,
    }


def load(user_data: dict) -> UploadSession | None:
    raw = user_data.get(_KEY)
    if not raw:
        return None
    return UploadSession(
        return_to=        raw.get("return_to",        ""),
        title=            raw.get("title",            ""),
        icon=             raw.get("icon",             "📎"),
        allowed_types=    raw.get("allowed_types",    ["photo", "document"]),
        min_files=        raw.get("min_files",        0),
        max_files=        raw.get("max_files",        0),
        max_file_size_mb= raw.get("max_file_size_mb", 0),
        collected=        raw.get("collected",        []),
        seen_unique_ids=  raw.get("seen_unique_ids",  []),
        ui_message_id=    raw.get("ui_message_id"),
        ui_chat_id=       raw.get("ui_chat_id"),
    )


def clear(user_data: dict) -> None:
    user_data.pop(_KEY, None)
