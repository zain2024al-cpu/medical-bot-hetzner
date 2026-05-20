# core/routing/registry.py
# Central module registry.
#
# Every platform module declares itself here with:
#   - a unique name
#   - the menu button texts that activate it
#   - (optional) extra user_data keys to wipe when interrupted
#   - (optional) activate / deactivate lifecycle hooks
#
# The registry is consulted by the interrupt layer so that no module
# needs to know about any other module's button set or cleanup logic.

import logging
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class ModuleRegistration:
    name: str
    menu_buttons: frozenset
    extra_wipe_keys: frozenset = field(default_factory=frozenset)
    on_activate: Callable | None = None
    on_deactivate: Callable | None = None


class ModuleRegistry:
    """
    Singleton registry of all platform modules.
    Use the module-level `registry` instance everywhere.
    """

    def __init__(self):
        self._modules: dict[str, ModuleRegistration] = {}
        self._button_to_module: dict[str, str] = {}

    def register(
        self,
        name: str,
        menu_buttons: set,
        extra_wipe_keys: set | None = None,
        on_activate: Callable | None = None,
        on_deactivate: Callable | None = None,
    ) -> None:
        """Register a module. Safe to call multiple times (last wins)."""
        reg = ModuleRegistration(
            name=name,
            menu_buttons=frozenset(menu_buttons),
            extra_wipe_keys=frozenset(extra_wipe_keys or set()),
            on_activate=on_activate,
            on_deactivate=on_deactivate,
        )
        self._modules[name] = reg
        for btn in reg.menu_buttons:
            self._button_to_module[btn] = name
        logger.info(
            f"[registry] registered module={name!r}  buttons={len(reg.menu_buttons)}"
        )

    def resolve_button(self, text: str) -> str | None:
        """Return the module name that owns this menu button, or None."""
        return self._button_to_module.get(text)

    def get(self, name: str) -> ModuleRegistration | None:
        return self._modules.get(name)

    def all_menu_buttons(self) -> set:
        """All registered menu button texts across every module."""
        return set(self._button_to_module.keys())

    def all_modules(self) -> list[str]:
        return list(self._modules.keys())


# Module-level singleton — import this everywhere
registry = ModuleRegistry()
