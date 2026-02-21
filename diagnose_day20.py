"""
سكربت تشخيصي: لماذا لا تظهر كل تقارير يوم 20 في التقييم؟
شغّله على السيرفر: python3 diagnose_day20.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db", "medical_reports.db")
con = sqlite3.connect(DB_PATH)
cur = con.cursor()

TARGET = "2026-02-20"
NEXT = "2026-02-21"

print(f"{'='*70}")
print(f"  تشخيص تقارير يوم {TARGET}")
print(f"{'='*70}\n")

# 1) كل التقارير التي report_date يومها 20
print("=" * 50)
print("1) تقارير report_date = 20 فبراير")
print("=" * 50)
cur.execute("""
    SELECT id, translator_name, translator_id, patient_name,
           report_date, created_at, status
    FROM reports
    WHERE DATE(report_date) = ?
    AND status = 'active'
    ORDER BY created_at
""", (TARGET,))
rows_rd = cur.fetchall()
print(f"   عدد: {len(rows_rd)}")
for r in rows_rd:
    print(f"   ID={r[0]} | {r[1] or '?':10s} | tid={r[2]} | report_date={r[4]} | created_at={r[5]}")

# 2) كل التقارير التي created_at (UTC) يومها 20
print(f"\n{'='*50}")
print("2) تقارير created_at (UTC) يومها 20")
print("=" * 50)
cur.execute("""
    SELECT id, translator_name, translator_id, patient_name,
           report_date, created_at, status
    FROM reports
    WHERE DATE(created_at) = ?
    AND status = 'active'
    ORDER BY created_at
""", (TARGET,))
rows_ca = cur.fetchall()
print(f"   عدد: {len(rows_ca)}")
for r in rows_ca:
    print(f"   ID={r[0]} | {r[1] or '?':10s} | tid={r[2]} | report_date={r[4]} | created_at={r[5]}")

# 3) كل التقارير التي created_at بتوقيت IST يومها 20
print(f"\n{'='*50}")
print("3) تقارير created_at بتوقيت IST (+5:30) يومها 20")
print("=" * 50)
cur.execute("""
    SELECT id, translator_name, translator_id, patient_name,
           report_date, created_at, status,
           datetime(created_at, '+5 hours', '+30 minutes') as created_ist
    FROM reports
    WHERE DATE(datetime(created_at, '+5 hours', '+30 minutes')) = ?
    AND status = 'active'
    ORDER BY created_at
""", (TARGET,))
rows_ist = cur.fetchall()
print(f"   عدد: {len(rows_ist)}")
for r in rows_ist:
    print(f"   ID={r[0]} | {r[1] or '?':10s} | tid={r[2]} | report_date={r[4]} | created_at={r[5]} | IST={r[7]}")

# 4) COALESCE(report_date, created_at) بين 20 و 21
print(f"\n{'='*50}")
print("4) COALESCE(report_date, created_at) >= 20 AND < 21")
print("=" * 50)
cur.execute("""
    SELECT id, translator_name, translator_id, patient_name,
           report_date, created_at, status
    FROM reports
    WHERE COALESCE(report_date, created_at) >= ?
    AND COALESCE(report_date, created_at) < ?
    AND status = 'active'
    ORDER BY created_at
