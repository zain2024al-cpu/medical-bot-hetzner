# =============================
# states.py
# تعريف جميع الـ States - State Machine واضحة (FSM)
# =============================

# State Machine لإضافة التقارير الطبية - المرحلة الأساسية
(
    STATE_SELECT_DATE,           # اختيار التاريخ
    STATE_SELECT_DATE_TIME,      # اختيار التاريخ والوقت
    STATE_SELECT_PATIENT,        # اختيار اسم المريض
    STATE_SELECT_HOSPITAL,       # اختيار المستشفى
    STATE_SELECT_DEPARTMENT,     # اختيار القسم الرئيسي
    STATE_SELECT_SUBDEPARTMENT,  # اختيار القسم الفرعي
    STATE_SELECT_DOCTOR,         # اختيار اسم الطبيب
    STATE_SELECT_ACTION_TYPE,    # اختيار نوع الإجراء
) = range(8)

# States للرجوع - R_* states (للتوافق مع الكود القديم)
R_DATE = STATE_SELECT_DATE
R_DATE_TIME = STATE_SELECT_DATE_TIME
R_PATIENT = STATE_SELECT_PATIENT
R_HOSPITAL = STATE_SELECT_HOSPITAL
R_DEPARTMENT = STATE_SELECT_DEPARTMENT
R_SUBDEPARTMENT = STATE_SELECT_SUBDEPARTMENT
R_DOCTOR = STATE_SELECT_DOCTOR
R_ACTION_TYPE = STATE_SELECT_ACTION_TYPE

# مسار 1: استشارة جديدة (7-15) - تاريخ ووقت منفصلان
(
    NEW_CONSULT_COMPLAINT, NEW_CONSULT_DIAGNOSIS, NEW_CONSULT_DECISION,
    NEW_CONSULT_TESTS, NEW_CONSULT_FOLLOWUP_DATE, NEW_CONSULT_FOLLOWUP_TIME,
    NEW_CONSULT_FOLLOWUP_REASON, NEW_CONSULT_TRANSLATOR, NEW_CONSULT_CONFIRM
) = range(7, 16)

# مسار 2: مراجعة/عودة دورية (16-23) - مدمج بالفعل ✓
(
    FOLLOWUP_COMPLAINT, FOLLOWUP_DIAGNOSIS, FOLLOWUP_DECISION, FOLLOWUP_ROOM_FLOOR,
    FOLLOWUP_DATE_TIME, FOLLOWUP_REASON, FOLLOWUP_TRANSLATOR, FOLLOWUP_CONFIRM
) = range(16, 24)

# مسار 3: طوارئ (24-37) - مدمج بالفعل ✓
(
    EMERGENCY_COMPLAINT, EMERGENCY_DIAGNOSIS, EMERGENCY_DECISION,
    EMERGENCY_STATUS, EMERGENCY_ADMISSION_NOTES, EMERGENCY_OPERATION_DETAILS,
    EMERGENCY_ADMISSION_TYPE, EMERGENCY_ROOM_NUMBER,
    EMERGENCY_DATE_TIME, EMERGENCY_REASON,
    EMERGENCY_TRANSLATOR, EMERGENCY_CONFIRM
) = range(24, 36)

# مسار 4: ترقيد (36-42)
(
    ADMISSION_REASON, ADMISSION_ROOM, ADMISSION_NOTES,
    ADMISSION_FOLLOWUP_DATE, ADMISSION_FOLLOWUP_REASON,
    ADMISSION_TRANSLATOR, ADMISSION_CONFIRM
) = range(36, 43)

# مسار 5: استشارة مع قرار عملية (43-52)
(
    SURGERY_CONSULT_DIAGNOSIS, SURGERY_CONSULT_DECISION, SURGERY_CONSULT_NAME_EN,
    SURGERY_CONSULT_SUCCESS_RATE, SURGERY_CONSULT_BENEFIT_RATE, SURGERY_CONSULT_TESTS, SURGERY_CONSULT_FOLLOWUP_DATE,
    SURGERY_CONSULT_FOLLOWUP_REASON,
    SURGERY_CONSULT_TRANSLATOR, SURGERY_CONSULT_CONFIRM
) = range(43, 53)

# مسار 6: عملية (53-59)
(
    OPERATION_DETAILS_AR, OPERATION_NAME_EN, OPERATION_NOTES,
    OPERATION_FOLLOWUP_DATE, OPERATION_FOLLOWUP_REASON,
    OPERATION_TRANSLATOR, OPERATION_CONFIRM
) = range(53, 60)

# مسار 7: استشارة أخيرة (60-64)
(
    FINAL_CONSULT_DIAGNOSIS, FINAL_CONSULT_DECISION, FINAL_CONSULT_RECOMMENDATIONS,
    FINAL_CONSULT_TRANSLATOR, FINAL_CONSULT_CONFIRM
) = range(60, 65)

# مسار 8: خروج من المستشفى (65-72)
(
    DISCHARGE_TYPE, DISCHARGE_ADMISSION_SUMMARY, DISCHARGE_OPERATION_DETAILS,
    DISCHARGE_OPERATION_NAME_EN, DISCHARGE_FOLLOWUP_DATE, DISCHARGE_FOLLOWUP_REASON,
    DISCHARGE_TRANSLATOR, DISCHARGE_CONFIRM
) = range(65, 73)

