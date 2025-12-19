#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
💡 اقتراحات العمليات الطبية
Medical Procedures Suggestions
"""

# قائمة شاملة للعمليات والإجراءات الطبية (عربي + إنجليزي)
MEDICAL_PROCEDURES = [
    # فحوصات عامة
    "فحص سريري - Clinical Examination",
    "فحص شامل - Complete Checkup",
    "قياس العلامات الحيوية - Vital Signs",
    "قياس الضغط - Blood Pressure",
    "قياس السكر - Blood Sugar",
    "قياس الحرارة - Temperature",
    
    # تحاليل مخبرية
    "تحاليل دم - Blood Tests",
    "CBC - تعداد دم كامل",
    "CRP - بروتين سي التفاعلي",
    "ESR - سرعة ترسيب",
    "تحاليل وظائف كلى - Kidney Function",
    "تحاليل وظائف كبد - Liver Function",
    "Lipid Profile - دهون كاملة",
    "HbA1c - سكر تراكمي",
    "Troponin - تروبونين",
    "D-Dimer - دي دايمر",
    
    # تحاليل البول والبراز
    "تحليل بول - Urine Analysis",
    "مزرعة بول - Urine Culture",
    "تحليل براز - Stool Analysis",
    
    # أشعة وتصوير
    "أشعة سينية - X-Ray",
    "أشعة صدر - Chest X-Ray",
    "أشعة بطن - Abdominal X-Ray",
    "CT Scan - أشعة مقطعية",
    "MRI - رنين مغناطيسي",
    "Ultrasound - موجات صوتية",
    "Echocardiography - إيكو قلب",
    "Mammography - ماموجرام",
    
    # فحوصات قلبية
    "ECG - تخطيط قلب",
    "Holter Monitor - هولتر",
    "Stress Test - اختبار جهد",
    "Cardiac Catheterization - قسطرة قلبية",
    "Angiography - تصوير أوعية",
    
    # مناظير
    "منظار معدة - Gastroscopy",
    "منظار قولون - Colonoscopy",
    "منظار مثانة - Cystoscopy",
    "تنظير مفاصل - Arthroscopy",
    
    # عمليات جراحية
    "عملية جراحية - Surgery",
    "استئصال - Excision",
    "خياطة جرح - Wound Suturing",
    "كي - Cauterization",
    "فتح خراج - Abscess Drainage",
    
    # إجراءات طبية
    "حقنة عضلية - IM Injection",
    "حقنة وريدية - IV Injection",
    "تركيب محلول - IV Fluid",
    "قسطرة بولية - Urinary Catheter",
    "تركيب أنبوب أنفي - NG Tube",
    "غيار جرح - Wound Dressing",
    "إزالة غرز - Suture Removal",
    
    # علاج طبيعي
    "علاج طبيعي - Physiotherapy",
    "تمارين علاجية - Therapeutic Exercises",
    "كمادات - Compresses",
    
    # أدوية
    "صرف أدوية - Medication Prescription",
    "مضاد حيوي - Antibiotic",
    "مسكن ألم - Pain Killer",
    "خافض حرارة - Antipyretic",
    
    # قرارات طبية
    "إدخال - Hospital Admission",
    "إخراج - Discharge",
    "تحويل لقسم آخر - Transfer",
    "تحويل لمستشفى آخر - Referral",
    "متابعة - Follow-up",
    "إعادة فحص - Re-examination",
    "مراقبة - Observation",
    
    # طوارئ
    "إنعاش قلبي - CPR",
    "صدمة كهربائية - Defibrillation",
    "تنبيب - Intubation",
    "إعطاء أكسجين - Oxygen Therapy",
]

def get_procedure_suggestions(query: str = "") -> list:
    """
    الحصول على اقتراحات العمليات بناءً على البحث
    
    Args:
        query: نص البحث (اختياري)
    
    Returns:
        list: قائمة الاقتراحات
    """
    if not query or len(query) < 2:
        # إرجاع أول 20 اقتراح إذا لم يكن هناك بحث
        return MEDICAL_PROCEDURES[:20]
    
    # البحث في الاقتراحات
    query_lower = query.lower()
    suggestions = []
    
    for procedure in MEDICAL_PROCEDURES:
        if query_lower in procedure.lower():
            suggestions.append(procedure)
    
    # إذا لم يجد نتائج، ارجع الكل
    if not suggestions:
        return MEDICAL_PROCEDURES[:20]
    
    return suggestions[:15]  # أول 15 نتيجة


def get_common_procedures() -> list:
    """الإجراءات الأكثر شيوعاً"""
    return [
        "فحص سريري - Clinical Examination",
        "تحاليل دم - Blood Tests",
        "أشعة سينية - X-Ray",
        "ECG - تخطيط قلب",
        "صرف أدوية - Medication Prescription",
        "متابعة - Follow-up",
        "إدخال - Hospital Admission",
        "إخراج - Discharge",
    ]


def get_procedures_by_specialty(specialty: str) -> list:
    """
    الإجراءات حسب التخصص
    
    Args:
        specialty: التخصص (طوارئ، قلب، باطنية، إلخ)
    
    Returns:
        list: إجراءات التخصص
    """
    specialty_map = {
        'طوارئ': [
            "فحص سريري - Clinical Examination",
            "قياس العلامات الحيوية - Vital Signs",
            "خياطة جرح - Wound Suturing",
            "تركيب محلول - IV Fluid",
            "أشعة سينية - X-Ray",
            "تحاليل دم - Blood Tests",
        ],
        'قلب': [
            "ECG - تخطيط قلب",
            "Echocardiography - إيكو قلب",
            "Stress Test - اختبار جهد",
            "Troponin - تروبونين",
            "قسطرة قلبية - Cardiac Catheterization",
        ],
        'باطنية': [
            "فحص سريري - Clinical Examination",
            "تحاليل دم - Blood Tests",
            "منظار معدة - Gastroscopy",
            "Ultrasound - موجات صوتية",
        ],
        'عظام': [
            "أشعة سينية - X-Ray",
            "CT Scan - أشعة مقطعية",
            "تجبير - Splinting",
            "علاج طبيعي - Physiotherapy",
        ],
    }
    
    return specialty_map.get(specialty, MEDICAL_PROCEDURES[:10])


if __name__ == "__main__":
    # اختبار
    print("🧪 اختبار اقتراحات العمليات\n")
    
    print("1. بحث 'فحص':")
    print(get_procedure_suggestions('فحص')[:5])
    
    print("\n2. بحث 'ECG':")
    print(get_procedure_suggestions('ECG'))
    
    print("\n3. الشائعة:")
    print(get_common_procedures())
























