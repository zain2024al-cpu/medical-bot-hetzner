# modules/general_services/arrivals/group_documents.py
# 📎 ملفات وثائق دفعة الوصول — تُجمَّع في ملف PDF واحد يُنشَر في المجموعة
# **بعد** نصّ التقرير (انظر services/arrival_documents_pdf.py).
#
# نصّ التقرير يقول «✅ مرفق» أمام كل وثيقة، لكنّ الملف نفسه لم يكن يصل
# المجموعة أبداً: من يريد جواز مريضٍ كان يحتاج البوت. هذه الدالة تجمع
# الملفات بترتيب ظهور أصحابها في النصّ، بحقول **تركيبية** — لا نصّاً
# جاهزاً فقط — ليبني مولّد الـPDF فهرساً حقيقياً (شخص × نوع وثيقة) بلا
# اضطرار لتفكيك نصّ الوصف بتعابير نمطية هشّة.

from __future__ import annotations

# (مفتاح الحقل، مفتاح النوع الثابت، تسميته) — بترتيب ظهورها في التقرير.
# ⚠️ `key` ثابت ومستقرّ عبر النداءات (يُستعمَل لمطابقة أعمدة فهرس الـPDF)،
# بخلاف `label` الذي قد يحمل إيموجي للعرض في تليجرام لا يظهر في ملف الـPDF
# (خطوط الخادم لا تملك رموزه — يُحذَف تلقائياً هناك).
_PATIENT_DOCS = [
    ("passport_file_id",  "passport",  "🛂 جواز السفر"),
    ("visa_file_id",      "visa",      "📋 التأشيرة + ختم الدخول"),
    ("tickets_file_id",   "tickets",   "🎫 التذاكر"),
    ("residence_file_id", "residence", "🪪 الإقامة"),
]

# المرافق يُسأل عن الأربع كلها في التدفّق (STEP_C_RESIDENCE)، وإن كان نصّ
# التقرير لا يعرض إقامته — فالملف محفوظ ويُرسَل.
_COMPANION_DOCS = _PATIENT_DOCS

# ترتيب أعمدة الفهرس في الـPDF — ثابت لكل الدفعات.
DOC_TYPE_ORDER = [key for _f, key, _l in _PATIENT_DOCS]


def _clean(v) -> str:
    return str(v or "").strip()


def collect_arrival_documents(completed_patients: list[dict]) -> list[dict]:
    """[{"file_id", "person_label", "doc_key", "doc_label", "caption"}, ...]
    بترتيب النصّ: مريضٌ ثم مرافقوه.

    الوثيقة بلا `file_id` (تُخطّيت) تُحذَف بصمت — لا شيء لإرساله.
    `caption` وصفٌ جاهز (نفس ما كان يُعرَض على الصورة المفردة سابقاً)،
    محفوظ للسجلّ وللعرض حين لا يُحتاج التفكيك التركيبي.
    """
    out: list[dict] = []
    for i, p in enumerate(completed_patients or [], start=1):
        pname = _clean(p.get("name")) or "—"
        person_label = f"{i}. {pname}"
        for field, key, label in _PATIENT_DOCS:
            fid = _clean(p.get(field))
            if fid:
                out.append({
                    "file_id": fid, "person_label": person_label,
                    "doc_key": key, "doc_label": label,
                    "caption": f"{person_label} — {label}",
                })
        for c in p.get("companions") or []:
            cname = _clean(c.get("name")) or "—"
            comp_label = f"↳ {cname} (مرافق {pname})"
            for field, key, label in _COMPANION_DOCS:
                fid = _clean(c.get(field))
                if fid:
                    out.append({
                        "file_id": fid, "person_label": comp_label,
                        "doc_key": key, "doc_label": label,
                        "caption": f"{comp_label} — {label}",
                    })
    return out
