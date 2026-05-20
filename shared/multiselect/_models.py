# shared/multiselect/_models.py
# Value objects for the multiselect engine.
# Immutable and serializable — safe to store in session and pass to callers.

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Option:
    """
    A single selectable item.

    id    — caller-defined stable unique string (used as the selection key).
            Must not contain ':' (used as callback_data delimiter).
    label — Arabic display text shown on the button.
    icon  — optional emoji prepended to the label  (e.g. "💊", "🩺", "🩹").
    """
    id: str
    label: str
    icon: str = ""

    def display(self, selected: bool) -> str:
        """
        Formatted button text.
        Selected:   "✅ 💊 Amoxicillin"
        Unselected: "☐  💊 Amoxicillin"
        Truncated at 35 chars to stay safely under Telegram's button label limit.
        """
        prefix = "✅ " if selected else "☐  "
        body   = f"{self.icon} {self.label}" if self.icon else self.label
        full   = prefix + body
        return full if len(full) <= 35 else full[:33] + "…"

    def to_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "icon": self.icon}

    @staticmethod
    def from_dict(d: dict) -> "Option":
        return Option(id=d["id"], label=d["label"], icon=d.get("icon", ""))


@dataclass(frozen=True)
class MultiSelectResult:
    """
    Delivered to the caller's completion handler.

    selected  — tuple of chosen Option objects (empty if cancelled or nothing chosen).
    cancelled — True when the user pressed ❌ Cancel; False on ✅ Confirm.
    """
    selected: tuple
    cancelled: bool

    @property
    def ids(self) -> list[str]:
        """Convenience: list of selected option ids."""
        return [o.id for o in self.selected]

    @property
    def labels(self) -> list[str]:
        """Convenience: list of selected option labels."""
        return [o.label for o in self.selected]

    def is_empty(self) -> bool:
        return len(self.selected) == 0

    # ── Sentinel instances ────────────────────────────────────────────────────

    @staticmethod
    def cancelled_result() -> "MultiSelectResult":
        return MultiSelectResult(selected=(), cancelled=True)

    @staticmethod
    def confirmed(options: list[Option]) -> "MultiSelectResult":
        return MultiSelectResult(selected=tuple(options), cancelled=False)
