#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 AI Analyzer Enhanced - محلل بيانات ذكي متقدم
يستخدم OpenAI لتحليل البيانات الطبية والتنبؤ بالاتجاهات
"""

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

# تحميل الإعدادات
load_dotenv(".env")
load_dotenv("config.env")

logger = logging.getLogger(__name__)

# OpenAI Settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# ====================================================
# 🧠 تحليل ذكي للبيانات الطبية
# ====================================================

async def analyze_patient_trends(patient_data: Dict[str, Any]) -> str:
    """
    تحليل اتجاهات المريض باستخدام AI
    
    Args:
        patient_data: بيانات المريض (name, reports, visits, etc.)
    
    Returns:
        str: تحليل ذكي للاتجاهات
    """
    if not OPENAI_API_KEY:
        return analyze_trends_simple(patient_data)
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # إعداد البيانات للتحليل
        summary = f"""
بيانات المريض:
- الاسم: {patient_data.get('name', 'غير محدد')}
- عدد الزيارات: {patient_data.get('visits_count', 0)}
- عدد التقارير: {patient_data.get('reports_count', 0)}
- آخر زيارة: {patient_data.get('last_visit', 'غير محدد')}
- الأقسام المزارة: {', '.join(patient_data.get('departments', []))}
- الأطباء: {', '.join(patient_data.get('doctors', []))}
- الشكاوى الشائعة: {', '.join(patient_data.get('common_complaints', []))}
"""
        
        def call_openai():
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "أنت محلل بيانات طبية ذكي. حلل بيانات المريض وقدم:\n"
                                 "1. تقييم الحالة الصحية\n"
                                 "2. الاتجاهات الملاحظة\n"
                                 "3. التوصيات الطبية\n"
                                 "4. التنبؤ بالزيارات القادمة\n"
                                 "الرد يجب أن يكون بالعربية، منظم، ومهني."
                    },
                    {
                        "role": "user",
                        "content": f"حلل بيانات هذا المريض وقدم تقريراً شاملاً:\n\n{summary}"
                    }
                ],
                temperature=0.4,
                max_tokens=600
            )
            return response.choices[0].message.content.strip()
        
        result = await asyncio.to_thread(call_openai)
        return f"🧠 **تحليل ذكي للمريض:**\n\n{result}"
        
    except Exception as e:
        logger.error(f"AI Analysis Error: {e}")
        return analyze_trends_simple(patient_data)


def analyze_trends_simple(patient_data: Dict[str, Any]) -> str:
    """تحليل بسيط بدون OpenAI"""
    visits = patient_data.get('visits_count', 0)
    reports = patient_data.get('reports_count', 0)
    
    if visits >= 20:
        risk = "🔴 عالية - يحتاج متابعة دقيقة"
    elif visits >= 10:
        risk = "🟡 متوسطة - متابعة دورية"
    else:
        risk = "🟢 منخفضة - حالة مستقرة"
    
    return f"""📊 **تحليل بسيط:**

🏥 تقييم الحالة: {risk}
📈 عدد الزيارات: {visits}
📋 عدد التقارير: {reports}

✅ التوصية: متابعة دورية حسب الحالة."""


async def analyze_hospital_performance(hospital_stats: Dict[str, Any]) -> str:
    """
    تحليل أداء المستشفى باستخدام AI
    """
    if not OPENAI_API_KEY:
        return analyze_hospital_simple(hospital_stats)
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        stats_text = f"""
إحصائيات المستشفى:
- اسم المستشفى: {hospital_stats.get('name')}
- عدد التقارير: {hospital_stats.get('reports_count', 0)}
- عدد المرضى: {hospital_stats.get('patients_count', 0)}
- الأطباء النشطون: {hospital_stats.get('doctors_count', 0)}
- الأقسام: {', '.join(hospital_stats.get('departments', []))}
- الإجراءات الشائعة: {', '.join(hospital_stats.get('common_actions', []))}
"""
        
        def call_openai():
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "أنت محلل أداء مستشفيات. حلل الإحصائيات وقدم:\n"
                                 "1. تقييم الأداء العام\n"
                                 "2. نقاط القوة\n"
                                 "3. مجالات التحسين\n"
                                 "4. توصيات محددة"
                    },
                    {
                        "role": "user",
                        "content": f"حلل أداء هذا المستشفى:\n\n{stats_text}"
                    }
                ],
                temperature=0.3,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        
        result = await asyncio.to_thread(call_openai)
        return f"🏥 **تحليل أداء المستشفى:**\n\n{result}"
        
    except Exception as e:
        logger.error(f"Hospital Analysis Error: {e}")
        return analyze_hospital_simple(hospital_stats)


def analyze_hospital_simple(stats: Dict[str, Any]) -> str:
    """تحليل بسيط لأداء المستشفى"""
    reports = stats.get('reports_count', 0)
    patients = stats.get('patients_count', 0)
    
    if reports >= 100:
        performance = "🟢 ممتاز - نشاط عالي"
    elif reports >= 50:
        performance = "🟡 جيد - نشاط متوسط"
    else:
        performance = "🔴 ضعيف - نشاط منخفض"
    
    return f"""🏥 **تحليل أداء المستشفى:**

