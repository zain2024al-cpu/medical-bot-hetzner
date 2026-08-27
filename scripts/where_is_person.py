#!/usr/bin/env python3
# scripts/where_is_person.py
#
# "أين يوجد هذا الاسم بالضبط؟" — أداة تشخيص للقراءة فقط.
#
# ⚠️ لماذا وُجدت: الاسم الواحد قد يعيش في **أربعة أنظمة مستقلة** بلا أي
# مفتاح أجنبي بينها (المطابقة بالاسم الحرفي في كل المشروع):
#   • patients               — سجلّ المرضى (الظهور للمستخدمين)
#   • gs_arrival_patients    — الوصول (يُغذّي المغادرين)
#   • gs_arrival_companions  — مرافقو الوصول
#   • res_persons            — الإقامة (الحالات والتنبيهات)
# فغيابه من أحدها مع وجوده في غيره هو سبب معظم شكاوى "الاسم لا يظهر".
# هذه الأداة تُظهر الصورة الكاملة دفعة واحدة بدل تخمين أيّ نظام ينقصه.
#
# الاستخدام على الخادم:
#   cd ~/medical-bot-hetzner
#   ./venv/bin/python scripts/where_is_person.py "طلال الصوفي"
#   ./venv/bin/python scripts/where_is_person.py "طلال" "صلاح"
#
# 🔒 قراءة فقط — لا تكتب ولا تحذف شيئاً إطلاقاً.

import os
import sqlite3
import sys


def _db_path() -> str:
    p = os.getenv("DATABASE_PATH")
    if p and os.path.exists(p):
        return p
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(here, "db", "medical_reports.db")


def _q(con, sql, args=()):
    try:
        return con.execute(sql, args).fetchall()
    except sqlite3.Error as exc:
        print(f"      ⚠️ تعذّر الاستعلام: {exc}")
        return []


def report(con, term: str) -> None:
    like = f"%{term.strip()}%"
    print("=" * 66)
    print(f"🔍 البحث عن: {term!r}")
    print("=" * 66)

    # ── سجلّ المرضى ──
    rows = _q(con, """
        SELECT id, full_name, patient_type, companion_of_id,
               archived_at, gs_onboarded_at
        FROM patients WHERE full_name LIKE ?
        ORDER BY id
    """, (like,))
    print(f"\n📋 سجلّ المرضى — {len(rows)} نتيجة")
    for i, name, ptype, comp_of, arch, onb in rows:
        bits = [f"id={i}", f"نوع={ptype or 'general'}"]
        if comp_of:
            bits.append(f"مرافق لـid={comp_of}")
        if arch:
            bits.append("🧳 مؤرشَف (مخفيّ عن القوائم)")
        if onb:
            bits.append("🏠 مُدخَل كحالة موجودة")
        print(f"   • {name}   [{' · '.join(bits)}]")

    # ── الوصول ──
    rows = _q(con, """
        SELECT id, name, arrival_status, created_at
        FROM gs_arrival_patients WHERE name LIKE ? ORDER BY id
    """, (like,))
    print(f"\n🛬 جدول الوصول (كمريض) — {len(rows)} نتيجة")
    for i, name, st, created in rows:
        print(f"   • {name}   [id={i} · حالة={st} · أُنشئ={created}]")
        comps = _q(con, "SELECT name FROM gs_arrival_companions WHERE patient_id=?", (i,))
        if comps:
            print(f"        مرافقوه في الوصول: {[c[0] for c in comps]}")

    rows = _q(con, """
        SELECT c.id, c.name, c.patient_id, p.name
        FROM gs_arrival_companions c
        LEFT JOIN gs_arrival_patients p ON p.id = c.patient_id
        WHERE c.name LIKE ? ORDER BY c.id
    """, (like,))
    print(f"\n👥 مرافقو الوصول — {len(rows)} نتيجة")
    for i, name, pid, pname in rows:
        print(f"   • {name}   [id={i} · مرافق لـ: {pname or f'(مريض محذوف id={pid})'}]")

    # ── الإقامة ──
    rows = _q(con, """
        SELECT r.id, r.name, r.status, r.parent_id, p.name,
               r.expiry_date, r.reminder_date
        FROM res_persons r
        LEFT JOIN res_persons p ON p.id = r.parent_id
        WHERE r.name LIKE ? ORDER BY r.id
    """, (like,))
    print(f"\n🪪 وحدة الإقامة — {len(rows)} نتيجة")
    for i, name, st, par, pname, exp, rem in rows:
        role = f"مرافق لـ {pname}" if par else "مريض (جذر)"
        print(f"   • {name}   [id={i} · {role} · حالة={st}]")
        print(f"        انتهاء={exp or '—'} · تنبيه={rem or '—'}")

    # ── 🔴 الفجوة: مرافق في الوصول وغائب عن الإقامة ──
    print("\n🔎 فحص الفجوة بين الوصول والإقامة:")
    roots = _q(con, """
        SELECT id, name FROM res_persons
        WHERE parent_id IS NULL AND name LIKE ?
    """, (like,))
    if not roots:
        print("   (لا جذر إقامة بهذا الاسم — لا فجوة تُقاس)")
    for rid, rname in roots:
        arr_comps = [c[0] for c in _q(con, """
            SELECT c.name FROM gs_arrival_companions c
            JOIN gs_arrival_patients p ON p.id = c.patient_id
            WHERE p.name = ?
        """, (rname,))]
        res_comps = [c[0] for c in _q(
            con, "SELECT name FROM res_persons WHERE parent_id=?", (rid,))]
        missing = [n for n in arr_comps if n not in res_comps]
        print(f"   • {rname}: الوصول={len(arr_comps)} · الإقامة={len(res_comps)}")
        if missing:
            print(f"     ❌ ناقص في الإقامة: {missing}")
            print("     💡 الحل: 🪪 الإقامة ← الحالة ← تفاصيل الطلب ←")
            print("        «🔄 إضافة مرافقي الوصول»")
        elif arr_comps:
            print("     ✅ متطابقان")
    print()


def main() -> int:
    terms = [a for a in sys.argv[1:] if a.strip()]
    if not terms:
        print("الاستخدام: python scripts/where_is_person.py \"جزء من الاسم\" [اسم آخر ...]")
        return 2
    path = _db_path()
    if not os.path.exists(path):
        print(f"❌ لم تُعثر قاعدة البيانات: {path}")
        return 1
    print(f"قاعدة البيانات: {path}\n")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)   # 🔒 قراءة فقط
    try:
        for t in terms:
            report(con, t)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
