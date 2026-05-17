# ================================================
# services/case_summary_service.py
# 📋 Structured operational patient summary — rule-based, no AI APIs.
#
# Key design decisions based on production data analysis:
#
#   1. medical_action drives the narrative, not department alone.
#      Actions: مراجعة/عودة دورية, ترقيد, متابعة في الرقود, عملية,
#               استشارة جديدة, استشارة مع قرار عملية, استشارة أخيرة,
#               خروج من المستشفى, علاج طبيعي, جلسة إشعاعي, طوارئ.
#      Excluded: تأجيل موعد, أشعة وفحوصات (no narrative value).
#
#   2. doctor_decision contains structured sub-fields in free text:
#      "التشخيص النهائي:", "قرار الطبيب:", "نسبة نجاح العملية:",
#      "التوصيات الطبية:", "تفاصيل العملية:", "ملاحظات:" etc.
#      We parse these to extract richer content.
#
#   3. Departments are bilingual (Arabic | English). We normalise
#      by taking the Arabic part before "|".
#
#   4. Groups: CLINICAL VISITS, SURGERY, ADMISSION, DISCHARGE,
#      PHYSIOTHERAPY, ONCOLOGY/RADIATION, EMERGENCY.
#      Each group produces ONE narrative block.
#
# Extension: add future module builders to EXTRA_SECTIONS list
# inside build_full_summary().
# ================================================

from __future__ import annotations
from collections import defaultdict
from typing import Callable


# ─── Basic helpers ────────────────────────────────────────

_MONTHS = {
    1: "يناير", 2: "فبراير", 3: "مارس",  4: "أبريل",
    5: "مايو",  6: "يونيو",  7: "يوليو", 8: "أغسطس",
    9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
}

# Actions excluded entirely from summary
_SKIP_ACTIONS = {
    "تأجيل موعد", "تأجيل موعد━",
    "أشعة وفحوصات", "أشعة سينية", "أشعة",
    "عرض الفحوصات",
}

# Action normalisation map (typos / variants → canonical)
_ACTION_NORM = {
    "مراجعه":                     "مراجعة / عودة دورية",
    "عودة":                       "مراجعة / عودة دورية",
    "متابعة رقود":                "متابعة في الرقود",
    "مرقد":                       "ترقيد",
    "رقود - عناية مركزة":         "ترقيد",
    "ترقيد الحاله من أجل اجراء ابره الحبال الصوتي الايسر حيث سيتم الاجراء تحت التخدير العام":
                                   "ترقيد",
    "استشاره جديده":              "استشارة جديدة",
    "استشارة - جديدة":            "استشارة جديدة",
    "استشارة جديدة━":             "استشارة جديدة",
    "استشارة - مراجعة الطبيب":    "مراجعة / عودة دورية",
    "لم يتم شب":                  None,   # invalid — skip
    "علاج طبيعي وإعادة تأهيل":   "علاج طبيعي",
}

# Action → group key
_ACTION_GROUP = {
    "استشارة جديدة":              "clinical",
    "استشارة":                    "clinical",
    "استشارة مع قرار عملية":      "clinical",
    "استشارة أخيرة":              "clinical",
    "مراجعة / عودة دورية":        "clinical",
    "متابعة في الرقود":           "admission",
    "ترقيد":                      "admission",
    "عملية":                      "surgery",
    "خروج من المستشفى":           "discharge",
    "علاج طبيعي":                 "physio",
    "جلسة إشعاعي":                "oncology",
    "طوارئ":                      "emergency",
}


def _normalise_action(action: str) -> str | None:
    if not action:
        return None
    a = action.strip()
    return _ACTION_NORM.get(a, a)


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


def _clean_dept(dept: str) -> str:
    """'جراحة الصدر | Thoracic Surgery' → 'جراحة الصدر'"""
    if not dept:
        return ""
    return dept.split("|")[0].strip()


# ─── Junk / noise filtering ───────────────────────────────

_JUNK_EXACT = {
    "", "none", "لا يوجد", "—", "لايوجد", "null",
    "n/a", "na", "لا", ".", "-", "لم يوجد",
}
_JUNK_PREFIX = ("لا يوجد", "لايوجد")


