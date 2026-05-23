# modules/healthcare/medications/constants.py
# Static data for the medication dispensing flow.
# flow.py / views.py import from here — never define lists/maps inline.

# ── Step 7: اسم الصحي — shared staff registry ────────────────────────────────

from modules.healthcare.staff import HC_SP_MAP as SP_MAP, HC_STAFF_LIST as STAFF_LIST

# ── "أخرى" guard IDs ─────────────────────────────────────────────────────────

DEPT_OTHER_ID = "dept_other"

# ── Step 6: جهة الصرف — callback action IDs ──────────────────────────────────

DISPENSE_SOURCE_PHARMACY  = "disp_pharmacy"   # الصيدلية
DISPENSE_SOURCE_WAREHOUSE = "disp_warehouse"  # المخزن

DISPENSE_SOURCE_MAP: dict[str, str] = {
    DISPENSE_SOURCE_PHARMACY:  "الصيدلية",
    DISPENSE_SOURCE_WAREHOUSE: "المخزن",
}
