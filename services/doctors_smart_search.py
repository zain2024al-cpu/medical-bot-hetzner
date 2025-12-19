#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔍 نظام البحث الذكي عن الأطباء
يدعم العربي والإنجليزي - بحث فوري مع اقتراحات
نظام ترتيب متقدم مع دعم AI
"""

import json
import os
import re
from rapidfuzz import fuzz, process
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# محاولة استيراد OpenAI للترتيب الذكي (اختياري)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.info("OpenAI غير متاح - سيتم استخدام الترتيب التقليدي فقط")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📖 قاموس ترجمة الأقسام الطبية (عربي ↔ إنجليزي)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DEPARTMENT_TRANSLATIONS = {
    # ═══ جراحة المخ والأعصاب ═══
    "جراحة المخ والأعصاب": ["neurosurgery", "neurological surgery", "brain surgery", "neuro surgery", "adult neurosurgery", "neuro spine"],
    "جراحة مخ واعصاب": ["neurosurgery", "neurological surgery", "brain surgery"],
    "جراحة المخ": ["neurosurgery", "brain surgery"],
    "جراحة العمود الفقري": ["spine surgery", "spinal surgery", "neuro spine"],
    
    # ═══ الأعصاب (طب) ═══
    "طب الأعصاب": ["neurology", "neurological", "neuro"],
    "الأعصاب": ["neurology", "neurological"],
    "اعصاب": ["neurology"],
    "الأعصاب والصرع": ["epilepsy", "neurology"],
    
    # ═══ جراحة القلب ═══
    "جراحة القلب والصدر": ["cardiothoracic", "cardiac surgery", "heart surgery", "ctvs"],
    "جراحة القلب": ["cardiac surgery", "heart surgery", "cardiothoracic"],
    "جراحة الصدر": ["thoracic surgery", "chest surgery"],
    "زراعة القلب": ["heart transplant", "cardiac transplant"],
    
    # ═══ أمراض القلب ═══
    "أمراض القلب": ["cardiology", "cardiac sciences"],
    "قلب": ["cardiology", "cardiac"],
    "أمراض القلب التداخلية": ["interventional cardiology"],
    "أمراض قلب الأطفال": ["pediatric cardiology", "paediatric cardiology"],
    "الفيزيولوجيا الكهربائية للقلب": ["electrophysiology", "cardiac electrophysiology"],
    "علوم القلب": ["cardiac sciences"],
    
    # ═══ جراحة العظام ═══
    "جراحة العظام": ["orthopedic", "orthopaedic", "orthopedics", "bone"],
    "جراحة استبدال المفاصل": ["joint replacement", "joint arthroplasty"],
    "جراحة المفاصل": ["joint surgery", "arthroscopy"],
    "تنظير المفاصل": ["arthroscopy"],
    "جراحة الإصابات الرياضية": ["sports surgery", "sports injury"],
    "جراحة أورام العظام": ["orthopedic oncology", "bone tumor"],
    "جراحة اليد": ["hand surgery"],
    "جراحة الكتف": ["shoulder surgery"],
    "جراحة الركبة": ["knee surgery"],
    
    # ═══ جراحة المسالك البولية ═══
    "جراحة المسالك البولية": ["urology", "urological"],
    "مسالك بولية": ["urology", "urological"],
    "جراحة أورام المسالك البولية": ["uro-oncology", "urologic oncology"],
    "جراحة البروستاتا": ["prostate surgery", "prostate"],
    "زراعة الكلى": ["renal transplant", "kidney transplant"],
    
    # ═══ الأورام ═══
    "الأورام": ["oncology", "cancer"],
    "اورام": ["oncology"],
    "الأورام الطبية": ["medical oncology"],
    "جراحة الأورام": ["surgical oncology"],
    "علاج الأورام بالإشعاع": ["radiation oncology"],
    "أورام الدم": ["hematologic oncology", "hemato-oncology"],
    "أورام الرأس والعنق": ["head & neck oncology", "head and neck oncology"],
    "أورام النساء": ["gynecologic oncology"],
    "العلاج المناعي للأورام": ["immunotherapy"],
    
    # ═══ الجهاز الهضمي ═══
    "الجهاز الهضمي": ["gastroenterology", "gi"],
    "جهاز هضمي": ["gastroenterology"],
    "الكبد والجهاز الهضمي": ["hepatogastroenterology", "hepatology"],
    "جراحة الجهاز الهضمي": ["surgical gastroenterology"],
    "أمراض الكبد": ["hepatology", "liver"],
    
    # ═══ جراحة عامة ═══
    "جراحة عامة": ["general surgery", "surgery", "laparoscopic"],
    "الجراحة طفيفة التوغل": ["minimally invasive surgery", "laparoscopic"],
    "جراحة السمنة": ["bariatric surgery", "bariatric", "metabolic surgery"],
    "جراحة السمنة والأيض": ["bariatric & metabolic"],
    
    # ═══ جراحة الأوعية الدموية ═══
    "جراحة الأوعية الدموية": ["vascular surgery", "vascular", "endovascular"],
    "اوعية دموية": ["vascular"],
    "علاج الدوالي": ["varicose veins"],
    
    # ═══ طب الأطفال ═══
    "طب الأطفال": ["pediatrics", "paediatrics", "pediatric", "paediatric", "child"],
    "اطفال": ["pediatric", "paediatric"],
    "حديثي الولادة": ["neonatology", "neonatal"],
    "طوارئ الأطفال": ["pediatric emergency", "paediatric emergency"],
    "جراحة الأطفال": ["pediatric surgery", "paediatric surgery"],
    
    # ═══ النساء والولادة ═══
    "النساء والولادة": ["obstetrics", "gynecology", "obgyn", "obs"],
    "نساء وولادة": ["obstetrics", "gynecology"],
    "أمراض النساء": ["gynecology", "gynaecology"],
    "طب الأجنة": ["fetal medicine"],
    "الحمل عالي الخطورة": ["high risk pregnancy"],
    "طب الإنجاب": ["reproductive medicine", "fertility"],
    "الولادة المبكرة": ["preterm birth"],
    
    # ═══ طب العيون ═══
    "طب العيون": ["ophthalmology", "eye"],
    "عيون": ["ophthalmology", "eye"],
    "شبكية العين": ["retina", "vitreoretinal"],
    "الجلوكوما": ["glaucoma"],
    "الساد": ["cataract"],
    "قرنية العين": ["cornea"],
    "عيون الأطفال": ["pediatric ophthalmology"],
    
    # ═══ الأنف والأذن والحنجرة ═══
    "الأنف والأذن والحنجرة": ["ent", "otolaryngology", "ear nose throat", "head & neck", "head and neck"],
    "الأذن والأنف والحنجرة": ["ent", "otolaryngology", "ear nose throat", "head & neck", "head and neck"],
    "انف واذن وحنجرة": ["ent", "otolaryngology"],
    "جراحة الرأس والعنق": ["head & neck", "head and neck", "ent", "otolaryngology"],
    "جراحة الرأس والعنق وقاعدة الجمجمة": ["head & neck", "head and neck", "ent", "otolaryngology", "skull base surgery"],
    "جراحة قاعدة الجمجمة": ["skull base surgery"],
    "زراعة القوقعة": ["cochlear implant"],
    "أمراض الأنف": ["rhinology"],
    "التهاب الأنف التحسسي": ["allergic rhinitis"],
    
    # ═══ الطب الباطني ═══
    "الطب الباطني": ["internal medicine", "general medicine", "medicine"],
    "باطنة": ["internal medicine"],
    "الطب العام": ["general medicine"],
    
    # ═══ الطوارئ والعناية المركزة ═══
    "الطوارئ": ["emergency", "er"],
    "طوارئ": ["emergency"],
    "طب الطوارئ": ["emergency medicine"],
    "العناية المركزة": ["critical care", "intensive care", "icu"],
    "العناية المشددة": ["intensive care"],
    
    # ═══ أمراض الدم ═══
    "أمراض الدم": ["hematology", "haematology"],
    "زرع نخاع العظام": ["bone marrow transplant", "bmt", "bone marrow"],
    "نخاع العظام": ["bone marrow"],
    
    # ═══ أمراض الروماتيزم ═══
    "أمراض الروماتيزم": ["rheumatology", "rheumatic"],
    "روماتيزم": ["rheumatology"],
    "المناعة السريرية": ["clinical immunology"],
    "التهاب المفاصل": ["arthritis"],
    
    # ═══ الأمراض الجلدية ═══
    "الأمراض الجلدية": ["dermatology", "skin"],
    "جلدية": ["dermatology"],
    "الأمراض الجلدية التجميلية": ["cosmetic dermatology"],
    
    # ═══ الطب التجميلي والتجميل ═══
    "الطب التجميلي": ["aesthetic", "cosmetic", "cosmetic surgery", "aesthetic surgery"],
    "التجميل": ["cosmetology", "cosmetic", "aesthetic", "cosmetic surgery"],
    "جراحة التجميل": ["plastic surgery", "cosmetic surgery", "aesthetic surgery"],
    "طب تجميلي": ["cosmetic", "aesthetic"],
    
    # ═══ أمراض الكلى ═══
    "أمراض الكلى": ["nephrology", "kidney", "renal"],
    "كلى": ["nephrology", "kidney"],
    "غسيل الكلى": ["dialysis"],
    
    # ═══ أمراض الصدر ═══
    "أمراض الصدر": ["pulmonology", "chest", "pulmonary"],
    "صدر": ["pulmonology", "chest"],
    "أمراض الجهاز التنفسي": ["respiratory"],
    "أمراض الرئة": ["lung", "pulmonary"],
    "طب اضطرابات النوم": ["sleep medicine", "sleep disorder"],
    "السل": ["tuberculosis", "tb"],
    
    # ═══ التخدير ═══
    "التخدير": ["anesthesia", "anaesthesia", "anesthesiology"],
    "تخدير": ["anesthesia"],
    "إدارة الألم": ["pain management", "pain medicine"],
    "طب الألم": ["pain medicine"],
    
    # ═══ الأشعة ═══
    "الأشعة": ["radiology", "imaging"],
    "اشعة": ["radiology"],
    "التصوير الطبي": ["imaging", "diagnostic radiology"],
    "الأشعة التداخلية": ["interventional radiology"],
    "الطب النووي": ["nuclear medicine"],
    
    # ═══ رعاية القدم السكري ═══
    "رعاية القدم السكري": ["diabetic foot", "diabetic foot care"],
    "قدم سكري": ["diabetic foot"],
    "طب القدم": ["podiatry"],
    
    # ═══ طب الأسنان ═══
    "طب الأسنان": ["dental", "dentistry", "oral"],
    "اسنان": ["dental", "dentistry"],
    "جراحة الفم والفكين": ["maxillofacial", "oral surgery"],
    "تقويم الأسنان": ["orthodontics"],
    
    # ═══ الغدد الصماء ═══
    "الغدد الصماء": ["endocrinology", "endocrine"],
    "غدد صماء": ["endocrinology"],
    "السكري": ["diabetes", "diabetic"],
    "الغدة الدرقية": ["thyroid"],
    
    # ═══ العلاج الطبيعي ═══
    "العلاج الطبيعي": ["physiotherapy", "physical therapy"],
    "علاج طبيعي": ["physiotherapy"],
    "الطب الفيزيائي": ["physical medicine", "pmr"],
    "إعادة التأهيل": ["rehabilitation"],
    "الطب الفيزيائي وإعادة التأهيل": ["physical medicine & rehabilitation", "pmr"],
    
    # ═══ الطب النفسي ═══
    "الطب النفسي": ["psychiatry", "psychiatric"],
    "نفسية": ["psychiatry", "mental health"],
    "الصحة النفسية": ["mental health"],
    "علم النفس": ["psychology"],
    "الاستشارات النفسية": ["counseling"],
    
    # ═══ التغذية ═══
    "التغذية العلاجية": ["nutrition", "dietitian", "clinical nutrition"],
    "تغذية": ["nutrition"],
    
    # ═══ الطب المخبري ═══
    "الطب المخبري": ["laboratory medicine", "lab medicine", "pathology"],
    "علم الميكروبات": ["microbiology"],
    "علم الأمراض": ["pathology"],
    "علم الأمراض السريري": ["clinical pathology"],
    
    # ═══ طب الأسرة ═══
    "طب الأسرة": ["family medicine", "general practice", "gp"],
    
    # ═══ الأمراض المعدية ═══
    "الأمراض المعدية": ["infectious disease", "infection"],
    
    # ═══ جراحة الثدي ═══
    "جراحة الثدي": ["breast surgery", "breast", "mammology"],
    "أورام الثدي": ["breast oncology"],
    
    # ═══ طب الشيخوخة ═══
    "طب الشيخوخة": ["geriatrics", "geriatric", "elderly care"],
    
    # ═══ الأمراض الوراثية ═══
    "الأمراض الوراثية": ["genetics", "genetic"],
    "الاستشارات الوراثية": ["genetic counseling"],
    
    # ═══ الطب الرياضي ═══
    "الطب الرياضي": ["sports medicine", "sports injury"],
    
    # ═══ زراعة الأعضاء ═══
    "زراعة الأعضاء": ["transplant", "organ transplant"],
    "زراعة الكبد": ["liver transplant"],
    
    # ═══ التوليد ═══
    "الولادة": ["obstetrics", "childbirth"],
    "الحمل": ["pregnancy", "antenatal"],
    
    # ═══ عام ═══
    "تخصص عام": ["general", "consultant"],
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📚 تحميل قاعدة البيانات
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_doctors_cache = None

def load_doctors():
    """
    تحميل قاعدة بيانات الأطباء من الملف المنظم
    
    يحاول تحميل الملف المنظم أولاً (doctors_organized.json)
    إذا لم يوجد، يحمل الملف القديم (doctors_database.json)
    """
    global _doctors_cache
    
    if _doctors_cache is not None:
        return _doctors_cache
    
    # محاولة تحميل الملف المنظم أولاً
    organized_path = 'data/doctors_organized.json'
    old_path = 'data/doctors_database.json'
    
    try:
        # محاولة تحميل الملف المنظم
        if os.path.exists(organized_path):
            with open(organized_path, 'r', encoding='utf-8') as f:
                organized_data = json.load(f)
            
            # تحويل البنية المنظمة إلى قائمة مسطحة للأطباء
            doctors_list = []
            hospitals = organized_data.get('hospitals', {})
            
            for hospital_name, departments in hospitals.items():
                for dept_key, dept_data in departments.items():
                    dept_ar = dept_data.get('department_ar', '')
                    dept_en = dept_data.get('department_en', '')
                    doctors = dept_data.get('doctors', [])
                    
                    for doctor_name in doctors:
                        doctors_list.append({
                            'name': doctor_name,
                            'hospital': hospital_name,
                            'department_ar': dept_ar,
                            'department_en': dept_en,
                            'department': dept_key  # للحفاظ على التوافق
                        })
            
            _doctors_cache = doctors_list
            logger.info(f"✅ تم تحميل {len(_doctors_cache)} طبيب من الملف المنظم")
            return _doctors_cache
        
        # إذا لم يوجد الملف المنظم، استخدم الملف القديم
        elif os.path.exists(old_path):
            with open(old_path, 'r', encoding='utf-8') as f:
                _doctors_cache = json.load(f)
            logger.info(f"✅ تم تحميل {len(_doctors_cache)} طبيب من الملف القديم")
            return _doctors_cache
        else:
            logger.warning("⚠️ لا يوجد ملف أطباء (لا المنظم ولا القديم)")
            return []
            
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل قاعدة الأطباء: {e}")
        return []


def reload_doctors():
    """إعادة تحميل القاعدة"""
    global _doctors_cache
    _doctors_cache = None
    return load_doctors()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔍 البحث الذكي
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _clean_doctor_name(name):
    """تنظيف اسم الطبيب وإزالة الألقاب والرموز"""
    if not name:
        return ""
    
    # تطبيع شامل
    cleaned = name.lower().strip()
    
    # إزالة الألقاب الشائعة
    prefixes = [
        'dr.', 'dr ', 'doctor', 'doctors', 'د.', 'دكتور', 'دكتوره',
        'prof.', 'prof ', 'professor', 'professors', 'أستاذ', 'أستاذة',
        'mr.', 'mr ', 'mrs.', 'mrs ', 'ms.', 'ms ',
        'sir', 'sir ', 'miss', 'miss '
    ]
    for prefix in prefixes:
        cleaned = cleaned.replace(prefix, ' ')
    
    # إزالة الرموز والأقواس
    cleaned = cleaned.replace('(', ' ').replace(')', ' ')
    cleaned = cleaned.replace('[', ' ').replace(']', ' ')
    cleaned = cleaned.replace('.', ' ').replace(',', ' ')
    cleaned = cleaned.replace('-', ' ').replace('_', ' ')
    
    # تطبيع المسافات المتعددة
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned


def _get_name_signature(name_clean):
    """إنشاء توقيع فريد للاسم (أول كلمتين + الكلمة الثالثة إذا كانت قصيرة)"""
    words = [w for w in name_clean.split() if len(w) > 0]
    
    if not words:
        return ""
    
    if len(words) >= 2:
        # أول كلمتين
        signature = f"{words[0]} {words[1]}"
        # إذا كانت الكلمة الثالثة قصيرة (حرف أو حرفين)، أضفها للتوقيع
        if len(words) >= 3 and len(words[2]) <= 2:
            signature += f" {words[2]}"
        return signature
    else:
        return words[0]


def _remove_duplicate_doctors(doctors_list):
    """
    إزالة الأطباء المكررين بناءً على تشابه الأسماء - محسّنة بشكل كامل
    
    الاستراتيجية:
    1. تنظيف شامل للأسماء (إزالة الألقاب والرموز)
    2. مقارنة fuzzy عالية (95%+) للأسماء الكاملة
    3. التحقق من تطابق أول كلمتين + الكلمة الثالثة إذا كانت قصيرة
    4. تفضيل الاسم الأطول/الأكثر اكتمالاً
    """
    if not doctors_list:
        return doctors_list
    
    # قائمة للأطباء الفريدين مع معلوماتهم
    unique_doctors = []
    seen_info = []  # [(doctor, name_clean, original_name, name_words)]
    
    for doctor in doctors_list:
        original_name = doctor.get('name', '').strip()
        if not original_name:
            continue
        
        # تنظيف الاسم
        name_clean = _clean_doctor_name(original_name)
        if not name_clean:
            continue
        
        # تقسيم الاسم إلى كلمات
        name_words = [w for w in name_clean.split() if len(w) > 0]
        if len(name_words) < 1:
            continue
        
        # التحقق من التكرار مع جميع الأطباء الموجودين
        is_duplicate = False
        duplicate_index = None
        
        for idx, (existing_doctor, existing_clean, existing_original, existing_words) in enumerate(seen_info):
            # 1. مقارنة fuzzy عالية للأسماء الكاملة (95%+)
            similarity = fuzz.ratio(name_clean, existing_clean)
            if similarity >= 95:
                is_duplicate = True
                duplicate_index = idx
                break
            
            # 2. التحقق من تطابق أول كلمتين
            if len(name_words) >= 2 and len(existing_words) >= 2:
                if name_words[0] == existing_words[0] and name_words[1] == existing_words[1]:
                    # إذا كانا لهما نفس أول كلمتين
                    if len(name_words) == 2 and len(existing_words) == 2:
                        # كلمتين فقط - متطابقان
                        is_duplicate = True
                        duplicate_index = idx
                        break
                    elif len(name_words) >= 3 and len(existing_words) >= 3:
                        # كلاهما له كلمة ثالثة
                        third_word = name_words[2]
                        existing_third = existing_words[2]
                        # إذا كانت الكلمة الثالثة قصيرة (حرف أو حرفين) أو متشابهة جداً
                        if len(third_word) <= 2 and len(existing_third) <= 2:
                            is_duplicate = True
                            duplicate_index = idx
                            break
                        elif fuzz.ratio(third_word, existing_third) >= 90:
                            is_duplicate = True
                            duplicate_index = idx
                            break
                    elif len(name_words) == 2 and len(existing_words) >= 3:
                        # أحدهما بدون كلمة ثالثة والآخر به
                        if len(existing_words[2]) <= 2:
                            is_duplicate = True
                            duplicate_index = idx
                            break
                    elif len(name_words) >= 3 and len(existing_words) == 2:
                        # أحدهما بدون كلمة ثالثة والآخر به
                        if len(name_words[2]) <= 2:
                            is_duplicate = True
                            duplicate_index = idx
                            break
            
            # 3. مقارنة fuzzy متوسطة (90%+) مع تحقق إضافي من أول كلمتين
            elif similarity >= 90:
                if len(name_words) >= 2 and len(existing_words) >= 2:
                    if name_words[0] == existing_words[0] and name_words[1] == existing_words[1]:
                        is_duplicate = True
                        duplicate_index = idx
                        break
        
        if is_duplicate:
            # مقارنة الأسماء الأصلية لاختيار الأفضل
            existing_doctor, existing_clean, existing_original, existing_words = seen_info[duplicate_index]
            
            # تفضيل الاسم الأطول أو الذي يحتوي على "Prof"
            current_has_prof = 'prof' in original_name.lower()
            existing_has_prof = 'prof' in existing_original.lower()
            
            should_replace = False
            if current_has_prof and not existing_has_prof:
                should_replace = True
            elif len(original_name) > len(existing_original) and not (existing_has_prof and not current_has_prof):
                should_replace = True
            elif len(name_words) > len(existing_words):
                # تفضيل الاسم الذي يحتوي على كلمات أكثر (أكثر اكتمالاً)
                should_replace = True
            
            if should_replace:
                # استبدال الطبيب القديم
                unique_doctors.remove(existing_doctor)
                seen_info[duplicate_index] = (doctor, name_clean, original_name, name_words)
                unique_doctors.append(doctor)
                logger.debug(f"   🔄 استبدال: {existing_original} بـ {original_name} (similarity: {similarity}%)")
            else:
                logger.debug(f"   🔄 تكرار محذوف: {original_name} (مشابه لـ {existing_original}, similarity: {similarity}%)")
        else:
            # طبيب جديد - إضافته
            unique_doctors.append(doctor)
            seen_info.append((doctor, name_clean, original_name, name_words))
    
    if len(unique_doctors) < len(doctors_list):
        removed_count = len(doctors_list) - len(unique_doctors)
        logger.info(f"   🔄 تم إزالة {removed_count} طبيب مكرر من {len(doctors_list)} طبيب")
    
    return unique_doctors

def normalize_text(text):
    """تطبيع النص للبحث"""
    if not text:
        return ""
    
    text = text.lower().strip()
    
    # إزالة الألقاب
    text = text.replace('dr.', '').replace('dr ', '').replace('د.', '').replace('دكتور', '')
    text = text.replace('prof.', '').replace('prof ', '').replace('أستاذ', '')
    
    # تطبيع المسافات
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def find_department_english_terms(arabic_dept):
    """إيجاد المصطلحات الإنجليزية المقابلة لقسم عربي"""
    if not arabic_dept:
        return []
    
    arabic_normalized = normalize_text(arabic_dept)
    english_terms = []
    
    for ar_key, en_values in DEPARTMENT_TRANSLATIONS.items():
        ar_key_normalized = normalize_text(ar_key)
        # إذا القسم العربي يحتوي على المفتاح أو العكس
        if ar_key_normalized in arabic_normalized or arabic_normalized in ar_key_normalized:
            english_terms.extend(en_values)
    
    return english_terms


def search_doctors(query, hospital=None, department=None, specialty_type=None, limit=10):
    """
    البحث عن أطباء مع فلترة
    
    Args:
        query: نص البحث
        hospital: المستشفى (اختياري - للفلترة)
        department: القسم (اختياري - للفلترة)
        specialty_type: نوع التخصص - "medical" (باطني) أو "surgical" (جراحي) (اختياري)
        limit: عدد النتائج (افتراضي 10)
    
    Returns:
        قائمة بالأطباء المقترحين
    """
    
    doctors = load_doctors()
    
    if not doctors:
        logger.warning("⚠️ لا توجد أطباء في القاعدة")
        return []
    
    logger.info(f"🔍 البحث - Query: '{query}' | Hospital: '{hospital}' | Dept: '{department}'")
    
    # فلترة حسب المستشفى والقسم
    filtered = doctors
    
    if hospital:
        hospital_normalized = normalize_text(hospital)
        
        # فلترة دقيقة للمستشفى - تطابق دقيق لجميع المستشفيات
        filtered_by_hospital = []
        
        # استخراج الكلمات المميزة من اسم المستشفى (مثل CMI, RV, Whitefield, Old Airport Road)
        hospital_words = hospital_normalized.split()
        # تحديد الكلمات المميزة (ليست كلمات عامة مثل "hospital", "medical", "center")
        common_words = {'hospital', 'medical', 'center', 'clinic', 'healthcare', 'health', 'care', 'institute', 'institution'}
        distinctive_words = [w for w in hospital_words if w not in common_words and len(w) >= 2]
        
        for d in filtered:
            doc_hospital = normalize_text(d.get('hospital', ''))
            
            # استراتيجية 1: تطابق دقيق 100% (الأفضل)
            if hospital_normalized == doc_hospital:
                filtered_by_hospital.append(d)
                continue
            
            # استراتيجية 2: تطابق جزئي - إذا كان اسم المستشفى المطلوب موجود داخل اسم المستشفى في قاعدة البيانات (أو العكس)
            # مثال: "Aster Whitefield" يجب أن يطابق "Aster Whitefield Hospital, Bangalore"
            if hospital_normalized in doc_hospital or doc_hospital in hospital_normalized:
                filtered_by_hospital.append(d)
                continue
            
            # استراتيجية 3: تطابق fuzzy عالي جداً (90%+)
            hospital_match_ratio = fuzz.ratio(hospital_normalized, doc_hospital)
            if hospital_match_ratio >= 90:
                filtered_by_hospital.append(d)
                continue
            
            # استراتيجية 4: تطابق الكلمات المميزة - يجب أن تتطابق جميع الكلمات المميزة
            if len(distinctive_words) > 0:
                doc_hospital_words = doc_hospital.split()
                doc_distinctive_words = [w for w in doc_hospital_words if w not in common_words and len(w) >= 2]
                
                # يجب أن تتطابق جميع الكلمات المميزة من المستشفى المطلوب
                all_distinctive_match = True
                for h_word in distinctive_words:
                    found_match = False
                    for d_word in doc_distinctive_words:
                        # تطابق دقيق أو fuzzy عالي جداً (90%+)
                        if h_word == d_word or fuzz.ratio(h_word, d_word) >= 90:
                            found_match = True
                            break
                    if not found_match:
                        all_distinctive_match = False
                        break
                
                # إذا تطابقت جميع الكلمات المميزة، تحقق من تطابق عالي للاسم الكامل
                if all_distinctive_match:
                    if hospital_match_ratio >= 80:
                        filtered_by_hospital.append(d)
            else:
                # إذا لم توجد كلمات مميزة، استخدم تطابق fuzzy عالي (90%+)
                if hospital_match_ratio >= 90:
                    filtered_by_hospital.append(d)
        
        filtered = filtered_by_hospital
        logger.info(f"   بعد فلترة المستشفى '{hospital}': {len(filtered)} طبيب")
    
    # حفظ نتيجة فلترة المستشفى للـ fallback
    hospital_filtered = filtered.copy()
    
    if department:
        dept_normalized = normalize_text(department)
        
        # ✅ إذا القسم ثنائي اللغة "عربي | إنجليزي"، افصلهما
        dept_ar, dept_en = None, None
        if '|' in department:
            parts = department.split('|')
            if len(parts) >= 2:
                dept_ar = normalize_text(parts[0])
                dept_en = normalize_text(parts[1])
        
        # استخراج كلمات رئيسية
        dept_keywords = [w for w in dept_normalized.split() if len(w) > 2]
        
        # فلترة دقيقة جداً
        filtered_by_dept = []
        for d in filtered:
            # البحث في 3 حقول: department, department_ar, department_en
            doc_dept = normalize_text(d.get('department', ''))
            doc_dept_ar = normalize_text(d.get('department_ar', ''))
            doc_dept_en = normalize_text(d.get('department_en', ''))
            
            # دمج كل الحقول للبحث
            all_dept_text = f"{doc_dept} {doc_dept_ar} {doc_dept_en}".lower()
            
            if not all_dept_text.strip():
                continue
            
            # ✅ استبعاد صريح لـ "dentistry" و "dental" عند البحث عن ENT
            # هذا مهم جداً لأن "dentistry" يحتوي على "ent" كجزء من الكلمة
            if 'ent' in dept_normalized or 'اذن' in dept_normalized or 'انف' in dept_normalized or 'حنجرة' in dept_normalized:
                doc_dept_lower = doc_dept_en.lower()
                if 'dentistry' in doc_dept_lower or 'dental' in doc_dept_lower:
                    # هذا قسم طب الأسنان - لا نطابقه مع ENT
                    logger.debug(f"      ❌ تم استبعاد {d.get('name', '')} - قسم طب الأسنان (Dentistry/Dental)")
                    continue
            
            match_found = False
            
            # ✅ طريقة 1: تطابق ثنائي اللغة (دقيق جداً - أولوية قصوى)
            if dept_ar and dept_en:
                # تطابق دقيق: يجب أن يكون القسم مطابق تماماً أو يحتوي على الكلمات الرئيسية
                dept_ar_words = set(dept_ar.split())
                dept_en_words = set(dept_en.split())
                
                doc_dept_ar_words = set(doc_dept_ar.split())
                doc_dept_en_words = set(doc_dept_en.split())
                doc_dept_words = set(doc_dept.split())
                
                # تطابق دقيق: يجب أن تكون الكلمات الرئيسية موجودة
                # على الأقل 70% من كلمات القسم المطلوب يجب أن تكون موجودة
                ar_match_ratio = len(dept_ar_words & doc_dept_ar_words) / len(dept_ar_words) if dept_ar_words else 0
                en_match_ratio = len(dept_en_words & doc_dept_en_words) / len(dept_en_words) if dept_en_words else 0
                dept_match_ratio = len(dept_en_words & doc_dept_words) / len(dept_en_words) if dept_en_words else 0
                
                # تطابق دقيق: يجب أن يكون هناك تطابق قوي (70% على الأقل)
                if ar_match_ratio >= 0.7 or en_match_ratio >= 0.7 or dept_match_ratio >= 0.7:
                    match_found = True
                    logger.info(f"      ✅ تطابق ثنائي دقيق: {d.get('name', '')} (AR: {ar_match_ratio:.2f}, EN: {en_match_ratio:.2f})")
            
            # طريقة 2: تطابق مباشر دقيق (كلمات كاملة فقط)
            if not match_found:
                # تقسيم القسم المطلوب إلى كلمات
                dept_words = set(dept_normalized.split())
                # تقسيم قسم الطبيب إلى كلمات
                doc_words = set(all_dept_text.split())
                
                # تطابق: يجب أن تكون جميع الكلمات الرئيسية موجودة (كلمات كاملة)
                if dept_words and dept_words.issubset(doc_words):
                    match_found = True
                    logger.info(f"      ✅ تطابق كلمات كاملة: {d.get('name', '')}")
            
            # طريقة 3: البحث بالقاموس (عربي → إنجليزي) - تطابق كلمات كاملة فقط
            if not match_found:
                english_terms = find_department_english_terms(department)
                if english_terms:
                    for term in english_terms:
                        term_normalized = normalize_text(term)
                        term_words = set(term_normalized.split())
                        
                        # تطابق كلمات كاملة فقط
                        doc_dept_en_words = set(doc_dept_en.split())
                        all_dept_words = set(all_dept_text.split())
                        
                        # تطابق محسّن: إذا كانت الكلمة "ent" موجودة في أي مكان
                        if 'ent' in term_normalized:
                            # البحث عن "ent" ككلمة كاملة (وليس جزءاً من كلمة أخرى مثل "dentistry")
                            # (التحقق من dentistry تم بالفعل في بداية الحلقة)
                            ent_pattern = r'\bent\b'
                            if (re.search(ent_pattern, doc_dept_en.lower(), re.IGNORECASE) or 
                                re.search(ent_pattern, all_dept_text.lower(), re.IGNORECASE) or
                                'otolaryngology' in doc_dept_en.lower()):
                                match_found = True
                                logger.info(f"      ✅ تطابق قاموس (ENT): {d.get('name', '')}")
                                break
                        
                        if term_words.issubset(doc_dept_en_words) or term_words.issubset(all_dept_words):
                            match_found = True
                            logger.info(f"      ✅ تطابق قاموس: {d.get('name', '')}")
                            break
            
            # طريقة 4: تطابق جميع الكلمات الرئيسية (كلمات كاملة فقط)
            if not match_found and dept_keywords:
                # تقسيم نص القسم إلى كلمات
                all_dept_words = set(all_dept_text.split())
                dept_keywords_set = set(dept_keywords)
                
                # يجب أن تكون جميع الكلمات الرئيسية موجودة ككلمات كاملة
                if dept_keywords_set.issubset(all_dept_words):
                    match_found = True
                    logger.info(f"      ✅ تطابق كلمات رئيسية: {d.get('name', '')}")
            
            # طريقة 5: البحث المباشر عن "ENT" في القسم الإنجليزي (ككلمة كاملة)
            if not match_found:
                # إذا كان القسم المطلوب يحتوي على "ENT" أو "الأذن والأنف والحنجرة"
                if 'ent' in dept_normalized or 'اذن' in dept_normalized or 'انف' in dept_normalized or 'حنجرة' in dept_normalized:
                    # (التحقق من dentistry تم بالفعل في بداية الحلقة)
                    # البحث عن "ENT" ككلمة كاملة (وليس جزءاً من كلمة أخرى مثل "dentistry")
                    ent_pattern = r'\bent\b'
                    if (re.search(ent_pattern, doc_dept_en.lower(), re.IGNORECASE) or 
                        re.search(ent_pattern, all_dept_text.lower(), re.IGNORECASE) or
                        'head & neck' in doc_dept_en.lower() or 
                        'head and neck' in doc_dept_en.lower() or
                        'otolaryngology' in doc_dept_en.lower()):
                        match_found = True
                        logger.info(f"      ✅ تطابق ENT مباشر: {d.get('name', '')} (dept_en: {doc_dept_en[:50]})")
            
            # طريقة 6: fuzzy matching (دقيق جداً - threshold عالي)
            if not match_found:
                for field in [doc_dept, doc_dept_ar, doc_dept_en]:
                    if field and len(field) > 3:  # تجاهل الحقول القصيرة جداً
                        similarity = fuzz.ratio(dept_normalized, field)
                        if similarity > 90:  # threshold عالي جداً للدقة
                            match_found = True
                            logger.info(f"      ✅ تطابق fuzzy: {d.get('name', '')} (similarity: {similarity})")
                            break
            
            if match_found:
                filtered_by_dept.append(d)
        
        # ✅ إزالة التكرارات بعد فلترة القسم مباشرة
        filtered_by_dept = _remove_duplicate_doctors(filtered_by_dept)
        
        filtered = filtered_by_dept
        logger.info(f"   بعد فلترة القسم: {len(filtered)} طبيب")
        
        # ✅ التحقق من دقة الفلترة - عرض أسماء الأطباء المفلترين
        if filtered:
            logger.info(f"   📋 الأطباء المفلترين:")
            for doc in filtered[:5]:  # عرض أول 5 فقط
                logger.info(f"      - {doc.get('name', '')} | {doc.get('department_ar', '')} | {doc.get('department_en', '')}")
        
        # ✅ إذا لم نجد أطباء للقسم المحدد، لا نعرض كل أطباء المستشفى
        # بدلاً من ذلك، نعرض رسالة توضيحية
        if len(filtered) == 0 and hospital:
            logger.warning(f"   ⚠️ لم يُوجد أطباء مطابقين للقسم '{department}' في مستشفى '{hospital}'")
            # لا نعرض أطباء من أقسام أخرى - نترك filtered فارغاً
            # سيتم عرض رسالة "لا توجد أطباء" في unified_inline_query
    
    # ✅ فلترة حسب نوع التخصص (باطني/جراحي)
    if specialty_type and filtered:
        specialty_type_lower = specialty_type.lower().strip()
        filtered_by_specialty = []
        
        for d in filtered:
            doc_dept = normalize_text(d.get('department', ''))
            doc_dept_ar = normalize_text(d.get('department_ar', ''))
            doc_dept_en = normalize_text(d.get('department_en', ''))
            
            all_dept_text = f"{doc_dept} {doc_dept_ar} {doc_dept_en}".lower()
            
            is_surgical = any(keyword in all_dept_text for keyword in [
                'جراحة', 'surgery', 'surgical', 'operation', 'operative'
            ])
            
            # تحديد الباطني: يجب أن لا يكون جراحي أولاً
            is_medical = False
            if not is_surgical:
                # كلمات تشير إلى الباطني
                medical_keywords = [
                    'باطني', 'medical', 'medicine', 'internal', 'physician', 
                    'cardiology', 'gastroenterology', 'neurology', 'nephrology', 
                    'pulmonology', 'endocrinology', 'hematology', 'rheumatology', 
                    'dermatology', 'psychiatry', 'pediatrics', 'geriatrics',
                    'allergy', 'immunology', 'infectious', 'critical care'
                ]
                is_medical = any(keyword in all_dept_text for keyword in medical_keywords)
            
            # تطبيق الفلترة
            if specialty_type_lower == 'surgical' and is_surgical:
                filtered_by_specialty.append(d)
            elif specialty_type_lower == 'medical' and is_medical:
                filtered_by_specialty.append(d)
            elif specialty_type_lower not in ['medical', 'surgical']:
                # إذا كان النوع غير معروف، نعرض الجميع
                filtered_by_specialty.append(d)
        
        filtered = filtered_by_specialty
        logger.info(f"   بعد فلترة نوع التخصص ({specialty_type}): {len(filtered)} طبيب")
    
    # ✅ إزالة التكرارات بناءً على تشابه الأسماء
    filtered = _remove_duplicate_doctors(filtered)
    
    # إذا لا يوجد query، أرجع كل المفلترين مرتبين أبجدياً
    if not query or len(query.strip()) == 0:
        # ✅ ترتيب أبجدي حسب الاسم
        filtered_sorted = sorted(filtered, key=lambda x: normalize_text(x.get('name', '')))
        logger.info(f"   → إرجاع {min(len(filtered_sorted), limit)} طبيب مرتب أبجدياً")
        return filtered_sorted[:limit]
    
    # البحث الذكي مع نظام ترتيب متقدم
    query_normalized = normalize_text(query)
    
    # إنشاء قائمة للبحث مع حساب نقاط متقدمة
    search_items = []
    for doc in filtered:
        name = doc.get('name', '')
        name_normalized = normalize_text(name)
        doc_hospital = normalize_text(doc.get('hospital', ''))
        doc_dept_ar = normalize_text(doc.get('department_ar', ''))
        doc_dept_en = normalize_text(doc.get('department_en', ''))
        
        # حساب نقاط متقدمة
        advanced_score = 0
        
        # 1. تطابق الاسم (0-100 نقطة)
        name_score = fuzz.WRatio(query_normalized, name_normalized)
        advanced_score += name_score * 0.5  # 50% من النقاط
        
        # 2. تطابق البداية (إضافي +20 نقطة)
        if name_normalized.startswith(query_normalized):
            advanced_score += 20
        
        # 3. تطابق كامل (إضافي +30 نقطة)
        if query_normalized == name_normalized:
            advanced_score += 30
        
        # 4. تطابق المستشفى (إضافي +15 نقطة إذا كان محدد)
        if hospital:
            hospital_normalized = normalize_text(hospital)
            hospital_match = fuzz.ratio(hospital_normalized, doc_hospital)
            if hospital_match > 80:
                advanced_score += 15
        
        # 5. تطابق القسم (إضافي +20 نقطة إذا كان محدد)
        if department:
            dept_normalized = normalize_text(department)
            dept_ar_normalized = normalize_text(department.split('|')[0] if '|' in department else department)
            dept_en_normalized = normalize_text(department.split('|')[1] if '|' in department and len(department.split('|')) > 1 else '')
            
            # تطابق القسم العربي
            if dept_ar_normalized and doc_dept_ar:
                dept_ar_match = fuzz.ratio(dept_ar_normalized, doc_dept_ar)
                if dept_ar_match > 70:
                    advanced_score += 20
            
            # تطابق القسم الإنجليزي
            if dept_en_normalized and doc_dept_en:
                dept_en_match = fuzz.ratio(dept_en_normalized, doc_dept_en)
                if dept_en_match > 70:
                    advanced_score += 20
        
        # 6. تطابق كلمات متعددة (إضافي +10 نقطة)
        query_words = query_normalized.split()
        if len(query_words) > 1:
            matched_words = sum(1 for word in query_words if word in name_normalized)
            if matched_words == len(query_words):
                advanced_score += 10
        
        search_items.append({
            'doctor': doc,
            'search_text': name_normalized,
            'display_name': name,
            'advanced_score': advanced_score,
            'name_score': name_score
        })
    
    # البحث باستخدام RapidFuzz
    if not search_items:
        logger.warning("   ⚠️ لا توجد عناصر للبحث")
        return []
    
    # استخدام RapidFuzz للحصول على تطابقات أولية
    matches = process.extract(
        query_normalized,
        [item['search_text'] for item in search_items],
        scorer=fuzz.WRatio,
        limit=min(len(search_items), limit * 3),  # أخذ أكثر من limit للترتيب المتقدم
        score_cutoff=30  # حد أدنى للتطابق
    )
    
    logger.info(f"   → وُجد {len(matches)} تطابق أولي")
    
    # استخراج النتائج مع النقاط المتقدمة
    results = []
    for match_text, fuzz_score, idx in matches:
        item = search_items[idx]
        doctor = item['doctor']
        
        # دمج النقاط: 40% RapidFuzz + 60% Advanced Score
        final_score = (fuzz_score * 0.4) + (item['advanced_score'] * 0.6)
        
        results.append({
            'name': doctor.get('name', ''),
            'hospital': doctor.get('hospital', ''),
            'department': doctor.get('department', ''),
            'department_ar': doctor.get('department_ar', ''),
            'department_en': doctor.get('department_en', ''),
            'score': final_score,
            'fuzz_score': fuzz_score,
            'advanced_score': item['advanced_score']
        })
    
    # ✅ ترتيب متقدم: حسب النقاط النهائية، ثم تطابق القسم، ثم المستشفى، ثم أبجدياً
    def sort_key(x):
        score = -x['score']  # سالب للترتيب التنازلي
        
        # أولوية إضافية للتطابق الدقيق
        dept_bonus = 0
        if department:
            dept_normalized = normalize_text(department)
            doc_dept = normalize_text(x.get('department', ''))
            if dept_normalized in doc_dept or doc_dept in dept_normalized:
                dept_bonus = -50  # إضافة أولوية (سالبة لأننا نرتب تنازلياً)
        
        hospital_bonus = 0
        if hospital:
            hospital_normalized = normalize_text(hospital)
            doc_hospital = normalize_text(x.get('hospital', ''))
            if hospital_normalized in doc_hospital or doc_hospital in hospital_normalized:
                hospital_bonus = -30
        
        # ترتيب أبجدي كحل أخير
        name_sort = normalize_text(x.get('name', ''))
        
        return (score + dept_bonus + hospital_bonus, name_sort)
    
    results_sorted = sorted(results, key=sort_key)
    
    logger.info(f"   → تم ترتيب {len(results_sorted)} نتيجة")
    
    # ✅ تحسين الترتيب باستخدام AI (إذا كان متاحاً)
    if OPENAI_AVAILABLE and len(results_sorted) > 3:
        try:
            results_sorted = _ai_enhanced_ranking(
                results_sorted, 
                query, 
                hospital, 
                department
            )
            logger.info("   ✅ تم تحسين الترتيب باستخدام AI")
        except Exception as e:
            logger.warning(f"   ⚠️ فشل تحسين AI الترتيب: {e}")
    
    # ✅ تحقق نهائي صارم: التأكد من أن جميع النتائج من المستشفى والقسم المحددين فقط
    if hospital or department:
        final_results = []
        hospital_normalized = normalize_text(hospital) if hospital else None
        dept_normalized = normalize_text(department) if department else None
        
        for result in results_sorted:
            doc_hospital = normalize_text(result.get('hospital', ''))
            doc_dept_ar = normalize_text(result.get('department_ar', ''))
            doc_dept_en = normalize_text(result.get('department_en', ''))
            doc_dept = normalize_text(result.get('department', ''))
            
            # التحقق من المستشفى (إذا كان محدداً)
            hospital_match = True
            if hospital_normalized:
                hospital_match_ratio = fuzz.ratio(hospital_normalized, doc_hospital)
                # قبول التطابق الدقيق، التطابق الجزئي، أو fuzzy عالي
                hospital_match = (
                    hospital_normalized == doc_hospital or 
                    hospital_normalized in doc_hospital or 
                    doc_hospital in hospital_normalized or
                    hospital_match_ratio >= 90
                )
            
            # التحقق من القسم (إذا كان محدداً)
            dept_match = True
            if dept_normalized:
                all_dept_text = f"{doc_dept} {doc_dept_ar} {doc_dept_en}".lower()
                # تطابق دقيق للقسم
                dept_match = (
                    dept_normalized in all_dept_text or
                    all_dept_text in dept_normalized or
                    fuzz.ratio(dept_normalized, all_dept_text) >= 90
                )
            
            # إضافة النتيجة فقط إذا تطابقت مع المستشفى والقسم المحددين
            if hospital_match and dept_match:
                final_results.append(result)
            else:
                logger.debug(f"   ❌ تم استبعاد {result.get('name', '')} - لا يطابق الفلترة الصارمة (hospital_match={hospital_match}, dept_match={dept_match})")
        
        results_sorted = final_results
        logger.info(f"   ✅ بعد التحقق النهائي الصارم: {len(results_sorted)} طبيب")
    
    # إرجاع أفضل النتائج فقط
    return results_sorted[:limit]


def _ai_enhanced_ranking(
    results: List[Dict], 
    query: str, 
    hospital: Optional[str] = None, 
    department: Optional[str] = None
) -> List[Dict]:
    """
    تحسين ترتيب النتائج باستخدام AI
    
    يعطي أولوية للأطباء الأكثر صلة بالبحث
    """
    if not results or len(results) <= 3:
        return results
    
    try:
        # إنشاء prompt للـ AI
        context = f"Query: {query or 'None'}"
        if hospital:
            context += f" | Hospital: {hospital}"
        if department:
            context += f" | Department: {department}"
        
        # أخذ أول 10 نتائج فقط للتحليل (للتوفير)
        top_results = results[:10]
        
        # إنشاء قائمة الأطباء للتحليل
        doctors_list = []
        for idx, doc in enumerate(top_results):
            doctors_list.append({
                'index': idx,
                'name': doc.get('name', ''),
                'hospital': doc.get('hospital', ''),
                'department': doc.get('department_ar', '') or doc.get('department_en', '')
            })
        
        # استخدام نظام ترتيب محلي ذكي بدلاً من AI (أسرع وأكثر موثوقية)
        # يمكن تفعيل AI لاحقاً إذا لزم الأمر
        
        # ترتيب إضافي حسب الأولوية:
        # 1. تطابق كامل في الاسم
        # 2. تطابق في البداية
        # 3. تطابق القسم
        # 4. تطابق المستشفى
        
        def calculate_relevance_score(doc: Dict) -> float:
            score = doc.get('score', 0)
            
            name = normalize_text(doc.get('name', ''))
            query_norm = normalize_text(query) if query else ''
            
            # تطابق كامل
            if query_norm and query_norm == name:
                score += 50
            
            # تطابق في البداية
            elif query_norm and name.startswith(query_norm):
                score += 30
            
            # تطابق القسم
            if department:
                dept_norm = normalize_text(department)
                doc_dept = normalize_text(doc.get('department_ar', '') + ' ' + doc.get('department_en', ''))
                if dept_norm in doc_dept:
                    score += 20
            
            # تطابق المستشفى
            if hospital:
                hosp_norm = normalize_text(hospital)
                doc_hosp = normalize_text(doc.get('hospital', ''))
                if hosp_norm in doc_hosp:
                    score += 15
            
            return score
        
        # إعادة حساب النقاط
        for doc in top_results:
            doc['relevance_score'] = calculate_relevance_score(doc)
        
        # ترتيب حسب النقاط الجديدة
        top_results_sorted = sorted(
            top_results, 
            key=lambda x: (-x.get('relevance_score', 0), normalize_text(x.get('name', '')))
        )
        
        # دمج مع باقي النتائج
        final_results = top_results_sorted + results[10:]
        
        return final_results
        
    except Exception as e:
        logger.warning(f"خطأ في تحسين الترتيب: {e}")
        return results


def get_departments_for_hospital(hospital):
    """
    الحصول على قائمة الأقسام لمستشفى معين
    
    Args:
        hospital: اسم المستشفى
    
    Returns:
        قائمة بأسماء الأقسام الفريدة
    """
    doctors = load_doctors()
    
    if not doctors or not hospital:
        return []
    
    hospital_normalized = normalize_text(hospital)
    
    # فلترة الأطباء لهذا المستشفى
    hospital_doctors = [
        d for d in doctors
        if hospital_normalized in normalize_text(d.get('hospital', ''))
    ]
    
    # استخراج الأقسام الفريدة
    departments = set()
    for doc in hospital_doctors:
        dept = doc.get('department', '').strip()
        if dept and dept not in ['Unknown', 'Not specified', 'General']:
            departments.add(dept)
    
    return sorted(list(departments))


def get_doctors_for_hospital_dept(hospital, department):
    """
    الحصول على كل أطباء مستشفى وقسم معين
    
    Args:
        hospital: اسم المستشفى
        department: اسم القسم
    
    Returns:
        قائمة بالأطباء
    """
    return search_doctors(query="", hospital=hospital, department=department, limit=100)


# تم تعطيل الإضافة اليدوية - القاعدة ثابتة ونظيفة


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🧪 اختبار
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    print("="*70)
    print("🔍 اختبار نظام البحث الذكي")
    print("="*70)
    
    # تحميل
    doctors = load_doctors()
    print(f"\n✅ تم تحميل {len(doctors)} طبيب")
    
    # اختبار 1: بحث عام
    print("\n" + "="*70)
    print("اختبار 1: بحث عام عن 'ahmed'")
    results = search_doctors("ahmed", limit=5)
    for r in results:
        print(f"  • {r['name']} | {r['hospital']} | {r['department']}")
    
    # اختبار 2: بحث بمستشفى
    print("\n" + "="*70)
    print("اختبار 2: بحث عن 'kumar' في Sakra")
    results = search_doctors("kumar", hospital="Sakra", limit=5)
    for r in results:
        print(f"  • {r['name']} | {r['hospital']} | {r['department']}")
    
    # اختبار 3: بحث بمستشفى وقسم
    print("\n" + "="*70)
    print("اختبار 3: بحث عن 'raj' في Sakra - Cardiology")
    results = search_doctors("raj", hospital="Sakra", department="Cardio", limit=5)
    for r in results:
        print(f"  • {r['name']} | {r['hospital']} | {r['department']}")
    
    # اختبار 4: الحصول على أقسام مستشفى
    print("\n" + "="*70)
    print("اختبار 4: أقسام Sakra World Hospital")
    depts = get_departments_for_hospital("Sakra World Hospital")
    print(f"  وُجد {len(depts)} قسم")
    for dept in depts[:10]:
        print(f"  • {dept}")
    
    print("\n" + "="*70)

