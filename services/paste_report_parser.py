# -*- coding: utf-8 -*-
"""
تحليل نص تقرير جاهز (قالب الرسالة) إلى حقول لجدول Report.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

_AR_MONTHS = {
    "يناير": 1,
    "فبراير": 2,
    "مارس": 3,
    "أبريل": 4,
    "ابريل": 4,
    "مايو": 5,
    "يونيو": 6,
    "يوليو": 7,
    "أغسطس": 8,
    "اغسطس": 8,
    "سبتمبر": 9,
    "أكتوبر": 10,
    "اكتوبر": 10,
    "نوفمبر": 11,
    "ديسمبر": 12,
}


def _norm(s: str) -> str:
    s = s.replace("\u200f", "").replace("\u200e", "").replace("\ufeff", "")
    s = re.sub(r"\\([\\.])", r"\1", s)
    return s.strip()


def _parse_ar_report_datetime(line: str) -> Tuple[Optional[datetime], Optional[str]]:
    """
    مثال: 19 أبريل 2026 (الأحد) - 7:56 مساءً
    أو: 2026-04-19 ...
    """
    line = _norm(line)
    if not line:
        return None, None

    iso = re.match(r"^(\d{4}-\d{2}-\d{2})(?:\s+|$)", line)
    if iso:
        try:
            d = datetime.strptime(iso.group(1), "%Y-%m-%d")
            rest = line[iso.end() :].strip()
            tm = re.search(r"(\d{1,2}):(\d{2})", rest)
            visit = None
            if tm:
                visit = f"{tm.group(1)}:{tm.group(2)}"
                if "مساء" in rest or "م" in rest.split():
                    h, mi = int(tm.group(1)), int(tm.group(2))
                    if h < 12:
                        h += 12
                    visit = f"{h}:{mi:02d}"
            return d, visit or rest or None
        except ValueError:
            pass

    m = re.search(r"(\d{1,2})\s+(\S+?)\s+(\d{4})", line)
    visit_str: Optional[str] = None
    if m:
        day, mon_word, year = int(m.group(1)), _norm(m.group(2)), int(m.group(3))
        mon = _AR_MONTHS.get(mon_word)
        if mon:
            try:
                dt = datetime(year, mon, day)
            except ValueError:
                dt = None
            if dt:
                tm = re.search(r"-\s*(\d{1,2}):(\d{2})\s*(صباحاً|مساءً|ص|م)?", line)
                if tm:
                    h, mi = int(tm.group(1)), int(tm.group(2))
                    ap = tm.group(3) or ""
                    if "مساء" in ap or ap == "م":
                        if h < 12:
                            h += 12
                    elif "صباح" in ap or ap == "ص":
                        if h == 12:
                            h = 0
                    visit_str = f"{h}:{mi:02d}"
                return dt, visit_str

    return None, None


def _parse_followup_datetime(s: str) -> Optional[datetime]:
    s = _norm(s)
    if not s:
        return None
    m = re.match(r"^(\d{4}-\d{2}-\d{2})\s*-\s*(\d{1,2}):(\d{2})", s)
    if m:
        try:
            return datetime(
                int(m.group(1)[:4]),
                int(m.group(1)[5:7]),
                int(m.group(1)[8:10]),
                int(m.group(2)),
                int(m.group(3)),
            )
        except ValueError:
            pass
    m2 = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    if m2:
        try:
            return datetime.strptime(m2.group(1), "%Y-%m-%d")
        except ValueError:
            pass
    return None


def _extract_block(text: str, label_re: str, stop_res: List[str]) -> Tuple[str, str]:
    """يستخرج النص بعد تسمية حتى أول سطر يطابق أحد أنماط الإيقاف."""
    m = re.search(label_re, text, re.MULTILINE | re.DOTALL)
    if not m:
        return "", text
    rest = text[m.end() :]
    lines = rest.split("\n")
    buf: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            if buf:
                buf.append("")
            i += 1
            continue
        hit = False
        for sr in stop_res:
            if re.match(sr, stripped, re.UNICODE):
                hit = True
                break
        if hit and buf:
            break
        if hit and not buf:
            i += 1
            continue
        buf.append(line)
        i += 1
    return _norm("\n".join(buf)), text


def parse_full_report_text(raw: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    يعيد (حقول للـ Report، تحذيرات).
    حقول: report_date, visit_time, patient_name, hospital_name, department, doctor_name,
    medical_action, case_status, doctor_decision, room_number, followup_date, followup_reason,
    translator_name, complaint_text (اختياري فارغ).
    """
    warnings: List[str] = []
    text = _norm(raw)
    if len(text) < 40:
        raise ValueError("النص قصير جداً — الصق التقرير كاملاً كما في القالب.")

    out: Dict[str, Any] = {}

    # حقول سطر واحد
    def grab_line(pat: str) -> Optional[str]:
        m = re.search(pat, text, re.MULTILINE | re.IGNORECASE)
        return _norm(m.group(1)) if m else None

    date_line = grab_line(r"(?:📅🕐\s*|📅\s*)?التاريخ:\s*(.+?)(?:\n|$)")
    if not date_line:
        date_line = grab_line(r"التاريخ:\s*(.+?)(?:\n|$)")
    if date_line:
        rd, vt = _parse_ar_report_datetime(date_line)
        if rd:
            out["report_date"] = rd
        else:
            warnings.append("لم أستطع قراءة تاريخ التقرير — سيُستخدم تاريخ اليوم.")
        if vt:
            out["visit_time"] = vt
    else:
        warnings.append("لم يُعثر على «التاريخ» — سيُستخدم تاريخ ووقت الآن.")

    out["patient_name"] = grab_line(r"👤\s*اسم المريض:\s*(.+?)(?:\n|$)") or grab_line(
        r"اسم المريض:\s*(.+?)(?:\n|$)"
    )
    out["hospital_name"] = grab_line(r"🏥\s*المستشفى:\s*(.+?)(?:\n|$)") or grab_line(
        r"المستشفى:\s*(.+?)(?:\n|$)"
    )
    out["department"] = grab_line(r"🏷️\s*القسم:\s*(.+?)(?:\n|$)") or grab_line(
        r"القسم:\s*(.+?)(?:\n|$)"
    )
    out["doctor_name"] = grab_line(r"👨‍⚕️\s*اسم الطبيب:\s*(.+?)(?:\n|$)") or grab_line(
        r"اسم الطبيب:\s*(.+?)(?:\n|$)"
    )
    out["medical_action"] = grab_line(r"📌\s*نوع الإجراء:\s*(.+?)(?:\n|$)") or grab_line(
        r"نوع الإجراء:\s*(.+?)(?:\n|$)"
    )

    case_block, _ = _extract_block(
        text,
        r"(?:🛏️\s*)?حالة المريض اليومية:\s*",
        [
            r"^📝",
            r"^قرار الطبيب",
            r"^🏥\s*رقم الغرفة",
            r"^━━━",
        ],
    )
    out["case_status"] = case_block or None

    dec_block, _ = _extract_block(
        text,
        r"(?:📝\s*)?قرار الطبيب اليومي:\s*",
        [
            r"^🏥\s*رقم الغرفة",
            r"^━━━",
            r"^📅\s*موعد العودة",
        ],
    )
    out["doctor_decision"] = dec_block or None

    room = grab_line(r"🏥\s*رقم الغرفة والطابق:\s*(.+?)(?:\n|$)") or grab_line(
        r"رقم الغرفة والطابق:\s*(.+?)(?:\n|$)"
    )
    out["room_number"] = room

    fu_line = grab_line(r"(?:📅\s*)?موعد العودة:\s*(.+?)(?:\n|$)") or grab_line(
        r"موعد العودة:\s*(.+?)(?:\n|$)"
    )
    if fu_line:
        fd = _parse_followup_datetime(fu_line)
        if fd:
            out["followup_date"] = fd
        else:
            warnings.append("لم أستطع قراءة موعد العودة بالكامل.")

    fr_block, _ = _extract_block(
        text,
        r"(?:✍️\s*)?سبب العودة:\s*",
        [r"^━━━", r"^👨‍⚕️\s*المترجم", r"^المترجم:"],
    )
    out["followup_reason"] = fr_block or None

    tr = grab_line(r"👨‍⚕️\s*المترجم:\s*(.+?)(?:\n|$)") or grab_line(r"المترجم:\s*(.+?)(?:\n|$)")
    out["translator_name"] = tr

    out["complaint_text"] = ""

    if not out.get("patient_name"):
        raise ValueError("لم أجد «اسم المريض» — تأكد من سطر: 👤 اسم المريض: ...")

    return out, warnings
