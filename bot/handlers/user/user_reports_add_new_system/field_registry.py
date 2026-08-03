# =============================================================================
# field_registry.py
# 🎯 مصدر الحقيقة الوحيد لحقول كل نوع إجراء — تحل محل القوائم اليدوية
# المنفصلة التي كانت موجودة في flows/shared.py (قبل النشر) و
# user_reports_edit.py (بعد النشر)، وكانت تتباعد باستمرار (كل خلل واجهناه
# هذه الجلسة — رقم الجلسة مفقود، حقول الزراعة فارغة، تسمية خاطئة...— سببه
# نفس النمط: قائمتان منفصلتان بلا رابط برمجي بينهما).
#
# لكل حقل: مفتاح واحد نهائي (`key`) يُستخدم في `report_tmp` أثناء المحادثة
# الحية، وعمود واحد في `Report` (`db_column`، يساوي `key` افتراضياً إن لم
# يُحدَّد) يُقرأ منه/يُكتب إليه مباشرة — **بلا أي دمج نصّي مركّب ولا تحليل
# لاحق**. التسميات الموحَّدة التي اختِيرت لإنهاء تعارضات كانت موجودة فعلياً:
#   - `no_report_reason` (قبل النشر) + `no_paper_report_reason` (بعد النشر/DB)
#     → مفتاح واحد `no_paper_report_reason` في كل مكان.
#   - `device_name` (قبل النشر) + `device_details` (بعد النشر/الفورمه)
#     → `device_details` في كل مكان.
#   - `complaint`/`complaint_text` → `complaint_text` (عمود مباشر).
#   - `status`/`case_status` → `case_status` (عمود مباشر).
#   - `delivery_date`/`radiology_delivery_date` → `radiology_delivery_date`.
#   - `tests` (استشارة جديدة + استشارة مع قرار عملية) → عمود `medications`
#     صراحة لكليهما (كان "استشارة جديدة" يُقرأ خطأً من `notes` بعد النشر).
#   - `decision` → عمود `doctor_decision` (أصبح مخصَّصاً لهذا الحقل فقط،
#     وليس نصاً مركّباً يحوي حقولاً أخرى معه).
#   - `recommendations` (استشارة أخيرة) → عمود `treatment_plan` الموجود
#     أصلاً (كان يُكتب في doctor_decision لكن يُقرأ من treatment_plan
#     الفارغ دائماً — خطأ حقيقي، ثابت الآن).
#
# ⚠️ لا وقت مستقل (`followup_time`) كحقل قابل للتعديل بذاته — يُعدَّل دائماً
# مع `followup_date` عبر نفس شاشة التقويم/الساعة (تطابق سلوك ما بعد النشر
# الذي لم يكن يعرضه أصلاً كزر منفصل؛ توحيد بدل إضافة خطوة جديدة).
# =============================================================================

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldDef:
    key: str            # المفتاح في report_tmp (قبل النشر) وفي القواميس المبنية يدوياً
    label: str           # التسمية العربية المعروضة كزر
    db_column: str = ""  # عمود Report — افتراضياً نفس key إن لم يُحدَّد
    is_date: bool = False  # يمر بشاشة التقويم بدل نص حر

    def __post_init__(self):
        if not self.db_column:
            object.__setattr__(self, "db_column", self.key)


def _f(key, label, db_column=None, is_date=False):
    return FieldDef(key, label, db_column or key, is_date)


_NO_REPORT_REASON = _f("no_paper_report_reason", "📋 سبب عدم وجود تقرير طبي")
_TRANSLATOR = _f("translator_name", "👤 المترجم")
_FOLLOWUP_DATE = _f("followup_date", "📅 موعد العودة", is_date=True)
_FOLLOWUP_REASON = _f("followup_reason", "✍️ سبب العودة")