def _is_junk(text: str) -> bool:
    t = text.strip()
    tl = t.lower()
    if tl in _JUNK_EXACT:
        return True
    for p in _JUNK_PREFIX:
        if tl.startswith(p) and len(t) < 12:
            return True
    # UI noise: strings with more than 2 non-BMP / emoji chars
    if sum(1 for ch in t if ord(ch) > 0x2000) > 2:
        return True
    return False


def _v(row: dict, *keys) -> str:
    """Return first clean value (full text, not just first line)."""
    for k in keys:
        val = row.get(k)
        if not val:
            continue
        full = str(val).strip()
        if not _is_junk(full.splitlines()[0].strip()) and len(full) > 1:
            return full
    return ""


def _unique(items: list[str], limit: int = 3) -> list[str]:
    seen: set[str] = set()
    out = []
    for item in items:
        if not item:
            continue
        t = item.strip().rstrip(".,،")
        key = " ".join(t.split()).lower()
        if key and key not in seen and not _is_junk(t):
            seen.add(key)
            out.append(t)
            if len(out) >= limit:
                break
    return out


def _trim(text: str, limit: int = 300) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


# ─── Structured field parser for doctor_decision ─────────

# Sub-labels that appear inside doctor_decision free text
_DECISION_LABELS = [
    "التشخيص النهائي",
    "التشخيص",
    "قرار الطبيب",
    "التوصيات الطبية",
    "تفاصيل العملية",
    "ملاحظات",
    "نسبة نجاح العملية",
    "نسبة الاستفادة من العملية",
    "الفحوصات المطلوبة",
]


def _parse_decision(decision_text: str) -> dict[str, str]:
    """
    Parse 'التشخيص: X\nقرار الطبيب: Y\n...' into a dict.
    Returns {'التشخيص': 'X', 'قرار الطبيب': 'Y', ...}
    """
    if not decision_text:
        return {}
    result: dict[str, str] = {}
    lines = decision_text.strip().splitlines()
    current_key: str | None = None
    current_val: list[str] = []

    for line in lines:
        line = line.strip()
        matched = False
        for label in _DECISION_LABELS:
            if line.startswith(label + ":") or line.startswith(label + "："):
                if current_key and current_val:
                    val = " ".join(current_val).strip()
                    if not _is_junk(val):
                        result[current_key] = val
                current_key = label
                rest = line[len(label) + 1:].strip()
                current_val = [rest] if rest and not _is_junk(rest) else []
                matched = True
                break
        if not matched and line and current_key:
            current_val.append(line)

    if current_key and current_val:
        val = " ".join(current_val).strip()
        if not _is_junk(val):
            result[current_key] = val

    return result


def _extract_from_decisions(reports: list[dict], key: str, limit: int = 2) -> list[str]:
    """Extract a specific sub-field from all parsed decision texts."""
    vals = []
    for r in reports:
        parsed = _parse_decision(r.get("doctor_decision") or "")
        v = parsed.get(key, "").strip()
        if v and not _is_junk(v) and len(v) > 2:
            vals.append(v)
    return _unique(vals, limit=limit)


# ─── Report grouping ─────────────────────────────────────

