# PRODUCTION RUNTIME EVOLUTION LOG
# Medical Workflow Engine — bot/handlers/user/user_reports_add_new_system/

**Last Updated:** 2026-05-08 (Phase A complete — Data Authority Governance doctrine established)  
**Engineer Role:** Live Distributed Operational Data System Engineer  
**System Type:** Live Production Telegram Medical Workflow Platform — PRODUCTION RUNTIME EVOLUTION TERRITORY  

---

## ════════════════════════════════════════
## GOVERNING ENGINEERING DOCTRINE
## Established: 2026-05-08 — Applies to all work from Phase B onward
## Expanded: 2026-05-08 — Data Authority Governance added as top-level concern
## Expanded: 2026-05-08 — Temporal correctness added; wrong-valid-ID risk formalized
## ════════════════════════════════════════

### What this project is

A live distributed operational data system where:
- Telegram clients
- PM2 process memory
- DB rows
- JSON/file datasets
- inline keyboard callback payloads
- active user sessions
- admin mutations
- runtime selectors

all participate simultaneously in the runtime state model.

Specific runtime properties:
- implicit runtime state
- IDX-bound distributed protocols
- ordering-sensitive callbacks
- admin/user coupling across shared DB
- deferred resolution systems (globals().get, lazy imports, runtime import chains)
- compatibility bridges (step_flows aliases, edit System A + B parallel, dual state registrations)
- active in-flight user conversations
- stale UI risks (Telegram messages persist after bot state changes)
- shadow modular systems (modular handlers loaded but bypassed)
- state-identity dependencies (integer state values = live session keys)
- **multiple data authorities with divergent synchronization states**

The architecture is historically evolved, not randomly chaotic.
Every implicit pattern is a load-bearing runtime contract until proven otherwise.

---

### What changes from Phase B onward

**DO NOT think in terms of:**
- refactoring files
- simplifying code
- cleaning architecture
- reducing lines of code
- making systems look modern

**THINK IN TERMS OF:**
LIVE DISTRIBUTED RUNTIME GOVERNANCE.

This encompasses two equal domains:
1. DATA AUTHORITY STABILIZATION
2. RUNTIME PROTOCOL MIGRATION

**Authority stabilization MUST precede protocol migration where data sources diverge.**

---

### Domain 1 — Data Authority Governance

The system currently contains multiple data authorities with different synchronization states:

| Authority Type | Entity | Status |
|---|---|---|
| DB authority | Hospital, Doctor, Patient, Report | Primary ✅ |
| DB authority | TranslatorDirectory | Exists but admin bypasses it ❌ |
| File authority | translator_names.txt | Admin writes here; user does not read first ❌ |
| File authority | doctors_unified.json | Fallback + search index; no admin write path |
| File authority | hospitals_order.txt | Read by service for ordering; manual edits only |
| Module-memory authority | hospitals_service cache | Correctly invalidated ✅ |
| Module-memory authority | doctors_service cache | NEVER invalidated ❌ |
| Generated list authority | PREDEFINED_ACTIONS | Hardcoded; single source ✅ |
| Session authority | context.user_data / report_tmp | Per-user; correctly scoped ✅ |

**The translator system is the confirmed split-brain case:**
Admin writes to file. User reads DB first. If DB has rows, file additions are invisible to users.
Admin and production runtime can observe DIFFERENT translator realities simultaneously.
This is not a future risk. It is an active production data integrity bug.

**The wrong-valid-ID principle:**

An invalid index may fail visibly — out-of-range error, fallback trigger, observable anomaly.
A valid but wrong ID passes all validation, resolves successfully, saves successfully, and silently corrupts operational data.

This makes authority-divergent ID migration MORE dangerous than index migration.
An index problem can be detected. A wrong-valid-ID problem cannot.

**Correctness has two dimensions:**
- **Structural correctness:** the ID exists, the FK resolves, the save succeeds
- **Temporal correctness:** the runtime snapshot reflects current reality at the moment of use

Both must hold. Structural correctness without temporal correctness is the definition of silent corruption.

**Pre-migration checklist — must prove ALL before any IDX→ID migration:**
1. ONE authoritative data source exists for that entity
2. Admin and runtime observe the SAME dataset at all times
3. Cache invalidation is correct under all mutation paths
4. PM2 runtime freshness is controlled (cache not stale after process uptime)
5. Active conversations cannot resolve stale IDs incorrectly
6. Ordering assumptions are understood and preserved
7. Save/publish paths use the same authority source
8. Every ID that will be embedded in callback_data traces to a verified, current, correct entity

**NEVER migrate runtime protocols on top of unverified authority consistency.**
Protocol migration built on divergent data authorities creates silent corruption infrastructure.
ID-bound callbacks are NOT automatically safer than index-bound callbacks if the underlying data authority is stale or split.

---

### Domain 2 — Runtime Protocol Migration

INDEX-BOUND RUNTIME CONTRACTS are the highest-impact systemic risk in the production system.

```
hospital_idx:{i}             — hospital keyboard positional callback
doctor_idx:{i}               — doctor keyboard positional callback
dept_idx:{i}                 — department keyboard positional callback
simple_translator:{flow}:{i} — translator keyboard positional callback
action_idx:{i}               — action type keyboard positional callback
```

These are NOT UI details. They are distributed runtime protocols.

A Telegram message sent at time T retains its callback_data permanently.
If the DB changes at time T+1, the index i resolves to a different entity.
The system has no mechanism to detect or reject this staleness.
Result: silent wrong data written to report_tmp and saved to DB.

---

### Engineering discipline for every Phase B migration

For EVERY protocol migration, trace the FULL lifecycle:

```
render keyboard
  → callback_data embedded in Telegram message
  → message persists in Telegram client (no expiry)
  → user may interact hours/days later
  → PTB dispatches to handler
  → handler resolves idx → entity
  → entity written to report_tmp
  → report_tmp saved to DB
  → report broadcast to admin
  → edit path reads from report_tmp (not re-resolved)
```

At each step, identify:
- **stale callback window**: how long can idx be wrong?
- **active conversation hazard**: can a user have this message open right now?
- **ordering mutation hazard**: what admin action makes idx resolve wrong?
- **cache desync**: is entity resolution cached? when is cache invalidated?
- **fallback behavior**: what happens if idx is out of range?
- **rollback safety**: can old-format callbacks coexist with new-format handlers?

---

### Migration preferences (in order)

1. **Adapters** — new format handler that also accepts old format
2. **Dual-stack compatibility** — both formats active simultaneously during transition
3. **Compatibility bridges** — old idx temporarily resolved via current DB state with mismatch detection
4. **Phased migration** — one entity type at a time; never multiple protocol changes in one deploy
5. **Observability first** — add logging/warning for stale detection before removing old format

NEVER:
- big-bang rewrite
- instant normalization
- aggressive modular activation
- callback format change without compatibility layer
- removing runtime contract in same deploy that adds replacement

---

## ════════════════════════════════════════
## 1. CURRENT STATUS
## ════════════════════════════════════════

| Field | Value |
|-------|-------|
| **Current Phase** | PHASE 3 — Service Layer Audit |
| **Next Phase** | P3.1 — Audit services/doctors_smart_search.py |
| **Subsystem** | user_reports_add_new_system/ |
| **Files Being Modified** | NONE — analysis phase |
| **Overall Risk Level** | 🟢 LOW — No changes since P2.3 |

---

## ════════════════════════════════════════
## 2. COMPLETED TASKS
## ════════════════════════════════════════

### ✅ TASK 1.0 — Project-Wide Structure Analysis
- **What:** Full project tree exploration
- **Why:** Understand scope before touching anything
- **Risk Level:** 🟢 None (read-only)
- **Validation:** N/A
- **Result:** Full project map created (see Section 6 below)
- **Rollback:** N/A

---

### ✅ TASK 1.1 — Subsystem Deep Architectural Analysis
- **What:** Complete analysis of all 49 files in user_reports_add_new_system/
- **Why:** Must fully understand system before any modification
- **Risk Level:** 🟢 None (read-only)
- **Validation:** N/A
- **Result:** Architecture fully mapped (see Sections 9–18 below)
- **Rollback:** N/A

---

### ✅ TASK P2.7 + P2.8 — Dependency Graph Analysis (INVESTIGATION ONLY)

