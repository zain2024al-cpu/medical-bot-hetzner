# modules/general_services/arrivals/group_documents.py
# 📎 ملفات وثائق دفعة الوصول — تُنشَر في المجموعة **بعد** نصّ التقرير.
#
# نصّ التقرير يقول «✅ مرفق» أمام كل وثيقة، لكنّ الملف نفسه لم يكن يصل
# المجموعة أبداً: من يريد جواز مريضٍ كان يحتاج البوت. هذه الدالة تجمع
# الملفات بترتيب ظهور أصحابها في النصّ، وتضع على كل ملف وصفاً يعرّف
# صاحبه ونوعه — ملفٌ بلا وصف في مجموعة فيها عشرات الملفات ورقةٌ مجهولة.
#
# ⚠️ الوصف **نصّ عادي بلا Markdown**: أسماء المرضى قيمٌ مُدخَلة، ومحرف
# واحد (`_ * [`) يُفشِل الرسالة كلها بـ`can't parse entities` فيضيع الملف.

from __future__ import annotations

# (مفتاح الحقل، تسميته) — بترتيب ظهورها في نصّ التقرير نفسه.
_PATIENT_DOCS = [
    ("passport_file_id",  "🛂 جواز السفر"),
    ("visa_file_id",      "📋 التأشيرة + ختم الدخول"),
    ("tickets_file_id",   "🎫 التذاكر"),
    ("residence_file_id", "🪪 الإقامة"),
]

# المرافق يُسأل عن الأربع كلها في التدفّق (STEP_C_RESIDENCE)، وإن كان نصّ
# التقرير لا يعرض إقامته — فالملف محفوظ ويُرسَل.
_COMPANION_DOCS = _PATIENT_DOCS


def _clean(v) -> str:
    return str(v or "").strip()


def collect_arrival_documents(completed_patients: list[dict]) -> list[dict]:
    """[{"file_id": ..., "caption": ...}, ...] بترتيب النصّ: مريضٌ ثم مرافقوه.

    الوثيقة بلا `file_id` (تُخطّيت) تُحذَف بصمت — لا شيء لإرساله.
    """
    out: list[dict] = []
    for i, p in enumerate(completed_patients or [], start=1):
        pname = _clean(p.get("name")) or "—"
        for key, label in _PATIENT_DOCS:
            fid = _clean(p.get(key))
            if fid:
                out.append({"file_id": fid, "caption": f"{i}. {pname} — {label}"})
        for c in p.get("companions") or []:
            cname = _clean(c.get("name")) or "—"
            for key, label in _COMPANION_DOCS:
                fid = _clean(c.get(key))
                if fid:
                    out.append({
                        "file_id": fid,
                        "caption": f"↳ {cname} (مرافق {pname}) — {label}",
                    })
    return out