def _group_reports(reports: list[dict]) -> dict[str, list[dict]]:
    """Group by action group key. Skip excluded actions."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in reports:
        raw_action = _v(r, "medical_action")
        action = _normalise_action(raw_action)
        if not action or action in _SKIP_ACTIONS:
            continue
        group = _ACTION_GROUP.get(action, "clinical")
        groups[group].append(r)
    return dict(groups)


# ─── Narrative builders — one per group ──────────────────

def _bullet(text: str) -> str:
    return f"• {text}"


def _build_clinical_section(reports: list[dict]) -> str | None:
    """
    Covers: استشارة جديدة / مراجعة / استشارة مع قرار عملية / استشارة أخيرة
    Narrative: why came → what was found → doctor decision → final status
    """
    if not reports:
        return None

    n = len(reports)
    depts   = _unique([_clean_dept(_v(r, "department")) for r in reports], limit=3)
    doctors = _unique([_v(r, "doctor_name") for r in reports], limit=2)
    complain = _unique([_v(r, "complaint_text") for r in reports], limit=2)
    diagnoses = _extract_from_decisions(reports, "التشخيص النهائي") \
                or _extract_from_decisions(reports, "التشخيص") \
                or _unique([_v(r, "diagnosis") for r in reports], limit=2)
    decisions = _extract_from_decisions(reports, "قرار الطبيب", limit=2)
    recs      = _extract_from_decisions(reports, "التوصيات الطبية", limit=1)

    lines: list[str] = []

    # Visit summary
    if n == 1:
        visit = "راجع المريض الأطباء مرة واحدة"
    else:
        visit = f"راجع المريض الأطباء {n} مرة"
    if depts:
        visit += f" في أقسام: {' و'.join(depts[:2])}"
    if doctors:
        visit += f" — {' و'.join(doctors)}"
    lines.append(_bullet(visit + "."))

    # Reason for visit
    if complain:
        joined = " و".join(_trim(c) for c in complain)
        lines.append(_bullet(f"حضر بسبب: {joined}."))

    # Diagnosis
    if diagnoses:
        joined = "، ".join(_trim(d) for d in diagnoses)
        lines.append(_bullet(f"التشخيص: {joined}."))

    # Doctor decisions
    for dec in decisions:
        lines.append(_bullet(_trim(dec) + "."))

    # Recommendations
    for rec in recs:
        lines.append(_bullet(f"التوصية: {_trim(rec)}."))

    # Check for surgery decision
    surgery_pct = _extract_from_decisions(reports, "نسبة نجاح العملية", limit=1)
    if surgery_pct:
        lines.append(_bullet(f"نسبة نجاح العملية المقترحة: {surgery_pct[0]}."))

    return "🩺 الحالة الطبية والاستشارات\n" + "\n".join(lines)


def _build_surgery_section(reports: list[dict]) -> str | None:
    if not reports:
        return None

    n = len(reports)
    depts   = _unique([_clean_dept(_v(r, "department")) for r in reports], limit=2)
    doctors = _unique([_v(r, "doctor_name") for r in reports], limit=2)
    details = _extract_from_decisions(reports, "تفاصيل العملية", limit=2)
    notes   = _extract_from_decisions(reports, "ملاحظات", limit=1)
    recs    = _extract_from_decisions(reports, "التوصيات الطبية", limit=1)

    lines: list[str] = []

    op_text = f"تم إجراء {n} عملية جراحية" if n > 1 else "تم إجراء عملية جراحية"
    if depts:
        op_text += f" في قسم {' و'.join(depts)}"
    if doctors:
        op_text += f" — د. {' و'.join(doctors)}"
    lines.append(_bullet(op_text + "."))

    for det in details:
        lines.append(_bullet(_trim(det) + "."))
    for note in notes:
        lines.append(_bullet(_trim(note) + "."))
    for rec in recs:
        lines.append(_bullet(f"التوصية بعد العملية: {_trim(rec)}."))

    return "🔴 العمليات الجراحية\n" + "\n".join(lines)


def _build_admission_section(reports: list[dict]) -> str | None:
    if not reports:
        return None

    n = len(reports)
    depts   = _unique([_clean_dept(_v(r, "department")) for r in reports], limit=3)
    doctors = _unique([_v(r, "doctor_name") for r in reports], limit=2)
    rooms   = _unique([_v(r, "room_number") for r in reports], limit=1)
    decisions = _extract_from_decisions(reports, "قرار الطبيب", limit=1)

    lines: list[str] = []

    adm_text = f"تم ترقيد المريض وتلقّى {n} جلسة متابعة في الرقود"
    if depts:
        adm_text += f" — أقسام: {' و'.join(depts[:2])}"
    lines.append(_bullet(adm_text + "."))

    if rooms:
        lines.append(_bullet(f"الغرفة: {rooms[0]}."))
    if doctors:
        lines.append(_bullet(f"تحت إشراف: {' و'.join(doctors)}."))
    for dec in decisions:
        lines.append(_bullet(_trim(dec) + "."))

    return "🛏️ الترقيد والمتابعة\n" + "\n".join(lines)


def _build_discharge_section(reports: list[dict]) -> str | None:
    if not reports:
        return None

    dates    = [_date_str(r.get("report_date")) for r in reports if r.get("report_date")]
    recs     = _extract_from_decisions(reports, "التوصيات الطبية", limit=2)
    decisions = _extract_from_decisions(reports, "قرار الطبيب", limit=1)

    lines: list[str] = []
    discharge_text = "تم خروج المريض من المستشفى"
    if dates:
        discharge_text += f" بتاريخ {dates[0]}"
    lines.append(_bullet(discharge_text + "."))

    for dec in decisions:
        lines.append(_bullet(_trim(dec) + "."))
    for rec in recs:
        lines.append(_bullet(f"تعليمات الخروج: {_trim(rec)}."))

    return "✅ الخروج من المستشفى\n" + "\n".join(lines)


def _build_physio_section(reports: list[dict]) -> str | None:
    if not reports:
        return None

    n = len(reports)
    doctors   = _unique([_v(r, "doctor_name") for r in reports], limit=2)
    decisions = _extract_from_decisions(reports, "قرار الطبيب", limit=1)
    recs      = _extract_from_decisions(reports, "التوصيات الطبية", limit=1)

    lines: list[str] = []
    lines.append(_bullet(f"تلقّى المريض {n} جلسة علاج طبيعي وإعادة تأهيل."))
    if doctors:
        lines.append(_bullet(f"المعالج: {' و'.join(doctors)}."))
    for dec in decisions:
        lines.append(_bullet(_trim(dec) + "."))
    for rec in recs:
        lines.append(_bullet(f"التوصية: {_trim(rec)}."))

    return "🏋️ العلاج الطبيعي وإعادة التأهيل\n" + "\n".join(lines)


def _build_oncology_section(reports: list[dict]) -> str | None:
    if not reports:
        return None

    n       = len(reports)
    types   = _unique([_v(r, "radiation_therapy_type") for r in reports], limit=2)
    sess    = _v(reports[0], "radiation_therapy_session_number")
    rem     = _v(reports[0], "radiation_therapy_remaining")
    done    = any(r.get("radiation_therapy_completed") for r in reports)
    recs    = _unique([_v(r, "radiation_therapy_recommendations") for r in reports], limit=1)

    lines: list[str] = []
    if types:
        lines.append(_bullet(f"تلقّى المريض: {' و'.join(types)}."))
    else:
        lines.append(_bullet(f"تلقّى المريض {n} جلسة إشعاعية."))
    if sess:
        lines.append(_bullet(f"الجلسة رقم: {sess}."))
    if rem:
        lines.append(_bullet(f"الجلسات المتبقية: {rem}."))
    for rec in recs:
        lines.append(_bullet(_trim(rec) + "."))
    if done:
        lines.append(_bullet("✅ اكتمل العلاج الإشعاعي."))

    return "☢️ العلاج الإشعاعي\n" + "\n".join(lines)


def _build_emergency_section(reports: list[dict]) -> str | None:
    if not reports:
        return None

    n        = len(reports)
    complain = _unique([_v(r, "complaint_text") for r in reports], limit=2)
    decisions = _extract_from_decisions(reports, "قرار الطبيب", limit=1)
    dates    = [_date_str(r.get("report_date")) for r in reports if r.get("report_date")]

    lines: list[str] = []
    em_text = f"دخل المريض قسم الطوارئ {n} مرة" if n > 1 else "دخل المريض قسم الطوارئ"
    lines.append(_bullet(em_text + "."))
    if complain:
        lines.append(_bullet(f"بسبب: {' و'.join(_trim(c) for c in complain)}."))
    for dec in decisions:
        lines.append(_bullet(_trim(dec) + "."))
    if dates:
        lines.append(_bullet(f"آخر زيارة: {dates[0]}."))

    return "🚨 الطوارئ\n" + "\n".join(lines)


# ─── Follow-up section (cross-group) ─────────────────────

def _build_followup_section(reports: list[dict]) -> str | None:
    lines: list[str] = []

    # Latest standard follow-up appointment
    for r in reports:
        fdate  = _date_str(r.get("followup_date"))
        fdept  = _clean_dept(_v(r, "followup_department"))
        freason = _v(r, "followup_reason")
        if fdate or fdept or freason:
            parts: list[str] = []
            if fdate:   parts.append(f"موعد المراجعة: {fdate}")
            if fdept:   parts.append(f"في قسم {fdept}")
            if freason: parts.append(_trim(freason))
            lines.append(_bullet("، ".join(parts) + "."))
            break

    # Latest radiation therapy return
    for r in reports:
        rt_rd  = _date_str(r.get("radiation_therapy_return_date"))
        rt_rr  = _v(r, "radiation_therapy_return_reason")
        if rt_rd or rt_rr:
            parts = ["متابعة إشعاعية"]
            if rt_rd: parts.append(f"عودة {rt_rd}")
            if rt_rr: parts.append(_trim(rt_rr))
            lines.append(_bullet("، ".join(parts) + "."))
            break

    # Case status
    for r in reports:
        cs = _v(r, "case_status")
        if cs and not _is_junk(cs):
            lines.append(_bullet(f"حالة الملف: {_trim(cs)}."))
            break

    if not lines:
        return None
    return "📌 المتابعة والحالة الراهنة\n" + "\n".join(lines)


# ─── Medications section (cross-group) ───────────────────

def _build_medications_section(reports: list[dict]) -> str | None:
    meds  = _unique([_v(r, "medications")    for r in reports], limit=3)
    plans = _unique([_v(r, "treatment_plan") for r in reports], limit=2)
    if not meds and not plans:
        return None
    lines: list[str] = []
    for m in meds:
        lines.append(_bullet(_trim(m) + "."))
    for p in plans:
        lines.append(_bullet(f"خطة العلاج: {_trim(p)}."))
    return "💊 الأدوية والعلاج\n" + "\n".join(lines)


# ─── Group → builder dispatch ────────────────────────────

_GROUP_BUILDERS: dict[str, Callable] = {
    "clinical":   _build_clinical_section,
    "surgery":    _build_surgery_section,
    "admission":  _build_admission_section,
    "discharge":  _build_discharge_section,
    "physio":     _build_physio_section,
    "oncology":   _build_oncology_section,
    "emergency":  _build_emergency_section,
}

# Preferred display order
_GROUP_ORDER = [
    "emergency", "clinical", "surgery",
    "admission", "discharge", "physio", "oncology",
]


# ─── Main composer ────────────────────────────────────────

def build_full_summary(
    patient_name: str,
    hospital_name: str,
    reports: list[dict],
    last_date,
) -> str:
    """
    Compose the full structured operational patient summary.
    Extension: add future module builders to EXTRA_SECTIONS below.
    """
    SEP = "━━━━━━━━━━━━━━"

    # Header
    lines: list[str] = [
        "📋 *ملخص الحالة*", "",
        f"👤 *المريض:*\n{patient_name}",
    ]
    if hospital_name:
        lines.append(f"\n🏥 *المستشفى:*\n{hospital_name}")
    lines.append(f"\n📊 *إجمالي التقارير:* {len(reports)}")

    # Group reports by action type
    groups = _group_reports(reports)

    # Render each group in preferred order
    for group_key in _GROUP_ORDER:
        group_reports = groups.get(group_key)
        if not group_reports:
            continue
        builder = _GROUP_BUILDERS[group_key]
        section = builder(group_reports)
        if section and section.strip():
            lines.append(f"\n{SEP}\n")
            lines.append(section.strip())

    # Cross-group sections
    # Future modules (healthcare, pharmacy, residency) plug in here.
    EXTRA_SECTIONS: list[Callable] = [
        _build_medications_section,
        _build_followup_section,
    ]
    for builder in EXTRA_SECTIONS:
        result = builder(reports)
        if result:
            lines.append(f"\n{SEP}\n")
            lines.append(result.strip())

    # Footer
    lines.append(f"\n{SEP}")
    if last_date:
        lines.append(f"\n📅 *آخر تحديث:*\n{_date_str(last_date)}")

    return "\n".join(lines)