def _with_followup_and_gate(*fields):
    """الذيل المشترك لمعظم الأنواع: تاريخ العودة، سبب العودة، سبب عدم وجود
    تقرير طبي، المترجم — بهذا الترتيب بالضبط."""
    return [*fields, _FOLLOWUP_DATE, _FOLLOWUP_REASON, _NO_REPORT_REASON, _TRANSLATOR]


REPORT_FIELD_REGISTRY: dict[str, list[FieldDef]] = {
    "new_consult": _with_followup_and_gate(
        _f("complaint_text", "💬 شكوى المريض"),
        _f("diagnosis", "🔬 التشخيص الطبي"),
        _f("decision", "📝 قرار الطبيب", db_column="doctor_decision"),
        _f("tests", "🧪 الفحوصات والأشعة", db_column="medications"),
    ),
    "periodic_followup": _with_followup_and_gate(
        _f("complaint_text", "💬 شكوى المريض"),
        _f("diagnosis", "🔬 التشخيص الطبي"),
        _f("decision", "📝 قرار الطبيب", db_column="doctor_decision"),
    ),
    "inpatient_followup": _with_followup_and_gate(
        _f("complaint_text", "🛏️ حالة المريض اليومية"),
        _f("decision", "📝 قرار الطبيب اليومي", db_column="doctor_decision"),
        _f("room_number", "🏥 رقم الغرفة والطابق"),
    ),
    "emergency": _with_followup_and_gate(
        _f("complaint_text", "💬 شكوى المريض"),
        _f("diagnosis", "🔬 التشخيص الطبي"),
        _f("decision", "📝 قرار الطبيب وماذا تم", db_column="doctor_decision"),
        _f("case_status", "🏥 وضع الحالة"),
        _f("room_number", "🚪 رقم الغرفة"),
        # ✅ حقول فرع "تم الترقيد/تم إجراء عملية" — كانت تُحفَظ في doctor_decision
        # المركّب لتنجو من إعادة النشر، لكن لم تظهر كحقل قابل للتعديل في أي
        # من الشاشتين إطلاقاً (خلل حقيقي مكتشَف أثناء توحيد السجل). الآن
        # أعمدة مستقلة، تظهر تلقائياً فقط عند وجود قيمة فعلية (نفس آلية بقية
        # الحقول الاختيارية).
        _f("admission_type", "🏥 نوع الترقيد"),
        _f("admission_notes", "📝 ملاحظات الرقود"),
        _f("operation_details", "⚕️ تفاصيل العملية"),
    ),
    "admission": _with_followup_and_gate(
        _f("admission_reason", "🛏️ سبب الرقود"),
        _f("room_number", "🚪 رقم الغرفة"),
        _f("notes", "📝 ملاحظات"),
    ),
    "surgery_consult": _with_followup_and_gate(
        _f("diagnosis", "🔬 التشخيص"),
        _f("decision", "📝 قرار الطبيب وتفاصيل العملية", db_column="doctor_decision"),
        _f("operation_name_en", "🔤 اسم العملية بالإنجليزي"),
        _f("success_rate", "📊 نسبة نجاح العملية"),
        _f("benefit_rate", "💡 نسبة الاستفادة"),
        _f("tests", "🧪 الفحوصات والأشعة", db_column="medications"),
    ),
    "operation": _with_followup_and_gate(
        _f("operation_details", "⚕️ تفاصيل العملية بالعربي"),
        _f("operation_name_en", "🔤 اسم العملية بالإنجليزي"),
        _f("notes", "📝 ملاحظات"),
    ),
    "final_consult": [
        # ✅ لا موعد/سبب عودة لهذا النوع (استشارة أخيرة = لا عودة بالتصميم).
        _f("diagnosis", "🔬 التشخيص النهائي"),
        _f("decision", "📝 قرار الطبيب", db_column="doctor_decision"),
        _f("recommendations", "💡 التوصيات الطبية", db_column="treatment_plan"),
        _NO_REPORT_REASON,
        _TRANSLATOR,
    ],
    "discharge": _with_followup_and_gate(
        _f("discharge_type", "🚪 نوع الخروج"),
        _f("admission_summary", "📋 ملخص الرقود"),
        _f("operation_details", "⚕️ تفاصيل العملية"),
        _f("operation_name_en", "🔤 اسم العملية بالإنجليزي"),
    ),
    "rehab_physical": _with_followup_and_gate(
        _f("therapy_details", "🏃 تفاصيل جلسة العلاج الطبيعي"),
    ),
    "rehab_device": _with_followup_and_gate(
        _f("device_details", "🦾 تفاصيل الجهاز"),
    ),
    "radiology": [
        # ✅ لا موعد/سبب عودة — الحقل الخاص به هو تاريخ التسليم.
        _f("radiology_type", "🔬 نوع الأشعة والفحوصات"),
        _f("radiology_delivery_date", "📅 تاريخ التسليم", is_date=True),
        _NO_REPORT_REASON,
        _TRANSLATOR,
    ],
    "endoscopy": _with_followup_and_gate(
        _f("complaint_text", "💬 شكوى المريض"),
        _f("endoscopy_type", "🔬 نوع المنظار"),
        _f("endoscopy_result", "📋 نتيجة المنظار / خطة الطبيب"),
        _f("notes", "📝 ملاحظات"),
    ),
    "radiation_therapy": _with_followup_and_gate(
        _f("radiation_therapy_type", "☢️ نوع الإشعاعي"),
        _f("radiation_therapy_recommendations", "📝 ملاحظات / توصيات"),
        # ⚠️ رقم الجلسة/الجلسات المتبقية غير قابلين للتعديل هنا عمداً —
        # يُحسَبان من TreatmentPlan، تعديلهما هنا يفصلهما عن الخطة الفعلية.
        # التعديل الصحيح عبر "✏️ تعديل الخطة" أثناء إنشاء تقرير جديد.
    ),
    "treatment_chemo": _with_followup_and_gate(
        _f("session_number", "🔢 رقم الجلسة الحالية"),
        _f("complaint_text", "💬 شكوى المريض"),
        _f("notes", "📝 ملاحظات الطبيب"),
    ),
    "treatment_targeted": _with_followup_and_gate(
        _f("session_number", "🔢 رقم الجلسة الحالية"),
        _f("complaint_text", "💬 شكوى المريض"),
        _f("notes", "📝 ملاحظات الطبيب"),
    ),
    "treatment_immuno": _with_followup_and_gate(
        _f("session_number", "🔢 رقم الجلسة الحالية"),
        _f("complaint_text", "💬 شكوى المريض"),
        _f("notes", "📝 ملاحظات الطبيب"),
    ),
    "treatment_dialysis": [
        # ✅ لا شكوى/ملاحظات/سبب عدم وجود تقرير طبي — مسار مبسَّط جداً
        # بالتصميم (بناءً على طلب المستخدم صراحة هذه الجلسة).
        _f("session_number", "🔢 رقم الجلسة الحالية"),
        _f("followup_date", "📅 تاريخ الجلسة القادمة", is_date=True),
        _TRANSLATOR,
    ],
    "treatment_combined": _with_followup_and_gate(
        _f("complaint_text", "💬 شكوى المريض"),
        _f("notes", "📝 ملاحظات الطبيب"),
    ),
    "transplant": _with_followup_and_gate(
        _f("transplant_type", "🫁 نوع الزراعة"),
        _f("transplant_parties", "🏢 الجهة"),
        _f("transplant_details", "📝 تفاصيل المعاملة"),
    ),
    "appointment_reschedule": [
        # ✅ لا يمر ببوابة "هل يوجد تقرير طبي؟" — حقوله الخاصة بدل الموعد العام.
        _f("app_reschedule_reason", "📅 سبب تأجيل الموعد"),
        _f("app_reschedule_return_date", "📅 موعد العودة الجديد", is_date=True),
        _f("app_reschedule_return_reason", "✍️ سبب العودة"),
        _TRANSLATOR,
    ],
    "device": _with_followup_and_gate(
        _f("device_details", "🦾 تفاصيل الجهاز"),
    ),
}

