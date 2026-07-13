"""
سكربت لإصلاح التقارير المجهولة (translator_id=NULL)
يربط كل تقرير باسم المترجم الموجود في جدول translators

نفّذه على السيرفر: python fix_null_translator_ids.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db", "medical_reports.db")

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

# ═══ الخطوة 1: إصلاح ID صبري في جدول translators ═══
OLD_SABRI = 8172870113
NEW_SABRI = 1474333554

cur.execute("SELECT COUNT(*) FROM translators WHERE translator_id = ?", (OLD_SABRI,))
if cur.fetchone()[0] > 0:
    cur.execute("UPDATE translators SET translator_id = ? WHERE translator_id = ?", (NEW_SABRI, OLD_SABRI))
    print(f"✅ translators: صبري ID updated {OLD_SABRI} → {NEW_SABRI} ({cur.rowcount} rows)")

cur.execute("UPDATE reports SET translator_id = ? WHERE translator_id = ?", (NEW_SABRI, OLD_SABRI))
if cur.rowcount > 0:
    print(f"✅ reports: صبري old ID updated ({cur.rowcount} rows)")

# ═══ الخطوة 2: ربط التقارير المجهولة بالاسم ═══
# جلب كل المترجمين المسجلين
cur.execute("SELECT translator_id, name FROM translators")
translator_map = {}
for row in cur.fetchall():
    tid, name = row
    if name:
        translator_map[name.strip()] = tid
print(f"\n📋 المترجمين المسجلين: {len(translator_map)}")
for name, tid in translator_map.items():
    print(f"   {name} → {tid}")

# جلب التقارير بدون translator_id
cur.execute("""
    SELECT id, translator_name, patient_name
    FROM reports
    WHERE translator_id IS NULL
    AND translator_name IS NOT NULL
    AND translator_name != 'غير محدد'
""")
null_reports = cur.fetchall()
print(f"\n⚠️ تقارير بدون translator_id: {len(null_reports)}")

fixed = 0
not_found = []
for report_id, tname, pname in null_reports:
    tname_clean = tname.strip() if tname else ""
    if tname_clean in translator_map:
        tid = translator_map[tname_clean]
        cur.execute("UPDATE reports SET translator_id = ? WHERE id = ?", (tid, report_id))
        print(f"   ✅ ID={report_id} | {tname} → tid={tid}")
        fixed += 1
    else:
        not_found.append((report_id, tname, pname))
        print(f"   ❌ ID={report_id} | {tname} — اسم غير موجود في translators")

con.commit()

print(f"\n═══ النتيجة ═══")
print(f"✅ تم إصلاح: {fixed} تقرير")
if not_found:
    print(f"❌ لم يُصلح: {len(not_found)} تقرير (أسماء غير مطابقة)")
    for rid, tn, pn in not_found:
        print(f"   ID={rid} | مترجم: {tn} | مريض: {pn}")

# التحقق النهائي
remaining = cur.execute("SELECT COUNT(*) FROM reports WHERE translator_id IS NULL AND status='active'").fetchone()[0]
print(f"\n📊 التقارير المجهولة المتبقية: {remaining}")

con.close()
print("\nDone!")
