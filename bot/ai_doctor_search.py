# ================================================
# bot/ai_doctor_search.py
# 🤖 نظام البحث عن الأطباء - هجين (ملف + AI)
# ================================================

import os
import asyncio
import logging
import re
import time
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv("config.env")
logger = logging.getLogger(__name__)

# ✅ Cache للنتائج لتجنب الطلبات المتكررة
_last_request_time = 0
_min_request_interval = 1.5  # ثانية بين كل طلب
_request_cache = {}

# ✅ قاعدة بيانات الأطباء المحلية
_doctors_db = None


def _normalize_arabic_text(text):
    """تطبيع النص العربي للبحث"""
    if not text:
        return ""
    
    # إزالة التشكيل
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)
    
    # توحيد الحروف المتشابهة
    replacements = {
        'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا',
        'ة': 'ه',
        'ى': 'ي',
        'ئ': 'ي', 'ؤ': 'و'
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text.strip().lower()


def _load_doctors_from_file():
    """تحميل الأطباء من ملف data/doctors.txt"""
    doctors = []
    file_path = 'data/doctors.txt'
    
    if not os.path.exists(file_path):
        logger.warning(f"⚠️ ملف الأطباء غير موجود: {file_path}")
        return doctors
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f, 1):
                line = line.strip()
                
                # تجاهل السطور الفارغة والتعليقات
                if not line or line.startswith('#'):
                    continue
                
                # تقسيم السطر
                parts = line.split('|')
                if len(parts) < 1:
                    continue
                
                name = parts[0].strip()
                hospital = parts[1].strip() if len(parts) > 1 else ""
                department = parts[2].strip() if len(parts) > 2 else ""
                
                if name:
                    doctors.append({
                        'id': f'DB{idx:03d}',
                        'name': name,
                        'hospital': hospital or "متاح",
                        'department': department or "متاح",
                        'name_normalized': _normalize_arabic_text(name)
                    })
        
        logger.info(f"✅ تم تحميل {len(doctors)} طبيب من ملف الأطباء")
        return doctors
    
    except Exception as e:
        logger.error(f"❌ خطأ في تحميل ملف الأطباء: {e}")
        return doctors


def get_doctors_database():
    """الحصول على قاعدة بيانات الأطباء (مع cache)"""
    global _doctors_db
    
    if _doctors_db is None:
        _doctors_db = _load_doctors_from_file()
    
    return _doctors_db


def search_doctors_locally(query, hospital=None, department=None):
    """البحث في قاعدة البيانات المحلية للأطباء"""
    doctors = get_doctors_database()
    
    if not doctors:
        return []
    
    query_norm = _normalize_arabic_text(query) if query else ""
    hospital_norm = _normalize_arabic_text(hospital) if hospital else ""
    department_norm = _normalize_arabic_text(department) if department else ""
    
    results = []
    
    for doctor in doctors:
        # فحص المستشفى
        if hospital_norm and doctor['hospital'] != "متاح":
            doc_hospital_norm = _normalize_arabic_text(doctor['hospital'])
            if hospital_norm not in doc_hospital_norm and doc_hospital_norm not in hospital_norm:
                continue
        
        # فحص القسم
        if department_norm and doctor['department'] != "متاح":
            doc_dept_norm = _normalize_arabic_text(doctor['department'])
            if department_norm not in doc_dept_norm and doc_dept_norm not in department_norm:
                continue
        
        # فحص الاسم
        if query_norm:
            if query_norm in doctor['name_normalized']:
                results.append(doctor)
        else:
            # بدون query - إرجاع كل الأطباء المطابقين للمستشفى والقسم
            results.append(doctor)
    
    logger.info(f"🔍 البحث المحلي: وُجد {len(results)} طبيب للاستعلام '{query}'")
    return results


