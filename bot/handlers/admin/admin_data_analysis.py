# =============================
# bot/handlers/admin/admin_data_analysis.py
# 📊 تحليل البيانات الشامل مع الذكاء الاصطناعي المتقدم - AI Data Analysis
# =============================
import asyncio

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from datetime import datetime, timedelta
from db.session import SessionLocal
from db.models import Report, Patient, Hospital, Department, Doctor, Translator
from bot.shared_auth import is_admin
from collections import Counter, defaultdict
import re
from statistics import mean, median
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import os
import logging
import arabic_reshaper
from bidi.algorithm import get_display

# pdfkit معطل (نستخدم WeasyPrint)
# import pdfkit

# Logger
logger = logging.getLogger(__name__)

# 🤖 استيراد AI Analyzer المتقدم
try:
    from services.ai_analyzer_enhanced import (
        analyze_patient_trends,
        analyze_hospital_performance,
        predict_future_trends,
        generate_insights_report,
        is_ai_enabled
    )
    AI_ANALYZER_AVAILABLE = True
except ImportError:
    AI_ANALYZER_AVAILABLE = False

# الحالات
SELECT_ANALYSIS_TYPE, SELECT_DATE_FILTER, SELECT_ENTITY, SHOW_ANALYSIS = range(4)


# ================================================
# ✅ معالجة اختيار المريض من Inline Query للتحليل
# ================================================

async def handle_analyze_patient_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أمر /analyze_patient من Inline Query"""
    
    if not update.message or not update.message.text:
        return
    
    user = update.effective_user
    if not is_admin(user.id):
        return
    
    # استخراج معرف المريض من الأمر
    command_parts = update.message.text.split()
    if len(command_parts) < 2:
        await update.message.reply_text("❌ خطأ في اختيار المريض")
        return
    
    try:
        patient_id = int(command_parts[1])
    except ValueError:
        await update.message.reply_text("❌ معرف مريض غير صحيح")
        return
    
    # البحث عن المريض وتحليل بياناته
    with SessionLocal() as session:
        patient = session.query(Patient).filter(Patient.id == patient_id).first()
        
        if not patient:
            await update.message.reply_text("❌ لم يتم العثور على المريض")
            return
        
        # حساب عدد التقارير
        reports_count = session.query(Report).filter(
            Report.patient_id == patient.id
        ).count()
        
        await update.message.reply_text(
            f"✅ **تم اختيار المريض للتحليل**\n\n"
            f"👤 الاسم: {patient.full_name}\n"
            f"📊 عدد التقارير: {reports_count}\n\n"
            f"⏳ جاري التحليل...",
            parse_mode="Markdown"
        )
        
        # تنفيذ التحليل
        context.user_data["start_date"] = None
        context.user_data["end_date"] = None
        context.user_data["period_name"] = "كل الفترات"
        
        # استخدام دالة التحليل الموجودة
        await analyze_patient_direct(update.message, context, patient_id)


async def analyze_patient_direct(message, context, patient_id):
    """تحليل بيانات مريض مباشرة"""
    # نسخة مبسطة من analyze_patient للاستخدام المباشر
    with SessionLocal() as s:
        patient = s.query(Patient).get(patient_id)
        if not patient:
            await message.reply_text("❌ لم يتم العثور على المريض")
            return
        
        # جلب كل التقارير للمريض
        reports = s.query(Report).filter(Report.patient_id == patient_id).order_by(Report.report_date.desc()).all()
        
        if not reports:
            await message.reply_text(f"⚠️ لا توجد تقارير للمريض: {patient.full_name}")
            return
        
        # بناء النص التحليلي (مبسط)
        analysis_text = f"""
📊 **تحليل بيانات المريض**

👤 **المريض:** {patient.full_name}
📈 **عدد التقارير:** {len(reports)}
📅 **أول تقرير:** {reports[-1].report_date.strftime('%Y-%m-%d') if reports else 'غير محدد'}
📅 **آخر تقرير:** {reports[0].report_date.strftime('%Y-%m-%d') if reports else 'غير محدد'}

