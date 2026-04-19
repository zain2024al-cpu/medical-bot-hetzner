# -*- coding: utf-8 -*-
"""
ربط تقارير اللصق بجدول المرضى/المستشفيات/الأقسام (نفس منطق التقارير المُدخَلة من المعالج)
حتى تظهر في الطباعة والفلترة بـ ID وليس بالاسم فقط.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

from sqlalchemy import func

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from db.models import Patient, Hospital, Department


def resolve_patient_hospital_dept_ids(
    session: "Session",
    patient_name: Optional[str],
    hospital_name: Optional[str],
    department_name: Optional[str],
) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    يطابق الأسماء مع السجلات (TRIM + LOWER) كما في المترجمين.
    القسم يُفضَّل ضمن المستشفى المطابق إن وُجد.
    """
    pid: Optional[int] = None
    hid: Optional[int] = None
    did: Optional[int] = None

    pn = (patient_name or "").strip()
    if pn:
        p = (
            session.query(Patient)
            .filter(
                func.lower(func.trim(func.coalesce(Patient.full_name, ""))) == pn.lower()
            )
            .first()
        )
        if p:
            pid = p.id

    hn = (hospital_name or "").strip()
    if hn:
        h = (
            session.query(Hospital)
            .filter(
                func.lower(func.trim(func.coalesce(Hospital.name, ""))) == hn.lower()
            )
            .first()
        )
        if h:
            hid = h.id

    dn = (department_name or "").strip()
    if dn:
        q = session.query(Department).filter(
            func.lower(func.trim(func.coalesce(Department.name, ""))) == dn.lower()
        )
        if hid is not None:
            d = q.filter(Department.hospital_id == hid).first()
        else:
            d = q.first()
        if d:
            did = d.id
            if hid is None and d.hospital_id is not None:
                hid = d.hospital_id

    return pid, hid, did
