"""تدقيق شامل لزر الرجوع في وحدة الإقامة — كل شاشة، كل خطوة.

يفحص لكل شاشة يمكن الوصول إليها:
  ١) هل فيها زر رجوع أصلاً؟
  ٢) هل وجهته **يعالجها** المُوزِّع فعلاً (لا زر ميت)؟
  ٣) هل تُنظَّف الحالة الانتقالية بعد الضغط عليه؟
"""
import os, sys, asyncio, logging, tempfile
sys.path.insert(0, r"C:\Users\nalgu\medical-bot-clean")
os.environ.setdefault("BOT_TOKEN", "x")
DB = os.path.join(tempfile.gettempdir(), "audit_back.db")
if os.path.exists(DB):
    os.remove(DB)
os.environ["DATABASE_PATH"] = DB
logging.disable(logging.CRITICAL)

from datetime import datetime
from db.session import engine, SessionLocal
from db.models import (Base, ResidencyPerson, ResidencyDocument,
                       ArrivalPatient, ArrivalCompanion, ResidencyIssuance)
Base.metadata.create_all(bind=engine)
from modules.residency.constants import (
    STATUS_WAITING_ARRIVAL, STATUS_ACTIVE, STATUS_EXPIRY_PENDING,
    STATUS_SUBMITTED, STATUS_ISSUED, STATUS_LEGACY_PENDING, STATUS_ORDER,
)

IDS = {}
with SessionLocal() as s:
    ap = ArrivalPatient(name="واصل", arrival_status="active",
                        created_at=datetime.utcnow(), passport_file_id="F1")
    s.add(ap); s.flush()
    s.add(ArrivalCompanion(patient_id=ap.id, name="مرافق واصل"))
    for nm, st in (("واصل", STATUS_WAITING_ARRIVAL), ("نشط", STATUS_ACTIVE),
                   ("منتهٍ", STATUS_EXPIRY_PENDING), ("مقدَّم", STATUS_SUBMITTED),
                   ("مُصدَر", STATUS_ISSUED), ("سابقة", STATUS_LEGACY_PENDING)):
        p = ResidencyPerson(name=nm, status=st, expiry_date="2026-12-01",
                            photo_file_id="PH", residency_file_id="RS")
        s.add(p); s.flush()
        IDS[nm] = p.id
        s.add(ResidencyPerson(name=f"مرافق {nm}", parent_id=p.id, status=st))
    s.add(ResidencyDocument(person_id=IDS["نشط"], doc_type="form_c",
                            doc_name="Form C", file_id="D1"))
    s.add(ResidencyIssuance(person_id=IDS["مُصدَر"], expiry_date="2027-01-01",
                            file_id="I1", issued_at=datetime(2026, 8, 1)))
    s.commit()

LAST = {}
class Q:
    def __init__(self, d):
        self.data = d
        self.from_user = type("U", (), {"id": 2116274898})()
        self.message = type("M", (), {"chat_id": 1})()
    async def answer(self, *a, **k): pass
    async def edit_message_text(self, t, reply_markup=None, **kw):
        LAST["text"] = t or ""
        LAST["backs"] = [b.callback_data for row in getattr(reply_markup, "inline_keyboard", [])
                         for b in row if "رجوع" in (b.text or "")]
        LAST["all"] = [b.callback_data for row in getattr(reply_markup, "inline_keyboard", [])
                       for b in row]
    async def edit_message_reply_markup(self, **kw): pass
class U:
    def __init__(self, d):
        self.callback_query = Q(d)
        self.effective_user = type("U", (), {"id": 2116274898})()
        self.effective_message = None
UD = {}
C = type("C", (), {"user_data": UD, "bot": None})


