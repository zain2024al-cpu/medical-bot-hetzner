# ================================================
# services/case_summary_service.py
# 📋 Structured operational patient summary — rule-based only.
#
# Architecture:
#   build_full_summary()
#     └── _build_department_sections()   ← groups by dept/specialty
#     └── _build_followup_section()      ← latest follow-up state
#     └── _build_medications_section()   ← unified meds / treatment
#
# Each department section reads N reports for that department and
# produces ONE coherent narrative block — not a raw consultation list.
#
# Future modules (healthcare, pharmacy, residency, services) plug in
# as additional entries in SECTION_BUILDERS at the bottom.
# ================================================

from __future__ import annotations
from collections import defaultdict
from typing import Callable


# ─── Helpers ─────────────────────────────────────────────

_JUNK_EXACT = {"", "none", "لا يوجد", "—", "لايوجد", "null", "n/a", "na", "لا", ".", "-"}
_JUNK_PREFIX = ("لا يوجد", "لايوجد", "لا ", "لم يوجد")


def _is_junk(text: str) -> bool:
    t = text.strip()
    tl = t.lower()
    if tl in _JUNK_EXACT:
        return True
    for prefix in _JUNK_PREFIX:
        if tl.startswith(prefix) and len(t) < 12:
            return True
    # Reject strings that are mostly emoji / UI labels (contain ✏️ 🔬 etc.)
    # A field value with more than 2 emoji characters is UI noise
    emoji_count = sum(1 for ch in t if ord(ch) > 0x2000)
    if emoji_count > 2:
        return True
    return False


def _v(row: dict, *keys) -> str:
    for k in keys:
        val = row.get(k)
        if not val:
            continue
        first_line = str(val).strip().splitlines()[0].strip()
        if not _is_junk(first_line) and len(first_line) > 1:
            return first_line
    return ""


def _v_full(row: dict, key: str) -> str:
    """Like _v but returns full multi-line value (for decisions/notes)."""
    val = row.get(key)
    if not val:
        return ""
    t = str(val).strip()
    if t.lower() in _JUNK or len(t) <= 1:
        return ""
    return t


_MONTHS = {
    1: "يناير", 2: "فبراير", 3: "مارس",  4: "أبريل",
    5: "مايو",  6: "يونيو",  7: "يوليو", 8: "أغسطس",
    9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
}


def _date_str(val) -> str:
    if not val:
        return ""
    try:
        from datetime import datetime as _dt
        if isinstance(val, _dt):
            return f"{val.day} {_MONTHS.get(val.month, '')} {val.year}"
        s = str(val)[:10]
        y, m, d = int(s[:4]), int(s[5:7]), int(s[8:10])
        return f"{d} {_MONTHS.get(m, '')} {y}"
    except Exception:
        return str(val)[:10]


def _unique(items: list[str], limit: int = 4) -> list[str]:
    seen: set[str] = set()
    out = []
    for item in items:
        if not item:
            continue
        t = item.strip().rstrip(".,،")   # normalise trailing punctuation
        key = " ".join(t.split()).lower()  # collapse whitespace for dedup key
        if key and key not in seen and not _is_junk(t):
            seen.add(key)
            out.append(t)
            if len(out) >= limit:
                break
    return out


def _bullet(text: str) -> str:
    return f"• {text}"


# ─── Department / specialty grouping ─────────────────────

