# -*- coding: utf-8 -*-
"""تشخيص حالات الإقامة — يجيب على سؤال واحد: أين ذهب «تم التقديم»؟

يفصل بين احتمالين لا يفرّق بينهما أي كلام:
  • لا يوجد انتقال مُسجَّل إلى SUBMITTED ⇒ الزر لم يُنفَّذ أصلاً.
  • يوجد انتقال ثم الحالة الآن غيره      ⇒ نُفِّذ ثم أعاده شيء آخر.

⚠️ القراءة الأساسية بـSQL خام لا عبر الـORM: أداة تشخيص يجب أن تعمل حتى
لو اختلف المخطَّط عن النماذج (عمود جديد لم تُطبَّق هجرته بعد مثلاً) —
وإلا انهارت في اللحظة التي نحتاجها فيها. وكل قسم معزول بـtry/except
حتى لا يُسقِط فشلُ قسمٍ بقيةَ التقرير.

يُشغَّل من أي مجلد:  python ~/medical-bot-hetzner/scripts/rn_status_dump.py
"""
import os
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent   # لا مسار ثابت
sys.path.insert(0, str(ROOT))

if not (ROOT / "db" / "models.py").exists():
    print(f"⚠️ لم أجد المستودع عند {ROOT} — شغّله من داخل مجلد المشروع.")
    sys.exit(2)

from sqlalchemy import text                    # noqa: E402
from db.session import engine, DATABASE_PATH   # noqa: E402

print("=" * 64)
print("قاعدة البيانات:", DATABASE_PATH, "| موجودة؟", os.path.exists(DATABASE_PATH))
print("=" * 64)


def q(sql, **kw):
    with engine.connect() as c:
        return list(c.execute(text(sql), kw))


def section(title, fn):
    print(f"\n{title}")
    try:
        fn()
    except Exception as exc:
        print(f"   ⚠️ تعذّر هذا القسم: {type(exc).__name__}: {exc}")


def _statuses():
    rows = q("SELECT status, COUNT(*) FROM res_persons GROUP BY status ORDER BY 2 DESC")
    from modules.residency.constants import STATUS_ORDER
    if not rows:
        print("   (لا يوجد أي شخص في جدول الإقامات)")
    for st, n in rows:
        known = "✅ معروفة" if st in STATUS_ORDER else "🔴 غير معروفة للنظام!"
        print(f"   {repr(st):<28} {n:>3}   {known}")


def _people():
    rows = q("SELECT id, parent_id, name, status, "
             "COALESCE(residency_file_id,''), COALESCE(photo_file_id,'') "
             "FROM res_persons ORDER BY id")
    for pid, parent, name, st, resf, ph in rows:
        ndoc = q("SELECT COUNT(*) FROM res_documents WHERE person_id=:p", p=pid)[0][0]
        files = ndoc + (1 if resf.strip() else 0) + (1 if ph.strip() else 0)
        kind = "مريض" if not parent else f"مرافق({parent})"
        print(f"   #{pid:<4} {kind:<12} {str(name)[:24]:<26} {str(st):<18} ملفات={files}")


def _logs():
    rows = q("SELECT l.id, p.name, l.old_status, l.new_status, l.created_at "
             "FROM res_status_log l LEFT JOIN res_persons p ON p.id = l.person_id "
             "ORDER BY l.id DESC LIMIT 25")
    if not rows:
        print("   🔴 لا يوجد أي انتقال مُسجَّل إطلاقاً.")
        return
    for _i, nm, old, new, when in rows:
        print(f"   {str(nm)[:22]:<24} {str(old or '—'):<18} → {str(new):<18} {when}")


def _submitted_history():
    rows = q("SELECT p.name, l.old_status, l.created_at FROM res_status_log l "
             "LEFT JOIN res_persons p ON p.id = l.person_id "
             "WHERE l.new_status = 'SUBMITTED' ORDER BY l.id DESC")
    if not rows:
        print("   🔴 **لم يُسجَّل أي انتقال إلى SUBMITTED إطلاقاً** ⇒ زر «تم "
              "التقديم» لم يُنفَّذ (أو نُفِّذ ولم يُحفَظ).")
        return
    print(f"   ✅ عدد الانتقالات المُسجَّلة إلى SUBMITTED: {len(rows)}")
    for nm, old, when in rows:
        cur = q("SELECT status FROM res_persons WHERE name=:n", n=nm)
        cur = cur[0][0] if cur else "?"
        flag = "" if cur == "SUBMITTED" else f"   ⚠️ لكنه الآن {cur}"
        print(f"      {str(nm)[:22]:<24} من {old} في {when}{flag}")


def _views():
    from modules.residency import repository as R
    from modules.residency.constants import STATUS_ORDER, STATUS_LABELS
    counts = R.get_status_counts()
    for st in STATUS_ORDER:
        fams = R.get_requests_by_status(st)
        names = "، ".join(f.root.name[:16] for f in fams) or "(فارغة)"
        print(f"   {STATUS_LABELS.get(st, st):<32} عدّاد={counts.get(st, 0):<3} "
              f"قائمة={len(fams):<3} {names}")


def _overdue():
    """نشطة رغم استحقاق التنبيه أو انتهاء الإقامة — يجب أن تكون فارغة."""
    from datetime import date
    today = date.today().isoformat()
    rows = q("SELECT id, name, COALESCE(reminder_date,''), COALESCE(expiry_date,'') "
             "FROM res_persons WHERE status='ACTIVE'")
    bad = [r for r in rows
           if (r[2] and r[2] <= today) or (r[3] and r[3] <= today)]
    if not bad:
        print("   ✅ لا توجد حالة نشطة مستحقّة — المهمة اليومية مواكِبة.")
        return
    print(f"   🔴 {len(bad)} حالة نشطة كان يجب أن تنتقل إلى «معلّق انتهاء»:")
    for pid, nm, rem, exp in bad:
        why = []
        if rem and rem <= today: why.append(f"تنبيه {rem}")
        if exp and exp <= today: why.append(f"انتهاء {exp}")
        print(f"      #{pid:<4} {str(nm)[:26]:<28} {' · '.join(why)}")


section("📊 الحالات كما هي مخزَّنة حرفياً:", _statuses)
section("⏰ نشطة رغم الاستحقاق (يجب أن تكون فارغة):", _overdue)
section("📋 كل الأشخاص:", _people)
section("🕘 آخر ٢٥ انتقال حالة (الأحدث أولاً):", _logs)
section("🔵 تاريخ الانتقال إلى «تم التقديم»:", _submitted_history)
section("🔢 ما يعرضه البوت فعلياً (عدّاد القائمة ومحتواها):", _views)
print()