# ✅ اسم "علاج طبيعي" واسم "علاج طبيعي وإعادة تأهيل" يشيران لنفس الفورمه —
# بدل تكرار قائمة الحقول، كلاهما يُشيران لنفس مفتاح السجل.
REPORT_FIELD_REGISTRY["rehab_physical_short"] = REPORT_FIELD_REGISTRY["rehab_physical"]
# ✅ "app_reschedule" مفتاح flow_type بديل يظهر في بعض نقاط الكود القديمة
# لنفس "appointment_reschedule" — يُبقى مرادفاً لتفادي كسر أي استدعاء قديم.
REPORT_FIELD_REGISTRY["app_reschedule"] = REPORT_FIELD_REGISTRY["appointment_reschedule"]


def get_fields_for_flow_type(flow_type: str) -> list[FieldDef]:
    """القائمة الأولية — تُستخدم مباشرة قبل النشر (flow_type معروف من السياق)."""
    return list(REPORT_FIELD_REGISTRY.get(flow_type or "", []))


# =============================================================================
# medical_action (النص العربي المحفوظ في Report.medical_action) → flow_type
# =============================================================================
# بعد النشر لا يوجد flow_type محفوظ — فقط النص العربي. هذه الدالة توحّد كل
# منطق المطابقة المتناثر سابقاً بين عدة دوال في user_reports_edit.py.