🏥 **المستشفيات:**
"""
        
        # إحصائيات المستشفيات
        hospitals = {}
        for r in reports:
            if r.hospital_id:
                h = s.get(Hospital, r.hospital_id)
                if h:
                    hospitals[h.name] = hospitals.get(h.name, 0) + 1
        
        for hosp, count in sorted(hospitals.items(), key=lambda x: x[1], reverse=True)[:5]:
            analysis_text += f"• {hosp}: {count} تقرير\n"
        
        await message.reply_text(analysis_text, parse_mode="Markdown")


# =============================
# 🤖 دوال الذكاء الاصطناعي
# =============================

def extract_keywords(text):
    """استخراج الكلمات المفتاحية من النص"""
    if not text:
        return []
    
    # كلمات طبية شائعة
    medical_keywords = [
        'ألم', 'حمى', 'صداع', 'كسر', 'التهاب', 'عدوى', 'نزيف', 
        'دوخة', 'غثيان', 'سعال', 'ضيق', 'تنفس', 'إسهال', 'إمساك',
        'حساسية', 'طفح', 'حكة', 'جرح', 'ورم', 'تورم', 'إصابة'
    ]
    
    keywords = []
    text_lower = text.lower()
    for keyword in medical_keywords:
        if keyword in text_lower:
            keywords.append(keyword)
    
    return keywords

def predict_next_visit(visit_intervals, last_visit):
    """التنبؤ بموعد الزيارة القادمة"""
    if not visit_intervals or not last_visit:
        return None
    
    if len(visit_intervals) >= 2:
        avg_interval = mean(visit_intervals)
        next_visit = last_visit + timedelta(days=int(avg_interval))
        return next_visit, int(avg_interval)
    
    return None

def classify_patient_risk(reports_count, visit_intervals, departments_visited):
    """تصنيف خطورة حالة المريض"""
    risk_score = 0
    
    # عدد التقارير
    if reports_count >= 20:
        risk_score += 3
    elif reports_count >= 10:
        risk_score += 2
    elif reports_count >= 5:
        risk_score += 1
    
    # تكرار الزيارات
    if visit_intervals:
        avg_interval = mean(visit_intervals)
        if avg_interval < 7:  # أسبوع
            risk_score += 3
        elif avg_interval < 30:  # شهر
            risk_score += 2
        elif avg_interval < 90:  # 3 أشهر
            risk_score += 1
    
    # تنوع الأقسام
    dept_count = len(departments_visited)
    if dept_count >= 5:
        risk_score += 2
    elif dept_count >= 3:
        risk_score += 1
    
    # التصنيف
    if risk_score >= 6:
        return "🔴 عالي الخطورة", "يحتاج متابعة عاجلة ومستمرة"
    elif risk_score >= 3:
        return "🟡 متوسط الخطورة", "يحتاج متابعة دورية"
    else:
        return "🟢 منخفض الخطورة", "حالة مستقرة"

def generate_patient_ai_insights(reports, visit_intervals, departments_visited, 
                                 actions_done, complaints_keywords, last_visit):
    """توليد رؤى ذكاء اصطناعي للمريض"""
    insights = []
    
    # 1. التنبؤ بالزيارة القادمة
    next_visit_prediction = predict_next_visit(visit_intervals, last_visit)
    if next_visit_prediction:
        next_date, avg_days = next_visit_prediction
        insights.append(f"📅 **الزيارة المتوقعة القادمة:** {next_date.strftime('%Y-%m-%d')} (بعد ~{avg_days} يوم)")
    
    # 2. تصنيف الخطورة
    risk_level, risk_msg = classify_patient_risk(len(reports), visit_intervals, departments_visited)
    insights.append(f"⚠️ **تصنيف الحالة:** {risk_level}")
    insights.append(f"   💡 {risk_msg}")
    
    # 3. تحليل الأنماط
    if len(reports) >= 3:
        # متوسط الزيارات شهرياً
        if visit_intervals:
            avg_interval = mean(visit_intervals)
            visits_per_month = 30 / avg_interval if avg_interval > 0 else 0
            insights.append(f"📊 **معدل الزيارات:** {visits_per_month:.1f} زيارة/شهر")
    
    # 4. القسم الأكثر زيارة
    if departments_visited:
        most_dept = max(departments_visited.items(), key=lambda x: x[1])
        total_visits = sum(departments_visited.values())
        percentage = (most_dept[1] / total_visits) * 100
        insights.append(f"🎯 **القسم المفضل:** {most_dept[0]} ({percentage:.0f}% من الزيارات)")
    
    # 5. الإجراء الأكثر شيوعاً
    if actions_done:
        most_action = max(actions_done.items(), key=lambda x: x[1])
        total_actions = sum(actions_done.values())
        percentage = (most_action[1] / total_actions) * 100
        insights.append(f"💊 **الإجراء الأكثر شيوعاً:** {most_action[0]} ({percentage:.0f}%)")
    
    # 6. الكلمات المفتاحية في الشكاوى
    if complaints_keywords:
        keyword_counter = Counter(complaints_keywords)
        top_keywords = keyword_counter.most_common(3)
        if top_keywords:
            keywords_str = "، ".join([f"{kw[0]} ({kw[1]})" for kw in top_keywords])
            insights.append(f"🔍 **الأعراض الأكثر تكراراً:** {keywords_str}")
    
    # 7. توصيات ذكية
    recommendations = []
    
    if len(reports) >= 10 and visit_intervals:
        avg_interval = mean(visit_intervals)
        if avg_interval < 14:
            recommendations.append("⚠️ زيارات متكررة - يُنصح بفحص شامل")
    
    if len(departments_visited) >= 4:
        recommendations.append("⚠️ زيارة لأقسام متعددة - قد يحتاج تشخيص متخصص")
    
    if len(actions_done) >= 1:
        if 'عملية' in str(actions_done.keys()).lower() or 'جراحة' in str(actions_done.keys()).lower():
            recommendations.append("💡 خضع لعمليات - يحتاج متابعة ما بعد الجراحة")
    
    if recommendations:
        insights.append(f"\n💡 **التوصيات الذكية:**")
        for rec in recommendations:
            insights.append(f"   {rec}")
    
    return insights

def generate_hospital_ai_insights(reports, departments_used, actions_done, monthly_reports):
    """توليد رؤى ذكاء اصطناعي للمستشفى"""
    insights = []
    
    total_reports = len(reports)
    
    # 1. القسم الأكثر ازدحاماً
    if departments_used:
        busiest_dept = max(departments_used.items(), key=lambda x: x[1])
        percentage = (busiest_dept[1] / total_reports) * 100
        insights.append(f"🏆 **القسم الأكثر ازدحاماً:** {busiest_dept[0]} ({percentage:.1f}%)")
        
        if percentage > 40:
            insights.append(f"   ⚠️ قد يحتاج دعم إضافي (نسبة عالية)")
    
    # 2. الإجراء الأكثر شيوعاً
    if actions_done:
        most_action = max(actions_done.items(), key=lambda x: x[1])
        percentage = (most_action[1] / total_reports) * 100
        insights.append(f"💊 **الإجراء المهيمن:** {most_action[0]} ({percentage:.1f}%)")
    
    # 3. التوزيع الزمني
    if monthly_reports:
        sorted_months = sorted(monthly_reports.items(), key=lambda x: x[1], reverse=True)
        busiest_month = sorted_months[0]
        slowest_month = sorted_months[-1]
        
        insights.append(f"📈 **الشهر الأكثر نشاطاً:** {busiest_month[0]} ({busiest_month[1]} تقرير)")
        insights.append(f"📉 **الشهر الأقل نشاطاً:** {slowest_month[0]} ({slowest_month[1]} تقرير)")
        
        # حساب التباين
        values = list(monthly_reports.values())
        if len(values) >= 2:
            avg = mean(values)
            variation = (max(values) - min(values)) / avg * 100 if avg > 0 else 0
            if variation > 50:
                insights.append(f"   ⚠️ تباين عالي في الأحمال ({variation:.0f}%) - يحتاج تخطيط أفضل")
    
    # 4. التنبؤ بالحمل المستقبلي
    if monthly_reports and len(monthly_reports) >= 3:
        recent_months = sorted(monthly_reports.items())[-3:]
        trend = [count for _, count in recent_months]
        
        if len(trend) >= 3:
            if trend[2] > trend[1] > trend[0]:
                insights.append(f"📈 **اتجاه:** تزايد مستمر - توقع زيادة الحمل")
            elif trend[2] < trend[1] < trend[0]:
                insights.append(f"📉 **اتجاه:** تناقص مستمر - توقع انخفاض الحمل")
            else:
                avg_recent = mean(trend)
                insights.append(f"📊 **التوقع للشهر القادم:** ~{int(avg_recent)} تقرير")
    
    # 5. توصيات
    recommendations = []
    
    if departments_used and len(departments_used) >= 1:
        top_dept_percentage = (max(departments_used.values()) / total_reports) * 100
        if top_dept_percentage > 50:
            recommendations.append("💡 قسم واحد يستحوذ على أكثر من 50% - قد يحتاج توسعة")
    
    if visit_intervals := []:  # ستحسب لاحقاً إن لزم
        pass
    
    if recommendations:
        insights.append(f"\n💡 **التوصيات:**")
        for rec in recommendations:
            insights.append(f"   {rec}")
    
    return insights

def generate_system_ai_insights(reports, total_patients, total_hospitals, 
                                total_departments, total_doctors, top_patients, top_hospitals, top_depts):
    """توليد رؤى ذكاء اصطناعي للنظام الشامل"""
    insights = []
    
    total_reports = len(reports)
    
    # 1. تحليل الحمل على النظام
    if total_reports >= 100:
        load_level = "عالي" if total_reports >= 500 else "متوسط"
        insights.append(f"📊 **حمل النظام:** {load_level} ({total_reports} تقرير)")
    
    # 2. تركيز المرضى (هل هناك مرضى يستحوذون على نسبة كبيرة؟)
    if top_patients and total_reports > 0:
        top_5_total = sum(count for _, count in top_patients)
        concentration = (top_5_total / total_reports) * 100
        insights.append(f"👥 **تركيز المرضى:** أعلى 5 مرضى = {concentration:.1f}% من التقارير")
        
        if concentration > 30:
            insights.append(f"   ⚠️ تركيز عالي - قد يحتاج برنامج متابعة خاص")
    
    # 3. توزيع الحمل على المستشفيات
    if top_hospitals and total_reports > 0:
        top_hospital_count = top_hospitals[0][1] if top_hospitals else 0
        percentage = (top_hospital_count / total_reports) * 100
        insights.append(f"🏥 **توازن المستشفيات:** المستشفى الأكثر نشاطاً = {percentage:.1f}%")
        
        if percentage > 50:
            insights.append(f"   ⚠️ مستشفى واحدة تستحوذ على {percentage:.0f}% - يحتاج توزيع أفضل")
        elif percentage < 30:
            insights.append(f"   ✅ توزيع متوازن بين المستشفيات")
    
    # 4. تحليل الاتجاه الزمني
    if reports:
        # تجميع التقارير حسب الأشهر
        monthly_counts = defaultdict(int)
        for r in reports:
            if r.report_date:
                month_key = r.report_date.strftime("%Y-%m")
                monthly_counts[month_key] += 1
        
        if len(monthly_counts) >= 3:
            recent_months = sorted(monthly_counts.items())[-3:]
            trend = [count for _, count in recent_months]
            
            if trend[2] > trend[1] > trend[0]:
                growth_rate = ((trend[2] - trend[0]) / trend[0] * 100) if trend[0] > 0 else 0
                insights.append(f"📈 **الاتجاه:** تزايد مستمر (+{growth_rate:.0f}% في 3 أشهر)")
                insights.append(f"   💡 توقع استمرار الزيادة - جهّز الموارد")
            elif trend[2] < trend[1] < trend[0]:
                decline_rate = ((trend[0] - trend[2]) / trend[0] * 100) if trend[0] > 0 else 0
                insights.append(f"📉 **الاتجاه:** تناقص مستمر (-{decline_rate:.0f}% في 3 أشهر)")
            else:
                insights.append(f"📊 **الاتجاه:** مستقر نسبياً")
    
    # 5. كفاءة استخدام الموارد
    if total_patients > 0 and total_doctors > 0:
        patients_per_doctor = total_patients / total_doctors
        if patients_per_doctor > 50:
            insights.append(f"👨‍⚕️ **الأطباء:** محمّلون ({patients_per_doctor:.0f} مريض/طبيب)")
            insights.append(f"   💡 قد تحتاج توظيف أطباء إضافيين")
        elif patients_per_doctor < 10:
            insights.append(f"👨‍⚕️ **الأطباء:** استخدام منخفض ({patients_per_doctor:.0f} مريض/طبيب)")
        else:
            insights.append(f"👨‍⚕️ **الأطباء:** معدل متوازن ({patients_per_doctor:.0f} مريض/طبيب)")
    
    # 6. تنوع الخدمات
    unique_depts = total_departments
    if unique_depts >= 10:
        insights.append(f"🩺 **تنوع الخدمات:** ممتاز ({unique_depts} قسم)")
    elif unique_depts >= 5:
        insights.append(f"🩺 **تنوع الخدمات:** جيد ({unique_depts} قسم)")
    else:
        insights.append(f"🩺 **تنوع الخدمات:** محدود ({unique_depts} قسم)")
        insights.append(f"   💡 قد تحتاج توسعة الأقسام")
    
    # 7. التوصيات الاستراتيجية
    recommendations = []
    
    if total_reports >= 1000:
        recommendations.append("📚 قاعدة بيانات كبيرة - يُنصح بالنسخ الاحتياطي الدوري")
    
    if top_depts:
        top_dept_percentage = (top_depts[0][1] / total_reports * 100) if total_reports > 0 else 0
        if top_dept_percentage > 40:
            recommendations.append(f"⚠️ قسم {top_depts[0][0]} مزدحم - قد يحتاج تعزيز")
    
    if recommendations:
        insights.append(f"\n💡 **التوصيات الاستراتيجية:**")
        for rec in recommendations:
            insights.append(f"   {rec}")
    
    return insights

# =============================
# 📊 دوال إنشاء الرسوم البيانية
# =============================

def format_arabic_text(text):
    """تنسيق النص العربي للرسوم البيانية"""
    if not text:
        return ""
    reshaped_text = arabic_reshaper.reshape(text)
    return get_display(reshaped_text)

def create_analysis_charts(analysis_type, data_dict):
    """إنشاء رسوم بيانية للتحليل"""
    charts = {}
    
    # إعدادات matplotlib للعربية
    plt.rcParams['font.family'] = ['Arial', 'DejaVu Sans', 'sans-serif']
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['font.size'] = 11
    
    if not data_dict:
        return charts
    
    try:
        # 1. رسم دائري للتوزيع (Pie Chart)
        if len(data_dict) > 1 and len(data_dict) <= 7:
            fig, ax = plt.subplots(figsize=(10, 8))
            labels = [format_arabic_text(k) for k in data_dict.keys()]
            values = list(data_dict.values())
            colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#C9CBCF']
            
            def make_autopct(values):
                def my_autopct(pct):
                    total = sum(values)
                    val = int(round(pct*total/100.0))
                    return f'{val}\n({pct:.1f}%)'
                return my_autopct
            
            wedges, texts, autotexts = ax.pie(
                values, 
                labels=labels, 
                autopct=make_autopct(values),
                startangle=90,
                colors=colors[:len(labels)],
                textprops={'fontsize': 10, 'weight': 'bold'}
            )
            
            ax.set_title(format_arabic_text(f'التوزيع - {analysis_type}'), 
                        pad=20, fontsize=16, fontweight='bold')
            
            buf = io.BytesIO()
            plt.tight_layout()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            charts['pie_chart'] = base64.b64encode(buf.read()).decode()
            plt.close()
        
        # 2. رسم بالأعمدة الأفقية (Horizontal Bar Chart)
        if len(data_dict) >= 2:
            fig, ax = plt.subplots(figsize=(12, max(6, len(data_dict) * 0.5)))
            sorted_items = sorted(data_dict.items(), key=lambda x: x[1], reverse=True)[:15]
            labels = [format_arabic_text(k) for k, _ in sorted_items]
            values = [v for _, v in sorted_items]
            
            colors = ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#00f2fe']
            bars = ax.barh(range(len(labels)), values, color=colors[0], height=0.6)
            
            # إضافة الأرقام على الأعمدة
            for i, (bar, value) in enumerate(zip(bars, values)):
                ax.text(value + max(values)*0.02, i, f'{value}', 
                       va='center', fontsize=11, fontweight='bold', color='#2c3e50')
            
            ax.set_yticks(range(len(labels)))
            ax.set_yticklabels(labels, fontsize=11)
            ax.set_xlabel(format_arabic_text('العدد'), fontsize=13, fontweight='bold')
            ax.set_title(format_arabic_text(f'التوزيع التفصيلي - {analysis_type}'), 
                        pad=20, fontsize=16, fontweight='bold')
            ax.grid(axis='x', alpha=0.3)
            ax.invert_yaxis()
            
            buf = io.BytesIO()
            plt.tight_layout()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            charts['bar_chart'] = base64.b64encode(buf.read()).decode()
            plt.close()
            
    except Exception as e:
        print(f"خطأ في إنشاء الرسوم: {e}")
    
    return charts

def _main_menu_kb():
    """القائمة الرئيسية لتحليل البيانات"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 تحليل المرضى", callback_data="analysis:patients")],
        [InlineKeyboardButton("🏥 تحليل المستشفيات", callback_data="analysis:hospitals")],
        [InlineKeyboardButton("🩺 تحليل الأقسام", callback_data="analysis:departments")],
        [InlineKeyboardButton("👨‍⚕️ تحليل المترجمين", callback_data="analysis:translators")],
        [InlineKeyboardButton("📊 تحليل شامل للنظام", callback_data="analysis:system")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="abort")],
    ])

