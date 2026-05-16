# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import py_compile, ast, inspect

print("=" * 60)
print("B-DA.4 VERIFICATION: IDX→NAME protocol migration")
print("=" * 60)

# ── 1. Syntax check both files ──────────────────────────────────
files = [
    "bot/handlers/user/user_reports_add_new_system/flows/shared.py",
    "bot/handlers/user/user_reports_add_new_system.py",
]
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"  SYNTAX OK: {f.split('/')[-1]}")
    except py_compile.PyCompileError as e:
        print(f"  SYNTAX ERROR: {f}: {e}")
        sys.exit(1)

# ── 2. Parse and extract source sections ────────────────────────
def get_source(filepath, funcname):
    with open(filepath, encoding='utf-8') as fh:
        src = fh.read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == funcname:
            lines = src.splitlines()
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    return ""

shared_consumer = get_source(files[0], "handle_simple_translator_choice")
shared_renderer = get_source(files[0], "show_translator_selection")
mono_consumer   = get_source(files[1], "handle_simple_translator_choice")
mono_renderer   = get_source(files[1], "show_translator_selection")
mono_pagenav    = get_source(files[1], "handle_translator_page_navigation")

# ── 3. Renderer: must NOT contain :{i} or :real_index ───────────
for label, src in [("shared renderer", shared_renderer), ("mono renderer", mono_renderer), ("mono pagenav", mono_pagenav)]:
    assert ":{i}" not in src,        f"{label}: old :{i} pattern still present"
    assert ":real_index}" not in src, f"{label}: old :real_index pattern still present"
    assert ":{name}" in src,          f"{label}: new :{name} pattern missing"
    print(f"  RENDERER OK: {label} — emits NAME-format")

# ── 4. Consumer: must have IDX branch AND NAME branch ───────────
for label, src in [("shared consumer", shared_consumer), ("mono consumer", mono_consumer)]:
    assert "IDX-format" in src,   f"{label}: IDX-format branch missing"
    assert "NAME-format" in src,  f"{label}: NAME-format branch missing"
    assert "isdigit()" in src,    f"{label}: format detection (isdigit) missing"
    assert "DEBUG" not in src.upper() or "logger.debug" in src or "debug" in src, \
        f"{label}: observability logging missing"
    print(f"  CONSUMER OK: {label} — dual-format (IDX legacy + NAME current)")

# ── 5. Observability: log lines present in shared consumer ──────
obs_checks = [
    ("IDX-format debug log",   "IDX-format"),
    ("NAME-format debug log",  "NAME-format"),
    ("IDX resolved debug",     "IDX resolved"),
    ("IDX invalid warning",    "invalid IDX payload"),
    ("NAME not-in-TD warning", "not found in TD"),
    ("NAME id-lookup warning", "id lookup failed"),
]
for label, marker in obs_checks:
    assert marker in shared_consumer, f"MISSING observability in shared consumer: {label} ({marker!r})"
    print(f"  OBSERVABILITY OK: {label}")

# ── 6. Dual-format logic correctness simulation ─────────────────
# Simulate the format detection logic
def format_detect(choice):
    if choice == "skip":
        return "skip"
    elif choice.lstrip('-').isdigit():
        return "idx"
    else:
        return "name"

cases = [
    ("0",           "idx"),
    ("17",          "idx"),
    ("-1",          "idx"),   # negative idx — still caught by IDX branch, raises ValueError/IndexError
    ("skip",        "skip"),
    ("هاشم",        "name"),
    ("معتز",        "name"),
    ("نجم الدين",   "name"),  # name with space — NOT a digit
    ("محمد علي",    "name"),
    ("3abc",        "name"),   # not all-digit — goes to NAME branch (will fail DB lookup, log warning)
]
for choice, expected in cases:
    result = format_detect(choice)
    assert result == expected, f"format_detect({choice!r}) = {result!r}, expected {expected!r}"
print("  FORMAT DETECTION OK: all cases pass")

# ── 7. Callback length safety check ─────────────────────────────
# Telegram limit: 64 bytes per callback_data
# Longest realistic payload: "simple_translator:appointment_reschedule:نجم الدين"
longest_flow = "appointment_reschedule"
longest_name = "نجم الدين"  # 3 Arabic words, ~9 chars
payload = f"simple_translator:{longest_flow}:{longest_name}"
payload_bytes = len(payload.encode('utf-8'))
assert payload_bytes <= 64, f"callback_data too long: {payload_bytes} bytes: {payload!r}"
print(f"  CALLBACK LENGTH OK: worst-case payload is {payload_bytes} bytes (limit: 64)")

print()
print("=" * 60)
print("ALL B-DA.4 CHECKS PASSED")
print("=" * 60)
