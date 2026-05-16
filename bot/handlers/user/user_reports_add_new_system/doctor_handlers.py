# =============================
# doctor_handlers.py
# معالجات اختيار الطبيب
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging
from sqlalchemy import func

from .states import STATE_SELECT_DOCTOR, R_DOCTOR, R_ACTION_TYPE
from .managers import DoctorDataManager
from .selector_context import SelectorContext
from .ui_primitives import screen_header, smart_rows
from ..user_reports_add_helpers import validate_text_input

logger = logging.getLogger(__name__)

# -----------------------------
# Helpers
# -----------------------------

def _norm(s: str) -> str:
    """Normalize for loose DB matching (case/space)."""
    return " ".join((s or "").strip().split()).casefold()


def _hospital_name_variants(hospital_name: str) -> list[str]:
    """
    Generate common variants that appear after hospital dedupe/merge scripts.
    Example:
      "Manipal Hospital - Old Airport Road" <-> "Manipal Hospital, Old Airport Road"
    """
    base = (hospital_name or "").strip()
    if not base:
        return []

    variants = [base]

    # Swap first " - " with ", " (common normalization between UI lists and DB rows)
    if " - " in base:
        variants.append(base.replace(" - ", ", ", 1))

    # Sometimes suffixes like ", Bangalore" are present in some sources but not DB
    if base.lower().endswith(", bangalore"):
        variants.append(base[: -len(", bangalore")].strip())

    # de-dup preserving order
    out = []
    seen = set()
    for v in variants:
        k = _norm(v)
        if k and k not in seen:
            seen.add(k)
            out.append(v)
    return out


# Imports المشتركة
try:
    from db.session import SessionLocal
except ImportError:
    SessionLocal = None

try:
    from db.models import Doctor, Hospital, Department
except ImportError:
    Doctor = Hospital = Department = None