# Maps raw department strings → canonical Arabic label + icon.
# Unrecognised departments fall through to a generic label.
_DEPT_CANON: dict[str, tuple[str, str]] = {
    # keyword (Arabic or English, lowercased for matching)
    "عظ":              ("🦴", "العظام والمفاصل"),
    "مفص":             ("🦴", "العظام والمفاصل"),
    "orthop":          ("🦴", "العظام والمفاصل"),
    "مخ":              ("🧠", "المخ والأعصاب"),
    "أعصاب":           ("🧠", "المخ والأعصاب"),
    "عصب":             ("🧠", "المخ والأعصاب"),
    "neuro":           ("🧠", "المخ والأعصاب"),
    "قلب":             ("❤️", "القلب والأوعية"),
    "heart":           ("❤️", "القلب والأوعية"),
    "cardio":          ("❤️", "القلب والأوعية"),
    "جراح":            ("🔴", "الجراحة العامة"),
    "surg":            ("🔴", "الجراحة العامة"),
    "عيون":            ("👁", "طب العيون"),
    "ophthal":         ("👁", "طب العيون"),
    "أطفال":           ("👶", "طب الأطفال"),
    "pediatr":         ("👶", "طب الأطفال"),
    "نساء":            ("🤰", "النساء والتوليد"),
    "ولادة":           ("🤰", "النساء والتوليد"),
    "gynaec":          ("🤰", "النساء والتوليد"),
    "obstetr":         ("🤰", "النساء والتوليد"),
    "باطن":            ("🩺", "الطب الباطني"),
    "داخل":            ("🩺", "الطب الباطني"),
    "internal":        ("🩺", "الطب الباطني"),
    "جلد":             ("💊", "الأمراض الجلدية"),
    "dermat":          ("💊", "الأمراض الجلدية"),
    "أورام":           ("☢️", "الأورام والعلاج الإشعاعي"),
    "oncol":           ("☢️", "الأورام والعلاج الإشعاعي"),
    "إشعاع":           ("☢️", "الأورام والعلاج الإشعاعي"),
    "أشعة":            ("🔬", "الأشعة والتصوير"),
    "radiol":          ("🔬", "الأشعة والتصوير"),
    "تصوير":           ("🔬", "الأشعة والتصوير"),
    "imaging":         ("🔬", "الأشعة والتصوير"),
    "طوارئ":           ("🚨", "الطوارئ"),
    "emerg":           ("🚨", "الطوارئ"),
    "مختبر":           ("🧪", "المختبر والتحاليل"),
    "تحليل":           ("🧪", "المختبر والتحاليل"),
    "lab":             ("🧪", "المختبر والتحاليل"),
    "ترقيد":           ("🛏️", "الترقيد"),
    "inpatient":       ("🛏️", "الترقيد"),
    # Rehabilitation / physiotherapy
    "تأهيل":           ("🏋️", "العلاج الطبيعي والتأهيل"),
    "طبيعي":           ("🏋️", "العلاج الطبيعي والتأهيل"),
    "فيزياء":          ("🏋️", "العلاج الطبيعي والتأهيل"),
    "physiother":      ("🏋️", "العلاج الطبيعي والتأهيل"),
    "physical ther":   ("🏋️", "العلاج الطبيعي والتأهيل"),
    "rehab":           ("🏋️", "العلاج الطبيعي والتأهيل"),
    # Urology
    "بول":             ("🫘", "المسالك البولية"),
    "urol":            ("🫘", "المسالك البولية"),
    # Endocrine / diabetes
    "غدد":             ("🩸", "الغدد والسكري"),
    "سكري":            ("🩸", "الغدد والسكري"),
    "endocrin":        ("🩸", "الغدد والسكري"),
    # ENT
    "أنف":             ("👂", "الأنف والأذن والحنجرة"),
    "أذن":             ("👂", "الأنف والأذن والحنجرة"),
    "ent":             ("👂", "الأنف والأذن والحنجرة"),
}


def _canonical_dept(dept: str, specialty: str) -> tuple[str, str]:
    """Return (icon, label) for a department/specialty string."""
    search = (dept + " " + specialty).lower()
    for keyword, (icon, label) in _DEPT_CANON.items():
        if keyword in search:
            return icon, label
    # Fall back to raw dept name (truncated) or specialty
    display = dept or specialty
    if display:
        return "🏥", display[:60]
    return "🏥", "استشارات عامة"