- **What:** Full import dependency audit of shared.py and the entire subsystem
- **Files Examined:** flows/shared.py, conversation_handler.py, flows/_import_helper.py, flows/stub_flows.py, all edit_handlers/before_publish/*.py
- **Status:** ANALYSIS COMPLETE — NO CODE CHANGED

---

#### DEPENDENCY GRAPH

```
app.py
  └── handlers_registry.py
        └── user_reports_add_new_system/__init__.py
              └── conversation_handler.py  ← MASTER ORCHESTRATOR
                    ├── [importlib] user_reports_add_new_system.py  ← MONOLITH (still live)
                    │     └── register(app)  ← MONOLITH provides FULL ConversationHandler
                    │
                    ├── flows/shared.py  ← imported but NOT USED by active register()
                    │     ├── ..states
                    │     ├── ..utils (_nav_buttons, format_time_12h_str)
                    │     ├── ..navigation_helpers
                    │     ├── db.session / db.models
                    │     ├── [lazy] services.translators_service
                    │     ├── [lazy] services.broadcast_service (format_report_message, broadcast_new_report)
                    │     └── bot.handlers.user.user_reports_add_helpers (validate_text_input)
                    │
                    ├── date_time_handlers.py
                    ├── patient_handlers.py
                    ├── hospital_handlers.py
                    ├── department_handlers.py
                    ├── doctor_handlers.py
                    ├── action_type_handlers.py
                    └── navigation_helpers.py

flows/shared.py  ← 2,652 lines
  ├── ZERO imports from user_reports_add_new_system.py (monolith)
  ├── Contains: save_report_to_database (full DB logic, ~400 lines)
  ├── Contains: handle_edit_before_save (full edit routing, ~300 lines)
  ├── Contains: show_final_summary (calls broadcast_service.format_report_message)
  ├── Contains: show_review_screen
  ├── Contains: handle_final_confirm (routes: review / publish / save / edit)
  ├── Contains: translator selection (full 12-flow translator system)
  ├── Contains: _is_medical_report_step_enabled() ← duplicated here to avoid circular import
  └── NOTE: Comment at line 479 explicitly states it avoids circular import with monolith

edit_handlers/before_publish/*.py (13 files)
  ├── ALL import from flows.shared (get_confirm_state, show_final_summary)
  ├── SOME import from flows.new_consult (_render_followup_calendar)
  ├── ALL contain lazy import:
  │     from bot.handlers.user.user_reports_add_new_system import start_report
  │     ← This is called only when user sends "إضافة تقرير جديد" mid-edit
  └── These are registered where? → unknown (need to check conversation_handler.py)
```

---

#### CRITICAL FINDING 1: conversation_handler.py IS A FACADE

`conversation_handler.py` imports many things from `flows/shared.py` at lines 99-121,
**but then ignores all of them** at line 218:

```python
return _original_module.register(app)  # line 218
```

The actual `register(app)` used in production is **the monolith's register()**.
The subsystem's modular handlers (date_time, patient, hospital, etc.) are imported
but **never used** — the monolith provides the full ConversationHandler including
all these states.

**Implication:** `flows/shared.py` functions (`save_report_to_database`, `handle_final_confirm`,
etc.) are imported by `conversation_handler.py` but the active ConversationHandler
does NOT use them — unless the monolith itself delegates to them internally.

---

#### CRITICAL FINDING 2: flows/shared.py IS SELF-CONTAINED

`flows/shared.py` has **ZERO direct imports from the monolith** (`user_reports_add_new_system.py`).

All its dependencies are:
- `..states` (clean)
- `..utils` (clean)
- `..navigation_helpers` (clean)
- `db.*` (external, guarded with try/except)
- `services.broadcast_service` (lazy, guarded)
- `services.translators_service` (lazy, guarded)
- `bot.handlers.user.user_reports_add_helpers` (shared helper, guarded)

The circular import comment at line 479 says `_is_medical_report_step_enabled` is
duplicated to avoid importing from monolith. This means at some point this function
DID live in the monolith — confirming decoupling is already underway.

---

#### CRITICAL FINDING 3: MONOLITH HOLDS THE REAL ConversationHandler

```python
# conversation_handler.py line 218:
return _original_module.register(app)
```

This means: **the entire ConversationHandler in production is still the monolith's**.
All the modular files (date_time_handlers, patient_handlers, etc.) are loaded
but bypassed at runtime. The monolith's register() builds and returns the actual
ConversationHandler with ALL states and ALL handlers.

---

#### CRITICAL FINDING 4: edit_handlers HAVE A MONOLITH DEPENDENCY

Every `edit_handlers/before_publish/*.py` file contains:

```python
from bot.handlers.user.user_reports_add_new_system import start_report
```

This is a **lazy import** inside a specific branch (user says "إضافة تقرير جديد" during edit).
The `user_reports_add_new_system` package's `__init__.py` exports only `register()` —
so this import attempts to get `start_report` from the package `__init__.py`,
which does NOT export it directly. This import likely **fails silently** inside try/except.

---

#### IMPORT DIRECTION MAP

```
Direction: Who imports from whom

SAFE (subsystem → only clean dependencies):
  flows/shared.py → states ✅
  flows/shared.py → utils ✅
  flows/shared.py → navigation_helpers ✅
  flows/shared.py → db.models (guarded) ✅
  flows/shared.py → services.* (lazy, guarded) ✅

LEGACY (still tied to monolith):
  conversation_handler.py → [importlib] user_reports_add_new_system.py ⚠️
  flows/_import_helper.py → [importlib] user_reports_add_new_system.py ⚠️
  edit_handlers/*.py → bot.handlers.user.user_reports_add_new_system (start_report) ⚠️

SHARED HELPERS (both subsystem and monolith use):
  flows/shared.py → user_reports_add_helpers ✅ (guarded)
  flows/*.py → user_reports_add_helpers ✅ (guarded)
  monolith → user_reports_add_helpers ✅
```

---

#### COUPLING RISK TABLE

| Component | Coupling Level | Risk | Notes |
|-----------|----------------|------|-------|
| flows/shared.py ← → monolith | ZERO direct | 🟢 NONE | Already decoupled |
| flows/shared.py ← → states | Clean import | 🟢 NONE | Read-only constants |
| flows/shared.py ← → utils | Clean import | 🟢 NONE | Pure functions |
| flows/shared.py ← → services.broadcast_service | Lazy/guarded | 🟡 LOW | format_report_message: if this changes, summary breaks |
| conversation_handler.py → monolith via importlib | TIGHT | 🔴 HIGH | Active ConversationHandler lives in monolith |
| edit_handlers → user_reports_add_new_system.start_report | FRAGILE | 🟡 MEDIUM | Lazy import, probably fails silently, edge-case path |
| flows/*.py → user_reports_add_helpers | Clean | 🟢 NONE | Guarded imports |

---

#### SAVE/EDIT COUPLING ANALYSIS

`save_report_to_database` (flows/shared.py:1379):
- Self-contained: uses SessionLocal, Report, Patient, etc. directly
- External dependency: lazy import `services.broadcast_service.broadcast_new_report` (line 1937)
- No monolith dependency: CLEAN
- Runtime state: reads exclusively from `context.user_data["report_tmp"]`
- **Status: FULLY DECOUPLED from monolith** ✅

`handle_edit_before_save` (flows/shared.py:2555):
- Self-contained routing logic
- Calls `show_edit_fields_menu`, `show_final_summary`, `show_review_screen` (all in same file)
- No monolith dependency: CLEAN
- **Status: FULLY DECOUPLED from monolith** ✅

---

#### HIDDEN ORCHESTRATION LAYER ASSESSMENT

> **Is flows/shared.py acting as a hidden orchestration layer?**

**YES — and intentionally so.**

`flows/shared.py` is the ACTUAL orchestration layer for:
1. All translator selection flows
2. All confirmation/review screens
3. Save to DB (critical path)
4. Edit-before-publish routing
5. Medical report gate (MEDICAL_REPORT_ASK logic)

This is NOT a problem — it was extracted FROM the monolith deliberately.
The risk is that it's 2,652 lines and handles too many concerns.
But this is existing architecture debt, not a new risk introduced by refactoring.

---

#### RUNTIME STATE ASSUMPTION LEAKAGE

`flows/shared.py` assumes these `context.user_data` keys exist:
- `report_tmp.current_flow` — used in save/edit to determine flow
- `report_tmp.medical_action` — critical for dispatch logic
- `report_tmp.translator_name` / `translator_id`
- `_skip_medical_gate_once` — global flag, cleared after use
- `_conversation_state` — used by _nav_buttons

These are the SAME keys used by the monolith. The state contract is **shared and consistent**.
No leakage — both sides agree on the same schema.

---

#### SAFE EXTRACTION CANDIDATES (from shared.py)

| Function | Lines | Dependencies | Safe to Extract? |
|----------|-------|--------------|-----------------|
| `escape_markdown_v1` | ~8 | none | ✅ YES (already single location) |
| `format_field_value` | ~7 | none | ✅ YES (pure function) |
| `get_field_display_name` | ~30 | none | ✅ YES (pure dict lookup) |
| `get_editable_fields_by_flow_type` | ~50 | none | ✅ YES (pure dict) |
| `get_translator_state` | ~20 | states | ✅ YES (pure mapping) |
| `get_confirm_state` | ~20 | states | ✅ YES (pure mapping) |
| `load_translator_names` | ~20 | services.translators_service | 🟡 CAREFUL (service dep) |
| `_is_medical_report_step_enabled` | 4 | none | 🟡 CAREFUL (intentionally local — avoids circular import) |

---

#### DANGEROUS DEPENDENCY CHAINS

```
CHAIN 1: Active ConversationHandler (DO NOT TOUCH)
  app.py
    → handlers_registry
      → conversation_handler.register()
        → _original_module.register(app)   ← MONOLITH
          → full 12,800-line ConversationHandler
  
  Risk: ANY change to monolith's register() signature or logic = production break

CHAIN 2: save_report_to_database → broadcast_new_report (DO NOT TOUCH YET)
  flows/shared.py:save_report_to_database
    → [lazy] services.broadcast_service.broadcast_new_report
  
  Risk: broadcast_service must be running; its format_report_message is also used
  for the preview summary screen. If format changes, both preview AND broadcast change.

CHAIN 3: edit_handlers → start_report (FRAGILE, EDGE CASE)
  edit_handlers/before_publish/*.py (13 files)
    → [lazy] bot.handlers.user.user_reports_add_new_system.start_report
  
  Risk: __init__.py only exports register(), not start_report directly.
  This import probably fails silently. Needs verification before touching edit_handlers.
```

---

#### FINAL RECOMMENDATION

> **shared.py should REMAIN temporarily monolithic (as a single file).**
>
> Reasons:
> 1. It has ZERO coupling to the actual monolith file — fully self-contained
> 2. The active ConversationHandler is still entirely the monolith's — shared.py
>    is only used if/when the subsystem's register() takes over
> 3. Breaking shared.py into smaller pieces now would be premature — the priority
>    is first completing the ConversationHandler migration (replacing monolith)
> 4. The 2,652 lines in shared.py contain critical production logic (save, broadcast)
>    that must not be disturbed until the migration path is clear
>
> **The right next priority is:**
> Verify whether the modular handlers (date_time, patient, etc.) are ACTUALLY active
> or if the monolith still handles everything — this is the key blocker to Phase 3.

---

- **Decision:** INVESTIGATION ONLY — no changes made
- **Files Changed:** NONE

---

### ✅ TASK P2.6 — Behavioral Analysis of _nav_buttons() (INVESTIGATION ONLY)

- **What:** Full behavioral diff between monolith and utils versions of `_nav_buttons()`
- **Files Examined:**
  - `user_reports_add_new_system.py:539-550` — MONOLITH version
  - `user_reports_add_new_system/utils.py:235-287` — UTILS version
- **Status:** ANALYSIS COMPLETE — NO CODE CHANGED

---

#### SIGNATURE COMPARISON

| Version | Signature |
|---------|-----------|
| Monolith | `_nav_buttons(show_back=True)` |
| Utils | `_nav_buttons(show_back=True, previous_state_name=None, current_state=None, context=None)` |

---

#### BUTTON LABEL TEXT COMPARISON

| Scenario | Monolith back label | Utils back label | Same? |
|----------|--------------------|--------------------|-------|
| show_back=True, no context | `🔙 رجوع` → `nav:back` | `🔙 رجوع` → `nav:back` | ✅ YES |
| show_back=False | (no back button) | (no back button) | ✅ YES |
| Cancel button | `❌ إلغاء العملية` → `nav:cancel` | `❌ إلغاء العملية` → `nav:cancel` | ✅ YES |

---

#### CALL SITE INVENTORY

**MONOLITH callers (all in user_reports_add_new_system.py):**
- Pattern A: `_nav_buttons()` — ~20 occurrences — default show_back=True
- Pattern B: `_nav_buttons(show_back=True)` — ~90 occurrences — explicit True
- Pattern C: `_nav_buttons(show_back=False)` — 2 occurrences (lines 4176, 4185)
- **NEVER passes: previous_state_name, current_state, or context**

**UTILS callers (all in user_reports_add_new_system/ subsystem):**
- Pattern D: `_nav_buttons(show_back=True)` — ~100+ occurrences across all flow files
- Pattern E: `_nav_buttons(show_back=False)` — 2 occurrences (doctor_handlers.py:313, 322)
- Pattern F: `_nav_buttons(show_back=True, previous_state_name='new_consult_complaint', context=context)` — 3 occurrences:
  - `doctor_handlers.py:356`
  - `flows/shared.py:951`
  - `flows/shared.py:1046`

---

#### SIDE-BY-SIDE BEHAVIORAL DIFF

```
Pattern A/B/D — show_back=True, no extra params:
  Monolith:  [[nav:back], [nav:cancel]]
  Utils:     [[nav:back], [nav:cancel]]  (current_state=None → use_edit_button=True → nav:back)
  RESULT: ✅ IDENTICAL

Pattern C/E — show_back=False:
  Monolith:  [[nav:cancel]]
  Utils:     [[nav:cancel]]
  RESULT: ✅ IDENTICAL

Pattern F — show_back=True, previous_state_name='new_consult_complaint', context with flow state (>=7):
  Utils:     [[nav:back], [nav:cancel]]  (current_state>=7, not in BASE_SELECT → nav:back)
  NOTE: previous_state_name is effectively IGNORED in this case
  RESULT: ⚠️ previous_state_name passed but not used (current_state check wins)

Pattern F — show_back=True, previous_state_name='new_consult_complaint', context with BASE state (0-6):
  Utils:     [[go_to_new_consult_complaint], [nav:cancel]]  ← DIFFERENT callback_data
  RESULT: ⚠️ BEHAVIOR DIFFERS — generates go_to_{name} instead of nav:back
  NOTE: This is INTENTIONAL for base selection states; monolith never triggers this path
```

---

#### CRITICAL FINDING: INTERNAL LOGIC DIFFERENCE IN UTILS VERSION

The utils version contains **state-aware branching logic**:

```python
states_with_back_button = [0, 1, 2, 3, 4, 5, 6]  # BASE selection states

if current_state in states_with_back_button:
    use_edit_button = False  # → go_to_{previous_state_name}
else:
    use_edit_button = True   # → nav:back (default)
```

This logic path is **only reachable when context is passed** (Pattern F).
The monolith version **never passes context** — it always gets the simple `nav:back` path.

---

#### CONSOLIDATION RISK ASSESSMENT

| Risk | Level | Reason |
|------|-------|--------|
| Monolith callers behave differently if switched to utils version | 🟢 NONE | All monolith calls use only `show_back` param — utils falls through to identical output |
| callback_data change risk | 🟢 NONE | For monolith call patterns, callback is always `nav:back` or `nav:cancel` in both versions |
| Hidden behavior change from different default logic | 🟡 LOW | Only activated with `context` param — monolith never passes context |
| Label text change | 🟢 NONE | Both produce `🔙 رجوع` and `❌ إلغاء العملية` |
| Breaking Pattern F (go_to_ callbacks) | 🟢 N/A | Pattern F only exists in utils callers — no change needed there |

---

#### VERDICT

> **Consolidation is mathematically safe for monolith callers.**
>
> The utils version is a **strict superset** of the monolith version.
> All monolith call patterns (A/B/C) produce **identical output** from utils version
> because the extra logic paths are only activated via params the monolith never passes.
>
> However: **consolidation is NOT recommended yet** because:
> 1. The monolith (`user_reports_add_new_system.py`) is the legacy file, not the active subsystem
> 2. The monolith already tries to import utils._nav_buttons via try/except at line 516-525
> 3. **The monolith already uses utils._nav_buttons if import succeeds** — no change needed
> 4. Modifying the monolith's fallback definition adds risk with zero benefit
>
> **Current state is already correct**: subsystem uses utils, monolith falls back safely.

---

#### WHAT THE MONOLITH ALREADY DOES

```python
# user_reports_add_new_system.py lines 513-548:
_nav_buttons = None

try:
    from .utils import _chunked as _chunked_utils, _cancel_kb, _nav_buttons
    # ← NOTE: _nav_buttons is imported here if .utils is available
except ImportError:
    pass

# Fallback only if import failed:
def _nav_buttons(show_back=True):  # ← only defined if import above failed
    ...
```

Wait — this must be verified. The import at line 520 imports `_nav_buttons` by name,
but line 539 defines it again unconditionally. Let me flag this.

⚠️ **ANOMALY DETECTED**: Line 520 imports `_nav_buttons` from utils, but line 539 defines
`def _nav_buttons(...)` which is NOT inside `if _nav_buttons is None:` guard.
Unlike `_chunked`, the `_nav_buttons` fallback definition is **NOT conditional**.
This means the local definition at line 539 **always overrides** the imported one.

**Impact:** The monolith ALWAYS uses its own simplified `_nav_buttons`, never utils version.
**Risk of this anomaly:** None currently (outputs are identical for monolith call patterns).
**Action required:** Document. Do NOT fix yet — fixing requires verifying monolith is unused in production.

---

- **Decision:** NO CONSOLIDATION — investigation-only as instructed
- **Result:** Both versions behaviorally compatible for all actual call patterns. Architecture already correct for subsystem. Monolith has undocumented anomaly (see above).
- **Files Changed:** NONE

---

### ✅ TASK P2.5 — Audit _chunked() duplication

- **What:** Full audit of all `_chunked` definitions and call sites across the codebase
- **Why:** Verify if consolidation was needed
- **Risk Level:** 🟢 None (read-only audit)
- **Files Examined:** utils.py, user_reports_add_new_system.py, flows/radiation_therapy.py, flows/new_consult.py, date_time_handlers.py
- **Findings:**
  - Definition 1: `utils.py:94` — canonical source ✅
  - Definition 2: `user_reports_add_new_system.py:529-531` — intentional `if _chunked is None:` fallback, only activates if import from utils.py fails. This is defensive programming, NOT a real duplicate.
  - All subsystem files (`radiation_therapy.py`, `new_consult.py`, `date_time_handlers.py`) already import from `utils.py` correctly ✅
- **Verifications Run:**
  1. ✅ Behavioral identity: Both definitions produce identical output on all test cases
  2. ✅ Return type: list of lists confirmed in both
  3. ✅ Input mutation: NONE — sequences untouched
  4. ✅ Signature: `(seq, size)` — identical in both
  5. ✅ Caller pattern: `_chunked(seq, size)` — all callers compatible
- **Decision:** NO CHANGE NEEDED — architecture already correct
- **Result:** P2.5 is a confirmed no-op. Monolith fallback is intentional and safe.
- **Rollback:** N/A

---

### ✅ TASK P2.3 — Consolidate format_time_12h duplicates

- **What:** 
  - Discovered two distinct variants (Type A: `datetime` input; Type B: string input)
  - Added `format_time_12h_str()` to `utils.py` as canonical source for Type B
  - Replaced inline definition in `flows/shared.py` with import + alias
  - Left `user_reports_edit.py` untouched (outside subsystem scope)
- **Why:** Eliminate duplicated logic; establish utils.py as single source of truth
- **Risk Level:** 🟢 Very Low — pure functions, no state, no callbacks, no ConversationHandler
- **Files Changed:**
  - `bot/handlers/user/user_reports_add_new_system/utils.py` — added `format_time_12h_str()` (lines 117–139)
  - `bot/handlers/user/user_reports_add_new_system/flows/shared.py` — replaced 23-line definition with 2-line import+alias
- **Validation Performed:**
  - `format_time_12h(datetime(13,30))` → correct output ✅
  - `format_time_12h_str('13:30')` → correct output ✅
  - `format_time_12h_str('12:00')` → noon handling correct ✅
  - `format_time_12h_str(None)` → returns None ✅
  - `shared.format_time_12h('09:15')` via alias → correct ✅
  - ALL ASSERTIONS PASSED ✅
- **Result:** SUCCESS — no behavior change, backward compatible
- **Rollback:** Restore the 23-line `format_time_12h()` definition in `flows/shared.py` and remove import line; remove `format_time_12h_str` from `utils.py`

---

### ⚠️ PRE-TASK AUDIT FINDING — escape_markdown_v1

- **Finding:** `escape_markdown_v1` is defined ONLY in `flows/shared.py` (not duplicated)
- **Exported via:** `flows/__init__.py` line 36 and line 115
- **Used by:** Only within the flows/ package
- **Decision:** NOT a consolidation target — already in single location
- **Action:** Mark P2.4 as N/A (no duplication found)

---

### ⚠️ PRE-TASK AUDIT FINDING — format_time_12h variants

- **Finding:** Two different function signatures exist with same name
  - Type A (`utils.py`, `user_reports_add_new_system.py`): accepts `datetime` object
  - Type B (`flows/shared.py`, `user_reports_edit.py`): accepts string like `"13:30"`
- **Decision:** Cannot merge directly — different input types and different callers
- **Action:** Added Type B as `format_time_12h_str` in utils.py; aliased in shared.py; left user_reports_edit.py unchanged (outside subsystem)

---

## ════════════════════════════════════════
## 3. REMAINING TASKS
## ════════════════════════════════════════

### PHASE 2 — SAFE EXTRACTION (Pending)

- [ ] **P2.1** — Extract duplicate text-validation helpers into `utils/validators.py`
- [ ] **P2.2** — Extract Arabic calendar/month name constants into `utils/constants.py`
- [x] **P2.3** — ✅ DONE — `format_time_12h_str()` added to utils.py; flows/shared.py now imports from utils
- [x] **P2.4** — ✅ N/A — `escape_markdown_v1` is NOT duplicated; already single source in flows/shared.py
- [x] **P2.5** — ✅ VERIFIED NO-OP — `_chunked()` already correctly sourced from utils.py in all subsystem files; monolith uses deliberate fallback pattern only
- [x] **P2.6** — ✅ ANALYSIS COMPLETE — See detailed findings below. NO CONSOLIDATION performed (investigation-only per instruction)
- [x] **P2.7** — ✅ ANALYSIS COMPLETE — See detailed dependency graph below. NO changes made.
- [x] **P2.8** — ✅ DOCUMENTED — importlib usage fully mapped. NO changes made.

### PHASE 3 — SERVICE LAYER CLEANUP

- [ ] **P3.1** — Audit `services/doctors_smart_search.py`
- [ ] **P3.2** — Audit `services/translators_service.py`
- [ ] **P3.3** — Confirm hospital/department repositories
- [ ] **P3.4** — Centralize DB query patterns in patient_handlers.py

### P3-PRE — Architecture Determination

- [x] **P3-PRE** — ✅ ANALYSIS COMPLETE — See P3-PRE findings in Section 9. NO changes made.
  - Migration status: **~5–10% migrated** (radiation_therapy + edit_handlers + partial shared.py utilities)
  - Active modular: radiation_therapy flow, edit_handlers router, show_final_summary/get_confirm_state
  - Inactive modular: date_time, patient, hospital, department, doctor, action_type handlers; flows/shared.py save/confirm/translator
  - **Critical implication**: P3.1–P3.4 must target monolith call sites, NOT inactive modular handlers

### PHASE 3 — SERVICE LAYER CLEANUP (Blocked until P2 complete)

- [ ] **P3.1** — Audit `services/doctors_smart_search.py` — currently called from doctor_handlers.py
- [ ] **P3.2** — Audit `services/translators_service.py` — currently called from flows/shared.py
- [ ] **P3.3** — Confirm hospital/department repositories are not duplicated in handlers
- [ ] **P3.4** — Centralize all DB query patterns used in patient_handlers.py

### PHASE 4 — FLOW ISOLATION (Blocked until P3 complete)

- [ ] **P4.1** — Confirm all 12 flows are fully in flows/*.py (not partially in original file)
- [ ] **P4.2** — Remove stub_flows.py adapter once all flows are directly imported
- [ ] **P4.3** — Confirm conversation_handler.py no longer uses original monolithic file
- [ ] **P4.4** — Delete or archive original monolithic file after full migration confirmed

### PHASE 5 — ADVANCED (Do not touch yet)

- [ ] **P5.1** — Centralized callback router
- [ ] **P5.2** — Typed state objects (TypedDict or dataclass for report_tmp)
- [ ] **P5.3** — Navigation manager class
- [ ] **P5.4** — Callback registry pattern

---

## ════════════════════════════════════════
## 4. FILE MOVEMENT LOG
## ════════════════════════════════════════

| Status | Original Location | New Location | Reason | Date |
|--------|-------------------|--------------|--------|------|
| ✅ Already done | user_reports_add_new_system.py (monolithic) | flows/shared.py | Translator/confirm/save logic extracted | Pre-existing |
| ✅ Already done | user_reports_add_new_system.py | flows/new_consult.py | new_consult flow extracted | Pre-existing |
| ✅ Already done | user_reports_add_new_system.py | flows/followup.py | followup flow extracted | Pre-existing |
| ✅ Already done | user_reports_add_new_system.py | flows/emergency.py | emergency flow extracted | Pre-existing |
| ✅ Already done | user_reports_add_new_system.py | flows/surgery_consult.py | surgery_consult flow extracted | Pre-existing |
| ✅ Already done | user_reports_add_new_system.py | flows/rehab.py | rehab flow extracted | Pre-existing |
| ✅ Already done | user_reports_add_new_system.py | flows/radiation_therapy.py | radiation_therapy flow extracted | Pre-existing |
| ⚠️ Partial | user_reports_add_new_system.py | flows/admission.py, discharge.py, etc. | May still be partially in original — needs verification | — |
| ✅ Done | `format_time_12h` (Type B string variant) | `utils.py::format_time_12h_str` | Canonical source established | 2026-05-07 |
| ✅ N/A | `escape_markdown_v1` | Already single source in flows/shared.py | No duplication found | 2026-05-07 |

---

## ════════════════════════════════════════
## 5. SAFETY VALIDATION CHECKLIST
## ════════════════════════════════════════

_Run after EVERY modification step:_

- [ ] `app.py` starts without errors (`python app.py` — check for ImportError)
- [ ] ConversationHandler registers without error (no duplicate state numbers)
- [ ] All 12 flow entry points reachable from action_type_handlers.py routing dict
- [ ] `nav:back` callbacks still handled
- [ ] `nav:cancel` callbacks still handled
- [ ] Pagination callbacks still handled (patient:show_list:N)
- [ ] Doctor selection callbacks still handled (doctor_idx:N)
- [ ] Translator callbacks still handled (translator_idx:flow:id)
- [ ] Calendar callbacks still handled ({flow}_cal_day:Y-M-D)
- [ ] No circular import warnings in startup logs
- [ ] No `ImportError` in flows/ imports
- [ ] `report_tmp` structure untouched
- [ ] `context.user_data` key names untouched

---

## ════════════════════════════════════════
## 6. HIGH RISK WARNINGS
## ════════════════════════════════════════

### 🔴 CRITICAL — DO NOT TOUCH

| Area | File | Risk | Why Dangerous |
|------|------|------|---------------|
| ConversationHandler state numbers | states.py | CRITICAL | Any renumbering breaks ALL saved sessions in production |
| callback_data string formats | All handlers | CRITICAL | Old Telegram messages remain active with old callback data |
| context.user_data["report_tmp"] key names | All flows | CRITICAL | Live sessions hold these keys — renaming breaks in-flight reports |
| Navigation history stack | navigation.py | HIGH | Every back-button relies on exact pop/push semantics |
| flow routing dict | action_type_handlers.py | HIGH | All 12 flows route through this — any error = no reports possible |
| ConversationHandler handler order | conversation_handler.py | HIGH | Wrong order = wrong handler fires first |

---

### 🟡 MEDIUM RISK — TOUCH CAREFULLY

| Area | File | Risk | Why Careful |
|------|------|------|-------------|
| flows/shared.py (2,652 lines) | shared.py | MEDIUM | Shared by ALL 12 flows — any bug affects every flow |
| Translator selection logic | shared.py | MEDIUM | Hardcoded fallback list of 19 translators + DB fallback |
| Medical report gate | shared.py | MEDIUM | Logic gate that may block saving if misconfigured |
| Hospital name normalization | hospital_handlers.py, doctor_handlers.py | MEDIUM | " - " vs ", " variations must remain consistent |
| Inline query handler | patient_handlers.py | MEDIUM | Double-registered for patients AND doctors — fragile |

---

### 🟢 SAFE TO REFACTOR

| Area | File | Why Safe |
|------|------|----------|
| format_time_12h() | utils.py, shared.py | Pure function, no state |
| escape_markdown_v1() | shared.py, possibly others | Pure function, no state |
| _chunked() | utils.py | Pure utility, no state |
| MONTH_NAMES_AR constant | utils.py | Pure constant |
| WEEKDAYS_AR constant | utils.py | Pure constant |
| _nav_buttons() | utils.py | Returns keyboard, no state mutation |
| _build_hour_keyboard() | utils.py | Pure keyboard builder |
| _build_minute_keyboard() | utils.py | Pure keyboard builder |
| Arabic text formatting | shared.py | Pure functions |

---

### ⚠️ KNOWN FRAGILE PATTERNS

1. **Duplicate `format_time_12h`** — defined in `utils.py` AND `flows/shared.py`. Must consolidate carefully.
2. **`stub_flows.py` adapter** — dynamically imports from individual flow files. If any flow file changes its exported function name, stub breaks silently.
3. **`conversation_handler.py` hybrid** — currently still imports from original monolithic file for some flows. The exact set of flows still in the original is UNKNOWN — needs verification before P4 begins.
4. **Inline query handler** — registered for both patients AND doctors (`_current_search_type` determines which mode). Double-registration risk with ConversationHandler.
5. **`_is_medical_report_step_enabled()` gate** — this function's return value controls whether medical report upload is prompted. If it returns wrong value, users either skip required upload or get blocked.
6. **Hardcoded translator fallback list** — `load_translator_names()` in shared.py has 19 hardcoded Arabic names as fallback. These must never be accidentally removed.

---

## ════════════════════════════════════════
## 7. ARCHITECTURE MAP (Phase 1 Result)
## ════════════════════════════════════════

### File Inventory (49 files)

```
user_reports_add_new_system/
├── __init__.py                      (8 lines) — exports register()
├── conversation_handler.py          (219 lines) — MASTER REGISTRATION
├── states.py                        (115 lines) — ALL STATE CONSTANTS
├── navigation.py                    (126 lines) — history stack ops
├── navigation_helpers.py            (332 lines) — back/cancel/goto handlers
├── managers.py                      (89 lines) — DataManager classes
├── utils.py                         (263 lines) — pure helpers, keyboard builders
├── date_time_handlers.py            (502 lines) — calendar + time selection
├── patient_handlers.py              (581 lines) — patient search/select
├── hospital_handlers.py             (259 lines) — hospital search/select
├── department_handlers.py           (349 lines) — dept/subdept search/select
├── doctor_handlers.py               (448 lines) — doctor search/select
├── action_type_handlers.py          (372 lines) — action selection + ROUTING
├── inline_query.py                  (? lines) — Telegram inline search
└── flows/
    ├── __init__.py
    ├── _import_helper.py            — dynamic import utilities
    ├── stub_flows.py                — adapter: imports from individual flow files
    ├── shared.py                    (2,652 lines) — SHARED ACROSS ALL FLOWS
    ├── new_consult.py               (1,008 lines)
    ├── followup.py                  (312 lines)
    ├── emergency.py                 (425 lines)
    ├── surgery_consult.py           (295 lines)
    ├── rehab.py                     (289 lines)
    ├── radiation_therapy.py         (747 lines)
    ├── admission.py                 (? lines)
    ├── operation.py                 (? lines)
    ├── final_consult.py             (? lines)
    ├── discharge.py                 (? lines)
    ├── radiology.py                 (? lines)
    └── app_reschedule.py            (? lines)
```

---

### State Machine Map (102 states total)

```
States 0–7:   BASE SELECTION (date → patient → hospital → dept → subdept → doctor → action)
States 7–15:  NEW_CONSULT flow
States 16–23: FOLLOWUP flow
States 24–35: EMERGENCY flow
States 36–42: ADMISSION flow
States 43–52: SURGERY_CONSULT flow
States 53–59: OPERATION flow
States 60–64: FINAL_CONSULT flow
States 65–72: DISCHARGE flow
States 73–83: REHAB flow (branches: physical therapy / device)
States 84–87: RADIOLOGY flow
States 88–92: APP_RESCHEDULE flow
States 93–101: RADIATION_THERAPY flow
```

---

### Data Flow

```
/new_report command
       ↓
start_report()          [date_time_handlers.py]
       ↓
STATE_SELECT_DATE (0)
       ↓ calendar
STATE_SELECT_DATE_TIME (1)
       ↓ time or skip
STATE_SELECT_PATIENT (2)
       ↓ search/select
STATE_SELECT_HOSPITAL (3)
       ↓ search/select
STATE_SELECT_DEPARTMENT (4)
       ↓ optional subdept
STATE_SELECT_SUBDEPARTMENT (5)
       ↓ or skip
STATE_SELECT_DOCTOR (6)
       ↓ search/select/manual
STATE_SELECT_ACTION_TYPE (7)
       ↓ action_type_handlers.py routing dict
       ├─ استشارة جديدة     → NEW_CONSULT_COMPLAINT (7)
       ├─ متابعة في الرقود  → FOLLOWUP_COMPLAINT (16)
       ├─ طوارئ             → EMERGENCY_COMPLAINT (24)
       ├─ ترقيد              → ADMISSION_REASON (36)
       ├─ استشارة مع عملية  → SURGERY_CONSULT_DIAGNOSIS (43)
       ├─ عملية             → OPERATION_DETAILS (53)
       ├─ استشارة أخيرة    → FINAL_CONSULT_DIAGNOSIS (60)
       ├─ خروج              → DISCHARGE_TYPE (65)
       ├─ علاج طبيعي        → REHAB_TYPE (73)
       ├─ أشعة              → RADIOLOGY_TYPE (84)
       ├─ تأجيل موعد        → APP_RESCHEDULE_REASON (88)
       └─ جلسة إشعاعي       → RADIATION_THERAPY_TYPE (93)
              ↓
       [Flow-specific handlers]
              ↓
       {FLOW}_TRANSLATOR
              ↓
       [flows/shared.py: translator selection]
              ↓
       {FLOW}_CONFIRM
              ↓
       [flows/shared.py: review + save]
              ↓
       ConversationHandler.END
```

---

### context.user_data Structure

```python
context.user_data = {
    # Navigation
    "history": [int, ...],                # Stack of visited states
    "_conversation_state": int,           # Current state constant
    "last_valid_state": str,              # Named state label

    # Core report data
    "report_tmp": {
        # Base selection (always present)
        "report_date": datetime,
        "patient_name": str,
        "patient_id": int,
        "hospital_name": str,
        "department_name": str,
        "main_department": str,
        "doctor_name": str,
        "doctor_id": int,
        "medical_action": str,
        "action_type": str,
        "current_flow": str,

        # Flow-specific fields (partial presence by flow)
        "complaint": str,
        "diagnosis": str,
        "decision": str,
        "tests": str,
        "followup_date": str|datetime,
        "followup_time": str|None,
        "followup_reason": str,
        "room_number": str,
        "room_floor": str,
        "admission_reason": str,
        "notes": str,
        "operation_details": str,
        "operation_name_en": str,
        "success_rate": str,
        "benefit_rate": str,
        "discharge_type": str,
        "admission_summary": str,
        "therapy_details": str,
        "device_name": str,
        "device_details": str,
        "radiology_type": str,
        "delivery_date": str|datetime,
        "radiation_therapy_type": str,
        "radiation_therapy_session_number": str,
        "radiation_therapy_remaining": str,
        "radiation_therapy_recommendations": str,
        "app_reschedule_reason": str,
        "app_reschedule_return_date": str,
        "app_reschedule_return_reason": str,
        "translator_name": str,
        "translator_id": int|None,

        # Internal flags
        "_medical_report_step_done": bool,
        "_pending_translator_flow": str,
        "translator_add_new": bool,
        "step_history": [int],
        "patient_search_mode": str,
        "doctor_search_mode": str,
        "doctor_manual_mode": bool,
        "{flow}_calendar_year": int,
        "{flow}_calendar_month": int,
    },

    # Cached search results
    "_patient_names_list": [str],
    "_doctors_list": [str],
    "_translators_list": [{"id": int, "name": str}],

    # Inline search
    "_current_search_type": str,       # 'patient'|'doctor'|'translator'

    # Flags
    "_skip_medical_gate_once": bool,
    "_is_approved": bool,
}
```

---

## ════════════════════════════════════════
## 8. DUPLICATE CODE CANDIDATES (Phase 2 Targets)
## ════════════════════════════════════════

The following functions are confirmed or suspected duplicates across files.
These are SAFE to consolidate as they are pure functions with no state.

| Function | Locations | Action |
|----------|-----------|--------|
| `format_time_12h()` | utils.py, shared.py, possibly flows | Consolidate in utils.py, import everywhere |
| `escape_markdown_v1()` | shared.py, likely others | Consolidate in utils.py |
| `_chunked(seq, size)` | utils.py, possibly hospital_handlers | Consolidate in utils.py |
| `MONTH_NAMES_AR` | utils.py, possibly date_time_handlers | Single source in utils.py |
| `WEEKDAYS_AR` | utils.py, possibly date_time_handlers | Single source in utils.py |
| `_cancel_kb()` | utils.py, possibly handlers | Consolidate in utils.py |
| `_nav_buttons()` | utils.py, possibly handlers | Consolidate in utils.py |

---

## ════════════════════════════════════════
## 9. NEXT SAFE STEP
## ════════════════════════════════════════

### ✅ COMPLETED: P3-PRE — Runtime Registration Map (INVESTIGATION ONLY)

**Status:** ANALYSIS COMPLETE — NO CODE CHANGED

---

#### MONOLITH register() COMPLETE ANALYSIS

The monolith's `register()` function at line 10993 builds the full ConversationHandler.
It does NOT import from flows/shared.py, date_time_handlers.py, or any other modular file
directly in the handler mapping — with one critical exception.

**Pattern: `_get_*_handler()` functions (lines 10888–10992)**

For all flows EXCEPT radiation_therapy, the monolith uses this pattern:
```python
def _get_new_consult_handler(handler_name):
    return globals().get(handler_name)
```
These `globals().get(handler_name)` calls resolve to **monolith-internal function definitions**.
None of these delegate to the modular flow files (`flows/new_consult.py`, etc.).

**EXCEPTION: radiation_therapy**
```python
def _get_radiation_therapy_handler(handler_name):
    # Explicitly imports from flows/radiation_therapy.py
    from .flows.radiation_therapy import {handler_name}
    return {handler_name}
```
This is the ONLY flow where the modular file (`flows/radiation_therapy.py`) is
actively used by the production ConversationHandler.

**Pattern: `route_edit_field_selection`**
```python
route_edit_field_selection = None  # line 20
```
This is loaded at startup via `_import_edit_routers()` which imports from
`edit_handlers/before_publish/router`. So the `edit_handlers/` subsystem IS
partially active in production — the router is loaded if available.

---

#### RUNTIME REGISTRATION MAP

| Handler Group | Source | Active in Production? |
|---|---|---|
| `start_report` | monolith line 2798 | ✅ YES |
| `handle_final_confirm` | monolith line 10006 | ✅ YES |
| `handle_simple_translator_choice` | monolith line 12702 | ✅ YES |
| All new_consult flow handlers | monolith globals() | ✅ YES |
| All followup flow handlers | monolith globals() | ✅ YES |
| All emergency flow handlers | monolith globals() | ✅ YES |
| All admission flow handlers | monolith globals() | ✅ YES |
| All surgery_consult flow handlers | monolith globals() | ✅ YES |
| All operation flow handlers | monolith globals() | ✅ YES |
| All final_consult flow handlers | monolith globals() | ✅ YES |
| All discharge flow handlers | monolith globals() | ✅ YES |
| All rehab flow handlers | monolith globals() | ✅ YES |
| All radiology flow handlers | monolith globals() | ✅ YES |
| All app_reschedule flow handlers | monolith globals() | ✅ YES |
| **radiation_therapy flow handlers** | **flows/radiation_therapy.py** | ✅ **YES — MODULAR** |
| edit_handlers/before_publish/router | edit_handlers subsystem | ✅ YES (loaded via _import_edit_routers) |
| date_time_handlers.py | modular subsystem | ❌ NOT ACTIVE (bypassed by monolith) |
| patient_handlers.py | modular subsystem | ❌ NOT ACTIVE |
| hospital_handlers.py | modular subsystem | ❌ NOT ACTIVE |
| department_handlers.py | modular subsystem | ❌ NOT ACTIVE |
| doctor_handlers.py | modular subsystem | ❌ NOT ACTIVE |
| action_type_handlers.py | modular subsystem | ❌ NOT ACTIVE |
| flows/shared.py (save, confirm, etc.) | modular subsystem | ❌ NOT ACTIVE (shadow copies) |
| flows/new_consult.py, followup.py, etc. | modular subsystem | ❌ NOT ACTIVE (imported by stub_flows but not wired) |
| conversation_handler.py modular imports | modular subsystem | ❌ LOADED BUT BYPASSED |

---

#### ACTIVE PRODUCTION PATH MAP

```
User sends /new_report
  → monolith.start_report()                        [monolith line 2798]
  → STATE_SELECT_DATE → monolith.handle_date_*()   [monolith internal]
  → STATE_SELECT_DATE_TIME → monolith...            [monolith internal]
  → STATE_SELECT_PATIENT → monolith...              [monolith internal]
  → STATE_SELECT_HOSPITAL → monolith...             [monolith internal]
  → STATE_SELECT_DEPARTMENT → monolith...           [monolith internal]
  → STATE_SELECT_SUBDEPARTMENT → monolith...        [monolith internal]
  → STATE_SELECT_DOCTOR → monolith...               [monolith internal]
  → STATE_SELECT_ACTION_TYPE → monolith...          [monolith internal]
  
  IF action = radiation_therapy:
    → flows/radiation_therapy.py handlers           [MODULAR — active]
    → flows/shared.py translator selection          [SHADOW — NOT called by these handlers]
    → monolith.handle_simple_translator_choice()    [monolith line 12702]
    → monolith.handle_final_confirm()               [monolith line 10006]
  
  ELSE (all other 11 flows):
    → monolith._get_{flow}_handler() → globals()    [monolith internal]
    → monolith.handle_simple_translator_choice()    [monolith line 12702]
    → monolith.handle_final_confirm()               [monolith line 10006]
  
  IF user tries to edit a field before publishing:
    → edit_handlers/before_publish/router           [MODULAR — active via _import_edit_routers]
    → edit_handlers/before_publish/*.py handlers    [MODULAR — active]
    → flows/shared.py.show_final_summary()          [MODULAR — active via edit_handlers]
    → flows/shared.py.get_confirm_state()           [MODULAR — active via edit_handlers]
```

---

#### INACTIVE MODULE MAP (loaded but not wired into active ConversationHandler)

```
conversation_handler.py (loaded but bypasses all of these via monolith delegation):
  ├── date_time_handlers.py        — handlers defined but never registered
  ├── patient_handlers.py          — handlers defined but never registered
  ├── hospital_handlers.py         — handlers defined but never registered
  ├── department_handlers.py       — handlers defined but never registered
  ├── doctor_handlers.py           — handlers defined but never registered
  ├── action_type_handlers.py      — handlers defined but never registered
  └── navigation_helpers.py        — imported but monolith handles nav callbacks

flows/stub_flows.py:
  ├── new_consult start fn         — imported but not used by active ConversationHandler
  ├── followup start fn            — same
  ├── emergency start fn           — same
  ├── admission start fn           — same
  ├── surgery_consult start fn     — same
  ├── operation start fn           — same
  ├── final_consult start fn       — same
  ├── discharge start fn           — same
  ├── rehab start fn               — same
  ├── radiology start fn           — same
  ├── app_reschedule start fn      — same
  └── radiation_therapy start fn   — same (monolith's _get_radiation_therapy_handler uses
                                     flows/radiation_therapy.py directly, not stub_flows)

flows/shared.py (most functions shadowed by monolith, EXCEPT those called by edit_handlers):
  ├── save_report_to_database()    — SHADOW — monolith has own version at line ~10450
  ├── handle_final_confirm()       — SHADOW — monolith uses line 10006
  ├── handle_simple_translator_choice() — SHADOW — monolith uses line 12702
  ├── show_final_summary()         — ✅ ACTIVE (called by edit_handlers/before_publish/*.py)
  ├── get_confirm_state()          — ✅ ACTIVE (called by edit_handlers/before_publish/*.py)
  ├── show_review_screen()         — ✅ ACTIVE (called by edit_handlers)
  └── translator selection fns     — SHADOW (monolith handles translator selection)
```

---

#### MIGRATION COMPLETENESS ESTIMATE

| Component | % Migrated to Modular | Status |
|---|---|---|
| radiation_therapy flow | ~90% | Modular (flows/radiation_therapy.py active) |
| edit_handlers (before_publish) | ~70% | Modular (router + handlers active) |
| flows/shared.py utilities (show_final_summary, etc.) | ~30% | Partially active via edit_handlers |
| All other 11 flows | ~0% | Shadow only — monolith handles everything |
| Base selection (date/patient/hospital/dept/doctor) | ~0% | Shadow only — modular files inactive |
| Translator selection | ~0% | Shadow only |
| Save to database | ~0% | Shadow only |
| ConversationHandler itself | ~0% | 100% monolith |
| **Overall** | **~5–10%** | Migration-in-progress (early stage) |

---

#### MIGRATION STATUS: **MIGRATION-IN-PROGRESS (EARLY STAGE)**

The system is NOT abandoned, NOT purely compatibility-only.
Active modular components: radiation_therapy + edit_handlers + flows/shared.py utilities.
The migration began with the highest-risk flow (radiation_therapy) and the edit path.

---

#### IMPLICATIONS FOR PHASE 3

**What this means for P3.1–P3.4:**

1. **P3.1 — services/doctors_smart_search.py**: This service is called by the MONOLITH's
   own doctor search handlers (not the modular doctor_handlers.py which is inactive).
   Auditing it is safe but changes must be verified against the monolith's call sites.

2. **P3.2 — services/translators_service.py**: Called by BOTH the monolith AND flows/shared.py.
   The monolith's lazy import path is the active one for 11 flows. flows/shared.py path
   is only active in edge cases (edit_handlers calling show_final_summary).

3. **P3.3 — hospital/department repositories**: These are called by the MONOLITH's own handlers,
   not the modular hospital_handlers.py or department_handlers.py (which are inactive).

4. **P3.4 — DB query patterns in patient_handlers.py**: patient_handlers.py is INACTIVE.
   DB patterns to centralize must be found in the MONOLITH's patient search section.

**Revised Phase 3 approach:**
All Phase 3 service-layer audits must target the monolith's actual call sites,
not the modular handler files (which are inactive). This changes the scope significantly.

---

- **Decision:** INVESTIGATION ONLY — no changes made
- **Files Changed:** NONE

---

### ✅ COMPLETED: P3.1 — Audit services/doctors_smart_search.py (INVESTIGATION ONLY)

**Status:** ANALYSIS COMPLETE — NO CODE CHANGED

---

#### ARCHITECTURE OVERVIEW: TWO SEPARATE SEARCH SYSTEMS

The production doctor search is NOT a single service. There are **two completely separate
data-loading pipelines** active in different parts of the doctor selection flow:

```
User selects hospital + department
        ↓
 monolith: render_doctor_selection()  [line 2737]
        ↓
 monolith: _get_doctors_from_database()  [line 2607]
        ↓
     PRIMARY:  services.doctors_service.get_doctors_for_selection()
     FALLBACK: monolith._get_doctors_fallback()  [reads data/doctors.txt]
        ↓
 builds _doctors_list in context.user_data
        ↓
 _build_doctors_keyboard() → callback_data = "doctor_idx:{i}"

User switches to inline search mode (🔍 switch_inline_query_current_chat)
        ↓
 Telegram inline query → doctor_inline_query_handler()  [line 11158]
        ↓
     services.doctors_smart_search.search_doctors()  ← DIFFERENT SERVICE
        ↓
 builds InlineQueryResultArticle with message_text = "__DOCTOR_SELECTED__:{idx}:{name}"
```

---

#### FINDING 1: doctors_smart_search.search_doctors IS CALLED FROM ONE PLACE

**Only call site in production:** `doctor_inline_query_handler()` at monolith line 11186.

```python
doctors_results = search_doctors(
    query=query_text if query_text else "",
    hospital=search_hospital if search_hospital else None,
    department=department_name if department_name else None,
    limit=20
)
```

Parameters:
- `query`: from `update.inline_query.query.strip()` — user's typed search text
- `hospital`: from `report_tmp["hospital_name"]`, mapped via hardcoded `hospital_mapping` dict
- `department`: from `report_tmp["department_name"]`
- `specialty_type`: NOT PASSED — this parameter of `search_doctors()` is never used in production
- `limit`: hardcoded 20

The `hospital_mapping` dict (lines 11170–11179) translates 8 short hospital names to full
database names. This mapping is **hardcoded inside the handler**, not in the service.

---

#### FINDING 2: doctors_service IS THE PRIMARY BUTTON-LIST PATH

`render_doctor_selection()` calls `_get_doctors_from_database()` which calls
`services.doctors_service.get_doctors_for_selection()`. This is a **different service
from doctors_smart_search** and loads from a different file: `data/doctors_unified.json`.

`doctors_smart_search` loads from: `data/doctors_organized.json` (primary) or
`data/doctors_database.json` (fallback). These are DIFFERENT JSON files from
`doctors_unified.json`.

**Summary: two services, two different JSON data files, two different loading paths.**

---

#### FINDING 3: RETURN FORMAT DIVERGENCE — CRITICAL

The two services return different dict shapes:

| Field | `doctors_smart_search.search_doctors()` | `doctors_service.get_doctors_for_selection()` |
|---|---|---|
| `name` | ✅ str | ✅ str |
| `hospital` | ✅ str (from JSON `hospital`) | ✅ str (from `hospital_name`) |
| `department` | ✅ str (raw `department` key) | ✅ str (from `department` key) |
| `department_ar` | ✅ str | ❌ NOT PRESENT |
| `department_en` | ✅ str | ❌ NOT PRESENT |
| `score` | ✅ float (search score) | ❌ NOT PRESENT |
| `fuzz_score` | ✅ float | ❌ NOT PRESENT |
| `advanced_score` | ✅ float | ❌ NOT PRESENT |

**Production consumption of `doctors_smart_search` results** (inline handler, line 11196–11208):
```python
name = doctor.get('name', 'طبيب بدون اسم')
hospital = doctor.get('hospital', 'مستشفى غير محدد')
department = doctor.get('department_ar', doctor.get('department_en', 'قسم غير محدد'))
# → Only uses: name, hospital, department_ar (fallback department_en)
# → Score fields IGNORED at consumption point
```

**Production consumption of `doctors_service` results** (button-list path, line 2704–2706):
```python
doctor['name'][:25]  # Only name is used for button label
# callback_data = f"doctor_idx:{i}" — not name-based
```

The button-list path only ever uses `doctor['name']`. The inline path uses
`name`, `hospital`, `department_ar`/`department_en`.

---

#### FINDING 4: CALLBACK DATA IS INDEX-BASED — ORDERING IS CRITICAL

The button-list doctor selection uses:
```python
callback_data = f"doctor_idx:{i}"  # i = index in _doctors_list
```
And selection uses:
```python
idx = int(query.data.split(":")[1])
doctors = context.user_data.get('_doctors_list', [])
doctor = doctors[idx]
```

**⚠️ The `doctor_idx:{i}` callback is bound to the current `_doctors_list` in
`context.user_data`. If the list ordering changes between display and selection
(e.g. cache refresh, re-query), the wrong doctor gets selected.**

The list is set once in `_build_doctors_keyboard()`:
```python
context.user_data['_doctors_list'] = doctors
```
And read back in `handle_doctor_btn_selection()`. This is a stable single-session
pairing — the list is not re-queried between display and click.

**Pagination safety:** pagination uses `doctor_page:{N}` which triggers
`_build_doctors_keyboard(page, doctors, context)` where `doctors` is read back from
`context.user_data['_doctors_list']` — the same cached list. The ordering is preserved
across pages. **This is safe because the list is cached, not re-queried on page turn.**

---

#### FINDING 5: INLINE SEARCH HAS AN INDEX BUG

The inline query path encodes the doctor as:
```python
message_text=f"__DOCTOR_SELECTED__:{idx}:{name}"
# where idx = position in doctors_results from search_doctors() call
```

But `handle_chosen_inline_result` does NOT save the doctor name — it passes to
`handle_doctor()` which reads from `update.message.text`. The `handle_doctor` function
sees the full `__DOCTOR_SELECTED__:{idx}:{name}` string and must parse the name from it.

Let me verify how `handle_doctor` processes `__DOCTOR_SELECTED__`:

---

#### FINDING 6: NO HIDDEN FALLBACK BYPASS IN MONOLITH

The monolith DOES bypass `doctors_smart_search` for the button-list path. This is
intentional — the button-list uses `doctors_service` (different service, different file).
`doctors_smart_search` is only used for the inline search path.

The monolith has a `_get_doctors_fallback()` function (line 2624) that reads
`data/doctors.txt` as a raw pipe-delimited text file — this fires if
`doctors_service` is not available. This is a tertiary fallback, not a bypass.

---

#### FINDING 7: specialty_type PARAMETER NEVER USED

`search_doctors()` accepts a `specialty_type` parameter ("medical"/"surgical") but
the monolith's only call site does NOT pass it. This entire filtering branch in
`doctors_smart_search` is dead code in production.

---

#### FINDING 8: AI RANKING IS ALSO DEAD CODE IN PRODUCTION

`_ai_enhanced_ranking()` in `doctors_smart_search.py` is called if `OPENAI_AVAILABLE=True`
and more than 3 results. However, the function never actually calls OpenAI — it runs
a local re-scoring algorithm instead (OpenAI call was replaced/stubbed). This is
effectively a second-pass local re-ranking. It IS active in production (for >3 results).

---

#### FINDING 9: SEARCH NORMALIZATION BEHAVIOR

`doctors_smart_search.normalize_text()` strips titles (dr., prof., etc.) and lowercases.
`doctors_service` does NOT normalize at search time — it uses raw lowercase comparison.

The two services have divergent normalization behavior. This is safe as they serve
different UI paths and are never compared against each other.

---

#### FINDING 10: HOSPITAL MAPPING IS HARDCODED IN HANDLER — NOT SERVICE

The hospital name translation (short → full) lives at monolith line 11170–11179:
```python
hospital_mapping = {
    "Aster CMI": "Aster CMI Hospital, Bangalore",
    "Aster RV": "Aster RV Hospital, Bangalore",
    ...8 hospitals total...
}
```

This mapping is inside `doctor_inline_query_handler()`, not in the service.
If a new hospital is added to the bot but not to this dict, inline search will
use the short name and may fail to match in `doctors_smart_search`.

---

#### PRODUCTION SEARCH ARCHITECTURE MAP

```
PATH 1: Button-list (primary UX)
  source: doctors_service.get_doctors_for_selection()
  data:   data/doctors_unified.json
  sort:   alphabetical by name (sorted() in service)
  cache:  context.user_data['_doctors_list']  (stable, session-scoped)
  select: callback_data="doctor_idx:{i}" → name = doctors[i]['name']
  result: report_tmp["doctor_name"] = doctor_name

PATH 2: Inline search (alternate UX, activated by switch_inline_query_current_chat)
  source: doctors_smart_search.search_doctors()
  data:   data/doctors_organized.json (or doctors_database.json)
  sort:   score-based + optional AI re-ranking
  cache:  NONE — results computed per query, idx is position in that query's result
  select: message_text="__DOCTOR_SELECTED__:{idx}:{name}" → handle_doctor() parses name
  result: report_tmp["doctor_name"] = parsed_name

PATH 3: Manual entry (fallback UX)
  source: user types name directly
  data:   none
  select: handle_doctor() saves raw text as doctor_name
  result: report_tmp["doctor_name"] = user_input

PATH 4: _get_doctors_fallback (tertiary, only if doctors_service unavailable)
  source: data/doctors.txt (pipe-delimited text)
  data:   data/doctors.txt
  sort:   alphabetical (sorted() in fallback)
  cache:  context.user_data['_doctors_list'] (same as PATH 1)
```

---

#### COUPLING RISK TABLE

| Component | Coupling Level | Risk | Notes |
|---|---|---|---|
| `doctors_smart_search` → monolith | LOOSE | 🟢 NONE | Called only from inline handler; returns pure data |
| Inline results format (name/hospital/dept_ar) | MEDIUM | 🟡 LOW | Removing `department_ar` would break inline display |
| `doctor_idx:{i}` callback format | TIGHT | 🔴 HIGH | MUST NOT CHANGE — tied to pagination, selection logic |
| `_doctors_list` key in user_data | TIGHT | 🔴 HIGH | MUST NOT CHANGE — multiple handlers read this key |
| `hospital_mapping` dict | MEDIUM | 🟡 MEDIUM | Hardcoded in handler; adding hospitals requires updating both handler AND service |
| `doctors_service` vs `doctors_smart_search` data files | STRUCTURAL | 🟡 MEDIUM | Different JSON files — if one is updated but not the other, results diverge |
| `_doctors_page` key in user_data | MEDIUM | 🟡 LOW | Used for pagination state; safe to read |

---

#### SAFE EXTRACTION CANDIDATES

| Item | Safe? | Notes |
|---|---|---|
| `DEPARTMENT_TRANSLATIONS` dict | ✅ YES (but unnecessary) | Pure constant, no state. However it's only used internally by `doctors_smart_search`. Leave in place. |
| `normalize_text()` in doctors_smart_search | ⚠️ CAREFUL | Distinct behavior from doctors_service normalization. Do NOT merge with other normalize_text functions. |
| `hospital_mapping` dict | ✅ COULD extract | Currently hardcoded in monolith handler. Could move to service but would require monolith change — defer. |
| `specialty_type` parameter | 🟡 DEAD CODE | Never passed by production code. Do NOT remove — could be passed by future code or admin tools. |
| `_ai_enhanced_ranking()` | 🟡 LIVE (local, no API) | Local re-ranking, not true AI. Harmless but misleadingly named. Investigation only. |

---

#### CRITICAL DO-NOT-TOUCH LIST

1. `callback_data="doctor_idx:{i}"` — format must never change
2. `context.user_data['_doctors_list']` — key name must never change
3. `context.user_data['_doctors_page']` — key name must never change
4. `message_text=f"__DOCTOR_SELECTED__:{idx}:{name}"` — format must never change
5. `search_doctors(query, hospital, department, limit)` — signature must not change
6. Result ordering from `doctors_smart_search.search_doctors()` — idx in inline results is position-sensitive
7. `hospital_mapping` entries — removing or renaming would break inline search for those hospitals

---

- **Decision:** INVESTIGATION ONLY — no changes made
- **Files Changed:** NONE

---

### ✅ COMPLETED: P3.2 — Audit services/translators_service.py (INVESTIGATION ONLY)

**Status:** ANALYSIS COMPLETE — NO CODE CHANGED

---

#### ARCHITECTURE OVERVIEW: THREE SEPARATE TRANSLATOR UX SYSTEMS

There are **three distinct translator selection UX flows** active in the codebase,
with different callback formats, different data sources, and different context.user_data contracts.

```
SYSTEM A: Monolith simple_translator (production-active for 11 flows)
  source: monolith.load_translator_names() → translators_service.get_all_translator_names()
  fallback: hardcoded 19-name list in monolith (line 12159)
  pagination: 2 pages, FIRST_PAGE_COUNT = 19 names per page
  callback: "simple_translator:{flow_type}:{real_index}" — INDEX-BOUND (position in full list)
  page nav: "translator_page:{flow_type}:{page_number}"
  user_data: NONE — no list stored in context (index is list position at render time)

SYSTEM B: flows/shared.py render_translator_selection (shadow, not used by monolith ConvHandler)
  source: TranslatorDirectory DB table, ordered by name (ORDER BY name)
  pagination: 10 per page
  callback: "translator_idx:{flow_type}:{translator.id}" — ID-BOUND (DB id, NOT index)
  page nav: "translator:show_list:{flow_type}:{page_number}"
  user_data: context.user_data["_translators_list"] = [{id, name}, ...]
  NOTE: This system is SHADOW — not called by monolith's active ConversationHandler

SYSTEM C: flows/shared.py show_translator_list (shadow, used only by System B's pagination)
  source: context.user_data["_translators_list"] (cached from System B) OR DB re-query
  callback: "translator_idx:{flow_type}:{translator.id}" — same as System B
  page nav: "translator:show_list:{flow_type}:{page}" / "translator:back_to_menu:{flow_type}"
  NOTE: Also SHADOW — only reachable via System B which is not active
```

---

#### FINDING 1: ACTIVE TRANSLATOR FUNCTIONS

The monolith's active translator path calls only ONE external function:

```python
# monolith line 12150 — load_translator_names() in monolith:
from services.translators_service import get_all_translator_names
names = get_all_translator_names()
```

`get_all_translator_names()` is the ONLY `translators_service` function called by the
production-active translator path (System A). It returns `List[str]` — names only.

**Other functions called:**
- `save_report_to_database` (flows/shared.py line 600): calls `get_translator_by_name(name)`
  to look up the ID after selection — but this is called from `flows/shared.py`'s
  `handle_simple_translator_choice`, which is the **SHADOW** version. The monolith's
  own `handle_simple_translator_choice` (line 12724–12728) does NOT call
  `get_translator_by_name` — it sets `translator_id = None` unconditionally.
- `handle_final_confirm` (monolith line 10076): calls
  `flows/shared.py.save_report_to_database` for `action == "publish"`.
  Inside `save_report_to_database` (flows/shared.py line 1379), the monolith DOES
  call `resolve_translator_for_report()` — see Finding 6.

---

#### FINDING 2: translator_id IS NULL AT SELECTION TIME IN MONOLITH

The monolith's `handle_simple_translator_choice` (line 12724–12728):
```python
translator_names = load_translator_names()
index = int(choice)
translator_name = translator_names[index]
translator_id = None  # لا نحتاج id للمترجمين الثابتين
```

`translator_id` is **always set to None** when the user picks a translator.
`report_tmp["translator_id"] = None` at selection.

The ID is resolved LATER at save time by `save_report_to_database` (flows/shared.py)
which calls `resolve_translator_for_report()` from `translators_service`.

---

#### FINDING 3: TRANSLATOR CALLBACKS ARE INDEX-BOUND IN SYSTEM A — ORDERING IS CRITICAL

System A callback format: `simple_translator:{flow_type}:{real_index}`

The `real_index` is `translator_names.index(name)` — position in the full list
returned by `get_all_translator_names()`. The handler reads:
```python
index = int(choice)
translator_name = translator_names[index]
```

**⚠️ CRITICAL: If `get_all_translator_names()` returns a different order between the
time the buttons are displayed and the time the callback fires (e.g. DB was updated),
the wrong translator name will be looked up.**

Mitigation: `get_all_translator_names()` uses a deterministic `priority_order` list
for the first N names, then sorts the remainder alphabetically — so ordering is
stable as long as the priority list doesn't change and the DB data doesn't change.

**The 19-item priority_order in translators_service must NEVER be reordered.**
Its order directly maps to button positions in the first page.

---

#### FINDING 4: HARDCODED FALLBACK LIST EXISTS IN THREE PLACES

| Location | Count | Names |
|---|---|---|
| monolith line 12159 | 19 names | معتز, ادم, هاشم, ... ياسر |
| translators_service `priority_order` (line 239) | 19 names | معتز, ادم, هاشم, ... ياسر |
| translators_service `TRANSLATORS_SEED` (line 20) | 16 entries (with telegram_ids) | ادريس, حسن, مصطفى, ... |
| flows/shared.py `ensure_default_translators` (line 87) | 14 names | مصطفى, واصل, نجم الدين, ... |

**⚠️ The four lists are NOT identical:**
- monolith fallback has 19 names
- `priority_order` has 19 names (same order as monolith fallback)
- `TRANSLATORS_SEED` has 16 entries with different ordering
- `ensure_default_translators` has 14 names

If the DB is empty and the file fallback fails, the monolith uses its own
19-name hardcoded list. This ensures System A always functions even without DB.

---

#### FINDING 5: PAGINATION CONTRACT — SYSTEM A vs SYSTEM B

**System A (production-active):**
- 2 pages maximum
- `FIRST_PAGE_COUNT = 19` (hardcoded in both `show_translator_selection` and `handle_translator_page_navigation`)
- Page 1: `translator_names[:19]`
- Page 2: `translator_names[19:]`
- No list stored in `context.user_data` — re-calls `load_translator_names()` on every page turn
- **⚠️ Race condition risk: if DB changes between page 1 display and page 2 request,
  the `real_index` computed on page 2 will be from the new list, but buttons on page 1
  still carry old indices. However this is low-risk because page navigation and selection
  happen in the same session with low DB churn.**

**System B (shadow):**
- N pages, 10 per page
- Stores `context.user_data["_translators_list"]` as `[{id, name}]`
- Callbacks use `translator.id` (DB id), NOT index
- ID-bound: immune to ordering changes after initial load
- This is the safer design, but it's not the active production path

---

#### FINDING 6: SAVE PIPELINE — resolve_translator_for_report IS PRODUCTION-ACTIVE

`handle_final_confirm` (monolith line 10076) imports and calls
`flows/shared.py.save_report_to_database` for `action == "publish"`.

Inside `save_report_to_database` (flows/shared.py):
- Reads `report_tmp["translator_name"]` (set by System A at selection time)
- Reads `report_tmp["translator_id"]` (= None from System A)
- Then calls `services.translators_service.resolve_translator_for_report(session, raw_name)`
  to canonicalize the name and look up the actual DB id

`resolve_translator_for_report()` (translators_service line 301):
1. Looks up `TranslatorDirectory` by `LOWER(TRIM(name)) == raw_name.lower()`
2. If found: returns `(translator_id, canonical_name_from_db)`
3. Else: looks up `User` by `full_name`
4. Else: returns `(None, raw_name)` — no match, saves raw name

**This means the translator saved to the DB report is the CANONICAL NAME from
`TranslatorDirectory`, not what the user saw on the button. If a DB translator name
was updated after the button list was rendered, the saved name could differ from
what the user selected.**

---

#### FINDING 7: APPROVAL / PUBLISH WORKFLOW COUPLING

The translator selection is NOT coupled to any approval workflow directly.

The sequence is:
```
show_translator_selection() → user selects → handle_simple_translator_choice()
  → report_tmp["translator_name"] = name
  → report_tmp["translator_id"] = None
  → show_final_summary()  [calls flows/shared.py — ACTIVE via handle_final_confirm]
  → handle_final_confirm() [action="publish"]
    → flows/shared.py.save_report_to_database()
      → resolve_translator_for_report() → canonical name + id
      → Report(translator_id=..., translator_name=...) saved to DB
      → broadcast_new_report() [async, fire-and-forget]
```

The "approval" step is absent from the flow — reports go directly to "publish" without
a separate approval gate for translators. The approval gate is for medical reports
(`MEDICAL_REPORT_ASK` / `medrep:yes/no/skip`), NOT for translator selection.

---

#### FINDING 8: MEDICAL REPORT GATE IS COUPLED TO TRANSLATOR SELECTION

The `show_translator_selection()` function checks `_is_medical_report_step_enabled(context)`
BEFORE showing the translator list. If the gate triggers:
1. Shows "هل يوجد تقرير طبي?" buttons (`medrep:yes/no/skip`)
2. Returns `MEDICAL_REPORT_ASK` state instead of translator state
3. Sets `report_tmp["_pending_translator_flow"] = flow_type`

After medical report handling, `_continue_to_translator_after_medical()` is called,
which sets `_skip_medical_gate_once = True` then calls `show_translator_selection()` again.

**The gate is bypassed for `appointment_reschedule` flow (explicitly excluded).**
**The gate is conditional on `_is_medical_report_step_enabled(context)` — runtime flag.**

`_medical_report_step_done` in `report_tmp` prevents the gate from firing twice.

Special case: `radiation_therapy` bypasses the standard `show_translator_selection()`
path and goes to `flows/radiation_therapy.py::show_radiation_translator_selection()`
via `_continue_to_translator_after_medical()`.

---

#### PRODUCTION TRANSLATOR ARCHITECTURE MAP

```
ALL 11 FLOWS (except radiation_therapy):

  flow_specific_handler()
        ↓
  show_translator_selection(message, context, flow_type)  [monolith line 12163]
        ↓
  [GATE] _is_medical_report_step_enabled()?
    YES → show medrep:yes/no/skip → MEDICAL_REPORT_ASK state → re-enter
    NO  → skip gate
        ↓
  load_translator_names()  [monolith line 12207]
    → translators_service.get_all_translator_names()
        → DB: TranslatorDirectory ORDER BY name, then priority-reordered
        → fallback: data/translator_names.txt
        → hardcoded 19-name list if all fail
        ↓
  Display buttons: simple_translator:{flow_type}:{real_index}  [INDEX-BOUND]
  Pagination:      translator_page:{flow_type}:{page_num}
        ↓
  handle_simple_translator_choice()  [monolith line 12702]
    → translator_name = translator_names[index]
    → report_tmp["translator_name"] = translator_name
    → report_tmp["translator_id"] = None  ← always None here
    → show_final_summary()  [flows/shared.py — ACTIVE]
    → return get_confirm_state(flow_type)
        ↓
  handle_final_confirm(action="publish")  [monolith line 10070]
    → flows/shared.py.save_report_to_database()
        → resolve_translator_for_report(session, translator_name)
            → canonical_id + canonical_name from TranslatorDirectory
        → Report(translator_name=canonical_name, translator_id=canonical_id)
        → broadcast_new_report()

RADIATION_THERAPY FLOW (special path):
  radiation_therapy flow handlers  [flows/radiation_therapy.py — ACTIVE]
        ↓
  show_radiation_translator_selection()  [flows/radiation_therapy.py]
    → different UI, but same callback pattern?  [not verified yet]
        ↓
  same save pipeline as above via handle_final_confirm
```

---

#### CONTEXT.USER_DATA TRANSLATOR CONTRACT

```python
context.user_data = {
    # Set by show_translator_selection (gate path):
    "_skip_medical_gate_once": bool,  # consumed once by gate, then deleted
    
    # Set in report_tmp by handle_simple_translator_choice:
    "report_tmp": {
        "translator_name": str,          # REQUIRED by save_report_to_database
        "translator_id": None,           # Always None at selection; resolved at save
        "_pending_translator_flow": str, # Set by gate if medrep gate fires
        "_medical_report_step_done": bool, # Prevents gate double-fire
    },
    
    # Set by flows/shared.py render_translator_selection (SHADOW ONLY):
    "_translators_list": [{"id": int, "name": str}, ...],  # not used by active path
}
```

---

#### COUPLING RISK TABLE

| Component | Coupling Level | Risk | Notes |
|---|---|---|---|
| `simple_translator:{flow_type}:{real_index}` callback format | TIGHT | 🔴 HIGH | Index-bound, order-sensitive. Must never change. |
| `translator_page:{flow_type}:{page_num}` callback format | TIGHT | 🔴 HIGH | Page nav for active translator system. |
| `medrep:yes/no/skip` callback format | TIGHT | 🔴 HIGH | Medical report gate — registered in ALL translator states. |
| `FIRST_PAGE_COUNT = 19` constant | TIGHT | 🔴 HIGH | Must match in both `show_translator_selection` AND `handle_translator_page_navigation`. Currently duplicated in 2 places in monolith. |
| `priority_order` list ordering | TIGHT | 🟡 MEDIUM | Determines index binding for page 1 buttons. Any reordering corrupts in-flight sessions. |
| `report_tmp["translator_name"]` key | TIGHT | 🔴 HIGH | Read by `save_report_to_database`. Must not be renamed. |
| `report_tmp["translator_id"]` key | MEDIUM | 🟡 LOW | Always None at selection. Resolved at save. Rename is risky. |
| `_skip_medical_gate_once` key | MEDIUM | 🟡 MEDIUM | Gate flag — one-shot, consumed by `pop()`. |
| `_pending_translator_flow` key | MEDIUM | 🟡 MEDIUM | Set by gate, read by `_continue_to_translator_after_medical`. |
| `_translators_list` key | LOW | 🟢 NONE | Only used by shadow System B path. |
| `resolve_translator_for_report()` behavior | TIGHT | 🟡 MEDIUM | Canonicalizes name at save. If TranslatorDirectory has different case/spacing, saved name differs from displayed name. |

---

#### THREE-SYSTEM SUMMARY

| System | Active? | Callback Format | Bound To | Data Source |
|---|---|---|---|---|
| A — monolith `simple_translator` | ✅ YES | `simple_translator:{flow}:{idx}` | Index (position) | `get_all_translator_names()` → DB or file or hardcoded |
| B — flows/shared.py `render_translator_selection` | ❌ SHADOW | `translator_idx:{flow}:{id}` | DB id | TranslatorDirectory ORDER BY name |
| C — flows/shared.py `show_translator_list` (pagination of B) | ❌ SHADOW | `translator_idx:{flow}:{id}` | DB id | `_translators_list` cache or DB |

**Systems B and C use a BETTER design (ID-bound) but are NOT active in production.**
System A is active and is INDEX-BOUND. Any change to list ordering corrupts in-flight callbacks.

---

#### CRITICAL DO-NOT-TOUCH LIST

1. `simple_translator:{flow_type}:{idx}` — callback format must never change
2. `translator_page:{flow_type}:{page_num}` — page nav format must never change
3. `medrep:yes/no/skip` — gate callback format must never change
4. `FIRST_PAGE_COUNT = 19` — in two places in monolith (lines 12218 and 12652) — must stay in sync
5. `priority_order` list order in `translators_service.get_all_translator_names()` — ordering is index-binding
6. `report_tmp["translator_name"]` — key name must never change
7. `_is_medical_report_step_enabled()` logic — gate control for all translator states
8. `_skip_medical_gate_once` flag — one-shot flag, consumed by `pop()` — fragile

---

- **Decision:** INVESTIGATION ONLY — no changes made
- **Files Changed:** NONE

---

### ✅ COMPLETED: P3.3 — Hospital/Department/Patient/Navigation Runtime Audit (INVESTIGATION ONLY)

**Status:** ANALYSIS COMPLETE — NO CODE CHANGED

---

## BASE SELECTION LAYER: COMPLETE RUNTIME MAP

### HOSPITALS

#### Data Source Chain
```
_get_hospitals_from_database_or_predefined()  [monolith line 3452]
  PRIMARY:  services.hospitals_service.get_all_hospitals()
              → DB: Hospital table, ORDER BY name
              → custom order: data/hospitals_order.txt (file-based priority reorder)
              → filters: _INVALID_HOSPITAL_NAMES set (UI button names excluded)
  FALLBACK1: services.hospitals_service.get_hospitals_with_details()
              → data/doctors_unified.json (hospitals array)
  FALLBACK2: PREDEFINED_HOSPITALS
              → from bot.handlers.user.user_reports_add_helpers
              → get_predefined_hospitals() → returns list from helper function
```

#### Callback Protocol — INDEX-BOUND
```
Display:   callback_data = f"hospital_idx:{hospital_index}"
           where hospital_index = i (position in hospitals_list at render time)
Pagination: callback_data = f"hosp_page:{page}"
Selection: hospital_index → context.user_data["report_tmp"]["hospitals_list"][hospital_index]
           → hospital name string → report_tmp["hospital_name"]
```

#### context.user_data Contracts
```python
report_tmp["hospitals_list"]     # List[str] — set at render, cleared at selection
report_tmp["hospitals_page"]     # int — current page
report_tmp["hospitals_search"]   # str — current search query
report_tmp["hospitals_search_mode"] # bool — waiting for text input
report_tmp["hospital_name"]      # str — FINAL: set at selection, preserved throughout
```

**⚠️ hospitals_list is CLEARED at selection (line 3609).** After hospital is selected,
`hospitals_list` is popped from `report_tmp`. The `hospital_idx:{i}` callback resolves
to a name via the still-alive `hospitals_list`, then the list is discarded.

#### Ordering Contract
`hospitals_order.txt` defines a priority order applied over DB results. This file
controls which hospitals appear first in the list. Adding a new hospital to DB without
adding it to `hospitals_order.txt` puts it at the end (after priority items, sorted
by original DB order). The priority order controls button index assignments.

**⚠️ If `hospitals_order.txt` changes between render and callback fire, the index
resolves to a different hospital.** Low risk (same session, short time window).

---

### DEPARTMENTS

#### Data Source — STATIC (hardcoded, not DB)
```
_build_departments_keyboard()  [monolith line 3666]
  Source: PREDEFINED_DEPARTMENTS + DIRECT_DEPARTMENTS
          (both imported from bot.handlers.user.user_reports_add_helpers)
  NOT from DB — departments are HARDCODED constants
  Order: priority_departments list (hardcoded, 4 items) → rest of PREDEFINED_DEPARTMENTS → DIRECT_DEPARTMENTS
```

`PREDEFINED_DEPARTMENTS` is a dict: `{main_dept_name: [subdept1, subdept2, ...]}`.
Built from 4 imported modules: `SURGERY_DEPARTMENTS`, `INTERNAL_DEPARTMENTS`,
`OPHTHALMOLOGY_DEPARTMENTS`, `PEDIATRICS_DEPARTMENTS`.

`DIRECT_DEPARTMENTS` is a list of department names that have no subdepartments.

#### Two-Level Department Selection
```
Level 1 (main dept):  dept_idx:{i} → departments_list[i]
  If dept in PREDEFINED_DEPARTMENTS:
    → report_tmp["main_department"] = dept
    → show subdepartments (Level 2)
    → return R_SUBDEPARTMENT
  Else (DIRECT_DEPARTMENTS):
    → report_tmp["department_name"] = dept
    → go to doctor selection
    → return STATE_SELECT_DOCTOR

Level 2 (subdept):   subdept_idx:{i} → subdepartments_list[i]
  → report_tmp["department_name"] = subdept_name
  → go to doctor selection
  → return STATE_SELECT_DOCTOR
```

#### Callback Protocol — INDEX-BOUND (both levels)
```
Main dept:  callback_data = f"dept_idx:{i}"       → departments_list[i]
            pagination = f"dept_page:{page}"
Subdept:    callback_data = f"subdept_idx:{i}"     → subdepartments_list[i]
            pagination = f"subdept_page:{page}"
Special:    "subdept:back"                          → back to main dept list
```

#### context.user_data Contracts
```python
report_tmp["departments_list"]      # List[str] — set at render, cleared at selection
report_tmp["departments_page"]      # int
report_tmp["departments_search"]    # str
report_tmp["departments_search_mode"] # bool
report_tmp["main_department"]       # str — set when main dept chosen, used for subdept lookup
report_tmp["subdepartments_list"]   # List[str] — set when main dept chosen
report_tmp["department_name"]       # str — FINAL: set when direct dept or subdept chosen
```

**⚠️ department_name contains the FULL BILINGUAL NAME string, e.g.
"جراحة المخ والأعصاب | Neurosurgery". This exact string is passed to
`_get_doctors_from_database(hospital_name, department_name)` for doctor filtering,
and to `doctors_smart_search.search_doctors(department=department_name)`.
Any change to the display name of a department would break doctor filtering.**

---

### PATIENTS

#### Data Source Chain
```
_get_patients_from_database()  [monolith line 2474]
  PRIMARY: services.patients_service.get_all_patients()
           → returns List[Dict] with 'id' and 'name' keys
           → sorted alphabetically: patients_list.sort(key=lambda x: x[1])
  (no explicit fallback in function body — returns [] on exception)
```

#### Two Patient Selection Paths

**PATH A: Button list (patient_idx)**
```
Display:   callback_data = f"patient_idx:{patient_id}"
           where patient_id = actual DB id from patients_list tuple (not index position)
           patients_list = [(patient_id, patient_name), ...]
Selection (handle_patient_btn_selection line 3232):
  → patient_id_int = int(patient_id)
  → searches patients_list for matching pid → patient_name
  → FALLBACK: DB lookup Patient.filter_by(id=patient_id_int)
  → report_tmp["patient_name"] = patient_name
  → report_tmp["patient_id"] = patient_id_int
```

**⚠️ PATIENT IS ID-BOUND, NOT INDEX-BOUND.** The callback carries the actual DB id.
This is safer than hospital/department selection. Ordering changes do not corrupt selection.

**PATH B: Inline search (__PATIENT_SELECTED__)**
```
Display:   switch_inline_query_current_chat → Telegram inline search
           patient_inline_query_handler → DB query → InlineQueryResultArticle
           input_message_content = f"__PATIENT_SELECTED__:{patient.id}:{patient.full_name}"
Selection: handle_doctor() receives text starting with "__PATIENT_SELECTED__"
           → parses patient_id and patient_name from message text
           → report_tmp["patient_name"] / report_tmp["patient_id"]
```

#### Pagination: PATIENT callback is ID-bound, page navigation is safe
```
callback_data = f"user_patient_page:{page}"
context.user_data["report_tmp"]["patients_list"]  — stored for ID lookup
context.user_data["report_tmp"]["patients_page"]  — current page
```

---

### NAVIGATION — handle_smart_back_navigation

**Registered:** ALL ConversationHandler states, pattern `^nav:back$`

**Logic (line 2302):**
1. Reads `_conversation_state` from `context.user_data`
2. Reads `medical_action` from `report_tmp` — **THIS IS THE PRIMARY FLOW DETECTOR**
3. Direct flow detection:
   - `"متابعة في الرقود"` → `"followup"`
   - `"مراجعة / عودة دورية"` → `"periodic_followup"`
   - `"استشارة جديدة"` → `"new_consult"`
   - `"طوارئ"` → `"emergency"`
4. Secondary detection from state + `room_number` presence (followup vs periodic_followup)
5. Default fallback: `"periodic_followup"`

**⚠️ `medical_action` value in Arabic is the PRIMARY key for back navigation routing.**
If `medical_action` is not set correctly at action selection time, back navigation
will go to the wrong previous screen. Any change to the Arabic action strings in
`PREDEFINED_ACTIONS` would break back navigation for all in-flight sessions.

---

### COMPLETE BASE SELECTION CALLBACK REGISTRY

| Callback Pattern | Handler | Binding | Ordering-Sensitive? |
|---|---|---|---|
| `hospital_idx:{i}` | `handle_hospital_selection` | INDEX → `hospitals_list[i]` | 🔴 YES |
| `hosp_page:{n}` | `handle_hospital_page` | page number | 🟡 LOW (re-renders) |
| `dept_idx:{i}` | `handle_department_selection` | INDEX → `departments_list[i]` | 🔴 YES |
| `dept_page:{n}` | `handle_department_page` | page number | 🟡 LOW |
| `subdept_idx:{i}` | `handle_subdepartment_choice` | INDEX → `subdepartments_list[i]` | 🔴 YES |
| `subdept_page:{n}` | `handle_subdepartment_page` | page number | 🟡 LOW |
| `subdept:back` | `handle_subdepartment_choice` | literal | 🟢 NONE |
| `patient_idx:{id}` | `handle_patient_btn_selection` | DB ID (safe) | 🟢 NONE |
| `user_patient_page:{n}` | `handle_patient_page` | page number | 🟡 LOW |
| `doctor_idx:{i}` | `handle_doctor_btn_selection` | INDEX → `_doctors_list[i]` | 🔴 YES |
| `doctor_page:{n}` | `handle_doctor_page` | page number | 🟡 LOW |
| `doctor_manual` | `handle_doctor_selection` | literal | 🟢 NONE |
| `nav:back` | `handle_smart_back_navigation` | logic-based | 🟡 depends on medical_action |
| `nav:cancel` | `handle_calendar_cancel` | literal | 🟢 NONE |
| `simple_translator:{f}:{i}` | `handle_simple_translator_choice` | INDEX → `translator_names[i]` | 🔴 YES |
| `translator_page:{f}:{n}` | `handle_translator_page_navigation` | page number | 🟡 LOW |

---

### DATA SOURCE SUMMARY FOR ALL SELECTION STEPS

| Step | Data Source | Source Type | File/DB |
|---|---|---|---|
| Date | inline keyboard (hardcoded) | Static | — |
| Patient | `services/patients_service` → DB `Patient` table | DB query | SQLite |
| Hospital | `services/hospitals_service` → DB `Hospital` table | DB query | SQLite |
| Hospital order | `data/hospitals_order.txt` | File | text file |
| Department | `PREDEFINED_DEPARTMENTS + DIRECT_DEPARTMENTS` from `user_reports_add_helpers` | Static hardcoded | — |
| Subdepartment | `PREDEFINED_DEPARTMENTS[main_dept]` from helpers | Static hardcoded | — |
| Doctor (buttons) | `services/doctors_service` → `data/doctors_unified.json` | File (JSON) | JSON |
| Doctor (inline) | `services/doctors_smart_search` → `data/doctors_organized.json` | File (JSON) | JSON |
| Action type | `PREDEFINED_ACTIONS` from `user_reports_add_helpers` | Static hardcoded | — |
| Translator | `services/translators_service` → DB `TranslatorDirectory` | DB query | SQLite |
| Translator order | `priority_order` list in `translators_service` | Static hardcoded | — |

---

### CRITICAL CONTRACTS TABLE — BASE SELECTION LAYER

| Contract | Value | Risk if Broken |
|---|---|---|
| `report_tmp["hospital_name"]` | exact string from hospitals_list | 🔴 doctor search fails |
| `report_tmp["department_name"]` | exact bilingual string `"عربي \| English"` | 🔴 doctor filtering fails |
| `report_tmp["main_department"]` | exact string key of `PREDEFINED_DEPARTMENTS` | 🔴 subdept lookup fails |
| `report_tmp["patient_name"]` | full_name from Patient DB | 🔴 report save fails |
| `report_tmp["patient_id"]` | integer DB id | 🔴 report save + DB linking fails |
| `report_tmp["doctor_name"]` | string (from list or manual) | 🟡 report save uses raw string |
| `report_tmp["medical_action"]` | Arabic string matching PREDEFINED_ACTIONS | 🔴 back navigation breaks |
| `PREDEFINED_ACTIONS` Arabic strings | fixed values | 🔴 routing + back nav + flow detection all break |
| `hospitals_order.txt` format | one hospital name per line | 🟡 ordering only |
| `PREDEFINED_DEPARTMENTS` key names | bilingual display strings | 🔴 subdept lookup + doctor filter |

---

#### SUMMARY FINDING: DEPARTMENT NAMES ARE BOTH DISPLAY AND CONTRACT KEYS

The department display strings (e.g. `"الجراحة | Surgery"`) serve TRIPLE duty:
1. UI button label
2. `PREDEFINED_DEPARTMENTS` dict key (for subdept lookup)
3. `department_name` in `report_tmp` (passed to doctor search)

This means the department display format is a **runtime contract**. Reformatting
the display name (e.g. changing `"|"` separator) would silently break:
- Subdepartment lookup
- Doctor filtering in `doctors_smart_search`
- Doctor filtering in `doctors_service`

---

- **Decision:** INVESTIGATION ONLY — no changes made
- **Files Changed:** NONE

---

### ✅ COMPLETED: P3.4 — Action Type Routing and Flow Dispatch Audit (INVESTIGATION ONLY)

**Target:** `handle_action_type_choice`, `_get_action_routing()`, `SmartNavigationManager`, flow start functions.

---

#### P3.4.1 — PREDEFINED_ACTIONS: The Action List Contract

`PREDEFINED_ACTIONS` is a **13-item Python list** defined in `user_reports_add_helpers.py` line 90.

```
PREDEFINED_ACTIONS = [
    "استشارة جديدة",           # index 0 → new_consult
    "استشارة مع قرار عملية",   # index 1 → surgery_consult
    "استشارة أخيرة",            # index 2 → final_consult
    "طوارئ",                    # index 3 → emergency
    "متابعة في الرقود",         # index 4 → followup
    "مراجعة / عودة دورية",     # index 5 → periodic_followup
    "عملية",                    # index 6 → operation
    "علاج طبيعي وإعادة تأهيل", # index 7 → rehab_physical
    "ترقيد",                    # index 8 → admission
    "خروج من المستشفى",         # index 9 → discharge
    "أشعة وفحوصات",             # index 10 → radiology
    "تأجيل موعد",               # index 11 → appointment_reschedule
    "جلسة إشعاعي",              # index 12 → radiation_therapy
]
```

**RUNTIME CONTRACT — INDEX-BOUND:**
- Action buttons use `action_idx:{i}` callbacks (line 4372 monolith)
- `handle_action_type_choice` resolves index back to `PREDEFINED_ACTIONS[action_idx]` (line 4750)
- If PREDEFINED_ACTIONS order changes, existing Telegram messages with old callbacks fire wrong flow
- **Same risk as hospital/department/translator** — ordering is part of the callback protocol

---

#### P3.4.2 — Two-Level Flow Dispatch

When action is selected, two things are set simultaneously in `report_tmp`:

1. `report_tmp["medical_action"]` = Arabic string (e.g. `"استشارة جديدة"`)
2. `report_tmp["current_flow"]` = flow_type string (e.g. `"new_consult"`)
3. `report_tmp["action_type"]` = same Arabic string as medical_action (redundant field)

**The `action_to_flow_type` mapping (line 4762–4776):**

| Arabic Action | flow_type string |
|---|---|
| استشارة جديدة | `new_consult` |
| متابعة في الرقود | `followup` |
| مراجعة / عودة دورية | `periodic_followup` |
| استشارة مع قرار عملية | `surgery_consult` |
| طوارئ | `emergency` |
| عملية | `operation` |
| استشارة أخيرة | `final_consult` |
| علاج طبيعي وإعادة تأهيل | `rehab_physical` |
| أشعة وفحوصات | `radiology` |
| تأجيل موعد | `appointment_reschedule` |
| ترقيد | `admission` |
| خروج من المستشفى | `discharge` |
| جلسة إشعاعي | `radiation_therapy` |

**These flow_type strings ARE the runtime contract.**
Any rename breaks back-navigation, flow start functions, `SmartNavigationManager`, and `get_translator_state`/`get_confirm_state`.

---

#### P3.4.3 — `_get_action_routing()`: Flow Dispatch Gate

After setting medical_action and current_flow, dispatch is done via `_get_action_routing()` dict (line 4280–4361).

Each entry maps Arabic action name → `{state, flow, pre_process}`:
- `state`: the ConversationHandler state to return
- `flow`: async function `start_*_flow(message, context)` to call immediately
- `pre_process`: optional lambda to prep context before calling flow function

**CRITICAL OBSERVATION:**
- `start_followup_flow` and `start_periodic_followup_flow` are IMPORTED from modular `flows/followup.py`
- All other start functions (`start_emergency_flow`, `start_operation_flow`, etc.) are defined INLINE in the monolith
- `start_radiation_therapy_flow` is imported from modular `flows/radiation_therapy.py` at call time (lazy import inside `_get_action_routing()`) — ImportError is caught and set to `None`

**If `start_radiation_therapy_flow` fails to import:** routing entry `"جلسة إشعاعي"` silently has `flow=None`. Then line 4841 will crash: `await routing["flow"](query.message, context)` → `TypeError: 'NoneType' is not callable`. This is a latent runtime crash risk.

---

#### P3.4.4 — start_*_flow Functions: Re-Override Pattern

Each `start_*_flow` function **re-saves** medical_action and current_flow redundantly (defensive re-override):

```python
# Example: start_emergency_flow (line 5811)
context.user_data["report_tmp"]["medical_action"] = "طوارئ"
context.user_data["report_tmp"]["current_flow"] = "emergency"
context.user_data['_conversation_state'] = EMERGENCY_COMPLAINT
```

This is intentional: if the flow function is ever called independently (not via action_type_choice), the contract values are still set correctly. This creates a redundancy but prevents state corruption.

---

#### P3.4.5 — SmartNavigationManager: The Back-Navigation Contract

`SmartNavigationManager` (line 1007–1540) contains `step_flows` dict with 13 flow maps.

**KEY CONTRACT — flow_type keys in step_flows:**
```
'new_consult', 'surgery_consult', 'final_consult', 'emergency',
'followup', 'periodic_followup', 'operation', 'rehab', 'radiology',
'admission', 'discharge', 'app_reschedule'
```

**MISMATCH DISCOVERED:**
- `action_to_flow_type` uses `"rehab_physical"` (line 4773)
- `step_flows` uses `'rehab'` (line 1151)
- `action_to_flow_type` uses `"appointment_reschedule"` (line 4772)
- `step_flows` uses `'app_reschedule'` (line 1233)
- `action_to_flow_type` has `"radiation_therapy"` — **NO matching key in step_flows**

This means:
1. For `rehab_physical` flows: `SmartNavigationManager.get_previous_step("rehab_physical", ...)` → "not found" → falls back to `STATE_SELECT_ACTION_TYPE`
2. For `appointment_reschedule`: same issue with key name `"appointment_reschedule"` vs `"app_reschedule"`
3. For `radiation_therapy`: no navigation map at all — back button likely broken

These are **pre-existing production back-navigation bugs** for those three flows. Do not fix during investigation.

---

#### P3.4.6 — medical_action as Back-Navigation Primary Signal

`handle_smart_back_navigation` (line 2302) uses `medical_action` Arabic string as **primary flow type detector** with hardcoded string comparisons (lines 2335–2344):

```python
if medical_action == "متابعة في الرقود":   flow_type = "followup"
elif medical_action == "مراجعة / عودة دورية": flow_type = "periodic_followup"
elif medical_action == "استشارة جديدة":    flow_type = "new_consult"
elif medical_action == "طوارئ":            flow_type = "emergency"
```

Only these 4 Arabic strings have explicit back-nav detection. All other flows fall through to:
- Check `current_state` against `followup_states` list
- Or use `current_flow` from report_tmp
- Or safe fallback to `'periodic_followup'`

**RUNTIME CONTRACT:** These 4 Arabic strings (`"متابعة في الرقود"`, `"مراجعة / عودة دورية"`, `"استشارة جديدة"`, `"طوارئ"`) must never be changed. They are hardcoded comparison targets in back-navigation logic.

---

#### P3.4.7 — discharge flow: Dynamic Back-Navigation

`discharge` flow has one dynamic back step (line 1226):
```python
'DISCHARGE_FOLLOWUP_DATE': '_DYNAMIC_DISCHARGE_BACK_',
```
This is resolved by `_resolve_dynamic_back()` method (line 1277) which reads `report_tmp["discharge_type"]` to determine the previous step. This is the only flow with dynamic back-navigation.

---

#### P3.4.8 — ConversationHandler State Keys: Mixed-Type Map

`SmartNavigationManager.step_flows` uses two types as keys:
- **Integer constants** (e.g. `STATE_SELECT_DATE`, `FOLLOWUP_COMPLAINT`) for common states shared across flows
- **String names** (e.g. `'NEW_CONSULT_COMPLAINT'`, `'SURGERY_CONSULT_DIAGNOSIS'`) for flow-specific states

Lookup uses a two-pass approach (line 1256–1405):
1. Direct integer lookup in flow_map
2. If not found: convert integer to string name via `value_to_state_name` dict (line 1378–1383), then lookup string
3. Special fast-path for followup/periodic_followup with explicit integer→string mapping (line 1389–1404)

**CONTRACT:** The `state_name_to_value` dict at line 1282 must stay in sync with actual state integer values. If state constants are ever renumbered, this breaks.

---

#### P3.4.9 — P3.4 Summary: Confirmed Runtime Contracts

| Contract | Value | Risk if Changed |
|---|---|---|
| `PREDEFINED_ACTIONS` list | 13 items, exact order | Existing callbacks fire wrong flow |
| Arabic action strings | Exact Arabic text | Back-nav detection breaks |
| `action_to_flow_type` mapping | 13 entries | Flow start never called |
| `flow_type` strings in step_flows | Must match `action_to_flow_type` values | Back-nav lookup fails |
| `medical_action` values for followup/periodic_followup/new_consult/emergency | Exact Arabic strings | Back-nav falls through to wrong flow |
| `start_*_flow` re-override pattern | Each re-saves medical_action + current_flow | Removing causes state gaps for independent calls |

**KNOWN PRE-EXISTING BUG — DO NOT FIX (document only):**
- `rehab_physical` → step_flows key is `rehab` (mismatch)
- `appointment_reschedule` → step_flows key is `app_reschedule` (mismatch)
- `radiation_therapy` → no step_flows entry (back-nav completely broken for this flow)

---

- **Decision:** INVESTIGATION ONLY — no changes made
- **Files Changed:** NONE

---

### ✅ COMPLETED: P3.5 — ConversationHandler Registry Audit (INVESTIGATION ONLY)

**Target:** `conv_handler` defined inline at line 11244. Function is `setup_user_report_handler(app)`.

---

#### P3.5.1 — ConversationHandler Top-Level Configuration

```python
ConversationHandler(
    entry_points=[...],   # 9 entry points (lines 11245–11255)
    states={...},         # 103 states (lines 11257–12098)
    fallbacks=[...],      # 12 fallback handlers (lines 12100–12120)
    per_message=False,    # NOT per-message (entry points are mixed type)
    per_chat=True,
    per_user=True,
    allow_reentry=True,   # /start re-enters the conversation
)
```

---

#### P3.5.2 — Entry Points (9 handlers)

| # | Type | Pattern / Filter | Handler |
|---|---|---|---|
| 1 | CallbackQueryHandler | `^start_report$` | `start_report` |
| 2 | CallbackQueryHandler | `^user_action:add_report$` | `start_report` |
| 3 | CallbackQueryHandler | `^add_report$` | `start_report` |
| 4 | MessageHandler | `^📝\s*إضافة\s*تقرير\s*جديد\s*$` | `start_report` |
| 5 | MessageHandler | `^📝\s*إضافة تقرير جديد\s*$` | `start_report` |
| 6 | MessageHandler | `^📝 إضافة تقرير جديد$` | `start_report` |
| 7 | MessageHandler | `إضافة تقرير جديد` (partial) | `start_report` |
| 8 | MessageHandler | `📝.*إضافة.*تقرير.*جديد` | `start_report` |

**Note:** Entry points 4–8 are 5 overlapping regex patterns for the same Arabic button text. All route to `start_report`. This is redundant but harmless (first match wins). Patterns 4–8 will all match the same text message, but ptb processes entry_points in list order and stops at first match.

---

#### P3.5.3 — Complete State Registry (103 states)

**Group 1 — Common/Shared Selection States (12 states)**

| State | Registered Handlers | Notes |
|---|---|---|
| `STATE_SELECT_DATE` | `nav:cancel`, `date:|nav:`, `main_cal_(prev|next):`, `main_cal_day:` | Date selection |
| `R_DATE` | Same 4 as above | Duplicate of STATE_SELECT_DATE |
| `R_DATE_TIME` | `time_hour:`, `time_minute:`, `time_skip`, `nav:cancel` | Time selection |
| `STATE_SELECT_PATIENT` | `nav:cancel`, `patient_idx:`, TEXT message | Patient selection |
| `R_PATIENT` | Same 3 as above | Duplicate of STATE_SELECT_PATIENT |
| `STATE_SELECT_HOSPITAL` | `nav:cancel`, `hospital_idx:`, `(hospital_page|hosp_page):`, TEXT | Hospital selection |
| `STATE_SELECT_DEPARTMENT` | `nav:cancel`, `dept_idx:`, `dept_page:`, TEXT | Dept selection |
| `R_DEPARTMENT` | Same 4 as above | Duplicate of STATE_SELECT_DEPARTMENT |
| `R_SUBDEPARTMENT` | `nav:cancel`, `subdept(?:_idx)?:`, `subdept_page:` | Subdept selection |
| `STATE_SELECT_DOCTOR` | `nav:cancel`, `doctor_idx:`, `doctor_page:`, `doctor_manual$`, TEXT | Doctor selection |
| `R_DOCTOR` | Same 5 as above | Duplicate of STATE_SELECT_DOCTOR |
| `R_ACTION_TYPE` | `nav:cancel`, `action_idx:`, `noop$`, stale-callbacks pattern | Action type |
| `STATE_SELECT_ACTION_TYPE` | Same 4 as above | Duplicate of R_ACTION_TYPE |

**⚠ OBSERVATION — R_ prefix states:**
`R_DATE`, `R_PATIENT`, `R_DEPARTMENT`, `R_SUBDEPARTMENT`, `R_DOCTOR`, `R_ACTION_TYPE` appear to be aliases/duplicates of their `STATE_SELECT_*` counterparts. They have identical handler lists. Purpose: likely legacy from renaming — both old and new state names point to the same handlers to avoid breaking sessions in mid-conversation after a deploy.

**Group 2 — Medical Gate States (3 states)**

| State | Registered Handlers |
|---|---|
| `MEDICAL_REPORT_ASK` | `medrep:(yes|no|skip)$`, `nav:back` |
| `MEDICAL_REPORT_UPLOAD` | CommandHandler(`done`), PHOTO/VIDEO/Document/TEXT handlers, `nav:back` |
| `MEDICAL_REPORT_REASON` | TEXT, `nav:back` |

**Group 3 — new_consult flow (9 states)**

All text-input states use: `_get_new_consult_handler('handle_new_consult_*')` + `nav:back`
- `NEW_CONSULT_COMPLAINT`, `NEW_CONSULT_DIAGNOSIS`, `NEW_CONSULT_DECISION`, `NEW_CONSULT_TESTS`
- `NEW_CONSULT_FOLLOWUP_DATE` — calendar callbacks + text + back
- `NEW_CONSULT_FOLLOWUP_TIME` — time callbacks + back
- `NEW_CONSULT_FOLLOWUP_REASON` — text + back
- `NEW_CONSULT_TRANSLATOR` — translator page/choice/medrep
- `NEW_CONSULT_CONFIRM` — 10 handlers (confirm/edit/draft/router)

**Group 4 — Edit/Draft states (3 string-keyed states)**

| State | Key Type | Registered Handlers |
|---|---|---|
| `"EDIT_DRAFT_FIELD"` | **string key** | `back_to_edit_fields`, `back_to_summary:`, TEXT |
| `"EDIT_DRAFT_FOLLOWUP_CALENDAR"` | **string key** | 8 draft-edit calendar/time callbacks |
| `"EDIT_DRAFT_TRANSLATOR"` | **string key** | `draft_edit_translator:`, `back_to_edit_fields` |
| `"EDIT_FIELD"` | **string key** | TEXT → `handle_edit_field_input` |

**⚠ CRITICAL — String-keyed states:**
These 4 states use Python string keys instead of integer constants. This is unusual for python-telegram-bot ConversationHandler. The framework supports string state keys, but they create a contract: no other state can accidentally map to the same integer. These states are completely isolated from the integer state transition system. `handle_edit_field_input` vs `handle_draft_field_input` — two different handlers for editing.

**Group 5 — surgery_consult flow (10 states)**

States: `SURGERY_CONSULT_DIAGNOSIS` through `SURGERY_CONSULT_CONFIRM`
- All text-input states use `_get_surgery_consult_handler(...)` + `nav:back`
- `SURGERY_CONSULT_FOLLOWUP_DATE` uses MONOLITH-defined calendar functions directly (not `_get_surgery_consult_handler`)
- `SURGERY_CONSULT_CONFIRM` has 10 handlers with `route_edit_field_selection`

**Group 6 — final_consult flow (5 states)**
`FINAL_CONSULT_DIAGNOSIS` through `FINAL_CONSULT_CONFIRM` — same pattern.

**Group 7 — followup/periodic_followup flows (8 states, SHARED)**

Both `followup` and `periodic_followup` share the SAME registered states:
- `FOLLOWUP_COMPLAINT`, `FOLLOWUP_DIAGNOSIS`, `FOLLOWUP_DECISION`
- `FOLLOWUP_ROOM_FLOOR` — text + back (comment says "only for followup, not periodic_followup")
- `FOLLOWUP_DATE_TIME`, `FOLLOWUP_REASON`, `FOLLOWUP_TRANSLATOR`, `FOLLOWUP_CONFIRM`

**⚠ CRITICAL — Shared states for two flows:**
`periodic_followup` and `followup` share ALL state integers. `FOLLOWUP_ROOM_FLOOR` is registered for both flows — the comment says it's only for `followup`, but the ConversationHandler doesn't know about `flow_type`. If a user in `periodic_followup` somehow receives a `FOLLOWUP_ROOM_FLOOR` state, the text handler will fire. The flow logic inside the handler (`_get_followup_handler('handle_followup_room_floor')`) is responsible for skipping this step for `periodic_followup` — but the state IS reachable via back-navigation or stale callbacks.

**Group 8 — emergency flow (12 states)**
`EMERGENCY_COMPLAINT` through `EMERGENCY_CONFIRM`.
`EMERGENCY_DATE_TIME` has **DUPLICATE TEXT HANDLERS** (line 11649 and 11652):
```python
MessageHandler(filters.TEXT & ~filters.COMMAND, handle_followup_date_text_input),
...
MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_date_time_text')),
```
First registered wins in ptb. `handle_followup_date_text_input` takes precedence over `handle_emergency_date_time_text`. The emergency-specific handler is **DEAD CODE** in this state.

**Group 9 — operation flow (7 states)**
`OPERATION_DETAILS_AR` through `OPERATION_CONFIRM` — standard pattern.

**Group 10 — rehab flow (8 states)**
`REHAB_TYPE`, `PHYSICAL_THERAPY_DETAILS`, `PHYSICAL_THERAPY_FOLLOWUP_DATE`, `PHYSICAL_THERAPY_FOLLOWUP_REASON`, `PHYSICAL_THERAPY_TRANSLATOR`, `PHYSICAL_THERAPY_CONFIRM`, `DEVICE_NAME_DETAILS`, `DEVICE_FOLLOWUP_DATE`, `DEVICE_FOLLOWUP_REASON`, `DEVICE_TRANSLATOR`, `DEVICE_CONFIRM`

**⚠ ORPHAN NAVIGATION ENTRIES (not in ConversationHandler):**
`SmartNavigationManager.step_flows['rehab']` references `'PHYSICAL_THERAPY_DEVICES'`, `'PHYSICAL_THERAPY_NOTES'`, and `'DEVICE_NOTES'` — but these states are NOT registered in the ConversationHandler. They appear only in the navigation map. If back-navigation ever reaches these steps (e.g. from a state after them), it will call `execute_smart_state_action` for a state that has no ConversationHandler handler.

**Group 11 — radiology flow (4 states)**
`RADIOLOGY_TYPE`, `RADIOLOGY_DELIVERY_DATE`, `RADIOLOGY_TRANSLATOR`, `RADIOLOGY_CONFIRM`

**DIFFERENCE:** `RADIOLOGY_TYPE` and `RADIOLOGY_DELIVERY_DATE` use `handle_smart_cancel_navigation` in addition to `handle_smart_back_navigation`. Other flows only use `handle_calendar_cancel` for cancel. This is an inconsistency across flows.

**Group 12 — admission flow (7 states)**
`ADMISSION_REASON` through `ADMISSION_CONFIRM` — standard pattern.

**Group 13 — discharge flow (8 states)**
`DISCHARGE_TYPE` through `DISCHARGE_CONFIRM`.
`DISCHARGE_TYPE` uses `_get_discharge_handler('handle_discharge_type')` with `^discharge_type:` pattern (CallbackQueryHandler, not text).

**Group 14 — app_reschedule flow (5 states)**
`APP_RESCHEDULE_REASON` through `APP_RESCHEDULE_CONFIRM`.
`APP_RESCHEDULE_RETURN_DATE` uses `handle_cancel_navigation` (not `handle_smart_cancel_navigation` and not `handle_calendar_cancel`) — a third different cancel handler variant.

**Group 15 — radiation_therapy flow (8 states)**
`RADIATION_THERAPY_TYPE` through `RADIATION_THERAPY_CONFIRM`.
**ALL handlers use `_get_radiation_therapy_handler(...)` which IMPORTS from the modular file at call-time with try/except.** If `flows/radiation_therapy.py` import fails, every handler in this flow resolves to `None`. ptb will call `None(update, context)` → `TypeError`. This is an active runtime crash risk for every radiation_therapy flow step.

---

#### P3.5.4 — Fallback Handlers (12 handlers, registration order matters)

```
1. patient_idx:           → handle_patient_btn_selection
2. user_patient_page:     → handle_patient_page
3. hosp_page:             → handle_hospital_page
4. select_hospital:       → handle_hospital_selection
5. nav:cancel$            → handle_cancel_navigation
6. CommandHandler cancel  → handle_cancel_navigation
7. CommandHandler start   → handle_restart_from_start
8. /start regex           → handle_restart_from_start
9. 🚀 ابدأ regex          → handle_restart_from_start
10. start_main_menu       → handle_restart_from_start_main_menu
11. .*إضافة.*تقرير.* TEXT → start_report
12. nav:back$             → handle_smart_back_navigation
13. .* (wildcard)         → debug_all_callbacks
```

**⚠ CRITICAL — Wildcard fallback (handler #13):**
`CallbackQueryHandler(debug_all_callbacks, pattern=".*")` catches ALL unmatched callbacks in the fallback list. This means any callback that doesn't match a state-specific handler AND doesn't match fallbacks 1–12 will be silently consumed by `debug_all_callbacks` which just logs and returns `None`. The ConversationHandler state does NOT change when a fallback fires (unless the handler returns a new state). Since `debug_all_callbacks` returns `None`, the state is preserved — but the user gets no response. This is production-active debug code.

**⚠ CRITICAL — Fallback nav:back is redundant with per-state nav:back:**
`nav:back` is registered in BOTH every individual state handler list AND in fallbacks. If the ConversationHandler fails to match a state handler, fallback `handle_smart_back_navigation` will still fire. This is a safety net but can mask state tracking bugs.

---

#### P3.5.5 — Handler Wiring Architecture

**`_get_*_handler()` pattern:**
All handlers except `radiation_therapy` use `globals().get(handler_name)` — they look up the function by name from the monolith's own global namespace. This means:
- The actual handler functions ARE defined in the monolith (or imported into it at module load time from modular files)
- The `_get_*_handler()` wrapper is just a deferred name resolution via `globals()`
- If a function name doesn't exist in globals(), returns `None` → state handler is `None` → runtime crash

**`_get_radiation_therapy_handler()` is the exception:**
It does a live import from `flows/radiation_therapy.py` every single time it's called. This means:
- Import happens at ConversationHandler construction time (when states dict is evaluated)
- If import fails at that point, ALL radiation_therapy handlers are `None`
- Error is caught and logged, but no fallback is provided

**`route_edit_field_selection` and `route_edit_field_input`:**
Imported at module top from `edit_handlers/before_publish/router.py`. If import fails (caught at line 27–35), both are `None`. Every `_CONFIRM` state has a fallback: `route_edit_field_selection if route_edit_field_selection else (lambda u, c: ConversationHandler.END)`. The lambda returns `END` — this means if the edit router fails to import, pressing an `edit_field:` button in any CONFIRM state ends the entire conversation silently.

---

#### P3.5.6 — Identified Anomalies

| # | Type | Location | Description |
|---|---|---|---|
| 1 | DUPLICATE STATE | `R_DATE`/`STATE_SELECT_DATE`, `R_PATIENT`/`STATE_SELECT_PATIENT`, etc. | 6 R_ states duplicate their STATE_ counterparts |
| 2 | DUPLICATE HANDLERS | `EMERGENCY_DATE_TIME` line 11649+11652 | Two TEXT MessageHandlers — first wins, second is dead code |
| 3 | DUPLICATE CONFIRM PATTERN | All `*_CONFIRM` states | `^(save|publish|edit):` AND `^save:` both registered — `save:` matches both patterns; the second `^save:` handler is dead code since first pattern already matches `save:` |
| 4 | STRING-KEYED STATES | `"EDIT_DRAFT_FIELD"`, `"EDIT_DRAFT_FOLLOWUP_CALENDAR"`, `"EDIT_DRAFT_TRANSLATOR"`, `"EDIT_FIELD"` | Out-of-band from integer state system |
| 5 | WILDCARD FALLBACK | `debug_all_callbacks, pattern=".*"` | Production debug code consuming all unmatched callbacks |
| 6 | NULL HANDLER RISK | `_get_radiation_therapy_handler` | Returns `None` on import failure → runtime crash |
| 7 | NULL HANDLER RISK | `route_edit_field_selection=None` | Triggers `ConversationHandler.END` on `edit_field:` — silent conversation kill |
| 8 | ORPHAN NAV ENTRIES | `PHYSICAL_THERAPY_DEVICES`, `PHYSICAL_THERAPY_NOTES`, `DEVICE_NOTES` | In `step_flows` but not in ConversationHandler states |
| 9 | CANCEL INCONSISTENCY | `radiology` uses `handle_smart_cancel_navigation`; `app_reschedule` uses `handle_cancel_navigation`; others use `handle_calendar_cancel` | 3 different cancel handlers across flows |
| 10 | SHARED STATE INTEGERS | `followup` + `periodic_followup` share all `FOLLOWUP_*` state integers | ConversationHandler cannot distinguish between the two flows |
| 11 | NO nav:back in TRANSLATOR states | `*_TRANSLATOR` states lack `nav:back` | Back-navigation blocked at translator selection for most flows |
| 12 | PHYSICAL_THERAPY missing | `PHYSICAL_THERAPY_DEVICES`, `PHYSICAL_THERAPY_NOTES` not in ConversationHandler | If these are ever needed, user hits dead state |

---

#### P3.5.7 — Modular Handler Connection Status

| Module | Connected? | How |
|---|---|---|
| `flows/new_consult.py` | ✅ ACTIVE | Imported at module level; handlers accessed via `globals()` in `_get_new_consult_handler` |
| `flows/followup.py` | ✅ ACTIVE | Imported at module level (`start_followup_flow`, `start_periodic_followup_flow`, handlers) |
| `flows/surgery_consult.py` | ✅ ACTIVE | Imported at module level; handlers via `globals()` |
| `flows/final_consult.py` | ✅ ACTIVE | Imported at module level; handlers via `globals()` |
| `flows/emergency.py` | ✅ ACTIVE | Inline in monolith; `_get_emergency_handler` via `globals()` |
| `flows/operation.py` | ✅ ACTIVE | Inline in monolith; `_get_operation_handler` via `globals()` |
| `flows/rehab.py` | ✅ ACTIVE | Handlers imported into monolith globals; via `_get_rehab_handler` |
| `flows/radiology.py` | ⚠ PARTIALLY ACTIVE | Handlers appear inline in monolith |
| `flows/admission.py` | ✅ ACTIVE | Via `_get_admission_handler` and `globals()` |
| `flows/discharge.py` | ✅ ACTIVE | Via `_get_discharge_handler` and `globals()` |
| `flows/radiation_therapy.py` | ⚠ FRAGILE ACTIVE | Live import in `_get_radiation_therapy_handler` — crash risk if import fails |
| `flows/shared.py` | ✅ PARTIALLY ACTIVE | `show_final_summary`, `get_confirm_state`, `save_report_to_database`, `handle_edit_before_save` active |
| `edit_handlers/before_publish/router.py` | ⚠ CONDITIONAL | Imported at module top; `None` fallback kills conversation on import failure |

---

#### P3.5.8 — P3.5 Summary: Runtime State Machine Truth

- **103 total states** registered in the active ConversationHandler
- **9 entry points** (5 are redundant regex variants for the same Arabic button text)
- **12 fallbacks** including a wildcard debug catcher as last fallback
- **6 duplicate R_ states** that mirror STATE_SELECT_* states — legacy aliases
- **4 string-keyed states** outside the integer state system
- **1 active wildcard fallback** consuming all unmatched callbacks in production
- **3 null-handler risk points**: radiation_therapy import, edit router import, `globals()` name misses
- **1 confirmed dead code**: `handle_emergency_date_time_text` at `EMERGENCY_DATE_TIME` (shadowed by earlier TEXT handler)
- **1 confirmed dead code**: `^save:` pattern in all `*_CONFIRM` states (shadowed by `^(save|publish|edit):`)
- **3 orphan navigation entries** in `SmartNavigationManager` with no ConversationHandler state

---

- **Decision:** INVESTIGATION ONLY — no changes made
- **Files Changed:** NONE

---

### ✅ COMPLETED: P3.6 — Edit Handlers Subsystem Audit (INVESTIGATION ONLY)

**Target:** `edit_handlers/before_publish/` — 17 files (1 router + 15 per-flow edit files + 1 `__init__.py`)

---

#### P3.6.1 — Edit Subsystem File Map

```
edit_handlers/
  __init__.py
  before_publish/
    __init__.py
    router.py                       ← central dispatch router (ACTIVE)
    new_consult_edit.py             ← new_consult flow edit (ACTIVE)
    followup_edit.py                ← legacy followup fallback (PARTIALLY ACTIVE)
    inpatient_followup_edit.py      ← followup w/ room (ACTIVE)
    periodic_followup_edit.py       ← periodic followup (ACTIVE)
    emergency_edit.py               ← emergency (ACTIVE)
    surgery_consult_edit.py         ← surgery_consult (ACTIVE)
    operation_edit.py               ← operation (ACTIVE)
    final_consult_edit.py           ← final_consult (ACTIVE)
    admission_edit.py               ← admission (ACTIVE)
    discharge_edit.py               ← discharge (ACTIVE)
    radiology_edit.py               ← radiology (ACTIVE)
    appointment_reschedule_edit.py  ← appointment_reschedule (ACTIVE)
    rehab_physical_edit.py          ← rehab_physical (ACTIVE)
    rehab_device_edit.py            ← rehab_device/device (ACTIVE)
    radiation_therapy_edit.py       ← radiation_therapy (ACTIVE)
```

**All 15 per-flow edit files are imported by router.py in a single try/except block at module load time.**
If ANY ONE of the 15 imports fails, ALL are set to `None`. This is an all-or-nothing import: one broken edit file disables ALL edit functionality across all flows.

---

#### P3.6.2 — Complete Edit Workflow (Two Parallel Systems)

There are **TWO edit systems** in production, operating in parallel with overlapping callback patterns:

**System A — NEW edit system (primary path, via router):**
- Trigger: `edit_field:flow_type:field_key` callback
- Handler: `route_edit_field_selection` → per-flow `handle_*_edit_field_selection`
- Context key written: `edit_field_key`, `edit_flow_type`
- After edit: calls `show_final_summary(message, context, flow_type)` from `flows/shared.py`
- Returns: `get_confirm_state(flow_type)` — back to CONFIRM state

**System B — OLD edit system (legacy path, via monolith):**
- Trigger: `draft_field:field_key` or `edit_draft:flow_type` or `edit_field_draft:field_key`
- Handler: `handle_edit_draft_report` → `show_edit_fields_menu` → `handle_edit_draft_field` → `handle_draft_field_input`
- Context key written: `editing_field`, `editing_field_original`, `draft_flow_type`, `draft_medical_action`
- After edit: calls `bot.handlers.user.user_reports_edit.get_editable_fields_by_action_type` (external module)
- Returns: inconsistent (varies by path)

**Both systems are registered in every `*_CONFIRM` state.** When a user presses Edit in the confirm screen, they may hit either system depending on which button was pressed. The `edit_field:` pattern routes to System A; `edit_draft:` and `draft_field:` route to System B.

---

#### P3.6.3 — Callback Protocol Map (Complete Edit Callback Inventory)

| Callback Pattern | Handler | System | Registered In |
|---|---|---|---|
| `^(save\|publish\|edit):` | `handle_final_confirm` | MONOLITH | All `*_CONFIRM` states |
| `^save:` | `handle_save_callback` | MONOLITH | All `*_CONFIRM` states (DEAD — shadowed) |
| `^edit_draft:` | `handle_edit_draft_report` | System B | All `*_CONFIRM` states |
| `^draft_field:` | `handle_edit_field_selection` | System A/B hybrid | All `*_CONFIRM` states |
| `^edit_field:` | `route_edit_field_selection` (via router) | System A | All `*_CONFIRM` states |
| `^finish_edit_draft:` | `handle_finish_edit_draft` | System B | All `*_CONFIRM` states |
| `^back_to_summary:` | `handle_back_to_summary` | Shared | All `*_CONFIRM` states |
| `^edit_field_draft:` | `handle_edit_draft_field` | System B | All `*_CONFIRM` states |
| `^draft_edit_translator:` | `handle_draft_edit_translator` | System B | All `*_CONFIRM` states |
| `^back_to_edit_fields` | `handle_back_to_edit_fields` | Shared | All `*_CONFIRM` states |
| TEXT | `route_edit_field_input` or `handle_draft_field_input` | System A fallback | All `*_CONFIRM` states |

**CRITICAL OBSERVATION — `draft_field:` callback routes to `handle_edit_field_selection` (line 8405) which is a HYBRID handler:**
It writes BOTH `edit_field_key`/`edit_flow_type` (System A keys) AND `editing_field` (System B key). Then it returns `confirm_state` and stays in CONFIRM state. The subsequent TEXT input will be handled by `route_edit_field_input` (System A) if it is registered first, OR `handle_draft_field_input` (System B) if router is None. See P3.5 finding: TEXT handler in CONFIRM states is `route_edit_field_input if route_edit_field_input else handle_draft_field_input`.

---

#### P3.6.4 — Router Architecture

`route_edit_field_selection` (router.py line 114):
- Receives `edit_field:flow_type:field_key` callback
- Extracts `flow_type` from `parts[1]`
- **SPECIAL CASE for `followup`**: reads `report_tmp["medical_action"]` to disambiguate between `inpatient_followup` and `periodic_followup`
- Dispatches to per-flow `handle_*_edit_field_selection`
- Returns the state returned by the per-flow handler (always `*_CONFIRM` integer)

`route_edit_field_input` (router.py line 304):
- Called on TEXT message in CONFIRM state
- Reads `context.user_data.get("edit_flow_type")` OR `report_tmp["current_flow"]` OR `report_tmp["flow_type"]`
- **FALLBACK CHAIN**: if flow_type not found, attempts to re-derive from `medical_action` using a local `action_to_flow` dict
- **CRITICAL — `action_to_flow` dict in router is DIFFERENT from monolith's `action_to_flow_type`:**
  - Router uses `"متابعة في الرقود"` → `"inpatient_followup"` (different from monolith's `"followup"`)
  - Router uses `"استشارة نهائية"` instead of `"استشارة أخيرة"` — this is a wrong Arabic string that won't match
  - Router uses `"علاج طبيعي"` instead of `"علاج طبيعي وإعادة تأهيل"` — won't match
  - Router uses `"أجهزة تعويضية"` — this action string doesn't exist in PREDEFINED_ACTIONS at all
- Dispatches to per-flow `handle_*_edit_field_input`

**⚠ CRITICAL — Router action_to_flow fallback dict has WRONG Arabic strings** that will NEVER match actual `medical_action` values in production. The fallback recovery is silently broken for `final_consult`, `rehab_physical`, `rehab_device`. Only `new_consult`, `emergency`, `operation`, `admission`, `discharge`, `radiology`, `appointment_reschedule` have correct Arabic strings.

---

#### P3.6.5 — Per-Flow Edit Handler Pattern

All 15 per-flow edit files follow the same pattern:

**`handle_*_edit_field_selection`:**
1. Parses `edit_field:flow_type:field_key` callback
2. Reads `report_tmp[field_key]` for current value
3. Writes `context.user_data["edit_field_key"] = field_key`
4. Writes `context.user_data["edit_flow_type"] = flow_type`
5. Shows edit prompt (text or calendar)
6. Returns `*_CONFIRM` state (stays in same CONFIRM state)

**`handle_*_edit_field_input`:**
1. Reads `context.user_data["edit_field_key"]` and `context.user_data["edit_flow_type"]`
2. Validates `edit_flow_type == expected_flow` (returns silently if wrong flow)
3. Saves `report_tmp[field_key] = text`
4. Saves dual-key copies for compatibility (`complaint` AND `complaint_text`, `decision` AND `doctor_decision`)
5. Clears `edit_field_key` (but NOT `edit_flow_type`)
6. Calls `show_final_summary(update.message, context, flow_type)` from `flows/shared.py`
7. Returns `get_confirm_state(flow_type)`

**IMPORT DEPENDENCIES of every per-flow edit file:**
```python
from bot.handlers.user.user_reports_add_new_system.flows.shared import (
    get_confirm_state,
    show_final_summary,
    *_CONFIRM  # the confirm state constant
)
```
Every edit handler imports back into `flows/shared.py`. This creates a dependency cycle path:
`monolith` → `router.py` → `new_consult_edit.py` → `flows/shared.py` → (back to monolith at runtime)

The `new_consult_edit.py` also imports:
```python
from bot.handlers.user.user_reports_add_new_system.flows.new_consult import _render_followup_calendar
```
Used for calendar-based editing of `followup_date`. If this import fails, falls back to text input for dates.

---

#### P3.6.6 — handle_final_confirm: The Three-Way Edit Dispatch

`handle_final_confirm` at monolith line 10006 handles pattern `^(save|publish|edit):`:

| action | What happens |
|---|---|
| `publish` | Imports `flows/shared.py.save_report_to_database`, calls it, returns `ConversationHandler.END` |
| `save` | Imports `flows/shared.py.show_final_summary`, re-renders summary, returns `confirm_state` |
| `edit` | Imports `flows/shared.py.handle_edit_before_save`, calls it, returns `edit_state` or `confirm_state` |

**flow_type extraction from callback:**
- Format: `publish:flow_type`, `save:flow_type`, `edit:flow_type`
- Extracted as `parts[1]`
- **OVERRIDE LOGIC** (lines 10044–10058): if callback has `"followup"` but `report_tmp["current_flow"]` is `"periodic_followup"` or `"inpatient_followup"`, `current_flow` wins
- `"rehab_device"` is normalized to `"device"` before use
- Unknown flow_type falls back to `current_flow` from report_tmp

**NEW `inpatient_followup` flow_type exists at edit layer but NOT in monolith's original dispatch:**
- `action_to_flow_type` mapping (P3.4) maps `"متابعة في الرقود"` → `"followup"`
- But `handle_final_confirm` valid_flow_types list includes `"inpatient_followup"` (line 10033)
- And router uses `"inpatient_followup"` as the edit key for that flow
- This means: flow is CREATED as `"followup"` but EDITED as `"inpatient_followup"`
- The override logic at line 10050 handles this: if `current_flow == "inpatient_followup"` overrides `flow_type == "followup"`

---

#### P3.6.7 — handle_edit_before_save (flows/shared.py)

Called by `handle_final_confirm` for `action == "edit"`. This is the entry point to the edit field menu.

1. Resolves `flow_type` from callback, `current_flow`, or falls back to `stored_flow_type`
2. Special override: `"followup"` → `"periodic_followup"` or `"inpatient_followup"` if `current_flow` says so
3. Calls `show_edit_fields_menu(query, context, flow_type)` which:
   - Has a per-flow `editable_fields` dict defining which fields are editable per flow
   - Generates buttons with `edit_field:flow_type:field_key` callbacks
   - Returns `confirm_state` (stays in CONFIRM state)
4. All edit buttons trigger System A (router path) via `^edit_field:` pattern

---

#### P3.6.8 — context.user_data Keys Written by Edit Subsystem

| Key | Set By | Read By | Purpose |
|---|---|---|---|
| `edit_field_key` | `handle_*_edit_field_selection` | `handle_*_edit_field_input` | Which field is being edited |
| `edit_flow_type` | `handle_*_edit_field_selection`, router input | `route_edit_field_input`, `handle_*_edit_field_input` | Which flow the edit is for |
| `editing_field` | `handle_edit_draft_field` (System B) | `handle_draft_field_input` (System B) | Old system field key |
| `editing_field_original` | `handle_edit_draft_field` (System B) | `handle_draft_field_input` (System B) | Old system original key |
| `draft_flow_type` | System B path | `handle_draft_field_input` | Old system flow type |
| `draft_medical_action` | System B path | `handle_draft_field_input` | Old system medical action |

**COLLISION RISK:** Both `edit_field_key` (System A) and `editing_field` (System B) may be set simultaneously since `handle_edit_field_selection` (the `draft_field:` hybrid handler) writes BOTH. If the user switches between edit paths mid-session, stale keys from one system may mislead the other system's input handler.

---

#### P3.6.9 — Critical Failure Points

| # | Failure Point | Trigger | Consequence |
|---|---|---|---|
| 1 | ALL edit imports fail at once | Any one of 15 edit files has a syntax/import error | ALL edit buttons in ALL flows return `ConversationHandler.END` — silent conversation kill |
| 2 | Router `route_edit_field_selection` = `None` | Import failure | `edit_field:` button triggers lambda returning `ConversationHandler.END` (per P3.5 finding) |
| 3 | Router `action_to_flow` has wrong Arabic strings | `final_consult`, `rehab_physical`, `rehab_device` edits | `flow_type = None` → `ConversationHandler.END` if edit_flow_type also missing |
| 4 | `show_final_summary` import fails | `flows/shared.py` import error in edit file | Edit saves but no summary shown; falls back to "تم الحفظ" message |
| 5 | `_render_followup_calendar` import fails | `flows/new_consult.py` import error in `new_consult_edit.py` | Calendar edit falls back to text input for dates |
| 6 | `edit_flow_type` not set / stale | Mid-session state corruption | `route_edit_field_input` attempts medical_action fallback (broken for 3 flows) → `ConversationHandler.END` |
| 7 | `inpatient_followup` flow_type not in `get_confirm_state` | `get_confirm_state("inpatient_followup")` | Returns wrong CONFIRM state or None |

---

#### P3.6.10 — Modular Dependency Graph (Edit Subsystem)

```
monolith.handle_final_confirm
    ↓ (action=edit)
flows/shared.handle_edit_before_save
    ↓
flows/shared.show_edit_fields_menu
    → generates edit_field:flow_type:field_key buttons
        ↓ (user presses button)
router.route_edit_field_selection
    → per-flow: edit_handlers/before_publish/*_edit.py
        → imports: flows/shared.get_confirm_state
        → imports: flows/shared.show_final_summary
        → imports: flows/new_consult._render_followup_calendar (new_consult only)
        → saves to report_tmp
        → calls show_final_summary
        → returns confirm_state
```

All edit handlers call BACK into `flows/shared.py` — creating a circular dependency at runtime (though not at import time since imports are done at module load, not inside functions).

---

#### P3.6.11 — Safe Future Modularization Boundaries

Based on P3.6 investigation:

1. **Router is already the clean boundary.** `router.py` is the single integration point between ConversationHandler and the per-flow edit modules. Any future refactor should maintain this boundary.

2. **Per-flow edit files are fully isolated** — each handles exactly one flow's fields. They have no cross-flow dependencies. Safe to modify one without affecting others, EXCEPT the all-or-nothing import in router.py.

3. **The all-or-nothing import in router.py is the main fragility.** Fix: import each edit module separately with individual try/except blocks instead of a single block covering all 15 imports.

4. **System B (old edit path) is vestigial.** `draft_field:`, `edit_draft:`, `edit_field_draft:` callbacks still work but go through the old `handle_draft_field_input` which reads from `draft_flow_type`/`draft_medical_action` (not `edit_flow_type`/`edit_field_key`). This creates two parallel context key systems that must stay in sync.

5. **`inpatient_followup` is a pure edit-layer concept** — it doesn't exist as a `current_flow` value in the main dispatch (P3.4), only appears in the edit router and handle_final_confirm. Any future normalization must bridge this gap.

---

- **Decision:** INVESTIGATION ONLY — no changes made
- **Files Changed:** NONE

---

### ✅ COMPLETED: P3.7 — Phase 3 Runtime Truth Map Synthesis

---

## ════════════════════════════════════════
## P3.7 — COMPLETE PRODUCTION RUNTIME ARCHITECTURE MODEL
## ════════════════════════════════════════

---

### 1. RUNTIME ARCHITECTURE MAP

#### 1.1 — Active Production Layers (top to bottom)

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 0 — Telegram PTB                                      │
│  ConversationHandler (103 states, 9 entry points, 12 fb)    │
│  per_message=False, per_chat=True, per_user=True            │
│  allow_reentry=True                                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  LAYER 1 — Monolith Dispatcher                              │
│  user_reports_add_new_system.py (12,800+ lines)             │
│  ├─ Entry: start_report                                     │
│  ├─ Common stages: date, patient, hospital, dept,           │
│  │                 subdept, doctor, action_type             │
│  ├─ Flow dispatch: _get_action_routing()                    │
│  │   → 13 action types → 13 start_*_flow functions         │
│  ├─ Medical gate: MEDICAL_REPORT_ASK/UPLOAD/REASON          │
│  ├─ Translator selection: show_translator_selection()       │
│  ├─ Final confirm: handle_final_confirm()                   │
│  └─ Navigation: SmartNavigationManager                      │
└──────────────────────────┬──────────────────────────────────┘
                           │ imports/calls
         ┌─────────────────┼──────────────────────┐
         ▼                 ▼                      ▼
┌────────────────┐ ┌───────────────┐ ┌─────────────────────┐
│  LAYER 2A      │ │  LAYER 2B     │ │  LAYER 2C           │
│  flows/*.py    │ │  services/    │ │  edit_handlers/     │
│  (13 modules)  │ │  (4 services) │ │  before_publish/    │
│  ACTIVE paths: │ │  ACTIVE:      │ │  (15 flow editors)  │
│  followup.py   │ │  hospitals_   │ │  via router.py      │
│  new_consult.py│ │  service      │ │                     │
│  shared.py     │ │  translators_ │ │                     │
│  radiation_    │ │  service      │ │                     │
│  therapy.py    │ │  doctors_     │ │                     │
│                │ │  service      │ │                     │
│                │ │  doctors_     │ │                     │
│                │ │  smart_search │ │                     │
└────────────────┘ └───────────────┘ └─────────────────────┘
         │                 │                      │
         └─────────────────▼──────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  LAYER 3 — Data Layer                                       │
│  db/session.py + db/models.py (SQLAlchemy/SQLite)           │
│  data/doctors_unified.json (button-list doctors)            │
│  data/doctors_organized.json (inline search doctors)        │
│  data/hospitals_order.txt (custom ordering)                 │
└─────────────────────────────────────────────────────────────┘
```

#### 1.2 — Active vs Shadow System Inventory

| Component | Status | Active Path |
|---|---|---|
| `user_reports_add_new_system.py` (monolith) | ✅ ACTIVE RUNTIME | ConversationHandler root |
| `flows/shared.py` | ✅ PARTIALLY ACTIVE | `save_report_to_database`, `show_final_summary`, `get_confirm_state`, `handle_edit_before_save` |
| `flows/followup.py` | ✅ ACTIVE | `start_followup_flow`, `start_periodic_followup_flow`, all followup handlers |
| `flows/new_consult.py` | ✅ ACTIVE | All new_consult handlers, `_render_followup_calendar` |
| `flows/radiation_therapy.py` | ✅ ACTIVE (fragile) | All radiation therapy handlers — live import, crash risk |
| Other `flows/*.py` (9 files) | ✅ ACTIVE via globals() | Handlers imported into monolith global namespace |
| `edit_handlers/before_publish/router.py` | ✅ ACTIVE | Dispatches all `edit_field:` callbacks |
| `edit_handlers/before_publish/*_edit.py` (15 files) | ✅ ACTIVE | Per-flow edit input/selection |
| `flows/shared.py` — `show_translator_selection()` | ❌ SHADOW | Not called by active ConversationHandler |
| `flows/shared.py` — `render_translator_selection()` | ❌ SHADOW | ID-bound translator system, not wired |
| `user_reports_add_helpers.py` edit system (System B) | ⚠ LEGACY ACTIVE | `draft_field:` path still wired |
| `user_reports_add_new_system/` other modules | ❌ SHADOW | `patient_handlers.py`, `utils.py`, `states.py` not used by ConversationHandler |
| Inline query system (`user_patient_search_inline.py`) | ✅ ACTIVE | Registered outside ConversationHandler |
| `services/doctors_smart_search.py` | ✅ ACTIVE | Inline doctor search only |
| `services/doctors_service.py` | ✅ ACTIVE | Button-list doctor selection |
| `services/hospitals_service.py` | ✅ ACTIVE | Hospital list + ordering |
| `services/translators_service.py` | ✅ ACTIVE | `get_all_translator_names()`, `resolve_translator_for_report()` |

#### 1.3 — Compatibility Bridges

| Bridge | Purpose | Risk if Removed |
|---|---|---|
| `R_DATE`/`R_PATIENT`/`R_DEPARTMENT`/`R_SUBDEPARTMENT`/`R_DOCTOR`/`R_ACTION_TYPE` duplicate states | Keep in-flight sessions alive across deploys | Remove → mid-conversation sessions break after deploy |
| `handle_edit_field_selection` writes BOTH System A and B keys | Allows `draft_field:` callbacks to feed System A input handler | Remove → old-style edit buttons break |
| `action_to_flow_type` + `start_*_flow` re-override of `medical_action` | Defensive double-save prevents state corruption on independent calls | Remove → edge-case state gaps |
| `debug_all_callbacks` wildcard fallback | Prevents unhandled callback errors crashing the conversation | Remove → unmatched callbacks cause ptb to silently drop the update |
| `handle_draft_field_input` reads `draft_flow_type` from System B keys | System B still functional if `edit_flow_type` missing | Remove → System B edit path broken |

#### 1.4 — Fallback Chains

**Hospital data chain:**
`_get_hospitals_from_database_or_predefined` → DB Hospital table → `_apply_custom_order(hospitals_order.txt)` → FALLBACK: `doctors_unified.json`

**Translator name chain:**
`load_translator_names()` → `translators_service.get_all_translator_names()` → DB TranslatorDirectory → `priority_order` sort → FALLBACK: hardcoded 19-name list

**Doctor button list chain:**
`_build_doctors_keyboard` → `doctors_service.get_doctors_for_selection(hospital, dept)` → `doctors_unified.json` → FALLBACK: empty list (no doctors shown)

**Doctor inline search chain:**
`doctor_inline_query_handler` → `doctors_smart_search.search_doctors()` → `doctors_organized.json` → FALLBACK: `doctors_database.json`

**Edit router chain:**
`route_edit_field_selection` → per-flow handler → FALLBACK: `ConversationHandler.END` (silent kill)

**Edit field input chain:**
`route_edit_field_input` → reads `edit_flow_type` → FALLBACK: read `current_flow` → FALLBACK: derive from `medical_action` (broken for 3 flows) → FALLBACK: `ConversationHandler.END`

---

### 2. RUNTIME CONTRACT REGISTRY

#### 2.1 — Callback Protocol Contracts (INDEX-BOUND — ordering critical)

| Callback Format | Ordering Sensitive | Source | Bound To |
|---|---|---|---|
| `hospital_idx:{i}` | ✅ YES | `_build_hospitals_keyboard` | DB Hospital order + `hospitals_order.txt` |
| `dept_idx:{i}` | ✅ YES | `_build_departments_keyboard` | `PREDEFINED_DEPARTMENTS` list order |
| `subdept_idx:{i}` | ✅ YES | `show_subdepartment_options` | `PREDEFINED_DEPARTMENTS[main_dept]` list order |
| `doctor_idx:{i}` | ✅ YES | `_build_doctors_keyboard` | `doctors_service` return order + `_doctors_list` cache |
| `action_idx:{i}` | ✅ YES | `_build_action_type_keyboard` | `PREDEFINED_ACTIONS` list order |
| `simple_translator:{flow}:{real_index}` | ✅ YES | `show_translator_selection` | `load_translator_names()` order + priority_order |

#### 2.2 — Callback Protocol Contracts (ID-BOUND — ordering safe)

| Callback Format | Source | Bound To |
|---|---|---|
| `patient_idx:{patient_id}` | patient selection | DB Patient.id — actual PK |
| `edit_field:{flow_type}:{field_key}` | `show_edit_fields_menu` | flow_type string + field key name |
| `save:{flow_type}` | confirm screen | flow_type string |
| `publish:{flow_type}` | confirm screen | flow_type string |
| `edit:{flow_type}` | confirm screen | flow_type string |
| `medrep:(yes\|no\|skip)` | medical gate | fixed strings |
| `nav:back` / `nav:cancel` | navigation | fixed strings |
| `draft_field:{field_key}` | System B | field key name |

#### 2.3 — report_tmp Contract (complete key inventory)

| Key | Type | Set By | Read By | Notes |
|---|---|---|---|---|
| `medical_action` | Arabic string | `handle_action_type_choice`, `start_*_flow` | back-nav, edit router, `save_report_to_database` | **Primary flow identity** |
| `current_flow` | flow_type string | `handle_action_type_choice`, `start_*_flow` | `handle_final_confirm`, edit router, translator selection | **Secondary flow identity** |
| `action_type` | Arabic string | `handle_action_type_choice` | duplicate of `medical_action` | redundant |
| `hospital_name` | string | `handle_hospital_selection` | doctor filter, summary, save | |
| `department_name` | bilingual string `"AR \| EN"` | `handle_department_selection` | subdept lookup, doctor filter, summary, save | **triple-purpose contract** |
| `subdepartment_name` | string | `handle_subdepartment_choice` | summary, save | |
| `doctor_name` | string | `handle_doctor_btn_selection` | summary, save | |
| `patient_name` | string | `handle_patient_selection` | summary, save | |
| `patient_id` | int (DB PK) | `handle_patient_selection` | save | |
| `report_date` | date string | date selection | summary, save | |
| `report_time` | time string | time selection | summary, save | optional |
| `translator_name` | string | `handle_simple_translator_choice` | summary, `resolve_translator_for_report` | |
| `translator_id` | None | `handle_simple_translator_choice` | `save_report_to_database` → `resolve_translator_for_report` | **always None at set time** |
| `_medical_report_done` | bool | medical gate handlers | translator gate check | |
| `complaint` / `complaint_text` | string | flow handlers, edit | save (aliased) | dual-key |
| `diagnosis` | string | flow handlers, edit | save | |
| `decision` / `doctor_decision` | string | flow handlers, edit | save (aliased) | dual-key |
| `tests` | string | flow handlers, edit | save | |
| `followup_date` | string | date selection / edit | summary, save | |
| `followup_reason` | string | flow handlers, edit | summary, save | |
| `room_number` | string | followup handler | summary, save, back-nav disambiguation | |
| `status` | string | emergency flow | save | |
| `admission_reason` | string | admission flow | save | |
| `discharge_type` | string | discharge flow | dynamic back-nav | |

#### 2.4 — Text-Driven Routing Contracts

| Arabic String Value | Used As | If Changed |
|---|---|---|
| `"متابعة في الرقود"` | back-nav flow detection, edit router dispatch | back-nav fires wrong flow |
| `"مراجعة / عودة دورية"` | back-nav flow detection, edit router dispatch | back-nav fires wrong flow |
| `"استشارة جديدة"` | back-nav flow detection | back-nav fires wrong flow |
| `"طوارئ"` | back-nav flow detection | back-nav fires wrong flow |
| Department name `"AR \| EN"` | subdept lookup key, doctor filter argument | subdept/doctor selection broken |

#### 2.5 — Deferred Resolution Contracts

| What | When Set | When Resolved | How |
|---|---|---|---|
| `translator_id = None` | At translator button press | At `save_report_to_database` | `resolve_translator_for_report(session, translator_name)` |
| Hospital name → Hospital DB record | Never explicitly — used only as string | At save time | `report_tmp["hospital_name"]` saved as plain string |
| `department_name` bilingual | At button press (full string) | At doctor filter time (passed as-is) | no normalization |

#### 2.6 — Ordering Dependency Contracts

| System | Ordering Source | Risk |
|---|---|---|
| Hospital list | DB ORDER BY name + `hospitals_order.txt` override | Any DB reorder or file edit corrupts `hospital_idx:` callbacks |
| Department list | `PREDEFINED_DEPARTMENTS` dict iteration order | Python ≥ 3.7 insertion order maintained; changing order corrupts `dept_idx:` |
| Translator list | `priority_order` list in `translators_service` + sorted remainder | Adding/moving priority entries changes `real_index` in `simple_translator:` callbacks |
| Action type list | `PREDEFINED_ACTIONS` literal list in `user_reports_add_helpers.py` | Any reorder corrupts `action_idx:` callbacks |
| Doctor list | `doctors_service` return order (from JSON) + `_doctors_list` cache | Cache populated at render time; stale cache = wrong selection |

---

### 3. FRAGILITY HOTSPOT MAP

#### 3.1 — SEVERITY: CRITICAL (conversation kill or wrong data saved)

| ID | Risk | Location | Trigger | Consequence |
|---|---|---|---|---|
| F-01 | All-or-nothing edit import | `router.py` top-level try/except | Any one of 15 edit files fails | ALL edit buttons → `ConversationHandler.END` silently |
| F-02 | `route_edit_field_selection = None` | monolith line 27–35 | `router.py` import failure | `edit_field:` → lambda returning `END` — user loses entire conversation |
| F-03 | `start_radiation_therapy_flow = None` | `_get_action_routing()` | `flows/radiation_therapy.py` import failure | `TypeError: 'NoneType' is not callable` on flow start |
| F-04 | `_get_radiation_therapy_handler()` returns `None` | monolith line 10934 | Import failure | Every radiation_therapy ConversationHandler state has `None` handlers → `TypeError` |
| F-05 | `translator_id = None` saved to DB | `handle_simple_translator_choice` line 12728 | Normal operation | Relies entirely on `resolve_translator_for_report` — if that fails, translator FK is null |
| F-06 | `EMERGENCY_DATE_TIME` duplicate TEXT handler | monolith line 11649+11652 | Any text input in that state | `handle_emergency_date_time_text` is dead code; `handle_followup_date_text_input` runs instead |
| F-07 | Router fallback `action_to_flow` wrong strings | `router.py` line 326–340 | `edit_flow_type` missing for `final_consult`, `rehab_physical`, `rehab_device` | `flow_type = None` → `ConversationHandler.END` |
| F-08 | `save:` pattern dead code in all CONFIRM states | All `*_CONFIRM` states | Normal operation | `handle_save_callback` never fires; first `^(save\|publish\|edit):` handler wins |

#### 3.2 — SEVERITY: HIGH (wrong routing, state corruption, feature breakage)

| ID | Risk | Location | Trigger | Consequence |
|---|---|---|---|---|
| F-09 | `rehab_physical` nav map key mismatch | `SmartNavigationManager.step_flows` | Back button in rehab flow | Falls back to `STATE_SELECT_ACTION_TYPE` instead of correct previous step |
| F-10 | `appointment_reschedule` nav map key mismatch | `SmartNavigationManager.step_flows` | Back button in reschedule flow | Same fallback to `STATE_SELECT_ACTION_TYPE` |
| F-11 | `radiation_therapy` has no nav map entry | `SmartNavigationManager.step_flows` | Back button in radiation therapy | Falls back to `STATE_SELECT_ACTION_TYPE` always |
| F-12 | `inpatient_followup` phantom flow_type | edit router + `handle_final_confirm` | Edit in followup flows | If override chain fails, wrong edit module selected |
| F-13 | `PHYSICAL_THERAPY_DEVICES`, `PHYSICAL_THERAPY_NOTES`, `DEVICE_NOTES` in nav map but not ConversationHandler | `SmartNavigationManager` | Back-nav reaches these steps | `execute_smart_state_action` called for state with no handler — undefined behavior |
| F-14 | Hospital INDEX callbacks from stale messages | All hospital selection | User presses old button after hospital list changes | Wrong hospital selected silently |
| F-15 | Translator INDEX callbacks from stale messages | All translator selection | Translator list changes between render and press | Wrong translator name stored |

#### 3.3 — SEVERITY: MEDIUM (latent bugs, inconsistencies)

| ID | Risk | Location | Notes |
|---|---|---|---|
| F-16 | `debug_all_callbacks` wildcard in production | fallbacks | Silently consumes all unmatched callbacks; stack trace printed to console |
| F-17 | System B (`draft_field:`) and System A (`edit_field:`) parallel edit paths | All CONFIRM states | Conflicting user_data keys; possible stale key corruption |
| F-18 | `nav:back` in BOTH state handlers AND fallbacks | Every flow | Masks state tracking bugs; back-nav always fires even for malformed states |
| F-19 | 5 overlapping entry point regex patterns | entry_points | Redundant but harmless; wasteful pattern matching |
| F-20 | `department_name` as triple contract | `_build_departments_keyboard` | Format change breaks subdept lookup, doctor filter, and display simultaneously |
| F-21 | Cancel handler inconsistency (3 different handlers) | `radiology`, `app_reschedule`, others | `handle_smart_cancel_navigation` vs `handle_cancel_navigation` vs `handle_calendar_cancel` — different behavior |

---

### 4. MODULARIZATION READINESS MAP

#### 4.1 — SAFE TO ISOLATE (no runtime contract changes needed)

| Component | Why Safe | Notes |
|---|---|---|
| `services/hospitals_service.py` | Already isolated; monolith calls via clean function API | Only risk: `hospitals_order.txt` is a side-channel dependency |
| `services/translators_service.py` | Already isolated; clean function API; `resolve_translator_for_report` is the only cross-cutting concern | Ordering must not change |
| `services/doctors_service.py` | Already isolated; used only by `_build_doctors_keyboard` | Return format `{name, hospital, department}` is the contract |
| `services/doctors_smart_search.py` | Already isolated; used only by `doctor_inline_query_handler` | `specialty_type` parameter is dead code |
| `edit_handlers/before_publish/*_edit.py` (individual files) | Per-flow isolation already exists; router is the clean boundary | Can be modified one at a time safely |
| `flows/new_consult.py` (handlers only) | Handlers already wired via `globals()` in monolith | `_render_followup_calendar` is a shared dependency of `new_consult_edit.py` |
| `flows/followup.py` (handlers only) | Already wired; `start_followup_flow` and `start_periodic_followup_flow` are imports | |

#### 4.2 — NEEDS WRAPPERS (safe after thin adapter layer)

| Component | Why Needs Wrappers | Recommended Wrapper |
|---|---|---|
| `flows/shared.py` — `save_report_to_database` | Called by monolith via live import; imports `translators_service` at call time | Wrap with error boundary; add explicit `translator_id` fallback |
| `flows/shared.py` — `show_final_summary` | Called by monolith AND all edit handlers; must accept `message` or `query` | Already has try/except; add type-checking wrapper |
| `edit_handlers/before_publish/router.py` | All-or-nothing import is fragile | Refactor to 15 individual try/except blocks |
| `SmartNavigationManager.step_flows` | `rehab_physical`/`appointment_reschedule`/`radiation_therapy` key mismatches | Add alias resolution wrapper in `get_previous_step()` |
| Translator selection | 3 parallel systems; only one active | Wrapper that normalizes to active System A protocol |

#### 4.3 — NEEDS CONTRACT MIGRATION (significant work, high risk)

| Component | Why Blocked | Required Migration |
|---|---|---|
| Hospital/dept/subdept/doctor selection | All INDEX-bound; ordering is the implicit contract | Must migrate to ID-bound callbacks BEFORE changing ordering — requires coordinated deploy |
| `PREDEFINED_ACTIONS` order | INDEX-bound | Migrate to name-based callbacks (`action_name:استشارة_جديدة`) |
| `report_tmp["department_name"]` bilingual format | Triple-purpose string used as dict key, doctor filter, and display | Separate into 3 distinct fields: `dept_key`, `dept_display_ar`, `dept_display_en` |
| `medical_action` Arabic string routing | Hardcoded string comparison in back-nav | Add a `flow_type` enum and use it instead; keep `medical_action` as display-only |
| System B edit path (`draft_field:`) | Parallel to System A; conflicting user_data keys | Deprecate after confirming System A covers all fields |

#### 4.4 — MUST REMAIN MONOLITHIC TEMPORARILY

| Component | Why Cannot Move Yet | Condition for Safe Move |
|---|---|---|
| `handle_smart_back_navigation` + `SmartNavigationManager` | Tightly coupled to all 103 ConversationHandler states; uses integer state constants defined in monolith | After full state constant extraction into a standalone `states.py` used by all files |
| `handle_final_confirm` | Integrates with `save_report_to_database`, `show_final_summary`, `handle_edit_before_save`; flow_type override logic is fragile | After `inpatient_followup` ghost type is normalized into main dispatch |
| `show_translator_selection` (monolith version, System A active) | All 11 translator states in ConversationHandler use callbacks from this render; index ordering is baked in | After migrating translator callbacks to ID-bound format |
| `_get_action_routing()` | Calls `start_*_flow` functions, some inline, some imported; single failure point for flow dispatch | After all `start_*_flow` functions are confirmed importable |
| The full ConversationHandler registration block | Handler order matters (first-match); state integer values are global constants; any change risks breaking all sessions | After all state constants extracted and session migration strategy defined |

---

### 5. MIGRATION STRATEGY PROPOSAL

#### 5.1 — Safest Migration Order (phases)

**Phase A — Fix fragility hotspots (no behavioral change, low risk)**
1. Fix `router.py`: change single try/except to 15 individual try/excepts (F-01)
2. Fix `SmartNavigationManager`: add key aliases `"rehab_physical"→"rehab"`, `"appointment_reschedule"→"app_reschedule"`, add `"radiation_therapy"` entry (F-09, F-10, F-11)
3. Remove dead `^save:` pattern from all CONFIRM states (F-08) — or leave, harmless
4. Fix `EMERGENCY_DATE_TIME` duplicate TEXT handlers (F-06) — remove second handler

**Phase B — Contract normalization (medium risk, requires coordinated deploy)**
5. Extract all state integer constants into a shared `states_registry.py` imported by all files
6. Migrate `PREDEFINED_ACTIONS` callbacks from `action_idx:{i}` to `action_name:{key}` (requires new ConversationHandler pattern update)
7. Normalize `inpatient_followup` — add it as a real `current_flow` value in `action_to_flow_type`
8. Deprecate System B edit path (`draft_field:`) by removing callbacks from CONFIRM states

**Phase C — Modular activation (high risk, requires full test cycle)**
9. Activate the ID-bound translator system from `flows/shared.py` shadow (replaces INDEX-bound System A)
10. Migrate hospital/dept/subdept/doctor callbacks to ID-bound format
11. Extract `handle_final_confirm` into `flows/shared.py` (already has save/show_final_summary there)
12. Activate `SmartNavigationManager` from a standalone module (currently inline in monolith)

#### 5.2 — Safest Runtime Isolation Order

Isolate in this order (each step fully tested before next):
1. Services layer (already isolated — just verify)
2. Edit handlers (already modular — fix router.py fragility)
3. Individual flow handlers (new_consult, followup, emergency... one at a time)
4. Navigation manager
5. Translator selection
6. Final confirm + save pipeline
7. Common selection stages (date, patient, hospital, dept, doctor)
8. ConversationHandler registration block (last — highest risk)

#### 5.3 — Recommended Wrapper Strategy

- **Error boundary wrappers** for all `flows/shared.py` function calls from monolith (prevent import-failure kills)
- **Alias wrappers** for flow_type normalization (`"inpatient_followup"` ↔ `"followup"`, `"rehab_device"` ↔ `"device"`)
- **ID-resolution wrappers** for all index-bound callbacks before contract migration (log resolved vs expected)
- **Import guard decorators** for all `_get_*_handler()` functions — raise explicit error with function name if returns `None`

#### 5.4 — Recommended Compatibility Layer Strategy

- Keep R_ duplicate states until all users are confirmed on current session
- Keep System B edit path (`draft_field:`) until System A confirmed to cover all field types
- Keep monolith's `load_translator_names()` wrapper around `translators_service` even after service isolation
- Keep `medical_action` Arabic string in `report_tmp` even after migrating routing to flow_type enum (for backward compatibility with saved drafts)

#### 5.5 — Recommended Contract-Preservation Strategy

During any migration step:
1. Never change callback_data format without parallel processing period (accept both old and new format)
2. Never reorder any list that feeds INDEX-bound callbacks without first migrating to ID-bound
3. Never rename `report_tmp` keys without running both old and new key in parallel
4. Never change Arabic action/medical_action strings — they ARE the contracts
5. Always deploy state constant changes in a migration that handles both old integer and new value

---

### 6. UNIFIED COMPONENT OPPORTUNITIES

#### 6.1 — Translator Selector

**Current state:** 3 parallel systems
- System A (active): `simple_translator:{flow}:{real_index}` — INDEX-bound — monolith
- System B (shadow): `translator_idx:{flow}:{id}` — ID-bound — `flows/shared.py`
- System C (shadow): pagination of System B

**Can be unified safely?** YES — after callback migration
- Blocker: `simple_translator:` callbacks in active Telegram messages become stale on changeover
- Strategy: deploy System B alongside System A, accept both callback formats for one deploy window, then drop System A
- Benefit: eliminates ordering sensitivity, eliminates `FIRST_PAGE_COUNT` dual-definition sync risk

**Adapters required:** callback format adapter in `handle_simple_translator_choice` to also handle `translator_idx:` format

#### 6.2 — Date/Time Selector

**Current state:** monolith-inline calendar rendering functions shared across flows
- `handle_new_consult_followup_calendar_nav` / `handle_new_consult_followup_calendar_day` used by surgery_consult, followup, emergency, operation, admission, discharge, PHYSICAL_THERAPY, DEVICE, APP_RESCHEDULE
- `handle_new_consult_followup_time_hour` / `handle_new_consult_followup_time_minute` similarly shared

**Can be unified safely?** YES — these functions are ALREADY unified implicitly (multiple states share the same handler)
- No action needed for unification — it already exists
- Risk: renaming or moving these functions breaks all 8 dependent flows simultaneously
- Strategy: leave in place; extract to `utils/calendar.py` in Phase C only

#### 6.3 — Navigation Controls

**Current state:**
- `nav:back` → `handle_smart_back_navigation` (registered per-state + fallback)
- `nav:cancel` → 3 different handlers: `handle_calendar_cancel`, `handle_cancel_navigation`, `handle_smart_cancel_navigation`
- `handle_smart_back_navigation` depends on `SmartNavigationManager` which is inline in monolith

**Can be unified safely?** PARTIALLY
- `nav:back` is already effectively unified (single handler fires for all)
- `nav:cancel` inconsistency: CAN be unified — all 3 handlers do the same thing (end conversation + message)
- **Blocker:** `SmartNavigationManager` contains all flow state maps; cannot move without state constants being extracted first
- Strategy: Phase A — normalize cancel handlers; Phase C — extract navigation manager

#### 6.4 — Confirmation Screens

**Current state:** 11 separate CONFIRM states all showing the same UI pattern via `show_final_summary()` from `flows/shared.py`
- `show_final_summary` is already a unified function
- Each CONFIRM state has identical handler lists (10 handlers each)

**Can be unified safely?** YES — the display is already unified
- The 11 separate CONFIRM states exist only to preserve ConversationHandler state identity (so `get_confirm_state(flow_type)` returns the right state for back-navigation)
- These CANNOT be merged into one state without breaking back-navigation (state machine would lose flow identity)
- Can reduce code duplication by building CONFIRM state handler lists from a shared factory function

#### 6.5 — Pagination Systems

**Current state:** Multiple independent pagination systems
- Hospital pagination: `hospital_page:` / `hosp_page:` (dual callback pattern)
- Department pagination: `dept_page:`
- Subdept pagination: `subdept_page:`
- Doctor pagination: `doctor_page:`
- Translator pagination: `translator_page:` (System A) — page-relative index
- Patient pagination: `user_patient_page:` — in fallbacks only

**Can be unified safely?** NO — each pagination system has different state contracts
- Translator pagination is entangled with `FIRST_PAGE_COUNT` constant (2 places must stay in sync)
- Hospital pagination has dual callback pattern (`hospital_page:` AND `hosp_page:`) — legacy compatibility
- Patient pagination is in fallbacks (outside state handlers) — different routing context
- Strategy: fix dual hospital callback as Phase A cleanup; leave others until ID-bound migration (Phase B)

---

### 7. PHASE 3 COMPLETE — SUMMARY VERDICT

**System Health:** Functional but fragile. Production works today because all the active paths are established and tested. Fragility is concentrated in import chains and index-bound callback ordering.

**Migration Risk Level:** 🔴 HIGH without Phase A fixes; 🟡 MEDIUM after Phase A; 🟢 LOW after Phase B

**Biggest immediate risks (production impact if triggered today):**
1. Any one of 15 edit files having a syntax error → ALL edit disabled
2. `flows/radiation_therapy.py` import failure → entire radiation therapy flow crashes
3. `followup` translator list reordering → wrong translators silently selected

**Most valuable immediate fix (Phase A, zero behavioral change):**
- Fix `router.py` all-or-nothing import → individual try/excepts per edit module

**Readiness for Phase 4 (actual migration):**
- NOT READY until Phase A fragility fixes are done
- NOT READY until state constants extracted to shared module
- NOT READY until `inpatient_followup` ghost type normalized

---

- **Decision:** INVESTIGATION ONLY — no changes made
- **Files Changed:** NONE
- **Phase 3 Status:** ✅ COMPLETE

---

## ════════════════════════════════════════
## PHASE 4 — PRE-MIGRATION HARDENING PLAN
## (PLANNING ONLY — NO IMPLEMENTATION YET)
## ════════════════════════════════════════

**Status:** PLAN WRITTEN — AWAITING APPROVAL  
**Principle:** Stability before modularization. Contract-preserving changes only. No behavioral changes. No activations of shadow systems.

---

### ADMIN ↔ USER COUPLING AUDIT (P3.8 FINDINGS)

Before Phase A plan, recording the admin coupling findings from the investigation:

#### P3.8.1 — Shared Runtime Resources

Admin and user subsystems share the following resources without coordination:

| Resource | Written By Admin | Read By User | Risk |
|---|---|---|---|
| `Hospital` DB table | `admin_hospitals_management.py` (add/delete/update) | `hospitals_service.get_all_hospitals()` | Hospital added/deleted while user sees old list |
| `hospitals_service._HOSPITALS_DATA` cache | Partially reset by `service_reload_hospitals()` (called in some admin ops) | Every hospital selection screen | Cache stale between admin op and user render |
| `data/doctors_unified.json` | Admin ops via service functions | `doctors_service` (button-list), `hospitals_service` fallback | File written during active user session |
| `TranslatorDirectory` DB table | `admin_translators_management.py` | `translators_service.get_all_translator_names()` | Translator added/removed changes list ordering |
| `data/hospitals_order.txt` | Admin (indirectly, if ordering tool exists) | `hospitals_service._apply_custom_order()` | Order file change corrupts active `hospital_idx:` callbacks |
| `doctors_service` module caches (`_DOCTORS_BY_HOSPITAL_DEPT` etc.) | Never reset by admin | `get_doctors_for_selection()` | Doctor list always stale until process restart |

#### P3.8.2 — Runtime Ordering Corruption Scenarios

These scenarios can cause **wrong data silently saved to production DB** with no error shown to user:

**Scenario 1 — Hospital index corruption:**
1. User renders hospital list at T=0 → `hospital_idx:3` = "مستشفى X"
2. Admin deletes a hospital with lower index (e.g. index 1) at T=1
3. User presses `hospital_idx:3` at T=2
4. Handler resolves index 3 against NEW list → different hospital
5. Report saved under wrong hospital. No error. No warning.

**Scenario 2 — Translator index corruption:**
1. User renders translator list at T=0 → `simple_translator:new_consult:4` = "معتز"
2. Admin adds new translator to DB at T=1 (changes `priority_order` position)
3. User presses button at T=2
4. `load_translator_names()` returns updated list; index 4 now = different name
5. Report saved with wrong translator name. `resolve_translator_for_report` may find wrong record.

**Scenario 3 — Doctor index corruption:**
1. User renders doctor list → `doctor_idx:7` = "د. أحمد"
2. Admin adds doctor to same hospital/dept at T=1 → `_doctors_list` context cache is per-render
3. Handler reads `context.user_data["_doctors_list"]` — this is the RENDER-TIME snapshot
4. **This scenario is SAFE** — `_doctors_list` is stored in `context.user_data` at render time; admin changes to DB do NOT affect the cached list for the current user
5. Risk only materializes if user explicitly re-renders the doctor list

#### P3.8.3 — Cache Non-Invalidation

| Cache | Reset By | Not Reset By | Effect |
|---|---|---|---|
| `hospitals_service._HOSPITALS_DATA` | `service_reload_hospitals()` (sometimes called after admin hospital ops) | Doctor list changes, ordering file changes | Stale hospital list served to users |
| `doctors_service` (4 module-level caches) | `reload_database()` — **never called by admin handlers** | Any admin doctor operation | Doctor lists permanently stale until process restart |
| `translators_service` | No module-level cache — reads DB on every call | N/A | Safe — always fresh from DB |

#### P3.8.4 — Session Concurrency

- Both admin and user handlers use `SessionLocal()` from the same SQLAlchemy engine
- SQLite with WAL mode — concurrent reads allowed, writes serialize
- No application-level locking around cache updates
- Admin write + user cache read is not atomic → user may read partially-updated state

#### P3.8.5 — Admin Coupling: Phase A Implication

Admin coupling findings do NOT block Phase A. However they define constraints:
- Phase A changes must NOT alter how `_HOSPITALS_DATA`, `_doctors_list`, or translator ordering are consumed
- Phase A changes must NOT change when caches are populated or invalidated
- Admin coupling is a **Phase B concern** (contract stabilization) — specifically: adding render-time snapshots or version tokens to INDEX-bound callbacks

---

### PHASE A — HARDENING PLAN

**Scope:** Fragility reduction with zero behavioral change and full contract preservation.  
**Excluded:** No callback format changes, no state merges, no shadow activation, no ordering changes.

Each task below is self-contained. Each can be approved and executed independently.

---

#### PHASE A.1 — Fix `router.py` All-or-Nothing Import

**File:** `bot/handlers/user/user_reports_add_new_system/edit_handlers/before_publish/router.py`

**Problem (F-01):** Lines 15–107 import all 15 edit modules in a single `try/except` block. One broken file disables ALL editing across ALL flows.

**Fix:** Replace the single try/except with 15 individual try/except blocks, one per edit module. Each failed import sets only that module's handlers to `None`; the other 14 remain functional.

**Behavioral change:** None. Same runtime behavior when all imports succeed. When one fails, the affected flow shows an error message instead of silently killing the conversation.

**Contract impact:** None. Callback formats unchanged. State returns unchanged. `report_tmp` unchanged.

**Risk:** Very low. The change is purely in import mechanics — no handler logic touched.

**Validation:** Import the router module; verify each handler variable is independently `None` when its source file is absent.

---

#### PHASE A.2 — Fix `SmartNavigationManager` Flow Key Aliases

**File:** `bot/handlers/user/user_reports_add_new_system.py` — class `SmartNavigationManager`, method `get_previous_step` (line 1256)

**Problem (F-09, F-10, F-11):** Three confirmed key mismatches between `action_to_flow_type` dict (used when setting `current_flow`) and `step_flows` dict (used by back-navigation):
- `action_to_flow_type` produces `"rehab_physical"` → `step_flows` key is `"rehab"` → back-nav falls back to `STATE_SELECT_ACTION_TYPE`
- `action_to_flow_type` produces `"appointment_reschedule"` → `step_flows` key is `"app_reschedule"` → same fallback
- `action_to_flow_type` produces `"radiation_therapy"` → NO `step_flows` entry → back-nav always falls back

**Fix (Option A — alias at lookup):** In `get_previous_step()`, before looking up `flow_type` in `self.step_flows`, apply a normalization dict:
```python
_flow_aliases = {
    "rehab_physical": "rehab",
    "appointment_reschedule": "app_reschedule",
}
flow_type = _flow_aliases.get(flow_type, flow_type)
```
For `"radiation_therapy"`, add a `"radiation_therapy"` entry to `step_flows` with the correct state sequence.

**Fix (Option B — rename step_flows keys):** Rename `"rehab"` → `"rehab_physical"` and `"app_reschedule"` → `"appointment_reschedule"` in `step_flows`. Simpler but touches the dict structure.

**Recommended:** Option A (alias at lookup) — does not alter the `step_flows` dict, preserves all existing keys, safest change.

**Behavioral change:** Back-navigation now works correctly for `rehab_physical`, `appointment_reschedule`, and `radiation_therapy` flows. Previously these fell back to action type selection screen.

**Contract impact:** None to callbacks. None to `report_tmp`. None to ConversationHandler state integers.

**Risk:** Low. The alias lookup is a 3-line addition inside `get_previous_step()`. The fallback behavior (returning `STATE_SELECT_ACTION_TYPE`) is preserved for any unknown flow_type not in aliases.

**Validation:** Trigger back-navigation from each affected flow; verify correct previous state is shown.

---

#### PHASE A.3 — Fix `EMERGENCY_DATE_TIME` Duplicate TEXT Handler

**File:** `bot/handlers/user/user_reports_add_new_system.py` — ConversationHandler states dict, `EMERGENCY_DATE_TIME` entry (lines 11645–11653)

**Problem (F-06):** Two `MessageHandler(filters.TEXT & ~filters.COMMAND, ...)` registered in same state. PTB uses first match. `handle_followup_date_text_input` (line 11649) shadows `handle_emergency_date_time_text` (line 11652). The emergency-specific handler never fires.

**Fix:** Remove the second (dead) TEXT handler:
```python
# REMOVE this line:
MessageHandler(filters.TEXT & ~filters.COMMAND, _get_emergency_handler('handle_emergency_date_time_text')),
```

**Behavioral change:** None observable. The dead handler was never reachable. The active handler (`handle_followup_date_text_input`) continues to handle text input in this state.

**Contract impact:** None.

**Risk:** Very low. Removing unreachable code.

**Validation:** Text input in emergency date/time state still handled correctly.

---

#### PHASE A.4 — Fix `route_edit_field_input` Fallback Dict Wrong Arabic Strings

**File:** `bot/handlers/user/user_reports_add_new_system/edit_handlers/before_publish/router.py` — `route_edit_field_input`, lines 326–340

**Problem (F-07):** The fallback `action_to_flow` dict (used when `edit_flow_type` is not set) contains wrong Arabic strings that will never match actual `medical_action` values:
- `"استشارة نهائية"` — should be `"استشارة أخيرة"` (PREDEFINED_ACTIONS value)
- `"علاج طبيعي"` — should be `"علاج طبيعي وإعادة تأهيل"`
- `"أجهزة تعويضية"` — does not exist in PREDEFINED_ACTIONS at all

**Fix:** Correct the 3 Arabic strings to match PREDEFINED_ACTIONS exactly:
```python
"استشارة أخيرة": "final_consult",           # was "استشارة نهائية"
"علاج طبيعي وإعادة تأهيل": "rehab_physical", # was "علاج طبيعي"
# remove "أجهزة تعويضية" or map to "device"
```

**Behavioral change:** None in the normal path (this code only runs when `edit_flow_type` is missing, which is an error recovery path). Fixes silent `ConversationHandler.END` for `final_consult`, `rehab_physical` edits when `edit_flow_type` falls off context.

**Contract impact:** None to callbacks. The Arabic strings are read from `report_tmp["medical_action"]` which is already stored by the main flow — this fix only corrects the lookup dict.

**Risk:** Very low. Fixes a broken error-recovery path.

**Validation:** Simulate `edit_flow_type` missing for `final_consult` flow; verify edit still completes instead of ending conversation.

---

#### PHASE A.5 — Add `radiation_therapy` Navigation Map Entry

**File:** `bot/handlers/user/user_reports_add_new_system.py` — `SmartNavigationManager.step_flows` dict (starting line 1015)

**Problem (F-11, also part of A.2):** `radiation_therapy` has states registered in ConversationHandler (8 states: `RADIATION_THERAPY_TYPE` through `RADIATION_THERAPY_CONFIRM`) but NO entry in `step_flows`. Back-navigation for radiation therapy always returns `STATE_SELECT_ACTION_TYPE`.

**Fix:** Add `"radiation_therapy"` entry to `step_flows` with the correct linear sequence:
```python
"radiation_therapy": {
    STATE_SELECT_DATE: None,
    STATE_SELECT_PATIENT: STATE_SELECT_DATE,
    STATE_SELECT_HOSPITAL: STATE_SELECT_PATIENT,
    STATE_SELECT_DEPARTMENT: STATE_SELECT_HOSPITAL,
    STATE_SELECT_SUBDEPARTMENT: STATE_SELECT_DEPARTMENT,
    STATE_SELECT_DOCTOR: STATE_SELECT_SUBDEPARTMENT,
    STATE_SELECT_ACTION_TYPE: STATE_SELECT_DOCTOR,
    'RADIATION_THERAPY_TYPE': STATE_SELECT_ACTION_TYPE,
    'RADIATION_THERAPY_SESSION_NUMBER': 'RADIATION_THERAPY_TYPE',
    'RADIATION_THERAPY_REMAINING': 'RADIATION_THERAPY_SESSION_NUMBER',
    'RADIATION_THERAPY_NOTES': 'RADIATION_THERAPY_REMAINING',
    'RADIATION_THERAPY_RETURN_DATE': 'RADIATION_THERAPY_NOTES',
    'RADIATION_THERAPY_RETURN_REASON': 'RADIATION_THERAPY_RETURN_DATE',
    'RADIATION_THERAPY_TRANSLATOR': 'RADIATION_THERAPY_RETURN_REASON',
    'RADIATION_THERAPY_CONFIRM': 'RADIATION_THERAPY_TRANSLATOR',
},
```
Also need to add `RADIATION_THERAPY_*` state constants to `state_name_to_value` dict (line 1282).

**Behavioral change:** Back-navigation now works step-by-step for radiation therapy. Previously always jumped to action type selection.

**Contract impact:** None.

**Risk:** Low. Additive-only change to data dict. No existing entries modified.

**Validation:** Navigate radiation therapy flow; verify back button steps backward correctly.

---

#### PHASE A.6 — Harden `_get_radiation_therapy_handler()` Against Import Failure

**File:** `bot/handlers/user/user_reports_add_new_system.py` — `_get_radiation_therapy_handler()` (line 10934)

**Problem (F-03, F-04):** If `flows/radiation_therapy.py` fails to import, all 8 radiation therapy ConversationHandler states have `None` as their text/callback handlers. PTB will call `None(update, context)` → `TypeError` at runtime.

**Fix:** Add a safe no-op wrapper so that a `None` return from `_get_radiation_therapy_handler()` becomes a named async function that sends an error message instead of crashing:

At ConversationHandler registration (lines 12033–12093), wherever `_get_radiation_therapy_handler('...')` is used, wrap with:
```python
_get_radiation_therapy_handler('handle_x') or _radiation_therapy_unavailable
```
Where `_radiation_therapy_unavailable` is a defined async function that replies "هذا المسار غير متوفر حالياً" and returns the current state.

**Behavioral change:** Import failure now shows user an error message instead of crashing the bot process. Conversation remains alive.

**Contract impact:** None. State returns are preserved.

**Risk:** Very low. The `or` fallback is only activated when the import fails.

**Validation:** Temporarily break `flows/radiation_therapy.py` import; verify bot stays alive and user sees error.

---

#### PHASE A.7 — Harden `route_edit_field_selection` Null Guard

**File:** `bot/handlers/user/user_reports_add_new_system.py` — ConversationHandler states, all `*_CONFIRM` state edit_field handler (e.g. line 11406–11409)

**Problem (F-02):** If `router.py` fails to import, `route_edit_field_selection = None`. The registered handler is:
```python
route_edit_field_selection if route_edit_field_selection else (lambda u, c: ConversationHandler.END)
```
The lambda silently ends the conversation when `edit_field:` is pressed.

**Fix:** Replace the silent-END lambda with a named handler that sends an Arabic error message and returns the current confirm state:
```python
route_edit_field_selection if route_edit_field_selection else _edit_router_unavailable
```
Where `_edit_router_unavailable` is an async function that:
1. Answers the callback query
2. Sends "⚠️ ميزة التعديل غير متوفرة حالياً. يمكنك النشر أو الإلغاء."
3. Returns the same confirm state (extracted from callback data)

**Behavioral change:** Import failure now shows error + preserves conversation instead of silently ending it.

**Contract impact:** None.

**Risk:** Very low. Fallback only activates on import failure.

---

### PHASE A — EXECUTION ORDER AND DEPENDENCIES

| Task | Depends On | Risk Level | Behavioral Change | Lines Touched |
|---|---|---|---|---|
| A.1 — router.py individual imports | None | Very Low | None | ~90 lines replaced in router.py |
| A.2 — SmartNav aliases | None | Low | Back-nav fixed for 2 flows | ~5 lines added to get_previous_step |
| A.3 — Remove dead EMERGENCY handler | None | Very Low | None | 1 line removed from ConversationHandler |
| A.4 — Fix router fallback Arabic strings | None | Very Low | Error recovery fixed | ~3 lines changed in router.py |
| A.5 — Add radiation_therapy nav map | A.2 (same function) | Low | Back-nav fixed for 1 flow | ~18 lines added to step_flows dict + ~8 lines added to state_name_to_value |
| A.6 — Harden radiation_therapy handlers | None | Very Low | Import failure handled | ~8 lines changed in ConversationHandler |
| A.7 — Harden edit router null guard | A.1 (defines the failure scenario being handled) | Very Low | Import failure handled | ~11 lines changed across all CONFIRM states |

**Recommended execution order:** A.1 → A.4 → A.3 → A.2 → A.5 → A.6 → A.7

**Rationale:** A.1 and A.4 are in the same file (router.py) — do them together. A.3 is trivially safe. A.2 and A.5 are in the same function — do them together. A.6 and A.7 address failure modes that A.1 mitigates but does not eliminate.

---

### PHASE A — WHAT IS EXPLICITLY NOT INCLUDED

The following are KNOWN issues but deliberately excluded from Phase A:

| Issue | Why Excluded | Planned Phase |
|---|---|---|
| INDEX-bound callback corruption (admin changes during session) | Requires callback format migration — behavioral change | Phase B |
| `doctors_service` cache never invalidated by admin | Requires admin handler changes + cache version strategy | Phase B |
| System B edit path (`draft_field:`) deprecation | Requires removing registered callbacks — behavioral change | Phase B |
| `department_name` triple-contract | Requires report_tmp key restructure | Phase C |
| `PREDEFINED_ACTIONS` index migration | Requires new callback format | Phase B |
| `inpatient_followup` normalization in main dispatch | Requires `action_to_flow_type` change | Phase B |
| Cancel handler inconsistency (3 different handlers) | Low severity; would affect edge-case UX | Phase B |
| Wildcard `debug_all_callbacks` fallback in production | Logging concern only; removal safe but low priority | Phase B |
| `PHYSICAL_THERAPY_DEVICES`/`PHYSICAL_THERAPY_NOTES` orphan nav entries | Requires understanding if these states are ever reached | Investigation needed |

---

### APPROVAL GATE

Phase A work begins only after explicit approval of this plan.

Each task (A.1 through A.7) requires individual approval before implementation.

Tasks may be approved individually or as a batch.

---

### ⚠ VERIFICATION STEP BEFORE P2 BEGINS

Before any Phase 2 modification:

Run this mental checklist:
1. Is the function I'm moving truly pure? (no DB access, no context access, no side effects)
2. Does it appear in more than one file with different signatures?
3. After moving, will every import path resolve correctly?
4. Does the moved function depend on anything that isn't in utils.py already?

If ANY answer is uncertain → DO NOT MOVE. Document and escalate.

---

---

## ════════════════════════════════════════
## POST-HARDENING REASSESSMENT
## Phase A Complete — 2026-05-08
## ════════════════════════════════════════

---

### PH.1 — FRAGILITY ELIMINATED BY PHASE A

| Task | Fragility Eliminated | Mechanism |
|---|---|---|
| A.1 — Import isolation | All-or-nothing edit import failure | 15 independent try/except blocks; one module failure no longer disables all 15 edit flows |
| A.2 — Nav aliases | `rehab_physical` / `appointment_reschedule` back-nav always fell to `STATE_SELECT_ACTION_TYPE` | `step_flows` aliases map runtime flow_type keys to correct nav maps |
| A.3 — Dead handler removal | PTB state list had unreachable shadowed TEXT handler | Second `MessageHandler` removed; no execution path change |
| A.4 — Router fallback strings | Edit recovery path silently failed with `ConversationHandler.END` for `final_consult` and `rehab_physical` | Corrected 2 Arabic keys + removed 1 dead `rehab_device` mapping |
| A.5 — Radiation nav map | `radiation_therapy` back-nav always fell to `STATE_SELECT_ACTION_TYPE` for every state | Complete integer-keyed `step_flows` entry added |
| A.6 — Radiation null guard | Import failure → `None` callback → `TypeError` crash at dispatch time | `_radiation_import_failed_handler` fallback at all 9 registration sites |
| A.7 — Edit router null guard | Import failure → silent `ConversationHandler.END` with no log, no user message | `_edit_router_import_failed_handler` named function at all 13 `edit_field:` sites |

---

### PH.2 — FRAGILITY STILL REMAINING

The following known risks were explicitly excluded from Phase A. They remain active in production.

#### 🔴 CATASTROPHIC — Single-event production break

| Risk | Location | Mechanism | Trigger |
|---|---|---|---|
| INDEX-bound callback corruption | `_build_action_type_keyboard()`, `_build_hospital_keyboard()`, `_build_doctor_keyboard()` | Admin adds/removes hospital or doctor → index i shifts → old Telegram messages have stale `hospital_idx:3` pointing to wrong hospital | Admin makes DB change while user has open message with buttons |
| `PREDEFINED_ACTIONS` order change | `user_reports_add_helpers.py:90` | `action_idx:{i}` callbacks are positional — reordering PREDEFINED_ACTIONS remaps all buttons for any active session | Someone adds or reorders an action type |
| `states.py` renumbering | `states.py` range() assignments | Any reordering of state ranges invalidates all in-flight conversations | Developer adds state in wrong range |

#### 🟠 SILENT FAILURE — Fails without crash or log

| Risk | Location | Mechanism |
|---|---|---|
| `doctors_service` stale cache | `services/doctors_smart_search.py` | Module-level cache never invalidated after admin adds/removes doctor; users see stale list until bot restarts |
| `edit_handlers/*.py` → `start_report` lazy import | All 13 edit handlers | `user_reports_add_new_system.__init__.py` does not export `start_report`; this branch silently does nothing when user sends "إضافة تقرير جديد" during edit |
| `inpatient_followup` phantom flow_type | `flows/shared.py:handle_edit_before_save` | `followup` + room_number → overridden to `inpatient_followup` at edit layer only; `inpatient_followup` has no step_flows entry, no ConversationHandler states, no save path |
| System B edit path (`draft_field:`) | Registered in all CONFIRM states alongside System A | Two parallel edit systems with overlapping callbacks; System B (`draft_field:`) is legacy; unclear which fires when both match |
| `broadcast_new_report` failure | `flows/shared.py:save_report_to_database` | If broadcast service fails at save time, report may save but notification not sent; no retry mechanism visible |

#### 🟡 ORDERING / CALLBACK RISKS

| Risk | Location | Mechanism |
|---|---|---|
| `simple_translator:{flow}:{i}` index-bound | Translator keyboard builder | Translator list ordering is from DB query; if query order changes (DB migration, new index), callbacks silently misroute |
| `patient_idx:{patient_id}` safe | Patient selection | ID-bound, not index-bound — safe against reordering ✅ |
| `doctor_idx:{i}` INDEX-bound | Doctor selection keyboard | Same corruption vector as hospital_idx |
| `hospital_idx:{i}` INDEX-bound | Hospital selection keyboard | Admin DB change + stale message = wrong hospital selected silently |
| `dept_idx:{i}` INDEX-bound | Department selection keyboard | Same vector |

#### 🟡 ADMIN ↔ USER SYNCHRONIZATION RISKS

| Risk | Mechanism | Severity |
|---|---|---|
| Admin adds hospital during active user session | `hospital_idx:{i}` callbacks become stale | SILENT WRONG DATA |
| Admin adds doctor during active user session | `doctor_idx:{i}` callbacks become stale | SILENT WRONG DATA |
| Admin disables translator during active user session | `simple_translator:{flow}:{i}` resolves to different translator | SILENT WRONG ASSIGNMENT |
| No coordination mechanism exists | No session invalidation, no cache version, no lock | SYSTEMIC |
| Admin cache never expires | `doctors_service` cache, hospital cache | STALE DATA persists until bot restart |

#### 🟡 NAVIGATION RISKS (remaining)

| Risk | Location | Status |
|---|---|---|
| `PHYSICAL_THERAPY_DEVICES` / `PHYSICAL_THERAPY_NOTES` orphan nav entries | `rehab` step_flows | These states exist in step_flows but their reachability from actual flow is unverified |
| `discharge` dynamic back (`_DYNAMIC_DISCHARGE_BACK_`) | `step_flows['discharge']` | Depends on `discharge_type` in `report_tmp` — if missing, silently falls back to `DISCHARGE_OPERATION_NAME_EN` |
| `SmartNavigationManager` `step_flows` missing `rehab_device` / `device` | step_flows | `rehab_device` and `device` flow_types have no step_flows entry; back-nav falls to `STATE_SELECT_ACTION_TYPE` |
| `radiation_therapy` back-nav before A.5 was applied | FIXED by A.5 | ✅ Resolved |
| `rehab_physical` back-nav before A.2 | FIXED by A.2 | ✅ Resolved |
| `appointment_reschedule` back-nav before A.2 | FIXED by A.2 | ✅ Resolved |

#### 🟡 STATE IDENTITY RISKS

| Risk | Location | Mechanism |
|---|---|---|
| `R_DATE` / `R_DATE_TIME` etc. — duplicate state registration | ConversationHandler | Multiple state keys (e.g. `STATE_SELECT_DATE` and `R_DATE`) map to same handlers; if integer values collide, PTB silently uses first match |
| `NEW_CONSULT_CONFIRM` shared across entry + edit | Multiple states registered under same integer | If any new state accidentally gets same range(x, y) value, silent misdispatch |
| `STATE_SELECT_ACTION_TYPE` vs `R_ACTION_TYPE` — two registrations | Both in ConversationHandler | Same handler list registered under two different state IDs — correct behavior relies on monolith correctly setting `_conversation_state` |

---

### PH.3 — UPDATED MODULARIZATION READINESS

#### ✅ SAFE TO ISOLATE (zero behavioral dependencies on monolith)

| Component | Location | Reason |
|---|---|---|
| `flows/radiation_therapy.py` | Already isolated | Only active modular flow; A.5+A.6 hardened its nav + import fallback |
| `edit_handlers/before_publish/*.py` | Already isolated | A.1 made each module independently failable |
| `edit_handlers/before_publish/router.py` | Already isolated | A.4 corrected contracts; all 15 imports independent |
| `utils.py` — pure functions | Already isolated | Pure functions; no state; no monolith dependency |
| `states.py` | Already isolated | Constants only; imported cleanly everywhere |
| `flows/shared.py` — pure helper functions | Extractable | `get_confirm_state`, `get_editable_fields_by_flow_type`, `escape_markdown_v1`, `format_field_value` are pure |

#### 🟡 NEEDS WRAPPERS (has runtime contracts that must be preserved)

| Component | Blocker | Required Wrapper |
|---|---|---|
| `SmartNavigationManager` | Singleton `smart_nav_manager` used across monolith; `step_flows` dict is now the nav contract | Must remain as singleton; aliases (A.2) must stay; any new flow addition requires both step_flows + alias |
| `flows/shared.py:show_final_summary` | Called by all 15 edit handlers; relies on `report_tmp` shape | Interface contract must be preserved; `report_tmp` schema is the wire protocol |
| `flows/shared.py:save_report_to_database` | Live DB save path; broadcast dependency | Cannot be split from broadcast_new_report without coordination |
| `flows/shared.py:handle_edit_before_save` | Called by `handle_final_confirm` in monolith; generates `edit_field:{flow_type}:{field_key}` buttons | Button format is callback contract; cannot change format without migrating all 15 edit handlers |

#### 🔴 NEEDS CONTRACT MIGRATION (behavioral change required before isolation)

| Component | Required Migration | Risk |
|---|---|---|
| `hospital_idx:{i}` callback system | Migrate to `hospital_id:{db_id}` format | CATASTROPHIC if done partially — two message generations cannot coexist |
| `doctor_idx:{i}` callback system | Migrate to `doctor_id:{db_id}` format | Same |
| `action_idx:{i}` callback system | Migrate to `action_type:{slug}` format | Requires `PREDEFINED_ACTIONS` keyed by slug not index |
| `simple_translator:{flow}:{i}` | Migrate to `simple_translator:{flow}:{translator_id}` | Translator IDs already in DB; indexing is unnecessary |
| System B edit path (`draft_field:`) | Deprecate after System A (A.1 hardened) is proven stable | Cannot remove until confirmed System A handles 100% of edit callbacks |

#### 🔴 MUST REMAIN MONOLITHIC (for now)

| Component | Reason |
|---|---|
| `user_reports_add_new_system.py` (12,800+ lines) | Active ConversationHandler lives here; `conversation_handler.py` delegates to it via importlib; removing or restructuring = production break |
| `handle_action_type_choice` | Central flow dispatch — sets `medical_action`, `current_flow`, `action_type`; entangled with back-navigation heuristics |
| `handle_smart_back_navigation` | Heuristic flow detection hardcoded for specific `medical_action` Arabic strings; tightly coupled to `SmartNavigationManager` singleton |
| `_get_action_routing()` | 13-entry dict mapping action names to flow entry functions; some entry functions are live imports (radiation), some are local |

---

### PH.4 — UNIFIED COMPONENT OPPORTUNITY REASSESSMENT

#### Translator Selector

| Aspect | Status | Notes |
|---|---|---|
| Monolith's translator logic | Still in monolith via `show_translator_selection()` | Called for 11 of 13 flows |
| `radiation_therapy` translator | Already isolated in `flows/radiation_therapy.py` | Uses `show_radiation_translator_selection()` — different pagination |
| `flows/shared.py` translator system | 2,652-line file contains full translator selection system | INACTIVE — monolith's version is the active path |
| Phase A impact | None — translator untouched | Translator unification is still blocked by monolith active status |
| Readiness | 🔴 BLOCKED | Cannot unify until monolith's `register()` is replaced |

#### Hospital / Department / Doctor Selectors

| Aspect | Status | Notes |
|---|---|---|
| Modular handlers exist | `hospital_handlers.py`, `department_handlers.py`, `doctor_handlers.py` | All INACTIVE — monolith's ConversationHandler handles these |
| INDEX-bound callback risk | Active | Unification requires first migrating to ID-bound callbacks |
| Phase A impact | None | Selectors untouched |
| Readiness | 🔴 BLOCKED | Requires INDEX→ID migration first (Phase B prerequisite) |

#### Date/Time Selector

| Aspect | Status | Notes |
|---|---|---|
| Modular handler exists | `date_time_handlers.py` | INACTIVE |
| Active path | Monolith's `handle_date_choice`, `handle_date_time_hour`, `handle_date_time_minute` | These are in monolith |
| `radiation_therapy` calendar | Isolated in `flows/radiation_therapy.py` | Uses different `rad_cal_` / `rad_time_` callback prefixes |
| Phase A impact | A.3 removed dead TEXT handler from `EMERGENCY_DATE_TIME` | Calendar behavior for emergency state now uses single handler |
| Readiness | 🟡 SAFER than before | A.3 reduced handler count; but main date handlers still monolith |

#### Navigation Controls

| Aspect | Status | Notes |
|---|---|---|
| `nav:back` handler | `handle_smart_back_navigation` in monolith | A.2 + A.5 fixed nav maps — back-nav now correct for all flows |
| `nav:cancel` handler | 3 different cancel handlers (`handle_calendar_cancel`, `handle_smart_cancel_navigation`, `handle_finish_and_cancel`) | Still inconsistent — not addressed in Phase A |
| `_nav_buttons()` | Utils version is strict superset of monolith version | Monolith anomaly (always overwrites import) still present but harmless |
| Phase A impact | Navigation now correct for all 13 flows | A.2 (rehab_physical, appointment_reschedule) + A.5 (radiation_therapy) |
| Readiness | 🟡 IMPROVED | Nav maps complete for all flows; cancel inconsistency remains |

#### Confirmation Screens

| Aspect | Status | Notes |
|---|---|---|
| Active path | `handle_final_confirm` in monolith → delegates to `flows/shared.py:handle_edit_before_save` | Mixed — confirm routing in monolith, edit screen generation in shared.py |
| Edit router (System A) | `edit_handlers/before_publish/router.py` | A.1 hardened; A.7 guarded null route |
| Edit router (System B) | `handle_draft_field_input` in monolith | Legacy parallel system; still registered |
| Phase A impact | A.7: `edit_field:` failures now observable and logged | Before A.7: silent END with no log |
| Readiness | 🟡 HARDENED but not unified | Cannot remove System B until System A confirmed 100% coverage |

#### Pagination Systems

| Aspect | Status | Notes |
|---|---|---|
| Hospital pagination | `hospital_page:` / `hosp_page:` — two patterns registered | Dual pattern is legacy compatibility; both registered in STATE_SELECT_HOSPITAL |
| Doctor pagination | `doctor_page:` | Single pattern |
| Department pagination | `dept_page:` | Single pattern |
| Translator pagination | `translator_page:` (monolith) vs `rad_translator` (radiation) | Two different systems |
| Phase A impact | None | Pagination systems untouched |
| Readiness | 🔴 BLOCKED | Pagination is coupled to INDEX-bound callbacks; cannot unify before INDEX→ID migration |

---

### PH.5 — ADMIN ↔ USER RUNTIME COUPLING ANALYSIS (Architecture Planning Only)

#### Current Coupling Points

```
ADMIN SIDE                              USER SIDE
══════════════════════════════════════════════════════════════════
admin adds hospital                   user has open message with hospital_idx buttons
  → DB changes                        → old hospital_idx:{i} now resolves to different hospital
  → NO cache invalidation             → SILENT WRONG SELECTION
  → NO session invalidation

admin adds doctor                     user has doctor_idx buttons visible
  → doctors_service cache NOT updated → old doctor_idx:{i} wrong after cache refresh
  → cache lives until bot restart     → depends on timing

admin adds translator                 user is viewing translator selection
  → simple_translator:{flow}:{i} buttons → new translator inserts at unknown index position
  → if query returns in different order → SILENT WRONG ASSIGNMENT

admin modifies PREDEFINED_ACTIONS     user is viewing action_type screen (hypothetical)
  → action_idx:{i} callback contract   → silent wrong action selection
  → order IS the contract
```

#### Coordination Mechanisms Currently Present

| Mechanism | Present? | Notes |
|---|---|---|
| Session invalidation on admin change | ❌ NO | No signal sent to active user sessions |
| Cache versioning | ❌ NO | No version counter; no TTL |
| DB row-level locking during user flow | ❌ NO | Admin writes are independent |
| Stale callback detection | ❌ NO | No timestamp or version embedded in callbacks |
| Admin → user notification on change | ❌ NO | Admin changes take effect immediately and silently |

#### Risk Tiers

**Tier 1 — ALWAYS BROKEN if admin acts during session (silent wrong data)**
- `hospital_idx:{i}` + admin adds/removes hospital
- `doctor_idx:{i}` + admin adds/removes doctor
- `simple_translator:{flow}:{i}` + admin modifies translator list

**Tier 2 — BROKEN after bot restart if cache stale**
- `doctors_service` module-level cache — stale after any doctor DB change until restart
- Hospital/department caches (if any) — similar pattern

**Tier 3 — SAFE regardless of admin action**
- `patient_idx:{patient_id}` — ID-bound, safe ✅
- `report_tmp` data already captured — not re-read from DB mid-flow ✅
- State IDs — not affected by admin changes ✅

#### Recommended Future Direction (Architecture Only — NOT Implementation)

**Phase B prerequisite — Index→ID migration:**
Before any admin/user coordination mechanism is possible, all INDEX-bound callbacks must become ID-bound. This is the single most impactful safety migration available.

Specific migrations needed:
1. `hospital_idx:{i}` → `hospital_id:{db_id}` — hospital DB IDs available; safe lookup possible
2. `doctor_idx:{i}` → `doctor_id:{db_id}` — doctor IDs available in DB
3. `simple_translator:{flow}:{i}` → `simple_translator:{flow}:{translator_id}` — translator IDs available
4. `action_idx:{i}` → `action_type:{slug}` — requires defining slug constants for PREDEFINED_ACTIONS

**Phase B cache strategy (after ID migration):**
Once callbacks are ID-bound, stale index corruption is eliminated. Cache staleness becomes lower-priority (ID lookup at selection time reads current DB state). Module-level cache can then be replaced with TTL-based or invalidation-signal-based cache.

**Phase B coordination mechanism (after cache strategy):**
A lightweight "session version" stamp embedded in callback data would allow detecting stale sessions. But this requires callback format change — only safe after ID migration is complete.

**Key constraint:**
Admin and user subsystems share NO runtime boundary today. Any coordination mechanism requires either:
- A shared in-memory signal (e.g., Redis pub/sub, shared global version counter)
- Or accepting ID-bound callbacks as sufficient protection (simpler, recommended first)

The ID-bound migration is the correct Phase B starting point. No coordination mechanism should be designed until ID-bound callbacks are established.

---

### PH.6 — UPDATED PHASE PLAN

```
PHASE A — COMPLETE ✅
  Fragility hardening — 7 tasks — all approved and merged

PHASE B — NEXT (not started)
  TWO DOMAINS: Data Authority Stabilization FIRST, then Protocol Migration

  ── DOMAIN 1: DATA AUTHORITY STABILIZATION ──

  B-DA.1 — Establish single authoritative translator identity registry
            This is identity authority migration, not merely a data sync fix.
            Steps:
              1. Audit current TranslatorDirectory DB contents vs translator_names.txt — find divergence
              2. Establish DB (TranslatorDirectory) as the single authority
              3. Fix admin_translators_management.py to write to DB (add/delete/sync)
              4. Verify get_all_translator_names() reads DB exclusively (file as true last-resort only)
              5. Verify resolve_translator_for_report() can resolve all active operational identities
              6. Confirm every translator in use has a stable translator_id
            Risk: MEDIUM-HIGH — live identity system; wrong migration = save paths produce translator_id=None
            PREREQUISITE for B.3
            NOTE: file (translator_names.txt) becomes a backup/export artifact, not an authority

  B-DA.2 — Fix doctors_service cache invalidation (BUG-3)
            admin_hospitals_management.py must call reload_database() after mutations
            Risk: LOW — adding one call; no behavioral change when cache is warm
            PREREQUISITE for B.2

  ── DOMAIN 2: PROTOCOL MIGRATION ──

  B.1 — Migrate hospital_idx:{i} → hospital_id:{db_id}
         Prerequisites: B-DA.2 (cache correct), dual-stack compatibility layer
         Risk: HIGH — callback format change; old messages remain active
         Must preserve: stale message handling, rebuild fallback

  B.2 — Migrate doctor_idx:{i} → doctor_id:{db_id}
         Prerequisites: B-DA.2, B.1 pattern established
         Risk: HIGH — same vector as B.1

  B.3 — Migrate simple_translator:{flow}:{i} → simple_translator:{flow}:{translator_id}
         Prerequisites: B-DA.1 COMPLETE — TranslatorDirectory must be the single authority
         and every active operational identity must have a confirmed stable translator_id
         Risk: HIGH — migrating to ID-bound callbacks on a corrupt identity registry
         produces plausible-looking but wrong translator assignments in saved reports
         This migration is identity authority migration, not merely callback format change
         Goal: every saved report's translator_id traces to a verified operational identity

  B.4 — Deprecate System B edit path (draft_field:)
         Prerequisite: System A confirmed 100% coverage across all 13 flows
         Risk: LOW after confirmation

  B.5 — Resolve rehab_device / device step_flows gap
         Investigation needed: are these flows reachable in production?
         Risk: LOW (affects only those two flow types)

  B.6 — Fix cancel handler inconsistency (3 handlers → 1)
         Risk: MEDIUM (cancel is a fallback — must verify all paths)

PHASE C — LATER (after Phase B)
  Priority: Monolith migration activation
  Prerequisites: Phase B complete; INDEX→ID migration done

  C.1 — Activate modular ConversationHandler in conversation_handler.py
         (replace `_original_module.register(app)` with modular handler)
         This is the single largest risk in the entire migration
         
  C.2 — Activate flows/shared.py translator system (replace monolith translator)
  C.3 — Activate flows/shared.py save_report_to_database (replace monolith save)
  C.4 — Activate modular date_time, patient, hospital, department, doctor handlers
  C.5 — Delete or archive monolith after 100% activation confirmed

PHASE D — ADVANCED (after Phase C)
  P5.1 — Centralized callback router
  P5.2 — Typed state objects (TypedDict for report_tmp)
  P5.3 — Navigation manager class extraction
  P5.4 — Callback registry pattern
  P5.5 — Admin ↔ User coordination mechanism (after ID-bound migration)
```

---

### PH.7 — CURRENT RUNTIME TRUTH (Post Phase A)

**Active production runtime:**
- ConversationHandler: **monolith** (`user_reports_add_new_system.py`, ~12,800 lines)
- Active modular flows: `radiation_therapy` only (via `_get_radiation_therapy_handler`)
- Active modular edit: `edit_handlers/before_publish/` via `route_edit_field_selection` + `route_edit_field_input`
- Active shared utilities: `flows/shared.py:show_final_summary`, `get_confirm_state`, `save_report_to_database`, `handle_edit_before_save`
- Navigation: `SmartNavigationManager` in monolith, step_flows now has all 13 flows + 2 aliases ✅
- Import failure isolation: edit_handlers now independent ✅; radiation handlers now graceful ✅; edit router now observable ✅

**Migration status: ~8–12% modular (up from ~5–10% before Phase A)**

Phase A did not increase modular activation — it hardened the existing boundary contracts so that Phase B→C can proceed safely.

---

_End of POST-HARDENING REASSESSMENT — Updated: 2026-05-08_

---

## ════════════════════════════════════════
## ADMIN LAYER RUNTIME COUPLING AUDIT
## Completed: 2026-05-08
## ════════════════════════════════════════

### AL.1 — ADMIN HANDLER INVENTORY

20 files in `bot/handlers/admin/` (~17,200 lines total).

| File | Lines | Runtime Coupling to User Layer |
|---|---|---|
| `admin_hospitals_management.py` | 695 | **HIGH** — mutates Hospital DB table; triggers hospitals_service cache reload |
| `admin_translators_management.py` | 634 | **CRITICAL** — writes to file only; DB not synced (see AL.4) |
| `admin_start.py` | 515 | LOW — dashboard + user approvals; no selector mutation |
| `admin_reports.py` | 3,614 | LOW — reads reports; no selector mutation |
| `admin_printing.py` | 2,687 | LOW — reads reports for printing |
| `admin_schedule_management.py` | 1,493 | MEDIUM — schedule mutations may affect user appointment flows |
| `admin_evaluation.py` | 1,611 | LOW — translator evaluation; no selector mutation |
| `admin_data_analysis.py` | 1,836 | LOW — read-only analytics |
| `admin_initial_case.py` | 953 | LOW — creates InitialCase + Patient records; broadcasts to users but does not mutate selectors |
| `admin_users_management.py` | 273 | MEDIUM — approve/suspend users; affects who can submit reports |
| `admin_delete_reports.py` | 736 | LOW — deletes Report records only |
| `admin_admins.py` | 403 | LOW — admin user management |
| Others (8 files) | ~2,000 | LOW — monitoring, backup, notes, AI |

**Registration:** All admin and user handlers share a **single bot Application instance**. Admin ConversationHandlers are registered before user handlers in `handlers_registry.py`. No separate bot instance. Dispatch priority is determined by registration order.

---

### AL.2 — HOSPITALS DATA AUTHORITY MAP

**Storage:**
- Primary authority: `db.models.Hospital` (SQLite, `Hospital` table)
- Secondary: `data/doctors_unified.json` (hospital names embedded; used as fallback)
- Ordering: `data/hospitals_order.txt` (custom priority list; read by `hospitals_service._apply_custom_order()`)

**Admin mutation path:**
```
admin adds hospital
  → SessionLocal().add(Hospital(name=name)) → commit()
  → service_add_hospital(name) [JSON sync, optional — warning logged if fails]
  → service_reload_hospitals() [CALLED — invalidates module cache]
```

**Cache:**
- `hospitals_service.py`: `_HOSPITALS_DATA`, `_HOSPITALS_LIST` (module-level globals)
- **Invalidation: explicit** — `reload_hospitals()` IS called by admin handler after mutation ✅
- **Assessment:** Hospital cache is correctly managed. Admin mutations invalidate it synchronously.

**User exposure:**
- User selects hospital via `hospital_idx:{i}` callback
- Hospital list snapshot stored in `context.user_data["report_tmp"]["hospitals_list"]` at render time
- At callback resolution, if `hospitals_list` missing from user_data, code rebuilds from DB
- **Stale window exists:** user renders hospital keyboard at T, admin deletes hospital at T+1, user clicks at T+2 → index i now points to different hospital. Rebuild fires but selects current-position hospital, which may differ from what user saw

---

### AL.3 — DOCTORS DATA AUTHORITY MAP

**Storage:**
- Primary authority: `db.models.Doctor` (SQLite; FK to Hospital.id, Department.id)
- Secondary: `data/doctors_unified.json` (comprehensive index used as fallback and for fast search)

**Admin mutation path:**
- **NO admin Telegram interface for doctor mutation exists**
- Doctor mutations require direct DB scripts or manual JSON editing
- `add_doctor()` exists in `doctors_service.py` but is not called from any admin handler

**Cache:**
- `doctors_service.py`: `_DOCTORS_DATA`, `_HOSPITALS_INDEX`, `_DOCTORS_BY_HOSPITAL`, `_DOCTORS_BY_HOSPITAL_DEPT` (module-level globals)
- **Invalidation: NOT triggered by any admin handler** ❌
- `reload_database()` exists but is never called from admin mutation paths
- Cache stays stale until PM2 process restart
- **Assessment:** Low immediate risk (doctors rarely change) but cache architecture is broken — any DB doctor change is invisible until restart

**User exposure:**
- Doctor selection reads from DB via hospital+department FK query; JSON fallback if DB empty
- `doctor_idx:{i}` callbacks are INDEX-bound against the rendered doctor list
- Since doctors change rarely and no admin Telegram interface exists, stale callback risk is currently LOW in practice, but not by design

---

### AL.4 — TRANSLATOR SYSTEM: IDENTITY AUTHORITY MAP

**Architectural purpose — critical context:**

The translator system is NOT a simple display selector. It is an **operational identity normalization layer**.

Telegram account identity is unreliable in this operational context: translators may use single letters, nicknames, or usernames completely unrelated to their operational identity. A translator operationally known as "مهدي" may appear in Telegram as "m", "mh", or an unrelated username. The system was deliberately designed to separate:
1. Telegram account identity (unreliable, mutable)
2. Operational/business translator identity (stable, meaningful)

This explains the existence of `TranslatorDirectory`, `translator_id`, `translator_name`, and `resolve_translator_for_report()`. These are not just DB scaffolding — they are the implementation of a deliberate **identity authority layer**.

**Consequence:** The translator migration is NOT merely IDX→ID callback migration. It is **identity authority migration**. The goal is a single authoritative translator identity registry that admin writes, runtime reads, save paths resolve, and analytics reference — all from the same source.

---

**Current storage state (split-brain):**
- INTENDED authority: `db.models.TranslatorDirectory` (table `translators`; columns: `translator_id` INT PK, `name` STR)
- LEGACY authority: `data/translator_names.txt` (one name per line; ~20 entries)

**Admin mutation path (broken):**
```
admin adds translator
  → save_translator_names_to_file(names)  [writes to translator_names.txt ONLY]
  → db.TranslatorDirectory: NOT touched ❌
```

**User read path:**
```
get_all_translator_names()
  → tries DB first: SELECT from TranslatorDirectory table
  → if DB empty: falls back to translator_names.txt
  → applies priority order (16 hardcoded names in code)
```

**Identity resolution path (save time):**
```
resolve_translator_for_report(translator_name, context)
  → fuzzy name match against current translator list
  → returns translator_id from TranslatorDirectory if found
  → translator_id = None at selection time; resolved at save time
```

**THE SPLIT:**
- Admin writes to FILE — believes they are managing the operational roster
- User reads DB FIRST — sees a different roster if DB is already seeded
- New file-only additions are INVISIBLE to users (DB rows shadow the file)
- `sync_file_to_database()` function exists in `translators_service.py` but is NEVER called by admin handler
- Admin and production runtime can observe DIFFERENT translator realities simultaneously

**Identity integrity consequence:**
If admin adds translator "أحمد" to the file but TranslatorDirectory already has rows, "أحمد" never appears in user selections. If a report is somehow submitted with "أحمد" as translator_name, `resolve_translator_for_report()` cannot find a matching ID → `translator_id = None` in the saved report. The operational identity cannot be resolved.

**Cache:**
- `_TRANSLATORS_CACHE` and `_CACHE_TIMEOUT` defined but unused — no cache staleness risk (fresh reads every call)
- **The bug is not staleness — it is authority divergence**

**User exposure:**
- `simple_translator:{flow_type}:{i}` callbacks are INDEX-bound against the rendered translator list
- If admin modifies list between render and callback execution: index i resolves to wrong translator
- No rebuild logic (unlike hospitals) — stale index silently assigns wrong operational identity
- Wrong assignment is then persisted in the report and used for analytics/tracking

---

### AL.5 — CALLBACK MUTATION TIMELINE (DISTRIBUTED RUNTIME HAZARD)

This table maps the full lifecycle of each INDEX-bound callback system and when it becomes corrupted.

```
HOSPITAL CALLBACKS (hospital_idx:{i})
══════════════════════════════════════════
Render time:  user reaches hospital selection step
              → hospitals_service._HOSPITALS_LIST queried
              → InlineKeyboard built with hospital_idx:0, 1, 2, ...
              → message sent to Telegram client
              → message persists indefinitely in client

Mutation:     admin adds/deletes hospital via admin_hospitals_management.py
              → Hospital DB updated
              → reload_hospitals() called → module cache refreshed ✅
              → BUT: rendered Telegram message still has OLD index mapping

Callback:     user clicks hospital_idx:3 (may be days later)
              → handler resolves: hospitals_list[3] from context.user_data
              → if hospitals_list missing: rebuilds from CURRENT DB (different order)
              → WRONG HOSPITAL SELECTED if list changed between render and click

Mitigation:   partial — rebuild re-reads DB, but selects position 3 in new list
              which may be a different hospital than what user saw
Severity:     MEDIUM-HIGH — silent wrong data, not an error
```

```
TRANSLATOR CALLBACKS (simple_translator:{flow_type}:{i})
═════════════════════════════════════════════════════════
Render time:  user reaches translator selection step
              → get_all_translator_names() called → DB→file list
              → InlineKeyboard with simple_translator:flow:0, 1, 2...
              → message sent; persists in client

Mutation:     admin adds/deletes via admin_translators_management.py
              → translator_names.txt updated
              → TranslatorDirectory DB NOT updated ❌
              → No cache to invalidate (fresh reads already)
              → New translator may be invisible to users (DB-first read)

Callback:     user clicks simple_translator:emergency:4
              → handler resolves: translators_list[4] from rendered list
              → if list changed: index 4 = different translator
              → NO rebuild logic exists

Severity:     HIGH — silent wrong translator assignment; no detection mechanism
```

```
ACTION CALLBACKS (action_idx:{i})
══════════════════════════════════
Render time:  user reaches action type selection step
              → PREDEFINED_ACTIONS list (hardcoded, 13 items)
              → InlineKeyboard with action_idx:0 through action_idx:12
              → message sent; persists in client

Mutation:     PREDEFINED_ACTIONS is hardcoded in user_reports_add_helpers.py
              → cannot change without code deploy
              → No runtime mutation path exists from admin layer

Severity:     LOW — no admin mutation path; only risk is developer error on deploy
```

```
DOCTOR CALLBACKS (doctor_idx:{i})
══════════════════════════════════
Render time:  user reaches doctor selection
              → DB query for doctors by hospital+department
              → InlineKeyboard with doctor_idx:0, 1, 2...

Mutation:     No admin Telegram interface
              → Only via direct DB/JSON edit + restart
              → doctors_service cache never invalidated

Severity:     LOW in practice (no admin interface; rare changes)
              MEDIUM by design (no protection if direct DB edit occurs)
```

---

### AL.6 — MODULE-LEVEL CACHE INVENTORY (FULL PLATFORM)

| Cache Variable | File | What It Caches | Invalidated By | Risk |
|---|---|---|---|---|
| `_HOSPITALS_DATA` | `hospitals_service.py:15` | Full hospitals JSON dict | `reload_hospitals()` — called by admin handler ✅ | LOW |
| `_HOSPITALS_LIST` | `hospitals_service.py:16` | Ordered hospital name list | `reload_hospitals()` — called by admin handler ✅ | LOW |
| `_DOCTORS_DATA` | `doctors_service.py:15` | Full doctors_unified.json dict | `reload_database()` — NEVER called ❌ | MEDIUM |
| `_HOSPITALS_INDEX` | `doctors_service.py:16` | hospital_id/name → object | `reload_database()` — NEVER called ❌ | MEDIUM |
| `_DOCTORS_BY_HOSPITAL` | `doctors_service.py:17` | hospital_id → [doctors] | `reload_database()` — NEVER called ❌ | MEDIUM |
| `_DOCTORS_BY_HOSPITAL_DEPT` | `doctors_service.py:18` | (hospital_id, dept) → [doctors] | `reload_database()` — NEVER called ❌ | MEDIUM |
| `_TRANSLATORS_CACHE` | `translators_service.py:17` | (declared) | (declared but unused) | N/A — dead code |
| `smart_nav_manager` | `user_reports_add_new_system.py` | SmartNavigationManager singleton | never — immutable after construction | NONE — immutable ✅ |
| `context.user_data` | PTB per-user memory | Per-user session state | cleared on cancel/complete | session-scoped ✅ |
| `report_tmp` | inside context.user_data | In-flight report data | cleared on save/cancel | session-scoped ✅ |

**PM2 survival:** All module-level caches (`_HOSPITALS_DATA`, `_DOCTORS_*`) survive across requests for the full uptime of the PM2 process. They are only reset on process restart.

---

### AL.7 — ADMIN LAYER BUGS (CONFIRMED, NOT FIXED IN PHASE A)

These are confirmed production bugs identified during this audit. They are NOT Phase A targets. Listed here for Phase B planning.

#### BUG-1: Translator admin-DB split (CRITICAL)
- **Symptom:** Admin adds translator via Telegram → translator visible in admin confirmation → translator NOT visible to users
- **Root cause:** `admin_translators_management.py` writes to `translator_names.txt` only; `translators_service.get_all_translator_names()` reads DB first; `TranslatorDirectory` table not updated
- **Fix required:** Admin handler must call `translators_service.add_translator(name)` (DB write) in addition to file write, OR `get_all_translator_names()` must unify both sources
- **Phase B priority:** HIGH — affects live translator assignment

#### BUG-2: Translator delete does not touch DB
- **Symptom:** Admin deletes translator → translator still appears in user selections (from DB)
- **Root cause:** Same split — delete only removes from file; DB TranslatorDirectory not touched
- **Phase B priority:** HIGH

#### BUG-3: doctors_service cache never invalidated after hospital mutations
- **Symptom:** Admin adds new hospital → doctors for new hospital not visible until restart
- **Root cause:** `admin_hospitals_management.py` calls `reload_hospitals()` but NOT `doctors_service.reload_database()`
- **Fix required:** Add `doctors_service.reload_database()` call after hospital mutations
- **Phase B priority:** MEDIUM (doctors for new hospital are absent, not wrong)

#### BUG-4: stale translator callback — no rebuild
- **Symptom:** User renders translator list at T, admin changes list at T+1, user clicks at T+2 → wrong translator assigned silently
- **Root cause:** No rebuild logic for translator callbacks (unlike hospital callbacks which have partial rebuild)
- **Phase B priority:** HIGH — linked to B.3 (translator ID migration)

---

### AL.8 — ADMIN INITIAL_CASE FLOW — RUNTIME COUPLING ASSESSMENT

`admin_initial_case.py` (953 lines — visible in IDE) is a standalone admin ConversationHandler with 9 states (`range(9)`). Assessment:

**Runtime coupling to user layer:**
- Creates `Patient` + `InitialCase` DB records — user layer reads Patient records for patient search
- Calls `broadcast_initial_case()` from `services.broadcast_service` — broadcasts to ALL users and admins
- Does NOT mutate any selector (hospitals, doctors, translators, actions)
- Uses `back:{step}` callback pattern — completely separate from user layer's `nav:back` pattern
- Uses `context.user_data` but clears on completion — no overlap with user report_tmp

**Stale callback risk:** NONE — no INDEX-bound callbacks in this flow. Navigation uses named step identifiers (`back:patient_name`, `back:age`, etc.) — these are position-independent strings.

**Assessment:** `admin_initial_case.py` is runtime-safe from the user layer's perspective. The only coupling is the shared `Patient` table, which is also written by user report creation — no coordination mechanism exists for concurrent writes, but this is low-risk (patient records are additive).

---

### AL.9 — FIVE-LAYER RUNTIME TRUTH MAP (COMPLETE)

```
LAYER 1 — USER RUNTIME LAYER
─────────────────────────────
Active engine:   user_reports_add_new_system.py (monolith, 12,800 lines)
State machine:   103-state ConversationHandler
Navigation:      SmartNavigationManager singleton (step_flows complete ✅)
Selectors:       hospital_idx, doctor_idx, dept_idx, action_idx, simple_translator
Report state:    context.user_data["report_tmp"] — full in-flight report
Publish path:    flows/shared.py:save_report_to_database → broadcast_new_report
Edit system:     System A (router.py) + System B (legacy draft_field:) — both active

LAYER 2 — ADMIN CONTROL LAYER
───────────────────────────────
Engine:          20 separate admin handler files (17,200 lines total)
Hospital CRUD:   admin_hospitals_management.py → Hospital table + reload_hospitals() ✅
Translator CRUD: admin_translators_management.py → translator_names.txt ONLY ❌ (BUG-1,2)
Doctor:          NO admin interface — direct DB/JSON edits only
Patient:         admin_initial_case.py creates Patient+InitialCase records
Reports:         admin_reports.py reads/exports; admin_delete_reports.py deletes

LAYER 3 — TELEGRAM DISTRIBUTED UI LAYER
─────────────────────────────────────────
Persistence:     Telegram messages persist indefinitely in client after send
Stale window:    Any time between keyboard render and user click
INDEX risk:      hospital_idx, doctor_idx, dept_idx, simple_translator all vulnerable
ID-safe:         patient_idx:{patient_id} — safe ✅
No expiry:       Telegram provides no native callback expiry mechanism
Admin trigger:   Admin mutation → cache refresh → BUT old messages unaffected

LAYER 4 — CACHE / MEMORY LAYER
────────────────────────────────
hospitals_service:   _HOSPITALS_LIST — module-level; invalidated by admin handler ✅
doctors_service:     _DOCTORS_BY_HOSPITAL_* — module-level; NEVER invalidated ❌
translators_service: _TRANSLATORS_CACHE — declared but dead; fresh reads ✅ (by accident)
user sessions:       context.user_data — per-user, session-scoped, cleared on end ✅
report_tmp:          inside user_data — full in-flight report snapshot ✅
PM2 memory:          all module-level caches survive until process restart

LAYER 5 — DATA AUTHORITY LAYER
────────────────────────────────
Hospital:      DB (Hospital table) = primary; JSON = fallback
Doctor:        DB (Doctor table) = primary; doctors_unified.json = fallback + search index
Translator:    DB (TranslatorDirectory) = user-read primary; txt file = admin-write primary ❌ SPLIT
Patient:       DB (Patient table) = single authority ✅
Report:        DB (Report table) = single authority ✅
InitialCase:   DB (InitialCase table) = single authority ✅
Actions:       PREDEFINED_ACTIONS hardcoded list = single authority ✅
```

---

### AL.10 — PHASE B IMPACT ON ADMIN LAYER

The INDEX→ID migration planned for Phase B directly resolves the stale callback vulnerabilities in Layer 3. Per-entity impact:

| Entity | Phase B Task | Admin Layer Change Required |
|---|---|---|
| Hospital | B.1: hospital_idx→hospital_id | NONE — admin handler already correct; user selector lookup changes |
| Doctor | B.2: doctor_idx→doctor_id | Add `reload_database()` call to hospital admin handler (BUG-3 fix) |
| Translator | B.3: translator_idx→translator_id | Fix admin handler to also write to DB (BUG-1,2 fix); enables ID-bound callbacks |
| Action | Not Phase B (hardcoded list) | No admin layer change needed |

**Translator migration is the most complex:** Phase B.3 cannot proceed cleanly until BUG-1 and BUG-2 are resolved — if the DB and file are out of sync, migrating to ID-bound callbacks against a corrupt DB produces wrong assignments. BUG-1/2 must be fixed as a prerequisite to B.3, not as part of it.

---

_End of ADMIN LAYER RUNTIME COUPLING AUDIT — Updated: 2026-05-08_

---

_End of refactor_progress.md — Updated: 2026-05-08_
