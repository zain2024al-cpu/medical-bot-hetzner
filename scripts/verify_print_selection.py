"""ملف الحالة يحترم ما أُلغي تحديده — كل تركيبة."""
import os, sys, fitz
sys.path.insert(0, r"C:\Users\nalgu\medical-bot-clean")
os.environ.setdefault("BOT_TOKEN", "x")
from reportlab.platypus import Paragraph
CAP = []; _o = Paragraph.__init__
def spy(self, t, s=None, *a, **k):
    CAP.append(str(t)); return _o(self, t, s, *a, **k)
Paragraph.__init__ = spy
from arabic_reshaper import reshape
from bidi.algorithm import get_display
def r(t): return get_display(reshape(t))
src = fitz.open(r"C:\Users\nalgu\Downloads\ملف_الحالة_طلال_محمد_الصوفي_محمد_الصوفي_3 (1).pdf")
imgs = [src.extract_image(i[0])["image"] for pg in src for i in pg.get_images(full=True)]
passport, photo = imgs[0], imgs[-1]
from services.residency_case_pdf import build_case_pdf

SECTIONS = {"الصورة الشخصية:": "صورة", "وثائق الوصول:": "وصول",
            "صورة الإقامة (الأحدث):": "إقامة", "الوثائق (": "وثائق"}

def person(sel):
    """يحاكي ما يبنيه _build_person_pdf_dict لاختيار معيّن."""
    return {"name": "م", "role": "المريض", "status_text": "نشط",
            "expiry_date": "2027-01-01",
            "photo_selected": "photo" in sel,
            "docs_selected": ("formc" in sel) or ("otherdocs" in sel),
            "photo_bytes": photo if "photo" in sel else None,
            "residence_doc": ({"source": "من الوصول", "date": "", "file_bytes": passport}
                              if "residence" in sel else None),
            "arrival_docs": ({"passport": passport} if "passport" in sel else {}),
            # الصورة مرفوعة **كوثيقة** أيضاً — مصدر التسريب السابق
            "documents": ([{"label": "صوره شخصية", "file_bytes": photo, "doc_type": "other"}]
                          if "otherdocs" in sel else [])}

def shown(sel):
    CAP.clear()
    build_case_pdf({"case_no":1,"patient_name":"م","companion_count":0,
                    "created_at":"2026-08-28","people":[person(sel)]})
    return {v for k, v in SECTIONS.items() if any(r(k) in t for t in CAP)}

CASES = [
    ({"photo","passport","residence","otherdocs"}, {"صورة","وصول","إقامة","وثائق"}),
    (set(),                                        set()),
    ({"otherdocs"},                                {"وثائق"}),      # 🔴 التسريب السابق
    ({"photo"},                                    {"صورة"}),
    ({"passport","residence"},                     {"وصول","إقامة"}),
    ({"photo","otherdocs"},                        {"صورة","وثائق"}),
]
print(f"{'المختار':<42}{'الظاهر':<26}النتيجة")
print("─"*84)
ok = True
for sel, want in CASES:
    got = shown(sel)
    good = got == want
    ok &= good
    print(f"{str(sorted(sel) or '(لا شيء)'):<42}{str(sorted(got) or '(لا شيء)'):<26}"
          f"{'✅' if good else '❌ متوقَّع ' + str(sorted(want))}")
Paragraph.__init__ = _o
print()
assert ok, "فشل"
print("✅ كل تركيبة تُنتِج بالضبط ما اختاره المستخدم — لا زيادة ولا نقصان")