def _date_filter_kb():
    """لوحة اختيار فلتر التاريخ"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 اليوم", callback_data="date:today")],
        [InlineKeyboardButton("📅 آخر 3 أيام", callback_data="date:3days")],
        [InlineKeyboardButton("📅 آخر أسبوع", callback_data="date:week")],
        [InlineKeyboardButton("📅 آخر شهر", callback_data="date:month")],
        [InlineKeyboardButton("📅 آخر 3 أشهر", callback_data="date:3months")],
        [InlineKeyboardButton("📅 كل الفترة", callback_data="date:all")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back:main"), InlineKeyboardButton("❌ إلغاء", callback_data="abort")],
    ])

def get_date_range(filter_type):
    """حساب نطاق التاريخ حسب نوع الفلتر - من 2025 فصاعداً"""
    now = datetime.now()
    
    if filter_type == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_date, now, "اليوم"
    elif filter_type == "3days":
        start_date = now - timedelta(days=3)
        return start_date, now, "آخر 3 أيام"
    elif filter_type == "week":
        start_date = now - timedelta(days=7)
        return start_date, now, "آخر أسبوع"
    elif filter_type == "month":
        start_date = now - timedelta(days=30)
        return start_date, now, "آخر شهر"
    elif filter_type == "3months":
        start_date = now - timedelta(days=90)
        return start_date, now, "آخر 3 أشهر"
    else:  # all - ✅ من 2025 فصاعداً
        start_date = datetime(2025, 1, 1)  # بداية من 1 يناير 2025
        return start_date, now, "كل الفترة (من 2025)"

def apply_date_filter(query, start_date, end_date):
    """تطبيق فلتر التاريخ على query - من 2025 فصاعداً"""
    if start_date and end_date:
        return query.filter(Report.report_date >= start_date, Report.report_date <= end_date)
    else:
        # ✅ إذا لم يكن هناك فلتر - من 2025 فصاعداً
        default_start = datetime(2025, 1, 1)
        return query.filter(Report.report_date >= default_start)
    return query

def _export_format_kb(analysis_id=None):
    """اختيار صيغة التصدير للتحليلات"""
    buttons = []
    if analysis_id:
        buttons.append([InlineKeyboardButton("📕 تصدير PDF", callback_data=f"export_analysis:pdf:{analysis_id}")])
        buttons.append([InlineKeyboardButton("📗 تصدير Excel", callback_data=f"export_analysis:excel:{analysis_id}")])
    buttons.append([InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back:main")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="abort")])
    return InlineKeyboardMarkup(buttons)

def _back_kb(show_export=False, analysis_id=None):
    """زر رجوع مع خيار تصدير"""
    if show_export and analysis_id:
        return _export_format_kb(analysis_id)
    
    buttons = []
    buttons.append([InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back:main")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data="abort")])
    return InlineKeyboardMarkup(buttons)

async def start_data_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء تحليل البيانات"""
    user = update.effective_user
    if not is_admin(user.id):
        return ConversationHandler.END
    
    context.user_data.clear()
    await update.message.reply_text(
        "📊 **نظام تحليل البيانات الشامل**\n\n"
        "اختر نوع التحليل الذي تريده:",
        reply_markup=_main_menu_kb()
    )
    return SELECT_ANALYSIS_TYPE

async def handle_analysis_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار نوع التحليل"""
    query = update.callback_query
    await query.answer()
    
    analysis_type = query.data.split(":")[1]
    context.user_data["analysis_type"] = analysis_type
    
    # طلب اختيار فلتر التاريخ أولاً
    await query.edit_message_text(
        "📅 **اختر الفترة الزمنية للتحليل:**\n\n"
        "اختر الفترة التي تريد تحليل البيانات فيها:",
        reply_markup=_date_filter_kb()
    )
    return SELECT_DATE_FILTER

async def handle_date_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار فلتر التاريخ"""
    query = update.callback_query
    await query.answer()
    
    date_filter = query.data.split(":")[1]
    start_date, end_date, period_name = get_date_range(date_filter)
    
    context.user_data["date_filter"] = date_filter
    context.user_data["start_date"] = start_date
    context.user_data["end_date"] = end_date
    context.user_data["period_name"] = period_name
    
    analysis_type = context.user_data.get("analysis_type")
    
    if analysis_type == "system":
        # تحليل شامل للنظام بالكامل
        await show_system_analysis(query, context)
        return ConversationHandler.END
    
    # عرض قائمة الكيانات للتحليل
    await show_entity_list(query, context, analysis_type)
    return SELECT_ENTITY