# مسار 9: علاج طبيعي / أجهزة تعويضية (73-83)
(
    REHAB_TYPE, PHYSICAL_THERAPY_DETAILS, PHYSICAL_THERAPY_FOLLOWUP_DATE,
    PHYSICAL_THERAPY_FOLLOWUP_REASON,
    PHYSICAL_THERAPY_TRANSLATOR, PHYSICAL_THERAPY_CONFIRM,
    DEVICE_NAME_DETAILS, DEVICE_FOLLOWUP_DATE,
    DEVICE_FOLLOWUP_REASON, DEVICE_TRANSLATOR, DEVICE_CONFIRM
) = range(73, 84)

# مسار 10: أشعة وفحوصات (84-87)
(
    RADIOLOGY_TYPE, RADIOLOGY_DELIVERY_DATE, RADIOLOGY_TRANSLATOR, RADIOLOGY_CONFIRM
) = range(84, 88)

# مسار 11: تأجيل موعد (88-92)
(
    APP_RESCHEDULE_REASON, APP_RESCHEDULE_RETURN_DATE, APP_RESCHEDULE_RETURN_REASON,
    APP_RESCHEDULE_TRANSLATOR, APP_RESCHEDULE_CONFIRM
) = range(88, 93)

# مسار 12: جلسة إشعاعي (93-101)
(
    RADIATION_THERAPY_TYPE,           # نوع الإشعاعي
    RADIATION_THERAPY_SESSION_NUMBER, # رقم الجلسة
    RADIATION_THERAPY_REMAINING,      # الجلسات المتبقية
    RADIATION_THERAPY_NOTES,          # ملاحظات أو توصيات
    RADIATION_THERAPY_RETURN_DATE,    # تاريخ العودة والوقت
    RADIATION_THERAPY_RETURN_REASON,  # سبب العودة
    RADIATION_THERAPY_TRANSLATOR,     # اسم المترجم
    RADIATION_THERAPY_CONFIRM          # تأكيد
) = range(93, 101)

# مسار 13: المناظير (101-110)
(
    ENDOSCOPY_COMPLAINT,          # شكوى المريض
    ENDOSCOPY_TYPE,               # نوع المنظار (Colonoscopy / Upper GI / Both)
    ENDOSCOPY_RESULT,             # نتيجة المنظار / خطة الطبيب
    ENDOSCOPY_PROCEDURES,         # الإجراءات التي تمت (اختيار متعدد)
    ENDOSCOPY_PROCEDURES_OTHER,   # نص "أخرى" عند اختيارها
    ENDOSCOPY_NOTES,              # الملاحظات
    ENDOSCOPY_FOLLOWUP_DATE,      # تاريخ العودة (+ الوقت داخل نفس الحالة)
    ENDOSCOPY_FOLLOWUP_REASON,    # سبب العودة
    ENDOSCOPY_TRANSLATOR,         # اسم المترجم
    ENDOSCOPY_CONFIRM             # تأكيد
) = range(101, 111)

# مسار 14: جلسات العلاج (Treatment Plans) — نظام عام يخدم العلاج الكيماوي
# والموجه والمناعي وغسيل الكلى (والعلاج الإشعاعي يستمر يستخدم حالاته
# الخاصة RADIATION_THERAPY_* أعلاه، فقط منطق الجلسات الداخلي تغيّر).
# (111-124)
(
    TREATMENT_PLAN_SETUP,          # أول مرة: "كم عدد الجلسات الكلي؟" (نمط sessions فقط)
    TREATMENT_PLAN_EDIT_VALUE,     # تعديل: عدد جلسات جديد (نمط sessions)
    TREATMENT_PLAN_EDIT_REASON,    # سبب التعديل (اختياري، لأي نمط)
    TREATMENT_PLAN_DISPLAY,        # عرض التقدّم + أزرار متابعة/تعديل
    TREATMENT_NOTES,               # الملاحظات
    TREATMENT_FOLLOWUP_DATE,       # تاريخ العودة
    TREATMENT_FOLLOWUP_REASON,     # سبب العودة
    TREATMENT_TRANSLATOR,          # اسم المترجم
    TREATMENT_CONFIRM,             # تأكيد
    # ── خاص بالعلاج الكيماوي (اختيار جلسات/دورات) ──
    CHEMO_MODE_CHOICE,             # حسب الجلسات / حسب الدورات
    CHEMO_CYCLES_TOTAL,            # كم عدد الدورات؟
    CHEMO_CYCLES_UNIFORM_CHOICE,   # هل كل الدورات بنفس عدد الجلسات؟
    CHEMO_CYCLES_UNIFORM_COUNT,    # كم جلسة في كل دورة؟
    CHEMO_CYCLES_CUSTOM_ENTRY,     # إدخال عدد الجلسات لكل دورة على حدة (تسلسلي)
) = range(111, 125)

# حالة إضافية واحدة: سبب تعديل خطة العلاج الإشعاعي (اختياري) — العلاج
# الإشعاعي يستخدم TreatmentPlan أيضاً الآن، لكن يُبقي أعمدة Report القديمة
# (radiation_therapy_session_number/remaining) لعدم كسر بطاقة تقريره.
(RADIATION_THERAPY_EDIT_REASON,) = range(125, 126)

# حالة إضافية: شكوى المريض في مسار جلسات العلاج (chemo/targeted/immuno/
# dialysis) — تُسأل بعد عرض تقدُّم الخطة وقبل ملاحظات الطبيب.
(TREATMENT_COMPLAINT,) = range(126, 127)

# حالة إضافية: إدخال يدوي لرقم الجلسة الحالية في مسار جلسات العلاج — لتصحيح
# العدّاد عند مرضى بدأوا الجلسات قبل إنشاء الخطة في هذا النظام.
(TREATMENT_PLAN_MANUAL_SESSION,) = range(127, 128)