📊 التقييم: {performance}
📋 عدد التقارير: {reports}
👥 عدد المرضى: {patients}

✅ التوصية: متابعة تحسين الخدمات."""


async def predict_future_trends(historical_data: List[Dict]) -> str:
    """
    التنبؤ بالاتجاهات المستقبلية باستخدام AI
    """
    if not OPENAI_API_KEY or not historical_data:
        return "⚠️ بيانات غير كافية للتنبؤ"
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # تجهيز البيانات التاريخية
        data_summary = "\n".join([
            f"- {item.get('date')}: {item.get('count')} تقرير"
            for item in historical_data[-30:]  # آخر 30 يوم
        ])
        
        def call_openai():
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "أنت محلل بيانات متخصص في التنبؤ بالاتجاهات الطبية. "
                                 "حلل البيانات التاريخية وتنبأ بالأسبوع القادم."
                    },
                    {
                        "role": "user",
                        "content": f"البيانات التاريخية (آخر 30 يوم):\n\n{data_summary}\n\n"
                                 f"تنبأ بعدد التقارير المتوقعة خلال الأسبوع القادم واذكر الأسباب."
                    }
                ],
                temperature=0.2,
                max_tokens=400
            )
            return response.choices[0].message.content.strip()
        
        result = await asyncio.to_thread(call_openai)
        return f"🔮 **التنبؤ بالاتجاهات:**\n\n{result}"
        
    except Exception as e:
        logger.error(f"Prediction Error: {e}")
        return "⚠️ فشل التنبؤ"


async def generate_insights_report(all_data: Dict[str, Any]) -> str:
    """
    إنشاء تقرير رؤى ذكية شاملة
    """
    if not OPENAI_API_KEY:
        return "⚠️ OpenAI غير متوفر للرؤى المتقدمة"
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # تجهيز ملخص شامل
        data_summary = f"""
📊 **إحصائيات عامة:**
- إجمالي التقارير: {all_data.get('total_reports', 0)}
- إجمالي المرضى: {all_data.get('total_patients', 0)}
- المستشفيات النشطة: {all_data.get('active_hospitals', 0)}
- الأطباء النشطون: {all_data.get('active_doctors', 0)}

📈 **الاتجاهات:**
- أكثر شكوى: {all_data.get('top_complaint', 'غير محدد')}
- أكثر قسم نشاطاً: {all_data.get('top_department', 'غير محدد')}
- أكثر إجراء: {all_data.get('top_action', 'غير محدد')}