""", (TARGET, NEXT))
rows_coalesce = cur.fetchall()
print(f"   عدد: {len(rows_coalesce)}")
for r in rows_coalesce:
    print(f"   ID={r[0]} | {r[1] or '?':10s} | tid={r[2]} | report_date={r[4]} | created_at={r[5]}")

# 5) تقارير IST=20 لكنها ليست في COALESCE
print(f"\n{'='*50}")
print("5) تقارير IST يومها 20 لكن COALESCE لا يلتقطها (المفقودة)")
print("=" * 50)
coalesce_ids = {r[0] for r in rows_coalesce}
ist_ids = {r[0] for r in rows_ist}
missing_ids = ist_ids - coalesce_ids
if missing_ids:
    print(f"   عدد المفقودة: {len(missing_ids)}")
    for r in rows_ist:
        if r[0] in missing_ids:
            print(f"   ID={r[0]} | {r[1] or '?':10s} | tid={r[2]} | report_date={r[4]} | created_at={r[5]} | IST={r[7]}")
            # ماذا يقول COALESCE عن هذا التقرير؟
            cur.execute("SELECT COALESCE(report_date, created_at), report_date, created_at FROM reports WHERE id=?", (r[0],))
            coal = cur.fetchone()
            print(f"         COALESCE={coal[0]} | report_date={coal[1]} | created_at={coal[2]}")
else:
    print("   لا توجد تقارير مفقودة!")

# 6) تقارير report_date=20 لكن created_at ليس يوم 20
print(f"\n{'='*50}")
print("6) report_date يوم 20 لكن created_at (UTC) يوم مختلف")
print("=" * 50)
for r in rows_rd:
    ca_date = r[5][:10] if r[5] and len(r[5]) >= 10 else "?"
    rd_date = r[4][:10] if r[4] and len(r[4]) >= 10 else "?"
    if ca_date != rd_date:
        print(f"   ID={r[0]} | {r[1] or '?':10s} | report_date={r[4]} | created_at={r[5]}")

# 7) تقارير created_at (IST) يوم 20 لكن report_date يوم مختلف
print(f"\n{'='*50}")
print("7) created_at IST يوم 20 لكن report_date يوم مختلف (السبب الرئيسي)")
print("=" * 50)
for r in rows_ist:
    rd = r[4]
    if rd:
        rd_date = rd[:10] if len(rd) >= 10 else rd
        if rd_date != TARGET:
            print(f"   ID={r[0]} | {r[1] or '?':10s} | report_date={rd_date} | created_at={r[5]} | IST={r[7]}")
    else:
        print(f"   ID={r[0]} | {r[1] or '?':10s} | report_date=NULL | created_at={r[5]} | IST={r[7]}")

# 8) ملخص
print(f"\n{'='*50}")
print("8) ملخص")
print("=" * 50)
# كم تقرير المفروض يظهر ليوم 20
all_day20 = set()
for r in rows_rd:
    all_day20.add(r[0])
for r in rows_ist:
    all_day20.add(r[0])
print(f"   إجمالي التقارير التي يجب أن تظهر ليوم 20: {len(all_day20)}")
print(f"   ├ report_date=20: {len(rows_rd)}")
print(f"   ├ created_at UTC=20: {len(rows_ca)}")
print(f"   ├ created_at IST=20: {len(rows_ist)}")
print(f"   ├ COALESCE يلتقط: {len(rows_coalesce)}")
print(f"   └ مفقودة من COALESCE: {len(missing_ids)}")

# مع translator_id
with_tid = [r for r in rows_coalesce if r[2] is not None]
without_tid = [r for r in rows_coalesce if r[2] is None]
print(f"\n   من COALESCE:")
print(f"   ├ مع translator_id: {len(with_tid)}")
print(f"   └ بدون translator_id: {len(without_tid)}")

# الاستعلام المزدوج (الذي نستخدمه الآن)
print(f"\n{'='*50}")
print("9) الاستعلام المزدوج (COALESCE OR IST) - ما سيظهر فعلاً")
print("=" * 50)
cur.execute("""
    SELECT id, translator_name, translator_id, report_date, created_at,
           datetime(created_at, '+5 hours', '+30 minutes') as ist
    FROM reports
    WHERE (
        (COALESCE(report_date, created_at) >= ? AND COALESCE(report_date, created_at) < ?)
        OR (DATE(datetime(created_at, '+5 hours', '+30 minutes')) >= ? AND DATE(datetime(created_at, '+5 hours', '+30 minutes')) < ?)
    )
    AND status = 'active'
    AND translator_id IS NOT NULL
    ORDER BY created_at
""", (TARGET, NEXT, TARGET, NEXT))
dual_rows = cur.fetchall()
print(f"   عدد (مع tid): {len(dual_rows)}")
for r in dual_rows:
    print(f"   ID={r[0]} | {r[1] or '?':10s} | tid={r[2]} | report_date={r[3]} | created_at={r[4]} | IST={r[5]}")

con.close()
print(f"\n{'='*70}")
print("Done!")
