#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📄 PDF Generator with AI Insights
محرك PDF محسّن مع رؤى ذكية من AI
"""

import os
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
# import pdfkit  # معطل - نستخدم WeasyPrint

# تحميل الإعدادات
load_dotenv(".env")
load_dotenv("config.env")

logger = logging.getLogger(__name__)

# Paths (absolute)
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = str(BASE_DIR / "templates")
OUTPUT_DIR = str(BASE_DIR / "exports")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# PDF Options
DEFAULT_PDF_OPTIONS = {
    'enable-local-file-access': None,
    'print-media-type': None,
    'encoding': 'UTF-8',
    'page-size': 'A4',
    'margin-top': '20mm',
    'margin-right': '20mm',
    'margin-bottom': '20mm',
    'margin-left': '20mm',
    'dpi': 300,
}

# ====================================================
# 🤖 PDF مع رؤى AI
# ====================================================

async def generate_ai_enhanced_report(patient_data: Dict, reports: List[Dict]) -> str:
    """
    إنشاء تقرير PDF محسّن مع رؤى AI
    
    Args:
        patient_data: بيانات المريض
        reports: قائمة التقارير
    
    Returns:
        str: مسار ملف PDF
    """
    try:
        # تحليل البيانات بالـ AI
        ai_insights = None
        if OPENAI_API_KEY:
            logger.info("🤖 Generating AI insights for PDF...")
            ai_insights = await generate_patient_insights(patient_data, reports)
        
        # تحميل القالب
        env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        template = env.get_template('patient_history_ai.html')
        
        # تجهيز البيانات
        context = {
            'patient': patient_data,
            'reports': reports,
            'ai_insights': ai_insights,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'has_ai': ai_insights is not None
        }
        
        # إنشاء HTML
        html_content = template.render(**context)
        
        # إنشاء PDF
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(OUTPUT_DIR, f"patient_ai_{patient_data.get('id', 'x')}_{timestamp}.pdf")
        
        pdfkit.from_string(html_content, output_path, options=DEFAULT_PDF_OPTIONS)
        
        logger.info(f"✅ AI-enhanced PDF created: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ PDF creation error: {e}")
        raise


async def generate_patient_insights(patient_data: Dict, reports: List[Dict]) -> str:
    """إنشاء رؤى ذكية للمريض"""
    if not OPENAI_API_KEY:
        return None
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # تجهيز السجل الطبي
        medical_history = "\n".join([
            f"- {r.get('date', 'غير محدد')}: {r.get('complaint', '')} → {r.get('decision', '')}"
            for r in reports[-15:]  # آخر 15 تقرير
        ])
        
        patient_summary = f"""
معلومات المريض:
- الاسم: {patient_data.get('full_name', 'غير محدد')}
- العمر: {patient_data.get('age', 'غير محدد')}
- عدد الزيارات: {len(reports)}

السجل الطبي (آخر 15 زيارة):
{medical_history}
"""
        
        def call_openai():
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "أنت طبيب استشاري متخصص. راجع السجل الطبي للمريض وقدم:\n"
                                 "1. **ملخص الحالة الصحية**\n"
                                 "2. **التطور الملاحظ** (تحسن/تدهور/مستقر)\n"
                                 "3. **المخاطر المحتملة**\n"
                                 "4. **توصيات للمتابعة**\n\n"
                                 "اجعل الرد منظماً ومهنياً بالعربية."
                    },
                    {
                        "role": "user",
                        "content": f"راجع السجل الطبي وقدم تقييماً شاملاً:\n\n{patient_summary}"
                    }
                ],
                temperature=0.4,
                max_tokens=600
            )
            return response.choices[0].message.content.strip()
        
        insights = await asyncio.to_thread(call_openai)
        return insights
        
    except Exception as e:
        logger.error(f"Insights generation error: {e}")
        return None


async def generate_analysis_summary_pdf(analysis_data: Dict) -> str:
    """
    إنشاء تقرير تحليل شامل مع رؤى AI
    """
    try:
        # رؤى AI للتحليل الشامل
        ai_summary = None
        if OPENAI_API_KEY:
            ai_summary = await generate_analysis_insights(analysis_data)
        
        # تحميل قالب التحليل
        env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        template = env.get_template('analytics_report_ai.html')
        
        context = {
            **analysis_data,
            'ai_summary': ai_summary,
            'has_ai': ai_summary is not None,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        html_content = template.render(**context)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(OUTPUT_DIR, f"analysis_ai_{timestamp}.pdf")
        
        pdfkit.from_string(html_content, output_path, options=DEFAULT_PDF_OPTIONS)
        
        logger.info(f"✅ Analysis PDF with AI created: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Analysis PDF error: {e}")
        raise


async def generate_analysis_insights(data: Dict) -> str:
    """إنشاء رؤى ذكية للتحليل الشامل"""
    if not OPENAI_API_KEY:
        return None
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        data_summary = f"""
📊 **الإحصائيات العامة:**
- إجمالي التقارير: {data.get('total_reports', 0)}
- إجمالي المرضى: {data.get('total_patients', 0)}
- المستشفيات: {data.get('hospitals_count', 0)}
- الأطباء: {data.get('doctors_count', 0)}

📈 **الأكثر شيوعاً:**
- أكثر مستشفى: {data.get('top_hospital', 'غير محدد')}
- أكثر قسم: {data.get('top_department', 'غير محدد')}
- أكثر إجراء: {data.get('top_action', 'غير محدد')}
"""
        
        def call_openai():
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "أنت محلل بيانات طبية خبير. حلل الإحصائيات وقدم:\n"
                                 "1. **الرؤى الرئيسية** (أهم 3 ملاحظات)\n"
                                 "2. **الاتجاهات** (ما يحدث)\n"
                                 "3. **التوصيات** (خطوات عملية)\n"
                                 "4. **التنبؤات** (ما هو متوقع)"
                    },
                    {
                        "role": "user",
                        "content": f"حلل هذه البيانات الطبية وقدم رؤى استراتيجية:\n\n{data_summary}"
                    }
                ],
                temperature=0.5,
                max_tokens=700
            )
            return response.choices[0].message.content.strip()
        
        insights = await asyncio.to_thread(call_openai)
        return insights
        
    except Exception as e:
        logger.error(f"Analysis insights error: {e}")
        return None


# ====================================================
# 🧪 اختبار
# ====================================================

if __name__ == "__main__":
    async def test():
        print("="*60)
        print("🧪 اختبار PDF AI Enhanced")
        print("="*60)
        
        test_data = {
            'total_reports': 150,
            'total_patients': 45,
            'hospitals_count': 5,
            'doctors_count': 12,
            'top_hospital': 'مستشفى الملك فيصل',
            'top_department': 'الطوارئ',
            'top_action': 'فحص سريري'
        }
        
        insights = await generate_analysis_insights(test_data)
        if insights:
            print("\n💡 الرؤى الذكية:")
            print(insights)
        else:
            print("\n⚠️ OpenAI غير متوفر")
        
        print("\n" + "="*60)
    
    asyncio.run(test())