def resolve_flow_type_from_medical_action(medical_action: str) -> str:
    action = (medical_action or "").strip()
    if not action:
        return ""

    # ✅ الأنواع المدمجة من اختيار متعدد لجلسات الأورام — قد تشمل أكثر من
    # خطة علاج واحدة، فلا يوجد flow_type واحد واضح. يُعامَل بحقول عامة.
    if " + " in action and any(
        lbl in action for lbl in
        ("العلاج الكيماوي", "العلاج الموجه", "العلاج المناعي", "جلسات غسيل الكلى", "جلسة إشعاعي")
    ):
        return "treatment_combined"

    if "متابعة في الرقود" in action:
        return "inpatient_followup"

    direct_map = {
        "استشارة جديدة": "new_consult",
        "استشارة مع قرار عملية": "surgery_consult",
        "استشارة أخيرة": "final_consult",
        "طوارئ": "emergency",
        "مراجعة / عودة دورية": "periodic_followup",
        "عملية": "operation",
        "علاج طبيعي وإعادة تأهيل": "rehab_physical",
        "علاج طبيعي": "rehab_physical",
        "ترقيد": "admission",
        "خروج من المستشفى": "discharge",
        "خروج": "discharge",
        "تأجيل موعد": "appointment_reschedule",
        "أشعة وفحوصات": "radiology",
        "أجهزة تعويضية": "rehab_device",
        "جلسة إشعاعي": "radiation_therapy",
        "العلاج الكيماوي": "treatment_chemo",
        "العلاج الموجه": "treatment_targeted",
        "العلاج المناعي": "treatment_immuno",
        "جلسات غسيل الكلى": "treatment_dialysis",
        "معاملة الزراعة": "transplant",
        "المناظير": "endoscopy",
    }
    return direct_map.get(action, "")


def get_fields_for_medical_action(medical_action: str) -> list[FieldDef]:
    """القائمة بعد النشر — تُشتق من medical_action عبر نفس السجل الموحَّد.
    medical_action فارغ تماماً يُعامَل بمنطق منفصل في المستدعي (رسالة
    تحذير مختلفة) — هنا فقط حالة "نص غير فارغ لكن غير معروف"."""
    flow_type = resolve_flow_type_from_medical_action(medical_action)
    if not flow_type:
        return [
            _f("complaint_text", "💬 شكوى المريض"),
            _f("decision", "📝 قرار الطبيب", db_column="doctor_decision"),
            _FOLLOWUP_DATE,
            _TRANSLATOR,
        ]
    return get_fields_for_flow_type(flow_type)
