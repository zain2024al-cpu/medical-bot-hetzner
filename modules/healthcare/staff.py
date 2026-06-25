# modules/healthcare/staff.py
# Canonical healthcare staff registry — single source of truth.
# All workflow constants.py files import from here.

HC_SP_MAP: dict[str, str] = {
    "sp_fadl":     "د. فضل",
    "sp_sarour":   "د. سرور",
    "sp_zakariya": "د. زكريا",
    "sp_mabrook":  "د. مبروك",
}

HC_STAFF_LIST: list[str] = list(HC_SP_MAP.values())
# ["د. فضل", "د. سرور", "د. زكريا", "د. مبروك"]
