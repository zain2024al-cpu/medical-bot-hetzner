#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF Generator - نسخة محلية (Windows)
تعطيل مؤقت لـ WeasyPrint للاختبار المحلي
"""

def generate_pdf_report(report_data, output_path):
    """
    تعطيل PDF مؤقتاً للاختبار المحلي على Windows
    سيعمل على Cloud Run بدون مشاكل
    """
    print("⚠️ PDF معطل مؤقتاً للاختبار المحلي (Windows)")
    print("✅ سيعمل على Cloud Run بشكل طبيعي")
    
    # إنشاء ملف نصي بدلاً من PDF للاختبار
    txt_path = output_path.replace('.pdf', '.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write("تقرير طبي\n")
        f.write("="*50 + "\n\n")
        f.write(f"المريض: {report_data.get('patient_name', 'N/A')}\n")
        f.write(f"التاريخ: {report_data.get('date', 'N/A')}\n")
        f.write(f"المستشفى: {report_data.get('hospital', 'N/A')}\n")
        f.write(f"الطبيب: {report_data.get('doctor_name', 'N/A')}\n")
    
    return txt_path


def generate_pdf_reports(reports_list, output_path):
    """
    تعطيل PDF مؤقتاً للاختبار المحلي
    """
    print("⚠️ PDF معطل مؤقتاً للاختبار المحلي (Windows)")
    print("✅ سيعمل على Cloud Run بشكل طبيعي")
    
    txt_path = output_path.replace('.pdf', '.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write("تقارير طبية\n")
        f.write("="*50 + "\n\n")
        f.write(f"عدد التقارير: {len(reports_list)}\n")
    
    return txt_path

