async def get_ai_doctor_suggestions(
    query: str,
    *,
    hospital: str | None = None,
    department: str | None = None,
) -> list:
    """
    🤖 اقتراح أسماء أطباء باستخدام الذكاء الاصطناعي بناءً على المستشفى والقسم.
    
    Args:
        query: الاسم المدخل من المستخدم (يمكن أن يكون فارغاً)
        hospital: اسم المستشفى المختار
        department: اسم القسم/التخصص المختار
    
    Returns:
        list: قائمة من 5-8 أطباء مقترحين
    """
    global _last_request_time, _request_cache
    
    query = (query or "").strip()
    
    # ✅ حد أدنى 3 أحرف للبحث (لتجنب طلبات كثيرة أثناء الكتابة)
    if query and len(query) < 3:
        logger.info(f"⚠️ الاسم قصير جداً ({len(query)} أحرف) - الحد الأدنى 3 أحرف")
        return []
    
    # السماح بالبحث بدون query إذا كان هناك hospital و department
    if len(query) < 1 and (not hospital or not department):
        logger.info("⚠️ لا يوجد سياق كافٍ للبحث")
        return []

    # ✅ إنشاء مفتاح cache
    cache_key = f"{query}|{hospital}|{department}"
    
    # ✅ التحقق من الـ cache أولاً
    if cache_key in _request_cache:
        cache_time, cached_results = _request_cache[cache_key]
        # Cache صالح لمدة 5 دقائق
        if time.time() - cache_time < 300:
            logger.info(f"✅ استخدام cache للسياق: {cache_key}")
            return cached_results
    
    # ✅ 1️⃣ البحث المحلي أولاً (في ملف الأطباء)
    local_results = search_doctors_locally(query, hospital, department)
    
    if local_results:
        logger.info(f"✅ وُجد {len(local_results)} طبيب في القاعدة المحلية")
        # حفظ في الـ cache
        _request_cache[cache_key] = (time.time(), local_results)
        return local_results
    
    # ✅ 2️⃣ إذا لم يُوجد في القاعدة المحلية، استخدم الذكاء الاصطناعي
    logger.info("🤖 لم يُوجد في القاعدة المحلية - استخدام الذكاء الاصطناعي...")
    
    # ✅ Rate Limiting - تجنب الطلبات السريعة جداً
    current_time = time.time()
    time_since_last = current_time - _last_request_time
    
    if time_since_last < _min_request_interval:
        wait_time = _min_request_interval - time_since_last
        logger.info(f"⏳ انتظار {wait_time:.1f}s لتجنب Too Many Requests")
        await asyncio.sleep(wait_time)
    
    _last_request_time = time.time()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("⚠️ OpenAI API Key غير موجود")
        return []

    try:
        from openai import OpenAI
    except ImportError:
        logger.error("❌ OpenAI library not installed")
        return []

    client = OpenAI(api_key=api_key)

    # بناء السياق
    context_parts = []
    if query:
        context_parts.append(f"الاسم المدخل: '{query}'")
    if hospital:
        context_parts.append(f"المستشفى: {hospital}")
    if department:
        context_parts.append(f"القسم/التخصص: {department}")

    context_text = " | ".join(context_parts) if context_parts else "طلب عام"

    # Prompt محسّن للحصول على عدة اقتراحات (تقليل العدد لتسريع الاستجابة)
    prompt = f"""أنت مساعد طبي ذكي في الهند. أعطني قائمة بـ 5 أسماء أطباء حقيقيين ومناسبين للسياق التالي:

{context_text}

القواعد المهمة:
1. أسماء واقعية وشائعة في الهند (هندية، عربية، أو إنجليزية)
2. كل سطر: اسم طبيب واحد فقط بصيغة "د. الاسم الكامل" أو "Dr. Full Name"
3. إذا كان هناك اسم مدخل، اقترح أسماء مشابهة له أو تحتويه
4. متنوعة ومناسبة للتخصص المذكور
5. بدون أرقام أو رموز - فقط الأسماء
6. كل اسم في سطر منفصل
7. بدون شرح أو نصوص إضافية

مثال للصيغة المطلوبة:
د. أميت كومار
Dr. Rajesh Sharma
د. سانديا باتيل
Dr. Mohammed Ali

الآن أعطني 5 أسماء:"""

    def call_openai() -> str:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "أنت خبير طبي تقترح أسماء أطباء واقعية. أعطِ فقط الأسماء بدون أي نص إضافي."
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=150,  # تقليل لتسريع الاستجابة
            temperature=0.5,  # تقليل قليلاً للدقة
        )
        return response.choices[0].message.content.strip()

    try:
        logger.info(f"🔍 إرسال طلب للذكاء الاصطناعي: {context_text}")
        ai_response = await asyncio.to_thread(call_openai)
    except Exception as exc:
        logger.error(f"❌ AI doctor suggestion failed: {exc}")
        return []

    if not ai_response:
        return []

    # تحليل النتيجة وتحويلها لقائمة أطباء
    doctors_list = []
    lines = ai_response.strip().split('\n')
    
    for idx, line in enumerate(lines, 1):
        line = line.strip()
        
        # تنظيف السطر من الأرقام والرموز في البداية (مثل: 1. أو - أو *)
        line = re.sub(r'^[\d\.\-\*\•\◦\→\►]+\s*', '', line)
        
        if not line or len(line) < 3:
            continue
        
        # التأكد من وجود "د." أو "Dr."
        if not (line.startswith('د.') or line.startswith('Dr.') or line.startswith('دكتور')):
            # إضافة د. إذا لم تكن موجودة
            # التحقق إذا كان الاسم عربي
            has_arabic = bool(re.search(r'[\u0600-\u06FF]', line))
            if has_arabic:
                line = f"د. {line}"
            else:
                line = f"Dr. {line}"
        
        doctors_list.append({
            "id": f"AI{idx:03d}",
            "name": line,
            "hospital": hospital or "متاح",
            "department": department or "متاح",
        })
        
        # حد أقصى 8 أطباء
        if len(doctors_list) >= 8:
            break
    
    logger.info(f"✅ AI اقترح {len(doctors_list)} طبيب للسياق: {context_text}")
    
    # ✅ حفظ في الـ cache
    _request_cache[cache_key] = (time.time(), doctors_list)
    
    # ✅ تنظيف الـ cache القديم (أكثر من 100 إدخال)
    if len(_request_cache) > 100:
        # حذف أقدم 50 إدخال
        sorted_cache = sorted(_request_cache.items(), key=lambda x: x[1][0])
        for old_key, _ in sorted_cache[:50]:
            del _request_cache[old_key]
    
    return doctors_list