async def main():
    import bot.shared_auth as sa
    sa.is_admin = lambda uid: True
    import modules.residency.flow as F

    async def press(cb):
        LAST.clear()
        await F._dispatch_callback(U(f"rn:{cb}"), C())
        return dict(LAST)

    def transient():
        return sorted(k for k, v in UD.items()
                      if k.startswith("_rn_") and k != "_rn_last_status" and v)

    # كل شاشة: (وصف، مسار الوصول إليها)
    SCREENS = [
        ("القائمة الرئيسية", ["menu"]),
        *[(f"قائمة: {st}", ["menu", f"status_{st}"]) for st in STATUS_ORDER],
        ("تفاصيل: نشط", ["menu", f"status_{STATUS_ACTIVE}", f"family_{IDS['نشط']}"]),
        ("ملخّص الوصول", ["menu", f"status_{STATUS_WAITING_ARRIVAL}", f"family_{IDS['واصل']}"]),
        ("خطوة الاستكمال (تنبيه/مراجعة)", ["menu", f"status_{STATUS_WAITING_ARRIVAL}",
                                   f"family_{IDS['واصل']}", f"onboard_resume_{IDS['واصل']}"]),
        ("قائمة الوثائق", ["menu", f"status_{STATUS_ACTIVE}", f"family_{IDS['نشط']}",
                            f"docs_{IDS['نشط']}"]),
        ("نوع الوثيقة", ["menu", f"status_{STATUS_ACTIVE}", f"family_{IDS['نشط']}",
                          f"docs_{IDS['نشط']}", f"doc_add_{IDS['نشط']}"]),
        ("توثيق الإصدار", ["menu", f"status_{STATUS_ISSUED}", f"family_{IDS['مُصدَر']}",
                            f"issue_view_{IDS['مُصدَر']}"]),
        ("الحالات السابقة: قرار", ["menu", f"status_{STATUS_LEGACY_PENDING}",
                                    f"family_{IDS['سابقة']}"]),
        ("الحالات السابقة: خطوة", ["menu", f"status_{STATUS_LEGACY_PENDING}",
                                    f"family_{IDS['سابقة']}", f"lgc_ext_{IDS['سابقة']}"]),
        ("الحالات السابقة: بلا تمديد", ["menu", f"status_{STATUS_LEGACY_PENDING}",
                                         f"family_{IDS['سابقة']}", f"lgc_noext_{IDS['سابقة']}"]),
        ("البحث", ["menu", "search"]),
        ("السجل", ["menu", "log"]),
        ("التقارير", ["menu", "reports"]),
    ]

    print(f"{'الشاشة':<30}{'زر الرجوع':<28}{'الوجهة تعمل':<13}الجلسة")
    print("─" * 88)
    problems = []
    for name, path in SCREENS:
        UD.clear()
        res = {}
        for step in path:
            res = await press(step)
        backs = res.get("backs", [])
        if not res.get("text"):
            print(f"{name:<30}{'(لم تُرسَم)':<28}{'—':<13}—")
            problems.append((name, "الشاشة لم تُرسَم"))
            continue
        if not backs:
            # القائمة الرئيسية أعلى مستوى — غياب الرجوع فيها بالتصميم
            top = "القائمة الرئيسية" in name
            print(f"{name:<30}{('(أعلى مستوى)' if top else '❌ لا يوجد'):<28}{'—':<13}—")
            if not top:
                problems.append((name, "بلا زر رجوع"))
            continue
        target = backs[0]
        before = transient()
        # اضغط الرجوع
        res2 = await press(target.split(":", 1)[1])
        works = bool(res2.get("text"))
        after = transient()
        clean = not after
        mark_w = "✅" if works else "❌ ميت"
        mark_c = "✅ نظيفة" if clean else f"❌ {after}"
        print(f"{name:<30}{target:<28}{mark_w:<13}{mark_c}")
        if not works:
            problems.append((name, f"وجهة ميتة: {target}"))
        if before and not clean:
            problems.append((name, f"جلسة معلّقة: {after}"))

    print("\n" + "=" * 88)
    if problems:
        print(f"❌ {len(problems)} مشكلة:")
        for n, w in problems:
            print(f"   • {n}: {w}")
    else:
        print("✅ كل شاشة: زر رجوع موجود · وجهته تعمل · الجلسة تُنظَّف")
    return problems


problems = asyncio.run(main())