async def render_doctor_selection(message, context, query=None):
    """عرض شاشة اختيار الطبيب - عرض قائمة الأطباء المفلترين مباشرة.
    query: إذا مُمرَّر يُعدَّل الرسالة الحالية (للرجوع).
    """
    DoctorDataManager.clear_doctor_data(context)
    context.user_data['_current_search_type'] = 'doctor'

    report_tmp = context.user_data.get("report_tmp", {})
    hospital_name = report_tmp.get("hospital_name", "")
    department_name = report_tmp.get("department_name", "")

    logger.info(f"🎯 render_doctor_selection: hospital='{hospital_name}', department='{department_name}'")

    keyboard = []

    # ✅ جلب الأطباء المفلترين حسب المستشفى والقسم
    doctors_list = []
    doctor_names = []
    
    if hospital_name and department_name:
        try:
            # ✅ أولاً: البحث في قاعدة البيانات مباشرة
            if SessionLocal and Doctor and Hospital and Department:
                try:
                    with SessionLocal() as s:
                        from sqlalchemy import or_
                        # Collect ALL hospital IDs that match any name variant.
                        # A single logical hospital can appear under multiple rows
                        # ("Manipal Hospital - Old Airport Road" id=15 has 0 doctors;
                        # "Manipal Hospital, Old Airport Road" id=35 has 37 doctors).
                        # We must search across ALL matching rows, not stop at the first.
                        # Collect ALL hospital IDs that are logically the same hospital.
                        # Strategy: any Hospital row whose normalised name either (a) exactly
                        # matches one of our name variants, OR (b) contains the normalised
                        # UI name as a substring (e.g. "Aster Whitefield" ⊂ "Aster Whitefield
                        # Hospital, Bangalore").  This handles the common case where the UI
                        # list uses a short display name but DB rows use the full official name.
                        norm_base = _norm(hospital_name)
                        candidate_keys = {_norm(v) for v in _hospital_name_variants(hospital_name) if v}
                        all_hosps = s.query(Hospital).all()
                        hospital_ids = list({
                            h.id for h in all_hosps
                            if _norm(h.name) in candidate_keys or norm_base in _norm(h.name)
                        })
                        logger.info(
                            "Hospital name '%s' resolved to ids=%s",
                            hospital_name, hospital_ids,
                        )

                        # Join Doctor→Department on department_id and filter by hospital_id
                        # + Department.name.  We must NOT do a standalone Department lookup
                        # by name — department.hospital_id is unreliable in the DB (many rows
                        # have null or wrong hospital_id), so a global lookup returns the wrong
                        # department.id and the subsequent doctor filter yields nothing.
                        #
                        # UI department names are "Arabic | English" composites.  DB department
                        # names are English-only with spelling and naming variants across
                        # hospitals (Anesthesia/Anesthesiology/Anaesthesia, Orthopaedics/
                        # Orthopedics, "General Surgery" vs "General & Minimally Invasive
                        # Surgery", etc.).  We expand each UI English name to a set of known
                        # DB synonyms and use an OR LIKE filter across all of them.
                        db_doctors = []
                        if hospital_ids:
                            # Extract English part from "Arabic | English" UI name
                            if " | " in department_name:
                                en_part = department_name.split(" | ", 1)[1].strip()
                            else:
                                en_part = department_name.strip()

                            # Synonym map: UI English name → (exact_terms, prefix_terms).
                            # exact_terms: DB department name must equal one of these exactly.
                            # prefix_terms: DB department name must START WITH one of these
                            #   (safer than contains() for longer multi-word names).
                            # Short/ambiguous acronyms (ENT, ICU) use exact only to avoid
                            # substring pollution in unrelated department names.
                            # Maps normalised UI English name → (exact_match_list, startswith_list).
                            # exact: department.name (normalised) must equal one of these.
                            # startswith: department.name (normalised) must start with one of these.
                            # Keep startswith terms specific enough to avoid pulling in unrelated depts.
                            _DEPT_SYNONYMS: dict[str, tuple[list[str], list[str]]] = {
                                # ── Anaesthesia ──────────────────────────────────────────
                                "anesthesia": (
                                    ["anaesthesia", "anesthesia", "anesthesiology", "anaesthesiology",
                                     "anesthesiology & pain management", "cardiac anaesthesiology",
                                     "neuro anaesthesia", "liver transplant anaesthesia"],
                                    ["anaesthes", "anesthes"],
                                ),
                                # ── General Surgery ───────────────────────────────────────
                                "general surgery": (
                                    ["general surgery", "general & minimally invasive surgery",
                                     "general & laparoscopic surgery", "general & bariatric surgery",
                                     "general & surgical gastroenterology",
                                     "general surgery & allied specialities"],
                                    ["general surgery", "general & minimally", "general & lapar",
                                     "general & bariat", "general & surgical gastro"],
                                ),
                                # ── Orthopedics ──────────────────────────────────────────
                                "orthopedics": (
                                    ["orthopaedics", "orthopedics", "orthopaedic",
                                     "orthopedic & joint surgery", "orthopedics, joint replacement",
                                     "robotic orthopaedic surgery", "arthroscopy & sports injury",
                                     "hip & knee arthroplasty", "shoulder surgery",
                                     "paediatric ortho", "paediatric orthopaedics & spine surgery"],
                                    ["orthopaedic", "orthopedic"],
                                ),
                                # ── Spine ────────────────────────────────────────────────
                                "spine surgery": (
                                    ["spine surgery", "spine neurosurgery",
                                     "spine surgery / orthopaedics", "spine surgery / scoliosis",
                                     "neuro & spine surgery"],
                                    ["spine"],
                                ),
                                # ── Obstetrics & Gynaecology ─────────────────────────────
                                "obstetrics & gynecology": (
                                    ["obstetrics & gynaecology", "obstetrics & gynecology",
                                     "gynaecology", "fertility, ivf & obstetrics",
                                     "fetal medicine", "fetal medicine & genetics",
                                     "gynaecological endocrinology",
                                     "النساء والتوليد | obstetrics & gynecology"],
                                    ["obstetrics", "gynaecolog", "gynecolog"],
                                ),
                                "obstetrics & gynaecology": (
                                    ["obstetrics & gynaecology", "obstetrics & gynecology",
                                     "gynaecology", "النساء والتوليد | obstetrics & gynecology"],
                                    ["obstetrics", "gynaecolog", "gynecolog"],
                                ),
                                # ── Pediatrics ───────────────────────────────────────────
                                "pediatrics": (
                                    ["paediatrics", "pediatrics", "paediatrics & neonatology",
                                     "neonatology", "paediatric intensive care",
                                     "paediatrics, neonatology & neukids",
                                     "pediatric emergency", "pediatric emergency & picu"],
                                    ["paediatric", "pediatric"],
                                ),
                                "general pediatrics": (
                                    ["general paediatrics", "general pediatrics",
                                     "paediatrics", "pediatrics", "paediatrics & neonatology"],
                                    ["paediatric", "pediatric"],
                                ),
                                # ── Cardiology ───────────────────────────────────────────
                                "cardiology": (
                                    ["cardiology", "interventional cardiology",
                                     "interventional cardiology & structural heart",
                                     "electrophysiology", "electrophysiology & interventional cardiology",
                                     "cardiac electrophysiology", "paediatric cardiology",
                                     "pediatric cardiology"],
                                    ["cardiology", "electrophysiology"],
                                ),
                                # ── Cardiac Surgery / CTVS ───────────────────────────────
                                "cardiac surgery": (
                                    ["cardiac surgery", "cardiothoracic & vascular surgery",
                                     "cardiothoracic surgery", "cardio thoracic & vascular surgery (ctvs)",
                                     "cardio thoracic surgery", "ctvs",
                                     "cardiovascular & thoracic surgery (ctvs)",
                                     "cardiothoracic vascular & heart-lung transplant surgery",
                                     "robotic cardiac surgery", "heart & lung transplant",
                                     "paediatric cardiac surgery & cardiology"],
                                    ["cardiothoracic", "cardiac surgery", "cardio thoracic", "ctvs"],
                                ),
                                "thoracic surgery": (
                                    ["thoracic surgery", "cardiothoracic & vascular surgery",
                                     "cardiothoracic surgery", "ctvs"],
                                    ["thoracic"],
                                ),
                                "vascular surgery": (
                                    ["vascular surgery", "cardiothoracic & vascular surgery",
                                     "vascular & endovascular surgery"],
                                    ["vascular surgery"],
                                ),
                                # ── Neurology ────────────────────────────────────────────
                                "neurology": (
                                    ["neurology", "neurology & epilepsy", "neurology & stroke",
                                     "neurology & epilepsy centre", "neurology, epilepsy",
                                     "neurology & epileptology", "geriatric internal medicine",
                                     "paediatric neurology", "clinical psychology"],
                                    ["neurology"],
                                ),
                                # ── Neurosurgery ─────────────────────────────────────────
                                "neurosurgery": (
                                    ["neurosurgery", "adult neurosurgery", "spine neurosurgery",
                                     "neuro surgery", "neuro & spine surgery",
                                     "neurointerventional surgery"],
                                    ["neurosurgery", "neuro surgery"],
                                ),
                                # ── Critical Care / ICU ──────────────────────────────────
                                "critical care / icu": (
                                    ["critical care", "critical care medicine",
                                     "icu / critical care", "intensive care",
                                     "neuro critical care", "neuro critical care",
                                     "neuroanesthesia & neurocritical care",
                                     "neuroanaesthesia & neuro critical care"],
                                    ["critical care", "icu"],
                                ),
                                # ── Gastroenterology ─────────────────────────────────────
                                "gastroenterology": (
                                    ["gastroenterology", "gastroenterology & hepatology",
                                     "gastroenterology / gi surgery", "gastroenterology / general",
                                     "medical gastroenterology", "interventional endoscopy",
                                     "endoscopy & eus", "hepato-gastroenterology",
                                     "باطنية الجهاز الهضمي | gastroenterology",
                                     "ibd specialist"],
                                    ["gastroenterol", "endoscopy"],
                                ),
                                # ── GI Surgery ───────────────────────────────────────────
                                "gi surgery": (
                                    ["gi surgery", "gastrointestinal surgery",
                                     "gi, minimal access & bariatric surgery",
                                     "gi surgery & liver transplant",
                                     "surgical gastroenterology & bariatric",
                                     "bariatric & metabolic surgery",
                                     "bariatric, breast & surgical gastroenterology"],
                                    ["gi surgery", "gi,", "surgical gastro", "bariatric"],
                                ),
                                # ── Liver Transplant ─────────────────────────────────────
                                "hepatobiliary surgery": (
                                    ["hepatobiliary surgery", "hbp & liver transplant",
                                     "hpb surgery", "hpb & transplant",
                                     "liver transplant", "liver transplant surgery",
                                     "liver transplantation", "liver transplant & hpb surgery",
                                     "integrated liver care, liver transplant",
                                     "hepatology & transplant physician"],
                                    ["hepatobiliary", "hbp", "hpb", "liver transplant"],
                                ),
                                # ── Nephrology ───────────────────────────────────────────
                                "nephrology": (
                                    ["nephrology", "kidney transplant & nephrology",
                                     "kidney transplant & urology", "organ transplant & urology",
                                     "renal & transplant pathology"],
                                    ["nephrology", "kidney transplant"],
                                ),
                                # ── Urology ──────────────────────────────────────────────
                                "urology": (
                                    ["urology", "uro oncology", "uro-oncology, robotic surgery & renal transplantation",
                                     "uro-oncology & robotic surgery", "robotic surgery & urology",
                                     "robotic urology", "جراحة المسالك البولية | urology"],
                                    ["urology", "uro-oncology", "uro oncology"],
                                ),
                                # ── Pulmonology ──────────────────────────────────────────
                                "pulmonology / chest medicine": (
                                    ["pulmonology", "chest medicine", "respiratory medicine",
                                     "pulmonology & critical care", "pulmonology & sleep medicine",
                                     "pulmonology & lung transplant", "pediatric pulmonology"],
                                    ["pulmonology", "chest medicine", "respiratory"],
                                ),
                                # ── Endocrinology ────────────────────────────────────────
                                "endocrinology & diabetes": (
                                    ["endocrinology", "endocrinology & diabetes",
                                     "endocrinology / general medicine",
                                     "paediatric endocrinology", "pediatric endocrinology",
                                     "gynaecological endocrinology",
                                     "general physician & diabetologist"],
                                    ["endocrinology"],
                                ),
                                # ── Rheumatology ─────────────────────────────────────────
                                "rheumatology & immunology": (
                                    ["rheumatology", "rheumatology & immunology",
                                     "rheumatology & clinical immunology",
                                     "rheumatology / general medicine",
                                     "paediatric rheumatology & immunology",
                                     "paediatric haemato-oncology & rheumatology",
                                     "pediatric rheumatology"],
                                    ["rheumatology"],
                                ),
                                # ── Dermatology ──────────────────────────────────────────
                                "dermatology": (
                                    ["dermatology", "dermatology & cosmetology",
                                     "cosmetic & plastic surgery",
                                     "الأمراض الجلدية | dermatology"],
                                    ["dermatology"],
                                ),
                                # ── ENT ──────────────────────────────────────────────────
                                "ent": (
                                    ["ent", "ent surgery", "ent & skull base surgery",
                                     "ent, head & neck surgery, skull base surgery, cochlear implantology",
                                     "general opd (ent)", "الأذن والأنف والحنجرة | ent"],
                                    [],
                                ),
                                # ── Oncology ─────────────────────────────────────────────
                                "medical oncology": (
                                    ["medical oncology", "medical oncology & haematology",
                                     "medical oncology, immunotherapy & precision medicine",
                                     "medical & haemato oncology", "hematologic oncology",
                                     "oncology"],
                                    ["medical oncology"],
                                ),
                                "surgical oncology": (
                                    ["surgical oncology", "oncology surgery",
                                     "surgical oncology & head & neck oncology",
                                     "surgical oncology & robotic",
                                     "surgical oncology & robotic surgery",
                                     "robotic oncology surgery",
                                     "head & neck onco-surgery", "head & neck oncology",
                                     "head & neck oncology surgery",
                                     "head & neck cancer", "head & neck surgery & oncology",
                                     "breast oncology", "breast surgery",
                                     "breast surgery / oncology",
                                     "colon & rectal cancer", "gynaecological cancer",
                                     "gynaecological oncology", "gynecologic oncology",
                                     "onco imaging",
                                     "surgical & gynaecological oncology / robotic surgery, hipec, pipac",
                                     "surgical & head & neck oncology"],
                                    ["surgical oncology", "oncology surgery"],
                                ),
                                "radiation oncology": (
                                    ["radiation oncology", "radiation therapy", "radiotherapy"],
                                    ["radiation"],
                                ),
                                "the radiation therapy": (
                                    ["radiation oncology", "radiation therapy", "radiotherapy"],
                                    ["radiation"],
                                ),
                                # ── Hematology ───────────────────────────────────────────
                                "hematology": (
                                    ["hematology", "haematology", "hematology & bmt",
                                     "hematology & bone marrow transplantation",
                                     "haematology", "haematology & paediatric oncology",
                                     "haematology, haemato oncology & bmt",
                                     "haematology, paediatric haemato-oncology & bmt",
                                     "paediatric haemato-oncology & bmt",
                                     "paediatric haemato-oncology & rheumatology",
                                     "medical & haemato oncology"],
                                    ["hematolog", "haematolog"],
                                ),
                                # ── Physical Therapy / Rehab ─────────────────────────────
                                "physical therapy & rehabilitation": (
                                    ["physiotherapy & rehabilitation", "physiotherapy & rehab",
                                     "physical medicine & rehabilitation",
                                     "palliative medicine & rehab", "neuro rehabilitation"],
                                    ["physiotherapy", "physical medicine"],
                                ),
                                # ── Pain Management ──────────────────────────────────────
                                "pain management": (
                                    ["pain management", "pain medicine & palliative care",
                                     "palliative medicine", "palliative medicine & rehab"],
                                    ["pain management", "pain medicine", "palliative"],
                                ),
                                # ── Psychiatry ───────────────────────────────────────────
                                "psychiatry": (
                                    ["psychiatry", "mental health",
                                     "mental health & behavioural sciences", "psychology",
                                     "clinical psychology"],
                                    ["psychiatry", "mental health"],
                                ),
                                # ── Emergency ────────────────────────────────────────────
                                "emergency": (
                                    ["emergency", "emergency & trauma", "emergency medicine",
                                     "accident & emergency (emergency medicine)",
                                     "emergency & trauma services",
                                     "pediatric emergency", "pediatric emergency & picu"],
                                    ["emergency"],
                                ),
                                # ── Nuclear Medicine ─────────────────────────────────────
                                "nuclear medicine": (
                                    ["nuclear medicine", "nuclear medicine, theranostics"],
                                    ["nuclear medicine"],
                                ),
                                # ── Dentistry ────────────────────────────────────────────
                                "dentistry": (
                                    ["dentistry", "dental surgery", "oral & maxillofacial surgery",
                                     "pediatric dentistry", "maxillofacial radiology"],
                                    ["dentistry", "dental"],
                                ),
                                # ── Ophthalmology ────────────────────────────────────────
                                "ophthalmology": (
                                    ["ophthalmology", "general ophthalmology",
                                     "general ophthalmology, medical retina & uvea",
                                     "cataract & glaucoma", "cataract & medical retina",
                                     "cataract & refractive services",
                                     "cataract, cornea & refractive service",
                                     "cataract, cornea & refractive services",
                                     "cataract, cornea & refractive surgery",
                                     "cataract, medical retina & uvea services",
                                     "cornea & refractive services", "cornea services",
                                     "cornea (registrar – cornea)",
                                     "cornea, ocular surface & refractive services",
                                     "glaucoma", "medical retina",
                                     "oculoplastic & lacrimal surgery",
                                     "orbit & oculoplasty",
                                     "orbit, oculoplasty & ocular oncology",
                                     "paediatric ophthalmology",
                                     "paediatric ophthalmology & strabismus",
                                     "retinal services", "vitreoretina",
                                     "vitreoretina & ocular oncology",
                                     "vitreoretinal services",
                                     "vr ocular oncology & vitreoretinal services"],
                                    ["ophthalmology", "cataract", "cornea", "glaucoma",
                                     "retina", "oculoplast", "vitreoretina"],
                                ),
                                # ── Plastic Surgery ──────────────────────────────────────
                                "plastic surgery": (
                                    ["plastic surgery", "plastic & reconstructive surgery",
                                     "plastic, reconstructive & aesthetic surgery",
                                     "cosmetic & plastic surgery",
                                     "جراحة التجميل | plastic surgery"],
                                    ["plastic surgery", "plastic &", "plastic,"],
                                ),
                                # ── Infectious Diseases ──────────────────────────────────
                                "infectious diseases": (
                                    ["infectious diseases", "infectious disease",
                                     "الأمراض المعدية | infectious diseases"],
                                    ["infectious"],
                                ),
                                # ── Internal Medicine ─────────────────────────────────────
                                "internal medicine": (
                                    ["internal medicine", "general medicine",
                                     "family medicine", "general physician & diabetologist",
                                     "geriatric medicine", "geriatric internal medicine",
                                     "endocrinology / general medicine",
                                     "rheumatology / general medicine",
                                     "gastroenterology / general"],
                                    ["internal medicine", "general medicine", "family medicine"],
                                ),
                                # ── Radiology ────────────────────────────────────────────
                                "radiology": (
                                    ["radiology", "radiology & imaging",
                                     "clinical imaging & interventional radiology",
                                     "interventional radiology", "maxillofacial radiology",
                                     "onco imaging"],
                                    ["radiology", "imaging"],
                                ),
                                # ── Pathology / Lab ──────────────────────────────────────
                                "pathology": (
                                    ["pathology", "pathology & histopathology",
                                     "laboratory medicine", "laboratory services",
                                     "microbiology & laboratory medicine",
                                     "blood bank / transfusion medicine",
                                     "blood centre & transfusion medicine",
                                     "renal & transplant pathology", "medical genetics",
                                     "genetics", "clinical nutrition",
                                     "nutrition & dietetics"],
                                    ["pathology", "laboratory", "microbiology"],
                                ),
                                # ── IVF / Reproductive ───────────────────────────────────
                                "ivf": (
                                    ["ivf & reproductive medicine",
                                     "fertility, ivf & obstetrics"],
                                    ["ivf", "fertility"],
                                ),
                                # ── جراحة العظام (Arabic) ────────────────────────────────
                                "جراحة العظام": (
                                    ["orthopaedics", "orthopedics", "جراحة العظام"],
                                    ["orthopaedic", "orthopedic"],
                                ),
                            }

                            en_key = _norm(en_part)
                            exact_terms, prefix_terms = _DEPT_SYNONYMS.get(en_key, ([en_key], [en_key]))
                            # Always include the literal UI names as exact candidates too
                            all_exact = list({_norm(t) for t in exact_terms + [en_part, department_name]} - {""})
                            all_prefix = list({_norm(t) for t in prefix_terms} - {""})

                            exact_clauses = [func.lower(func.trim(Department.name)) == t for t in all_exact]
                            prefix_clauses = [func.lower(func.trim(Department.name)).startswith(t) for t in all_prefix]
                            dept_filter = or_(*(exact_clauses + prefix_clauses))

                            db_doctors = (
                                s.query(Doctor)
                                .join(Department, Doctor.department_id == Department.id)
                                .filter(
                                    Doctor.hospital_id.in_(hospital_ids),
                                    Doctor.full_name.isnot(None),
                                    Doctor.full_name != "",
                                    dept_filter,
                                )
                                .order_by(Doctor.full_name)
                                .all()
                            )
                        
                        # استخراج الأسماء من قاعدة البيانات
                        for doc in db_doctors:
                            name = doc.full_name or doc.name
                            if name and name not in doctor_names:
                                doctor_names.append(name)
                        
                        logger.info(f"✅ تم جلب {len(doctor_names)} طبيب من قاعدة البيانات للمستشفى '{hospital_name}' والقسم '{department_name}'")
                except Exception as db_error:
                    logger.error(f"❌ خطأ في جلب الأطباء من قاعدة البيانات: {db_error}", exc_info=True)
            
            # ✅ ثانياً: البحث في services.doctors_smart_search (للبحث عن أطباء إضافيين)
            try:
                from services.doctors_smart_search import get_doctors_for_hospital_dept
                doctors_list = get_doctors_for_hospital_dept(hospital_name, department_name)
                
                # إضافة الأسماء من services إلى القائمة (بدون تكرار)
                for doctor in doctors_list:
                    name = doctor.get('name', '') or doctor.get('full_name', '')
                    if name and name not in doctor_names:
                        doctor_names.append(name)
                
                logger.info(f"✅ تم إضافة {len(doctors_list)} طبيب من services للمستشفى '{hospital_name}' والقسم '{department_name}'")
            except Exception as e:
                logger.error(f"❌ خطأ في جلب الأطباء من services: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"❌ خطأ في جلب الأطباء: {e}", exc_info=True)

    # ✅ إذا كان هناك أطباء، عرضهم كأزرار
    if doctor_names:
        # ترتيب الأسماء أبجدياً
        doctor_names.sort()
        
        # حفظ قائمة الأطباء في context للاسترجاع لاحقاً
        context.user_data.setdefault("report_tmp", {})["_doctors_list"] = doctor_names
        
        # أزرار الأطباء بالتخطيط الذكي (حد أقصى 50 طبيب)
        display_names = doctor_names[:50]
        doctor_rows = smart_rows(
            [{"name": name, "_idx": idx} for idx, name in enumerate(display_names)],
            lambda item: InlineKeyboardButton(
                f"👨‍⚕️ {item['name']}",
                callback_data=f"doctor_idx:{item['_idx']}"
            )
        )
        keyboard.extend(doctor_rows)

        keyboard.append([InlineKeyboardButton(
            "✏️ إدخال اسم الطبيب يدوياً",
            callback_data="doctor_manual"
        )])

        ctx_line = f"🏥 {hospital_name}  ›  🏷️ {department_name}" if hospital_name else ""
        text = screen_header(
            icon="👨‍⚕️", title="اختيار الطبيب",
            step=5, total_steps=6,
            count=len(doctor_names), count_label="طبيب",
            context_line=ctx_line,
        )
    else:
        keyboard.append([InlineKeyboardButton(
            "✏️ إدخال اسم الطبيب يدوياً",
            callback_data="doctor_manual"
        )])

        if hospital_name and department_name:
            ctx_line = f"🏥 {hospital_name}  ›  🏷️ {department_name}"
            text = screen_header(
                icon="👨‍⚕️", title="اختيار الطبيب",
                step=5, total_steps=6,
                context_line=ctx_line,
            )
            text += "\n\n⚠️ لم يتم العثور على أطباء في هذا القسم.\nأدخل الاسم يدوياً:"
        else:
            text = screen_header(icon="👨‍⚕️", title="اختيار الطبيب", step=5, total_steps=6)
            text += "\n\n⚠️ اختر المستشفى والقسم أولاً."

    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="go_to_department_selection"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    markup = InlineKeyboardMarkup(keyboard)
    # حفظ السياق
    SelectorContext.save_doctor(context)
    if query:
        try:
            await query.edit_message_text(text, reply_markup=markup, parse_mode="Markdown")
            return
        except Exception:
            pass
    try:
        await message.reply_text(text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"❌ خطأ في عرض قائمة اختيار الطبيب: {e}", exc_info=True)
        try:
            await message.reply_text(text.replace("**", ""), reply_markup=markup)
        except Exception as e2:
            logger.error(f"❌ خطأ في المحاولة الثانية: {e2}")


async def show_doctor_selection(message, context, search_query="", query=None):
    """Navigation wrapper — single doctor render authority."""
    context.user_data['last_valid_state'] = 'search_doctor_screen'
    context.user_data['_conversation_state'] = STATE_SELECT_DOCTOR
    context.user_data['_current_search_type'] = 'doctor'
    await render_doctor_selection(message, context, query=query)


async def show_doctor_input(message, context, query=None):
    """Navigation wrapper — delegates to show_doctor_selection."""
    await show_doctor_selection(message, context, query=query)


async def handle_doctor_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار طبيب من القائمة أو زر الإدخال اليدوي"""
    from .utils import _nav_buttons
    from .action_type_handlers import show_action_type_menu
    
    query = update.callback_query
    await query.answer()
    
    logger.info(f"🔧 handle_doctor_selection: callback_data='{query.data}'")
    logger.info(f"🔧 handle_doctor_selection: Current _conversation_state = {context.user_data.get('_conversation_state', 'NOT SET')}")
    logger.info(f"🔧 handle_doctor_selection: Expected STATE_SELECT_DOCTOR = {STATE_SELECT_DOCTOR}")

    # ✅ معالجة اختيار طبيب من القائمة (باستخدام الفهرس)
    if query.data.startswith("doctor_idx:"):
        try:
            index_str = query.data.split(":", 1)[1]
            doctor_idx = int(index_str)
            
            # استرجاع قائمة الأطباء من context.user_data
            doctors_list = context.user_data.get("report_tmp", {}).get("_doctors_list", [])

            if not doctors_list:
                # Snapshot wiped by PM2 restart — self-heal by re-rendering selection screen
                logger.warning(
                    "_doctors_list snapshot missing for user %s — re-rendering doctor selection",
                    getattr(query.from_user, "id", "?"),
                )
                await query.answer()
                await render_doctor_selection(query.message, context)
                return STATE_SELECT_DOCTOR

            if doctor_idx < 0 or doctor_idx >= len(doctors_list):
                logger.error(f"❌ فهرس غير صالح: {doctor_idx}, القائمة تحتوي على {len(doctors_list)} عنصر")
                await query.answer("⚠️ حدث خطأ في اختيار الطبيب", show_alert=True)
                return STATE_SELECT_DOCTOR
            
            doctor_name = doctors_list[doctor_idx]
            
            # حفظ اسم الطبيب
            context.user_data.setdefault("report_tmp", {})["doctor_name"] = doctor_name
            context.user_data["report_tmp"].setdefault("step_history", []).append(R_DOCTOR)
            
            # تنظيف البيانات المؤقتة
            context.user_data.get("report_tmp", {}).pop("_doctors_list", None)
            
            await query.edit_message_text(
                f"✅ **تم اختيار الطبيب**\n\n"
                f"👨‍⚕️ **الطبيب:**\n"
                f"{doctor_name}",
                parse_mode="Markdown"
            )
            
            # الانتقال إلى اختيار نوع الإجراء
            context.user_data['last_valid_state'] = 'action_type_selection'
            context.user_data['_conversation_state'] = R_ACTION_TYPE
            await show_action_type_menu(query.message, context)
            return R_ACTION_TYPE
        except (ValueError, IndexError) as e:
            logger.error(f"❌ خطأ في معالجة اختيار الطبيب (فهرس): {e}", exc_info=True)
            await query.answer("⚠️ حدث خطأ في اختيار الطبيب", show_alert=True)
            return STATE_SELECT_DOCTOR

    if query.data == "doctor_manual":
        if "report_tmp" not in context.user_data:
            context.user_data["report_tmp"] = {}
        
        logger.info("🔧 تم الضغط على زر الإدخال اليدوي للطبيب")
        
        try:
            await query.edit_message_text(
                "👨‍⚕️ **اسم الطبيب**\n\n"
                "✏️ يرجى إدخال اسم الطبيب:",
                reply_markup=_nav_buttons(show_back=False),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"❌ خطأ في تعديل الرسالة: {e}")
            try:
                await query.message.reply_text(
                    "👨‍⚕️ **اسم الطبيب**\n\n"
                    "✏️ يرجى إدخال اسم الطبيب:",
                    reply_markup=_nav_buttons(show_back=False),
                    parse_mode="Markdown"
                )
            except:
                pass
        
        context.user_data["report_tmp"]["doctor_manual_mode"] = True
        logger.info("✅ تم تفعيل وضع الإدخال اليدوي للطبيب")
        return STATE_SELECT_DOCTOR


async def handle_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم الطبيب يدوياً أو اختياره من inline query"""
    from .action_type_handlers import show_action_type_menu
    from .utils import _nav_buttons
    
    text = update.message.text.strip()
    logger.info(f"🔍 handle_doctor: received text='{text}'")
    
    if "report_tmp" not in context.user_data:
        context.user_data["report_tmp"] = {}
    
    # ✅ إزالة دعم inline query - لم نعد نستخدمها

    # التحقق إذا كان في وضع الإدخال اليدوي
    manual_mode = context.user_data.get("report_tmp", {}).get("doctor_manual_mode", False)
    logger.info(f"🔍 handle_doctor: manual_mode={manual_mode}")
    
    if manual_mode:
        valid, msg = validate_text_input(text, min_length=2, max_length=100)
        if not valid:
            await update.message.reply_text(
                f"⚠️ **خطأ: {msg}**\n\n"
                f"يرجى إدخال اسم الطبيب:",
                reply_markup=_nav_buttons(show_back=True, previous_state_name="new_consult_complaint", context=context),
                parse_mode="Markdown"
            )
            return STATE_SELECT_DOCTOR

        context.user_data["report_tmp"]["doctor_name"] = text
        context.user_data["report_tmp"].setdefault("step_history", []).append(R_DOCTOR)
        context.user_data["report_tmp"].pop("doctor_manual_mode", None)
        logger.info(f"✅ تم حفظ اسم الطبيب يدوياً: {text}")
        
        # ✅ حفظ الطبيب في قاعدة البيانات مع المستشفى والقسم
        try:
            from db.session import SessionLocal
            from db.models import Doctor, Hospital, Department
            
            report_tmp = context.user_data.get("report_tmp", {})
            hospital_name = report_tmp.get("hospital_name", "")
            department_name = report_tmp.get("department_name", "")
            
            with SessionLocal() as s:
                # البحث عن الطبيب أولاً (البحث بـ full_name أو name)
                from sqlalchemy import or_
                doctor = s.query(Doctor).filter(
                    or_(
                        Doctor.full_name == text,
                        Doctor.name == text
                    )
                ).first()
                
                if not doctor:
                    # إنشاء طبيب جديد
                    doctor = Doctor(
                        name=text,
                        full_name=text
                    )
                    
                    # محاولة ربطه بالمستشفى إذا كان موجوداً
                    if hospital_name:
                        hospital = s.query(Hospital).filter(Hospital.name == hospital_name).first()
                        if hospital:
                            doctor.hospital_id = hospital.id
                    
                    # محاولة ربطه بالقسم إذا كان موجوداً
                    if department_name:
                        department = s.query(Department).filter(Department.name == department_name).first()
                        if department:
                            doctor.department_id = department.id
                    
                    s.add(doctor)
                    s.commit()
                    logger.info(f"✅ تم حفظ الطبيب في قاعدة البيانات: {text} (مستشفى: {hospital_name}, قسم: {department_name})")
                else:
                    # ✅ تحديث معلومات المستشفى والقسم إذا لم تكن موجودة
                    updated = False
                    if hospital_name and not doctor.hospital_id:
                        hospital = s.query(Hospital).filter(Hospital.name == hospital_name).first()
                        if hospital:
                            doctor.hospital_id = hospital.id
                            updated = True
                    
                    if department_name and not doctor.department_id:
                        department = s.query(Department).filter(Department.name == department_name).first()
                        if department:
                            doctor.department_id = department.id
                            updated = True
                    
                    if updated:
                        s.commit()
                        logger.info(f"✅ تم تحديث معلومات الطبيب: {text}")
                    else:
                        logger.info(f"ℹ️ الطبيب موجود بالفعل في قاعدة البيانات: {text}")
        except Exception as e:
            logger.error(f"❌ خطأ في حفظ الطبيب في قاعدة البيانات: {e}", exc_info=True)

        context.user_data['last_valid_state'] = 'action_type_selection'
        context.user_data['_conversation_state'] = R_ACTION_TYPE
        logger.info(f"📋 Moving to action_type_selection")

        await update.message.reply_text(
            f"✅ **تم حفظ اسم الطبيب**\n\n"
            f"👨‍⚕️ **الطبيب:**\n"
            f"{text}\n\n"
            f"💾 سيظهر هذا الطبيب في القائمة في المرة القادمة.",
            parse_mode="Markdown"
        )
        await show_action_type_menu(update.message, context)
        return R_ACTION_TYPE

    # إذا لم يكن في وضع الإدخال اليدوي، نعيد عرض القائمة
    logger.warning(f"⚠️ handle_doctor: لم يتم التعرف على النص. النص: '{text}'")
    await show_doctor_selection(update.message, context)
    return STATE_SELECT_DOCTOR