async def show_entity_list(query, context, analysis_type):
    """عرض قائمة الكيانات (مرضى/مستشفيات/أقسام/مترجمين)"""
    with SessionLocal() as s:
        if analysis_type == "patients":
            # ✅ استخدام البحث الفوري Inline Query للمرضى
            context.user_data["mode"] = "analyze_patient"  # تحديد وضع التحليل
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "🔍 ابحث عن المريض", 
                    switch_inline_query_current_chat=""
                )],
                [InlineKeyboardButton("🔙 رجوع", callback_data="back:main")],
                [InlineKeyboardButton("❌ إلغاء", callback_data="abort")]
            ])
            
            await query.edit_message_text(
                "👤 **تحليل بيانات مريض محدد**\n\n"
                "🔍 اضغط الزر أدناه ثم ابحث عن المريض:\n\n"
                "💡 ستظهر لك اقتراحات فورية أثناء الكتابة",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            return  # الخروج من الدالة
        
        elif analysis_type == "hospitals":
            entities = s.query(Hospital).all()
            title = "🏥 اختر مستشفى للتحليل:"
            items = [(h.id, h.name) for h in entities if h.name]
            callback_prefix = "hospital"
        
        elif analysis_type == "departments":
            entities = s.query(Department).all()
            title = "🩺 اختر قسم للتحليل:"
            items = [(d.id, d.name) for d in entities if d.name]
            callback_prefix = "dept"
        
        elif analysis_type == "translators":
            entities = s.query(Translator).all()
            title = "👨‍⚕️ اختر مترجم للتحليل:"
            items = [(t.id, t.full_name) for t in entities if t.full_name]
            callback_prefix = "trans"
        
        else:
            await query.edit_message_text("❌ نوع تحليل غير صحيح")
            return ConversationHandler.END
        
        if not items:
            await query.edit_message_text(
                f"⚠️ لا توجد بيانات متاحة للتحليل\n\n{title}",
                reply_markup=_back_kb()
            )
            return SELECT_ANALYSIS_TYPE
        
        # بناء لوحة المفاتيح
        keyboard = []
        for entity_id, name in sorted(items, key=lambda x: x[1])[:20]:  # أول 20
            keyboard.append([InlineKeyboardButton(
                f"📊 {name}", 
                callback_data=f"{callback_prefix}:{entity_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back:main")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="abort")])
        
        await query.edit_message_text(
            f"{title}\n\n"
            f"📈 عدد العناصر المتاحة: {len(items)}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_entity_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار الكيان للتحليل"""
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split(":")
    entity_type = data_parts[0]
    entity_id = int(data_parts[1])
    
    # تحليل البيانات حسب النوع
    if entity_type == "patient":
        await analyze_patient(query, context, entity_id)
    elif entity_type == "hospital":
        await analyze_hospital(query, context, entity_id)
    elif entity_type == "dept":
        await analyze_department(query, context, entity_id)
    elif entity_type == "trans":
        await analyze_translator(query, context, entity_id)
    
    return SHOW_ANALYSIS

async def analyze_patient(query, context, patient_id):
    """تحليل شامل لمريض محدد مع ذكاء اصطناعي"""
    with SessionLocal() as s:
        patient = s.get(Patient, patient_id)
        if not patient:
            await query.edit_message_text("❌ المريض غير موجود", reply_markup=_back_kb())
            return
        
        # جلب تقارير المريض مع تطبيق فلتر التاريخ
        start_date = context.user_data.get("start_date")
        end_date = context.user_data.get("end_date")
        period_name = context.user_data.get("period_name", "كل الفترة")
        
        reports_query = s.query(Report).filter_by(patient_id=patient_id)
        reports_query = apply_date_filter(reports_query, start_date, end_date)
        reports = reports_query.order_by(Report.report_date).all()
        
        if not reports:
            await query.edit_message_text(
                f"👤 **{patient.full_name}**\n\n"
                f"⚠️ لا توجد تقارير لهذا المريض",
                reply_markup=_back_kb()
            )
            return
        
        # تحليل البيانات
        hospitals_visited = defaultdict(int)
        departments_visited = defaultdict(int)
        actions_done = defaultdict(int)
        doctors_seen = defaultdict(int)
        complaints_keywords = []
        visit_intervals = []
        
        first_visit = None
        last_visit = None
        previous_visit = None
        
        for r in reports:
            if r.report_date:
                if not first_visit or r.report_date < first_visit:
                    first_visit = r.report_date
                if not last_visit or r.report_date > last_visit:
                    last_visit = r.report_date
                
                # حساب الفترات بين الزيارات
                if previous_visit:
                    interval = (r.report_date - previous_visit).days
                    if interval > 0:
                        visit_intervals.append(interval)
                previous_visit = r.report_date
            
            if r.hospital_id:
                h = s.get(Hospital, r.hospital_id)
                if h:
                    hospitals_visited[h.name] += 1
            
            if r.department_id:
                d = s.get(Department, r.department_id)
                if d:
                    departments_visited[d.name] += 1
            
            if r.medical_action:
                actions_done[r.medical_action] += 1
            
            if r.doctor_id:
                doc = s.get(Doctor, r.doctor_id)
                if doc:
                    doctors_seen[doc.full_name] += 1
            
            # جمع كلمات مفتاحية من الشكاوى
            if r.complaint_text:
                complaints_keywords.extend(extract_keywords(r.complaint_text))
        
        # 🤖 تحليل ذكاء اصطناعي
        ai_insights = generate_patient_ai_insights(
            reports, visit_intervals, departments_visited, 
            actions_done, complaints_keywords, last_visit
        )
        
        # بناء الرسالة
        msg = f"📊 **تحليل شامل للمريض مع الذكاء الاصطناعي**\n"
        msg += f"{'═' * 30}\n\n"
        msg += f"📅 **الفترة الزمنية:** {period_name}\n\n"
        msg += f"👤 **الاسم:** {patient.full_name}\n"
        msg += f"🆔 **رقم المريض:** {patient.id}\n"
        msg += f"📄 **إجمالي التقارير:** {len(reports)}\n\n"
        
        if first_visit:
            msg += f"📅 **أول زيارة:** {first_visit.strftime('%Y-%m-%d')}\n"
        if last_visit:
            msg += f"📅 **آخر زيارة:** {last_visit.strftime('%Y-%m-%d')}\n"
        
        if first_visit and last_visit:
            duration = (last_visit - first_visit).days
            msg += f"⏱️ **فترة المتابعة:** {duration} يوم\n\n"
        
        # 🤖 قسم الذكاء الاصطناعي
        if ai_insights:
            msg += f"🤖 **تحليل الذكاء الاصطناعي:**\n"
            msg += f"{'-' * 30}\n"
            for insight in ai_insights:
                msg += f"{insight}\n"
            msg += f"\n"
        
        # المستشفيات
        if hospitals_visited:
            msg += f"🏥 **المستشفيات ({len(hospitals_visited)}):**\n"
            for hospital, count in sorted(hospitals_visited.items(), key=lambda x: x[1], reverse=True):
                msg += f"   • {hospital}: {count} زيارة\n"
            msg += "\n"
        
        # الأقسام
        if departments_visited:
            msg += f"🩺 **الأقسام ({len(departments_visited)}):**\n"
            for dept, count in sorted(departments_visited.items(), key=lambda x: x[1], reverse=True)[:5]:
                msg += f"   • {dept}: {count} مرة\n"
            if len(departments_visited) > 5:
                msg += f"   • ... و{len(departments_visited) - 5} أقسام أخرى\n"
            msg += "\n"
        
        # الإجراءات
        if actions_done:
            msg += f"💊 **الإجراءات الطبية ({len(actions_done)}):**\n"
            for action, count in sorted(actions_done.items(), key=lambda x: x[1], reverse=True)[:5]:
                msg += f"   • {action}: {count} مرة\n"
            if len(actions_done) > 5:
                msg += f"   • ... و{len(actions_done) - 5} إجراءات أخرى\n"
            msg += "\n"
        
        # الأطباء
        if doctors_seen:
            msg += f"👨‍⚕️ **الأطباء ({len(doctors_seen)}):**\n"
            for doctor, count in sorted(doctors_seen.items(), key=lambda x: x[1], reverse=True)[:5]:
                msg += f"   • {doctor}: {count} مرة\n"
            if len(doctors_seen) > 5:
                msg += f"   • ... و{len(doctors_seen) - 5} أطباء آخرين\n"
        
        # حفظ البيانات للتصدير - أولوية للمستشفيات ثم الأقسام ثم الإجراءات
        chart_data = {}
        chart_title = ""
        if len(hospitals_visited) > 1:
            chart_data = dict(hospitals_visited)
            chart_title = "المستشفيات التي زارها المريض"
        elif len(departments_visited) > 1:
            chart_data = dict(departments_visited)
            chart_title = "الأقسام التي زارها المريض"
        elif len(actions_done) > 1:
            chart_data = dict(actions_done)
            chart_title = "الإجراءات الطبية للمريض"
        
        context.user_data['last_analysis'] = {
            'text': msg,
            'type': 'تحليل مريض محدد',
            'id': patient_id,
            'charts_data': chart_data,
            'chart_title': chart_title
        }
        
        await query.edit_message_text(msg, reply_markup=_back_kb(show_export=True, analysis_id=f"patient_{patient_id}"))

async def analyze_hospital(query, context, hospital_id):
    """تحليل شامل لمستشفى محدد مع ذكاء اصطناعي"""
    with SessionLocal() as s:
        hospital = s.get(Hospital, hospital_id)
        if not hospital:
            await query.edit_message_text("❌ المستشفى غير موجود", reply_markup=_back_kb())
            return
        
        # جلب تقارير المستشفى مع تطبيق فلتر التاريخ
        start_date = context.user_data.get("start_date")
        end_date = context.user_data.get("end_date")
        period_name = context.user_data.get("period_name", "كل الفترة")
        
        reports_query = s.query(Report).filter_by(hospital_id=hospital_id)
        reports_query = apply_date_filter(reports_query, start_date, end_date)
        reports = reports_query.order_by(Report.report_date).all()
        
        if not reports:
            await query.edit_message_text(
                f"🏥 **{hospital.name}**\n\n"
                f"⚠️ لا توجد تقارير لهذا المستشفى",
                reply_markup=_back_kb()
            )
            return
        
        # تحليل البيانات
        patients_count = len(set(r.patient_id for r in reports if r.patient_id))
        departments_used = defaultdict(int)
        actions_done = defaultdict(int)
        doctors_worked = defaultdict(int)
        translators_worked = defaultdict(int)
        monthly_reports = defaultdict(int)
        
        for r in reports:
            if r.department_id:
                d = s.get(Department, r.department_id)
                if d:
                    departments_used[d.name] += 1
            
            if r.medical_action:
                actions_done[r.medical_action] += 1
            
            if r.doctor_id:
                doc = s.get(Doctor, r.doctor_id)
                if doc:
                    doctors_worked[doc.full_name] += 1
            
            if r.translator_id:
                trans = s.get(Translator, r.translator_id)
                if trans:
                    translators_worked[trans.full_name] += 1
            
            if r.report_date:
                month_key = r.report_date.strftime("%Y-%m")
                monthly_reports[month_key] += 1
        
        # 🤖 تحليل ذكاء اصطناعي للمستشفى
        ai_insights = generate_hospital_ai_insights(
            reports, departments_used, actions_done, monthly_reports
        )
        
        # بناء الرسالة
        msg = f"📊 **تحليل شامل للمستشفى مع AI**\n"
        msg += f"{'═' * 30}\n\n"
        msg += f"📅 **الفترة الزمنية:** {period_name}\n\n"
        msg += f"🏥 **المستشفى:** {hospital.name}\n"
        msg += f"🆔 **الرقم:** {hospital.id}\n"
        msg += f"📄 **إجمالي التقارير:** {len(reports)}\n"
        msg += f"👥 **عدد المرضى:** {patients_count}\n"
        msg += f"📊 **معدل التقارير/مريض:** {len(reports)/patients_count:.1f}\n\n"
        
        # 🤖 قسم الذكاء الاصطناعي
        if ai_insights:
            msg += f"🤖 **رؤى الذكاء الاصطناعي:**\n"
            msg += f"{'-' * 30}\n"
            for insight in ai_insights:
                msg += f"{insight}\n"
            msg += f"\n"
        
        # الأقسام الأكثر نشاطاً
        if departments_used:
            msg += f"🩺 **الأقسام الأكثر نشاطاً ({len(departments_used)}):**\n"
            for dept, count in sorted(departments_used.items(), key=lambda x: x[1], reverse=True)[:5]:
                percentage = (count / len(reports)) * 100
                msg += f"   • {dept}: {count} ({percentage:.1f}%)\n"
            if len(departments_used) > 5:
                msg += f"   • ... و{len(departments_used) - 5} أقسام أخرى\n"
            msg += "\n"
        
        # الإجراءات الأكثر شيوعاً
        if actions_done:
            msg += f"💊 **الإجراءات الأكثر شيوعاً ({len(actions_done)}):**\n"
            for action, count in sorted(actions_done.items(), key=lambda x: x[1], reverse=True)[:5]:
                percentage = (count / len(reports)) * 100
                msg += f"   • {action}: {count} ({percentage:.1f}%)\n"
            if len(actions_done) > 5:
                msg += f"   • ... و{len(actions_done) - 5} إجراءات أخرى\n"
            msg += "\n"
        
        # الأطباء
        if doctors_worked:
            msg += f"👨‍⚕️ **الأطباء ({len(doctors_worked)}):**\n"
            for doctor, count in sorted(doctors_worked.items(), key=lambda x: x[1], reverse=True)[:5]:
                msg += f"   • {doctor}: {count} تقرير\n"
            if len(doctors_worked) > 5:
                msg += f"   • ... و{len(doctors_worked) - 5} أطباء آخرين\n"
            msg += "\n"
        
        # المترجمين
        if translators_worked:
            msg += f"🌐 **المترجمين ({len(translators_worked)}):**\n"
            for trans, count in sorted(translators_worked.items(), key=lambda x: x[1], reverse=True)[:5]:
                msg += f"   • {trans}: {count} تقرير\n"
            if len(translators_worked) > 5:
                msg += f"   • ... و{len(translators_worked) - 5} مترجمين آخرين\n"
            msg += "\n"
        
        # التوزيع الشهري
        if monthly_reports:
            msg += f"📅 **التوزيع الزمني:**\n"
            sorted_months = sorted(monthly_reports.items(), reverse=True)[:6]
            for month, count in sorted_months:
                msg += f"   • {month}: {count} تقرير\n"
        
        # حفظ البيانات للتصدير - أولوية للأقسام ثم الإجراءات
        chart_data = {}
        chart_title = ""
        if len(departments_used) > 1:
            chart_data = dict(departments_used)
            chart_title = "الأقسام في المستشفى"
        elif len(actions_done) > 1:
            chart_data = dict(actions_done)
            chart_title = "الإجراءات الطبية في المستشفى"
        
        context.user_data['last_analysis'] = {
            'text': msg,
            'type': 'تحليل مستشفى محدد',
            'id': hospital_id,
            'charts_data': chart_data,
            'chart_title': chart_title
        }
        
        await query.edit_message_text(msg, reply_markup=_back_kb(show_export=True, analysis_id=f"hospital_{hospital_id}"))

async def analyze_department(query, context, dept_id):
    """تحليل شامل لقسم محدد"""
    with SessionLocal() as s:
        department = s.get(Department, dept_id)
        if not department:
            await query.edit_message_text("❌ القسم غير موجود", reply_markup=_back_kb())
            return
        
        # جلب تقارير القسم مع تطبيق فلتر التاريخ
        start_date = context.user_data.get("start_date")
        end_date = context.user_data.get("end_date")
        period_name = context.user_data.get("period_name", "كل الفترة")
        
        reports_query = s.query(Report).filter_by(department_id=dept_id)
        reports_query = apply_date_filter(reports_query, start_date, end_date)
        reports = reports_query.all()
        
        if not reports:
            await query.edit_message_text(
                f"🩺 **{department.name}**\n\n"
                f"⚠️ لا توجد تقارير لهذا القسم",
                reply_markup=_back_kb()
            )
            return
        
        # تحليل البيانات
        patients_count = len(set(r.patient_id for r in reports if r.patient_id))
        hospitals_used = defaultdict(int)
        actions_done = defaultdict(int)
        doctors_worked = defaultdict(int)
        translators_worked = defaultdict(int)
        
        for r in reports:
            if r.hospital_id:
                h = s.get(Hospital, r.hospital_id)
                if h:
                    hospitals_used[h.name] += 1
            
            if r.medical_action:
                actions_done[r.medical_action] += 1
            
            if r.doctor_id:
                doc = s.get(Doctor, r.doctor_id)
                if doc:
                    doctors_worked[doc.full_name] += 1
            
            if r.translator_id:
                trans = s.get(Translator, r.translator_id)
                if trans:
                    translators_worked[trans.full_name] += 1
        
        # بناء الرسالة
        msg = f"📊 **تحليل شامل للقسم**\n"
        msg += f"{'═' * 30}\n\n"
        msg += f"📅 **الفترة الزمنية:** {period_name}\n\n"
        msg += f"🩺 **القسم:** {department.name}\n"
        msg += f"🆔 **الرقم:** {department.id}\n"
        msg += f"📄 **إجمالي التقارير:** {len(reports)}\n"
        msg += f"👥 **عدد المرضى:** {patients_count}\n"
        msg += f"📊 **معدل التقارير/مريض:** {len(reports)/patients_count:.1f}\n\n"
        
        # المستشفيات
        if hospitals_used:
            msg += f"🏥 **المستشفيات ({len(hospitals_used)}):**\n"
            for hospital, count in sorted(hospitals_used.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / len(reports)) * 100
                msg += f"   • {hospital}: {count} ({percentage:.1f}%)\n"
            msg += "\n"
        
        # الإجراءات
        if actions_done:
            msg += f"💊 **الإجراءات الطبية ({len(actions_done)}):**\n"
            for action, count in sorted(actions_done.items(), key=lambda x: x[1], reverse=True)[:5]:
                percentage = (count / len(reports)) * 100
                msg += f"   • {action}: {count} ({percentage:.1f}%)\n"
            if len(actions_done) > 5:
                msg += f"   • ... و{len(actions_done) - 5} إجراءات أخرى\n"
            msg += "\n"
        
        # الأطباء
        if doctors_worked:
            msg += f"👨‍⚕️ **الأطباء الأكثر نشاطاً ({len(doctors_worked)}):**\n"
            for doctor, count in sorted(doctors_worked.items(), key=lambda x: x[1], reverse=True)[:5]:
                msg += f"   • {doctor}: {count} تقرير\n"
            if len(doctors_worked) > 5:
                msg += f"   • ... و{len(doctors_worked) - 5} أطباء آخرين\n"
        
        # حفظ البيانات للتصدير - أولوية للإجراءات ثم المستشفيات
        chart_data = {}
        chart_title = ""
        if len(actions_done) > 1:
            chart_data = dict(actions_done)
            chart_title = "الإجراءات الطبية في القسم"
        elif len(hospitals_used) > 1:
            chart_data = dict(hospitals_used)
            chart_title = "المستشفيات التي يعمل فيها القسم"
        
        context.user_data['last_analysis'] = {
            'text': msg,
            'type': 'تحليل قسم محدد',
            'id': dept_id,
            'charts_data': chart_data,
            'chart_title': chart_title
        }
        
        await query.edit_message_text(msg, reply_markup=_back_kb(show_export=True, analysis_id=f"dept_{dept_id}"))

async def analyze_translator(query, context, translator_id):
    """تحليل شامل لمترجم محدد"""
    with SessionLocal() as s:
        translator = s.get(Translator, translator_id)
        if not translator:
            await query.edit_message_text("❌ المترجم غير موجود", reply_markup=_back_kb())
            return
        
        # جلب تقارير المترجم مع تطبيق فلتر التاريخ
        start_date = context.user_data.get("start_date")
        end_date = context.user_data.get("end_date")
        period_name = context.user_data.get("period_name", "كل الفترة")
        
        reports_query = s.query(Report).filter_by(translator_id=translator_id)
        reports_query = apply_date_filter(reports_query, start_date, end_date)
        reports = reports_query.all()
        
        if not reports:
            await query.edit_message_text(
                f"👨‍⚕️ **{translator.full_name}**\n\n"
                f"⚠️ لا توجد تقارير لهذا المترجم",
                reply_markup=_back_kb()
            )
            return
        
        # تحليل البيانات
        patients_count = len(set(r.patient_id for r in reports if r.patient_id))
        hospitals_worked = defaultdict(int)
        departments_worked = defaultdict(int)
        actions_done = defaultdict(int)
        monthly_reports = defaultdict(int)
        
        for r in reports:
            if r.hospital_id:
                h = s.get(Hospital, r.hospital_id)
                if h:
                    hospitals_worked[h.name] += 1
            
            if r.department_id:
                d = s.get(Department, r.department_id)
                if d:
                    departments_worked[d.name] += 1
            
            if r.medical_action:
                actions_done[r.medical_action] += 1
            
            if r.report_date:
                month_key = r.report_date.strftime("%Y-%m")
                monthly_reports[month_key] += 1
        
        # بناء الرسالة
        msg = f"📊 **تحليل شامل للمترجم**\n"
        msg += f"{'═' * 30}\n\n"
        msg += f"📅 **الفترة الزمنية:** {period_name}\n\n"
        msg += f"👨‍⚕️ **المترجم:** {translator.full_name}\n"
        msg += f"🆔 **الرقم:** {translator.id}\n"
        msg += f"📄 **إجمالي التقارير:** {len(reports)}\n"
        msg += f"👥 **عدد المرضى:** {patients_count}\n"
        msg += f"📊 **معدل التقارير/مريض:** {len(reports)/patients_count:.1f}\n\n"
        
        # المستشفيات
        if hospitals_worked:
            msg += f"🏥 **المستشفيات ({len(hospitals_worked)}):**\n"
            for hospital, count in sorted(hospitals_worked.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / len(reports)) * 100
                msg += f"   • {hospital}: {count} ({percentage:.1f}%)\n"
            msg += "\n"
        
        # الأقسام
        if departments_worked:
            msg += f"🩺 **الأقسام ({len(departments_worked)}):**\n"
            for dept, count in sorted(departments_worked.items(), key=lambda x: x[1], reverse=True)[:5]:
                percentage = (count / len(reports)) * 100
                msg += f"   • {dept}: {count} ({percentage:.1f}%)\n"
            if len(departments_worked) > 5:
                msg += f"   • ... و{len(departments_worked) - 5} أقسام أخرى\n"
            msg += "\n"
        
        # الإجراءات
        if actions_done:
            msg += f"💊 **الإجراءات ({len(actions_done)}):**\n"
            for action, count in sorted(actions_done.items(), key=lambda x: x[1], reverse=True)[:5]:
                percentage = (count / len(reports)) * 100
                msg += f"   • {action}: {count} ({percentage:.1f}%)\n"
            if len(actions_done) > 5:
                msg += f"   • ... و{len(actions_done) - 5} إجراءات أخرى\n"
            msg += "\n"
        
        # التوزيع الشهري
        if monthly_reports:
            msg += f"📅 **أكثر الأشهر نشاطاً:**\n"
            sorted_months = sorted(monthly_reports.items(), key=lambda x: x[1], reverse=True)[:6]
            for month, count in sorted_months:
                msg += f"   • {month}: {count} تقرير\n"
        
        # حفظ البيانات للتصدير - أولوية للمستشفيات ثم الأقسام
        chart_data = {}
        chart_title = ""
        if len(hospitals_worked) > 1:
            chart_data = dict(hospitals_worked)
            chart_title = "المستشفيات التي عمل فيها المترجم"
        elif len(departments_worked) > 1:
            chart_data = dict(departments_worked)
            chart_title = "الأقسام التي عمل فيها المترجم"
        
        context.user_data['last_analysis'] = {
            'text': msg,
            'type': 'تحليل مترجم محدد',
            'id': translator_id,
            'charts_data': chart_data,
            'chart_title': chart_title
        }
        
        await query.edit_message_text(msg, reply_markup=_back_kb(show_export=True, analysis_id=f"trans_{translator_id}"))

async def show_system_analysis(query, context):
    """تحليل شامل للنظام بالكامل مع ذكاء اصطناعي"""
    start_date = context.user_data.get("start_date")
    end_date = context.user_data.get("end_date")
    period_name = context.user_data.get("period_name", "كل الفترة")
    
    loop = asyncio.get_running_loop()
    try:
        analysis_result = await loop.run_in_executor(
            None,
            _compute_system_analysis,
            start_date,
            end_date,
            period_name
        )
    except Exception as exc:
        import traceback
        traceback.print_exc()
        await query.edit_message_text(
            f"❌ **حدث خطأ أثناء تحليل النظام**\n\n{exc}",
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    context.user_data['last_analysis'] = analysis_result['last_analysis']
    await query.edit_message_text(
        analysis_result['message'],
        reply_markup=_back_kb(show_export=True, analysis_id="system_all")
    )


def _compute_system_analysis(start_date, end_date, period_name):
    """تشغيل تحليل النظام في خيط منفصل"""
    with SessionLocal() as s:
        reports_query = s.query(Report)
        reports_query = apply_date_filter(reports_query, start_date, end_date)
        total_reports = reports_query.count()
        
        total_patients = s.query(Patient).count()
        total_hospitals = s.query(Hospital).count()
        total_departments = s.query(Department).count()
        total_translators = s.query(Translator).count()
        total_doctors = s.query(Doctor).count()
        
        reports = reports_query.order_by(Report.report_date).all()
        
        # مجاميع متقدمة
        patient_visits = Counter(r.patient_id for r in reports if r.patient_id)
        hospital_activity = Counter(r.hospital_id for r in reports if r.hospital_id)
        dept_activity = Counter(r.department_id for r in reports if r.department_id)
        trans_activity = Counter(r.translator_id for r in reports if r.translator_id)
        
        def _resolve_names(counter_obj, model):
            resolved = []
            for obj_id, count in counter_obj.most_common(5):
                entity = s.get(model, obj_id)
                if entity:
                    label = getattr(entity, 'full_name', None) or getattr(entity, 'name', 'غير محدد')
                    resolved.append((label, count))
            return resolved
        
        top_patients = _resolve_names(patient_visits, Patient)
        top_hospitals = _resolve_names(hospital_activity, Hospital)
        top_depts = _resolve_names(dept_activity, Department)
        top_translators = _resolve_names(trans_activity, Translator)
        
        ai_insights = generate_system_ai_insights(
            reports, total_patients, total_hospitals, total_departments, total_doctors,
            top_patients, top_hospitals, top_depts
        )
        
        msg_lines = [
            "📊 **تحليل شامل للنظام مع AI**",
            f"{'═' * 35}",
            "",
            f"📅 **الفترة الزمنية:** {period_name}",
            "",
            "📈 **الإحصائيات العامة:**",
            f"   📄 إجمالي التقارير: {total_reports}",
            f"   👥 إجمالي المرضى: {total_patients}",
            f"   🏥 عدد المستشفيات: {total_hospitals}",
            f"   🩺 عدد الأقسام: {total_departments}",
            f"   👨‍⚕️ عدد الأطباء: {total_doctors}",
            f"   🌐 عدد المترجمين: {total_translators}",
            ""
        ]
        
        if total_patients > 0 and total_hospitals > 0 and total_departments > 0:
            msg_lines.extend([
                "📊 **المعدلات:**",
                f"   • معدل التقارير/مريض: {total_reports/total_patients:.1f}",
                f"   • معدل التقارير/مستشفى: {total_reports/total_hospitals:.1f}",
                f"   • معدل التقارير/قسم: {total_reports/total_departments:.1f}",
                ""
            ])
        
        if ai_insights:
            msg_lines.append("🤖 **رؤى الذكاء الاصطناعي:**")
            msg_lines.append("-" * 35)
            msg_lines.extend(ai_insights)
            msg_lines.append("")
        
        def _append_top_section(title, items):
            if not items:
                return
            msg_lines.append(title)
            for name, count in items:
                percentage = (count / total_reports) * 100 if total_reports else 0
                msg_lines.append(f"   • {name}: {count} ({percentage:.1f}%)")
            msg_lines.append("")
        
        _append_top_section("👤 **أكثر المرضى زيارة:**", top_patients)
        _append_top_section("🏥 **أكثر المستشفيات نشاطاً:**", top_hospitals)
        _append_top_section("🩺 **أكثر الأقسام نشاطاً:**", top_depts)
        _append_top_section("🌐 **أكثر المترجمين نشاطاً:**", top_translators)
        
        hospitals_dict = {name: count for name, count in top_hospitals[:10]}
        depts_dict = {name: count for name, count in top_depts[:10]}
        
        last_analysis = {
            'text': "\n".join(msg_lines),
            'type': 'تحليل شامل للنظام',
            'id': 'all',
            'charts_data': hospitals_dict if len(hospitals_dict) > 1 else {},
            'chart_title': "المستشفيات الأكثر نشاطاً",
            'extra_charts': depts_dict if len(depts_dict) > 1 else {},
            'extra_chart_title': "الأقسام الأكثر نشاطاً"
        }
        
        return {
            "message": "\n".join(msg_lines).rstrip(),
            "last_analysis": last_analysis
        }

async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة زر الرجوع"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📊 **نظام تحليل البيانات الشامل**\n\n"
        "اختر نوع التحليل الذي تريده:",
        reply_markup=_main_menu_kb()
    )
    return SELECT_ANALYSIS_TYPE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء المحادثة"""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("❌ تم إلغاء تحليل البيانات")
    else:
        await update.message.reply_text("❌ تم إلغاء تحليل البيانات")
    
    context.user_data.clear()
    return ConversationHandler.END

async def handle_export_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة تصدير التحليلات"""
    query = update.callback_query
    await query.answer()
    
    # تحليل البيانات من callback_data
    # format: export_analysis:format:analysis_id
    parts = query.data.split(":")
    if len(parts) < 3:
        await query.edit_message_text("❌ خطأ في البيانات")
        return
    
    export_format = parts[1]  # pdf أو excel
    analysis_id = parts[2]    # patient_123, hospital_456, etc.
    
    if export_format == "pdf":
        await handle_export_pdf(update, context)
    elif export_format == "excel":
        await handle_export_excel(update, context)
    else:
        await query.edit_message_text("❌ صيغة غير مدعومة")

async def handle_export_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة طلب تصدير PDF بجداول احترافية"""
    query = update.callback_query
    await query.answer("⏳ جاري إنشاء ملف PDF بجداول احترافية...")
    
    try:
        # استخدام البيانات المخزنة في context
        analysis_data = context.user_data.get('last_analysis')
        if not analysis_data:
            await query.edit_message_text("❌ لا توجد بيانات للتصدير")
            return
        
        await query.edit_message_text("📊 جاري إنشاء تقرير بجداول...\n\n⏳ قد يستغرق 10-15 ثانية...")
        
        now = datetime.now()
        analysis_text = analysis_data.get('text', 'لا توجد بيانات')
        analysis_type = analysis_data.get('type', 'عام')
        charts_data = analysis_data.get('charts_data', {})
        chart_title = analysis_data.get('chart_title', analysis_type)
        extra_charts_data = analysis_data.get('extra_charts', {})
        extra_chart_title = analysis_data.get('extra_chart_title', 'تحليل إضافي')
        
        # جمع إحصائيات من قاعدة البيانات مع تطبيق الفلاتر الصحيحة
        db = SessionLocal()
        
        # تحديد نطاق التحليل
        analysis_scope = "كل البيانات"
        
        try:
            # بناء الاستعلام حسب نوع التحليل المحفوظ
            reports_query = db.query(Report)
            
            # استخدام البيانات المحفوظة من التحليل
            analysis_id = analysis_data.get('id')
            
            # تطبيق الفلتر حسب نوع التحليل
            if 'مريض' in analysis_type and analysis_id != 'all':
                # تحليل مريض محدد
                reports_query = reports_query.filter(Report.patient_id == analysis_id)
                patient = db.get(Patient, analysis_id)
                if patient:
                    analysis_scope = f"مريض: {patient.full_name}"
            elif 'مستشفى' in analysis_type and analysis_id != 'all':
                # تحليل مستشفى محدد
                reports_query = reports_query.filter(Report.hospital_id == analysis_id)
                hospital = db.get(Hospital, analysis_id)
                if hospital:
                    analysis_scope = f"مستشفى: {hospital.name}"
            elif 'قسم' in analysis_type and analysis_id != 'all':
                # تحليل قسم محدد
                reports_query = reports_query.filter(Report.department_id == analysis_id)
                dept = db.get(Department, analysis_id)
                if dept:
                    analysis_scope = f"قسم: {dept.name}"
            elif 'مترجم' in analysis_type and analysis_id != 'all':
                # تحليل مترجم محدد
                reports_query = reports_query.filter(Report.translator_id == analysis_id)
            
            # تطبيق فلتر التاريخ إن وجد
            start_date = context.user_data.get('start_date')
            end_date = context.user_data.get('end_date')
            if start_date and end_date:
                reports_query = reports_query.filter(
                    Report.report_date >= start_date,
                    Report.report_date <= end_date
                )
            
            reports = reports_query.all()
            
            # إحصائيات المستشفيات
            hospitals_stats = {}
            for r in reports:
                if r.hospital_id:
                    h = db.get(Hospital, r.hospital_id)
                    hospital_name = h.name if h else 'غير محدد'
                    hospitals_stats[hospital_name] = hospitals_stats.get(hospital_name, 0) + 1
            
            # إحصائيات الأقسام
            departments_stats = {}
            for r in reports:
                if r.department_id:
                    d = db.get(Department, r.department_id)
                    dept_name = d.name if d else 'غير محدد'
                    departments_stats[dept_name] = departments_stats.get(dept_name, 0) + 1
            
            # إحصائيات الأطباء
            doctors_stats = {}
            for r in reports:
                if r.doctor_id:
                    doc = db.get(Doctor, r.doctor_id)
                    doctor_name = doc.full_name if doc else 'غير محدد'
                    doctors_stats[doctor_name] = doctors_stats.get(doctor_name, 0) + 1
            
            # إحصائيات الشكاوى
            complaints_stats = {}
            for r in reports:
                if r.complaint_text:
                    complaint = r.complaint_text.strip()
                    if complaint:
                        complaints_stats[complaint] = complaints_stats.get(complaint, 0) + 1
            
            # إحصائيات الإجراءات
            actions_stats = {}
            for r in reports:
                if r.medical_action:
                    action = r.medical_action.strip()
                    if action:
                        actions_stats[action] = actions_stats.get(action, 0) + 1
            
            # المرضى الأكثر زيارة
            patients_visits = {}
            for r in reports:
                if r.patient_id:
                    if r.patient_id not in patients_visits:
                        p = db.get(Patient, r.patient_id)
                        if p:
                            patients_visits[r.patient_id] = {
                                'name': p.full_name,
                                'visits': 0,
                                'last_visit': r.report_date
                            }
                    if r.patient_id in patients_visits:
                        patients_visits[r.patient_id]['visits'] += 1
                        if r.report_date > patients_visits[r.patient_id]['last_visit']:
                            patients_visits[r.patient_id]['last_visit'] = r.report_date
        finally:
            db.close()
        
        # استيراد الدوال الجديدة للجداول
        from services.pdf_generator_enhanced import (
            generate_data_analysis_pdf_with_tables,
            prepare_hospitals_table_data,
            prepare_departments_table_data,
            prepare_doctors_table_data,
            prepare_complaints_table_data,
            prepare_actions_table_data,
            prepare_top_patients_data
        )
        
        # تجهيز بيانات الجداول
        pdf_data = {
            'date_from': analysis_scope,
            'date_to': context.user_data.get('period_name', now.strftime('%Y-%m-%d')),
            'total_reports': len(reports),
            'total_patients': len(set(r.patient_id for r in reports if r.patient_id)),
            'hospitals_count': len(hospitals_stats),
            'doctors_count': len(doctors_stats),
            'hospitals_data': prepare_hospitals_table_data(hospitals_stats),
            'departments_data': prepare_departments_table_data(departments_stats),
            'doctors_data': prepare_doctors_table_data(doctors_stats),
            'complaints_data': prepare_complaints_table_data(complaints_stats),
            'actions_data': prepare_actions_table_data(actions_stats),
            'top_patients': prepare_top_patients_data(list(patients_visits.values()))
        }
        
        # إنشاء الرسوم البيانية
        charts = {}
        if charts_data:
            charts = create_analysis_charts(chart_title, charts_data)
        if extra_charts_data:
            extra_charts = create_analysis_charts(extra_chart_title, extra_charts_data)
            if charts:
                charts.update(extra_charts)
            else:
                charts = extra_charts
        
        # محاولة الحصول على رؤى AI إذا كانت متاحة
        ai_insights = None
        if AI_ANALYZER_AVAILABLE and is_ai_enabled():
            try:
                await query.edit_message_text("🤖 جاري إضافة رؤى ذكية بالـ AI...\n\n⏳ قد يستغرق 5-10 ثواني...")
                ai_insights = await generate_insights_report({
                    'total_reports': pdf_data['total_reports'],
                    'total_patients': pdf_data['total_patients'],
                    'active_hospitals': pdf_data['hospitals_count'],
                    'active_doctors': pdf_data['doctors_count'],
                    'top_complaint': pdf_data['complaints_data'][0]['name'] if pdf_data['complaints_data'] else 'غير محدد',
                    'top_department': pdf_data['departments_data'][0]['name'] if pdf_data['departments_data'] else 'غير محدد',
                    'top_action': pdf_data['actions_data'][0]['name'] if pdf_data['actions_data'] else 'غير محدد',
                    'date_from': pdf_data['date_from'],
                    'date_to': pdf_data['date_to']
                })
            except Exception as e:
                logger.error(f"AI insights error: {e}")
                ai_insights = None
        
        # إنشاء PDF بالجداول الاحترافية
        pdf_filename = await generate_data_analysis_pdf_with_tables(
            pdf_data,
            ai_insights=ai_insights,
            charts=charts
        )
        
        # إرسال الملف
        with open(pdf_filename, 'rb') as pdf_file:
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=pdf_file,
                filename=os.path.basename(pdf_filename),
                caption=f"📊 **تقرير تحليل البيانات بجداول احترافية**\n\n"
                        f"🔖 النوع: {analysis_type}\n"
                        f"📊 عدد الجداول: 6\n"
                        f"📈 رسوم بيانية: {'✅ نعم' if charts else '❌ لا'}\n"
                        f"🤖 رؤى AI: {'✅ نعم' if ai_insights else '❌ لا'}\n"
                        f"📅 {pdf_data['date_from']} - {pdf_data['date_to']}"
            )
        
        # حذف الملف المؤقت
        try:
            os.remove(pdf_filename)
        except:
            pass
        
        await query.edit_message_text(
            "✅ **تم إنشاء التقرير بنجاح!**\n\n"
            "📊 التقرير يحتوي على:\n"
            "✅ 6 جداول احترافية\n"
            "✅ إحصائيات منظمة\n"
            "✅ ألوان ذكية\n"
            "✅ تقييمات بصرية\n"
            f"{'✅ رؤى AI من GPT-4o' if ai_insights else ''}\n\n"
            "🎨 تصميم عصري ومنسق!"
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ خطأ في إنشاء التقرير: {str(e)}")

async def handle_export_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة طلب تصدير Excel"""
    query = update.callback_query
    await query.answer("⏳ جاري إنشاء ملف Excel...")
    
    try:
        # استخدام البيانات المخزنة
        analysis_data = context.user_data.get('last_analysis')
        if not analysis_data:
            await query.edit_message_text("❌ لا توجد بيانات للتصدير")
            return
        
        await query.edit_message_text("📗 جاري إنشاء ملف Excel...\n\n⏳ قد يستغرق بضع ثوان...")
        
        # استخدام دالة التصدير من admin_reports إن وجدت
        from bot.handlers.admin.admin_reports import export_to_excel
        
        # جمع البيانات
        db = SessionLocal()
        try:
            reports_query = db.query(Report)
            
            # تطبيق الفلاتر
            analysis_id = analysis_data.get('id')
            analysis_type = analysis_data.get('type', '')
            
            if 'مريض' in analysis_type and analysis_id != 'all':
                reports_query = reports_query.filter(Report.patient_id == analysis_id)
            elif 'مستشفى' in analysis_type and analysis_id != 'all':
                reports_query = reports_query.filter(Report.hospital_id == analysis_id)
            elif 'قسم' in analysis_type and analysis_id != 'all':
                reports_query = reports_query.filter(Report.department_id == analysis_id)
            elif 'مترجم' in analysis_type and analysis_id != 'all':
                reports_query = reports_query.filter(Report.translator_id == analysis_id)
            
            # تطبيق فلتر التاريخ
            start_date = context.user_data.get('start_date')
            end_date = context.user_data.get('end_date')
            if start_date and end_date:
                reports_query = reports_query.filter(
                    Report.report_date >= start_date,
                    Report.report_date <= end_date
                )
            
            reports = reports_query.all()
            
            # تحويل إلى صيغة مناسبة
            reports_data = []
            for r in reports:
                # جلب بيانات المريض
                patient_name = 'غير محدد'
                if r.patient_id:
                    patient = db.query(Patient).filter_by(id=r.patient_id).first()
                    if patient:
                        patient_name = patient.full_name or 'غير محدد'
                
                # جلب بيانات المستشفى
                hospital_name = 'غير محدد'
                if r.hospital_id:
                    hospital = db.query(Hospital).filter_by(id=r.hospital_id).first()
                    if hospital:
                        hospital_name = hospital.name or 'غير محدد'
                
                # جلب بيانات القسم
                department_name = 'غير محدد'
                if r.department_id:
                    department = db.query(Department).filter_by(id=r.department_id).first()
                    if department:
                        department_name = department.name or 'غير محدد'
                
                # جلب بيانات الطبيب
                doctor_name = 'غير محدد'
                if r.doctor_id:
                    doctor = db.query(Doctor).filter_by(id=r.doctor_id).first()
                    if doctor:
                        doctor_name = doctor.full_name or doctor.name or 'غير محدد'
                
                reports_data.append({
                    'report_id': r.id,
                    'report_date': r.report_date.strftime("%Y-%m-%d %H:%M") if r.report_date else '',
                    'patient_name': patient_name,
                    'hospital_name': hospital_name,
                    'department_name': department_name,
                    'doctor_name': doctor_name,
                    'medical_action': r.medical_action or 'غير محدد',
                    'complaint_text': r.complaint_text or '',
                    'doctor_decision': r.doctor_decision or '',
                })
            
            # التحقق من وجود بيانات
            if not reports_data:
                await query.edit_message_text(
                    "⚠️ **لا توجد بيانات للتصدير**\n\n"
                    "لم يتم العثور على تقارير مطابقة للفلتر المحدد.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # إنشاء Excel
            try:
                excel_file = export_to_excel(reports_data, f"analysis_{analysis_type}")
            except Exception as excel_error:
                logger.error(f"❌ Error in export_to_excel: {excel_error}", exc_info=True)
                await query.edit_message_text(
                    f"❌ **خطأ في إنشاء ملف Excel**\n\n"
                    f"الخطأ: {str(excel_error)[:100]}\n\n"
                    f"يرجى المحاولة مرة أخرى.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # إرسال الملف
            if excel_file and os.path.exists(excel_file):
                try:
                    with open(excel_file, 'rb') as f:
                        await context.bot.send_document(
                            chat_id=query.message.chat_id,
                            document=f,
                            filename=os.path.basename(excel_file),
                            caption=f"✅ ملف Excel - تحليل: {analysis_type}\n📊 عدد السجلات: {len(reports_data)}"
                        )
                    
                    # حذف الملف المؤقت
                    try:
                        os.remove(excel_file)
                    except Exception as remove_error:
                        logger.warning(f"⚠️ Could not remove temp file: {remove_error}")
                    
                    await query.edit_message_text(
                        f"✅ **تم إنشاء ملف Excel بنجاح!**\n\n"
                        f"📊 عدد السجلات: {len(reports_data)}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as send_error:
                    logger.error(f"❌ Error sending Excel file: {send_error}", exc_info=True)
                    await query.edit_message_text(
                        f"❌ **خطأ في إرسال الملف**\n\n"
                        f"تم إنشاء الملف لكن فشل الإرسال.\n"
                        f"الخطأ: {str(send_error)[:100]}",
                        parse_mode=ParseMode.MARKDOWN
                    )
            else:
                logger.error(f"❌ Excel file not created or not found: {excel_file}")
                await query.edit_message_text(
                    "❌ **فشل إنشاء ملف Excel**\n\n"
                    "يرجى المحاولة مرة أخرى أو التواصل مع المطور.",
                    parse_mode=ParseMode.MARKDOWN
                )
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Excel export error: {e}", exc_info=True)
        error_msg = str(e)
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."
        try:
            await query.edit_message_text(
                f"❌ **خطأ في إنشاء Excel**\n\n"
                f"الخطأ: {error_msg}\n\n"
                f"يرجى المحاولة مرة أخرى أو التواصل مع المطور.",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass

def register(app):
    """تسجيل معالج تحليل البيانات"""
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📊 تحليل البيانات$"), start_data_analysis),
        ],
        states={
            SELECT_ANALYSIS_TYPE: [
                CallbackQueryHandler(handle_analysis_type, pattern="^analysis:"),
                CallbackQueryHandler(handle_back, pattern="^back:main$"),
            ],
            SELECT_DATE_FILTER: [
                CallbackQueryHandler(handle_date_filter, pattern="^date:"),
                CallbackQueryHandler(handle_back, pattern="^back:main$"),
            ],
            SELECT_ENTITY: [
                CallbackQueryHandler(handle_entity_selection, pattern="^(patient|hospital|dept|trans):"),
                CallbackQueryHandler(handle_back, pattern="^back:main$"),
            ],
            SHOW_ANALYSIS: [
                CallbackQueryHandler(handle_back, pattern="^back:main$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel, pattern="^abort$"),
        ],
        per_message=True,  # ✅ تفعيل per_message لتجنب التحذيرات
        allow_reentry=True,
    )
    
    app.add_handler(conv_handler)
    # إضافة handler للتصدير
    app.add_handler(CallbackQueryHandler(handle_export_pdf, pattern="^export_pdf:"))
    app.add_handler(CallbackQueryHandler(handle_export_analysis, pattern="^export_analysis:"))
    
    # ✅ تسجيل أمر /analyze_patient للبحث الفوري
    from telegram.ext import CommandHandler
    app.add_handler(CommandHandler("analyze_patient", handle_analyze_patient_command))

