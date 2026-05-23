# modules/healthcare/supplies/constants.py
# Re-exports from medications/constants.py — supplies flow shares the same
# staff list, dispense sources, and guard IDs.

from modules.healthcare.medications.constants import (
    SP_MAP,
    STAFF_LIST,
    DEPT_OTHER_ID,
    DISPENSE_SOURCE_PHARMACY,
    DISPENSE_SOURCE_WAREHOUSE,
    DISPENSE_SOURCE_MAP,
)

__all__ = [
    "SP_MAP",
    "STAFF_LIST",
    "DEPT_OTHER_ID",
    "DISPENSE_SOURCE_PHARMACY",
    "DISPENSE_SOURCE_WAREHOUSE",
    "DISPENSE_SOURCE_MAP",
]