# Actions that carry no clinical narrative value — excluded from summary
_SKIP_ACTIONS = {"أشعة", "فحص مخبري", "تأجيل موعد"}


def _group_by_department(reports: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """Group reports by (icon, canonical_label). Skips non-clinical action types."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in reports:
        action = _v(r, "medical_action")
        # Skip radiology, lab tests, and appointment reschedule entirely
        if action in _SKIP_ACTIONS:
            continue
        dept = _v(r, "department")
        spec = _v(r, "specialty")
        if action == "علاج إشعاعي" or _v(r, "radiation_therapy_type"):
            key = ("☢️", "الأورام والعلاج الإشعاعي")
        elif action == "طوارئ":
            key = ("🚨", "الطوارئ")
        elif action == "ترقيد":
            key = ("🛏️", "الترقيد")
        elif dept or spec:
            key = _canonical_dept(dept, spec)
        else:
            key = ("🏥", "استشارات عامة")
        groups[key].append(r)
    return dict(groups)


# ─── Narrative builders ───────────────────────────────────

_MAX_FIELD_LEN = 120   # truncate any single field value at this length


def _trim(text: str, limit: int = _MAX_FIELD_LEN) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _narrate_general_dept(icon: str, label: str, reports: list[dict]) -> str:
    """
    Builds one coherent narrative block for a group of same-department reports.
    Deduplicates and truncates — never dumps raw field values verbatim.
    """
    lines: list[str] = []
    n = len(reports)
    doctors  = _unique([_v(r, "doctor_name") for r in reports], limit=3)
    complain = _unique([_v(r, "complaint_text") for r in reports], limit=2)
    diagnose = _unique([_v(r, "diagnosis") for r in reports], limit=2)
    decision = _unique([_v(r, "doctor_decision") for r in reports], limit=2)
    actions  = _unique([_v(r, "medical_action") for r in reports if _v(r, "medical_action")])

    # Visit count
    if n == 1:
        visit_line = "راجع المريض هذا القسم مرة واحدة"
    else:
        visit_line = f"راجع المريض هذا القسم {n} مرات"
    if doctors:
        visit_line += f" مع {' و'.join(doctors[:2])}"
    lines.append(_bullet(visit_line + "."))

    # Complaints
    if complain:
        joined = " و".join(_trim(c) for c in complain)
        lines.append(_bullet(f"حضر بسبب: {joined}."))

    # Non-generic actions
    meaningful_actions = [a for a in actions if a not in ("استشارة جديدة", "مراجعة")]
    if meaningful_actions:
        lines.append(_bullet(f"تم: {' و'.join(meaningful_actions[:3])}."))

    # Diagnoses — single bullet, comma-separated
    real_diagnose = [d for d in diagnose if not _is_junk(d) and len(d) > 3]
    if real_diagnose:
        joined = "، ".join(_trim(d) for d in real_diagnose[:2])
        lines.append(_bullet(f"التشخيص: {joined}."))

    # Doctor decisions — skip if they're just restating diagnosis or junk
    _diag_label = "التشخيص:"
    informative = []
    for dec in decision:
        if not dec or len(dec) < 6:
            continue
        # Strip "التشخيص: ..." prefix before checking
        cleaned = dec[len(_diag_label):].strip() if dec.startswith(_diag_label) else dec
        if _is_junk(cleaned):
            continue
        if cleaned in complain or cleaned in diagnose:
            continue
        informative.append(cleaned)
    informative.sort(key=len)
    for dec in informative[:1]:
        lines.append(_bullet(_trim(dec) + "."))

    return f"{icon} {label}\n" + "\n".join(lines)


def _narrate_radiology(icon: str, label: str, reports: list[dict]) -> str:
    lines: list[str] = []
    types = _unique([_v(r, "radiology_type") for r in reports], limit=4)
    decisions = _unique([_v(r, "doctor_decision") for r in reports], limit=2)

    if types:
        lines.append(_bullet(f"تم إجراء: {' و'.join(types)}."))
    elif reports:
        lines.append(_bullet(f"تم إجراء {len(reports)} فحص إشعاعي."))

    for dec in decisions:
        if dec:
            lines.append(_bullet(dec + "."))

    return f"{icon} {label}\n" + "\n".join(lines) if lines else ""


def _narrate_radiation_therapy(icon: str, label: str, reports: list[dict]) -> str:
    lines: list[str] = []
    types   = _unique([_v(r, "radiation_therapy_type") for r in reports], limit=3)
    recs    = _unique([_v(r, "radiation_therapy_recommendations") for r in reports], limit=2)
    notes   = _unique([_v(r, "radiation_therapy_final_notes") for r in reports], limit=2)
    done    = any(r.get("radiation_therapy_completed") for r in reports)
    sess    = _v(reports[0], "radiation_therapy_session_number")
    rem     = _v(reports[0], "radiation_therapy_remaining")

    if types:
        lines.append(_bullet(f"تلقى المريض: {' و'.join(types)}."))
    if sess:
        lines.append(_bullet(f"جلسة رقم: {sess}."))
    if rem:
        lines.append(_bullet(f"الجلسات المتبقية: {rem}."))
    for r in recs:
        lines.append(_bullet(r + "."))
    for n in notes:
        lines.append(_bullet(n + "."))
    if done:
        lines.append(_bullet("✅ اكتمل العلاج الإشعاعي."))

    return f"{icon} {label}\n" + "\n".join(lines) if lines else ""


def _narrate_emergency(icon: str, label: str, reports: list[dict]) -> str:
    lines: list[str] = []
    complain = _unique([_v(r, "complaint_text") for r in reports], limit=2)
    decision = _unique([_v(r, "doctor_decision") for r in reports], limit=2)
    dates    = [_date_str(r.get("report_date")) for r in reports if r.get("report_date")]

    if complain:
        lines.append(_bullet(f"دخل الطوارئ بسبب: {' و'.join(complain)}."))
    elif reports:
        lines.append(_bullet(f"تم تلقي المريض في قسم الطوارئ {len(reports)} مرة."))
    for dec in decision:
        lines.append(_bullet(dec + "."))
    if dates:
        lines.append(_bullet(f"آخر مرة: {dates[0]}."))

    return f"{icon} {label}\n" + "\n".join(lines) if lines else ""


def _narrate_admission(icon: str, label: str, reports: list[dict]) -> str:
    lines: list[str] = []
    rooms   = _unique([_v(r, "room_number") for r in reports], limit=2)
    depts   = _unique([_v(r, "department") for r in reports], limit=2)
    doctors = _unique([_v(r, "doctor_name") for r in reports], limit=2)
    dates   = [_date_str(r.get("report_date")) for r in reports if r.get("report_date")]

    lines.append(_bullet(f"تم ترقيد المريض {len(reports)} مرة."))
    if depts:
        lines.append(_bullet(f"الأقسام: {' و'.join(depts)}."))
    if rooms:
        lines.append(_bullet(f"الغرفة: {rooms[0]}."))
    if doctors:
        lines.append(_bullet(f"تحت إشراف: {' و'.join(doctors)}."))
    if dates:
        lines.append(_bullet(f"آخر ترقيد: {dates[0]}."))

    return f"{icon} {label}\n" + "\n".join(lines) if lines else ""


# Dispatch table: maps canonical label → specialist narrator
_NARRATORS: dict[str, Callable] = {
    "الأورام والعلاج الإشعاعي":  _narrate_radiation_therapy,
    "الطوارئ":                    _narrate_emergency,
    "الترقيد":                    _narrate_admission,
}


def _build_department_sections(reports: list[dict]) -> list[str]:
    """Return one narrative block per department, ordered by report count desc."""
    groups = _group_by_department(reports)
    # Sort: largest group first
    sorted_groups = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)

    sections: list[str] = []
    for (icon, label), group_reports in sorted_groups:
        narrator = _NARRATORS.get(label, _narrate_general_dept)
        text = narrator(icon, label, group_reports)
        if text and text.strip():
            sections.append(text.strip())
    return sections


# ─── Stand-alone sections (cross-department) ─────────────

def _build_medications_section(reports: list[dict]) -> str | None:
    meds  = _unique([_v(r, "medications")     for r in reports], limit=4)
    plans = _unique([_v(r, "treatment_plan")  for r in reports], limit=3)
    if not meds and not plans:
        return None

    lines: list[str] = []
    for m in meds:
        lines.append(_bullet(m + "."))
    for p in plans:
        lines.append(_bullet(f"خطة: {p}."))
    return "💊 العلاج والأدوية\n" + "\n".join(lines)


def _build_followup_section(reports: list[dict]) -> str | None:
    lines: list[str] = []

    # Latest standard follow-up
    for r in reports:
        fdate   = _date_str(r.get("followup_date"))
        fdept   = _v(r, "followup_department")
        freason = _v(r, "followup_reason")
        if fdate or fdept or freason:
            parts: list[str] = []
            if fdate:   parts.append(f"موعد مراجعة: {fdate}")
            if fdept:   parts.append(f"قسم {fdept}")
            if freason: parts.append(freason)
            lines.append(_bullet("، ".join(parts) + "."))
            break

    # Radiation therapy return
    for r in reports:
        rt_rd  = _date_str(r.get("radiation_therapy_return_date"))
        rt_rr  = _v(r, "radiation_therapy_return_reason")
        if rt_rd or rt_rr:
            parts = ["متابعة إشعاعية"]
            if rt_rd: parts.append(f"عودة {rt_rd}")
            if rt_rr: parts.append(rt_rr)
            lines.append(_bullet("، ".join(parts) + "."))
            break

    # Current case status (latest report)
    for r in reports:
        cs = _v(r, "case_status")
        if cs:
            lines.append(_bullet(f"الحالة الراهنة: {cs}."))
            break

    # Latest notes
    for r in reports:
        n = _v(r, "notes")
        if n:
            lines.append(_bullet(n + "."))
            break

    if not lines:
        return None
    return "📌 المتابعة الحالية\n" + "\n".join(lines)


# ─── Main composer ────────────────────────────────────────

def build_full_summary(
    patient_name: str,
    hospital_name: str,
    reports: list[dict],
    last_date,
) -> str:
    """
    Compose the full structured operational patient summary.

    Extension point: add future module builders to EXTRA_SECTIONS.
    Each builder receives the full reports list and returns str|None.
    """
    SEP = "━━━━━━━━━━━━━━"

    # ── Header ──
    lines: list[str] = []
    lines.append("📋 *ملخص الحالة*")
    lines.append("")
    lines.append(f"👤 *المريض:*\n{patient_name}")
    if hospital_name:
        lines.append(f"\n🏥 *المستشفى:*\n{hospital_name}")
    lines.append(f"\n📊 *إجمالي التقارير:* {len(reports)}")

    # ── Department sections ──
    dept_sections = _build_department_sections(reports)
    for section in dept_sections:
        lines.append(f"\n{SEP}\n")
        lines.append(section)

    # ── Cross-department sections ──
    # Future modules (healthcare, pharmacy, residency, services) go here.
    EXTRA_SECTIONS: list[Callable] = [
        _build_medications_section,
        _build_followup_section,
    ]
    for builder in EXTRA_SECTIONS:
        result = builder(reports)
        if result:
            lines.append(f"\n{SEP}\n")
            lines.append(result)

    # ── Footer ──
    lines.append(f"\n{SEP}")
    if last_date:
        lines.append(f"\n📅 *آخر تحديث:*\n{_date_str(last_date)}")

    return "\n".join(lines)