📅 **الفترة الزمنية:**
- من: {all_data.get('date_from', 'غير محدد')}
- إلى: {all_data.get('date_to', 'غير محدد')}
"""
        
        def call_openai():
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "أنت محلل بيانات طبية خبير. قدم رؤى ذكية وتوصيات استراتيجية "
                                 "بناءً على البيانات. ركز على:\n"
                                 "1. الاتجاهات المهمة\n"
                                 "2. المشاكل المحتملة\n"
                                 "3. فرص التحسين\n"
                                 "4. توصيات قابلة للتنفيذ"
                    },
                    {
                        "role": "user",
                        "content": f"حلل هذه البيانات الطبية وقدم رؤى ذكية:\n\n{data_summary}"
                    }
                ],
                temperature=0.5,
                max_tokens=800
            )
            return response.choices[0].message.content.strip()
        
        result = await asyncio.to_thread(call_openai)
        return f"💡 **رؤى ذكية:**\n\n{result}"
        
    except Exception as e:
        logger.error(f"Insights Error: {e}")
        return "⚠️ فشل إنشاء الرؤى الذكية"


async def generate_pdf_with_ai_insights(report_data: Dict, patient_history: List[Dict]) -> str:
    """
    إنشاء تقرير PDF مع رؤى ذكية من AI
    """
    if not OPENAI_API_KEY:
        return "⚠️ OpenAI غير متوفر"
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # تحليل السجل الطبي
        history_summary = "\n".join([
            f"- {h['date']}: {h['complaint']} → {h['decision']}"
            for h in patient_history[-10:]  # آخر 10 تقارير
        ])
        
        def call_openai():
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "أنت طبيب استشاري. راجع السجل الطبي وقدم:\n"
                                 "1. ملخص الحالة\n"
                                 "2. التطور الملاحظ\n"
                                 "3. توصيات للمتابعة"
                    },
                    {
                        "role": "user",
                        "content": f"السجل الطبي للمريض:\n\n{history_summary}\n\n"
                                 f"قدم تقييماً شاملاً وتوصيات."
                    }
                ],
                temperature=0.3,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()
        
        insights = await asyncio.to_thread(call_openai)
        
        # إضافة الرؤى للتقرير
        report_data['ai_insights'] = insights
        
        return insights
        
    except Exception as e:
        logger.error(f"PDF Insights Error: {e}")
        return None


async def auto_categorize_complaints(complaints: List[str]) -> Dict[str, List[str]]:
    """
    تصنيف الشكاوى تلقائياً باستخدام AI
    """
    if not OPENAI_API_KEY or not complaints:
        return {}
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        complaints_text = "\n".join([f"{i+1}. {c}" for i, c in enumerate(complaints[:50])])
        
        def call_openai():
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "صنف هذه الشكاوى الطبية إلى فئات رئيسية. "
                                 "أعد قائمة بالفئات وعدد الشكاوى في كل فئة."
                    },
                    {
                        "role": "user",
                        "content": f"صنف هذه الشكاوى:\n\n{complaints_text}"
                    }
                ],
                temperature=0.2,
                max_tokens=400
            )
            return response.choices[0].message.content.strip()
        
        result = await asyncio.to_thread(call_openai)
        return {"categorization": result}
        
    except Exception as e:
        logger.error(f"Categorization Error: {e}")
        return {}


async def detect_anomalies(data_points: List[Dict]) -> str:
    """
    اكتشاف الأنماط غير الطبيعية في البيانات
    """
    if not OPENAI_API_KEY or not data_points:
        return "⚠️ بيانات غير كافية"
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # تجهيز البيانات
        data_summary = "\n".join([
            f"- {dp['date']}: {dp['count']} تقارير ({dp.get('notes', '')})"
            for dp in data_points[-30:]
        ])
        
        def call_openai():
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "أنت محلل بيانات متخصص في اكتشاف الأنماط غير الطبيعية. "
                                 "ابحث عن:\n"
                                 "1. ارتفاعات/انخفاضات مفاجئة\n"
                                 "2. أنماط غير متوقعة\n"
                                 "3. احتمالية وجود مشكلة"
                    },
                    {
                        "role": "user",
                        "content": f"حلل هذه البيانات واكتشف الأنماط غير الطبيعية:\n\n{data_summary}"
                    }
                ],
                temperature=0.3,
                max_tokens=400
            )
            return response.choices[0].message.content.strip()
        
        result = await asyncio.to_thread(call_openai)
        return f"⚠️ **كشف الأنماط:**\n\n{result}"
        
    except Exception as e:
        logger.error(f"Anomaly Detection Error: {e}")
        return "⚠️ فشل كشف الأنماط"


# ====================================================
# 🔍 دوال مساعدة
# ====================================================

def is_ai_enabled() -> bool:
    """التحقق من تفعيل AI"""
    return OPENAI_API_KEY is not None


async def test_ai_analyzer():
    """اختبار المحلل الذكي"""
    print("="*60)
    print("🧪 اختبار AI Analyzer Enhanced")
    print("="*60)
    
    if is_ai_enabled():
        print("✅ OpenAI متوفر")
        print(f"🤖 Model: {OPENAI_MODEL}")
        
        # اختبار تحليل مريض
        test_patient = {
            'name': 'أحمد محمد',
            'visits_count': 15,
            'reports_count': 15,
            'last_visit': '2025-10-29',
            'departments': ['الطوارئ', 'الباطنية', 'القلب'],
            'doctors': ['د. سارة', 'د. محمد'],
            'common_complaints': ['ألم صدر', 'ضغط مرتفع']
        }
        
        result = await analyze_patient_trends(test_patient)
        print("\n📊 نتيجة التحليل:")
        print(result)
    else:
        print("⚠️ OpenAI غير متوفر (سيتم استخدام التحليل البسيط)")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(test_ai_analyzer())

