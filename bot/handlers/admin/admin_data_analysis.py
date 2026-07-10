# =============================
# bot/handlers/admin/admin_data_analysis.py
# 📊 تحليل البيانات الشامل مع الذكاء الاصطناعي المتقدم - AI Data Analysis
# =============================
import asyncio

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters,
)
from datetime import datetime, timedelta
from db.session import SessionLocal
from db.models import Report, Patient, Hospital, Department, Doctor, Translator
from bot.shared_auth import is_admin
from bot.handlers.admin.decorators import require_admin
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

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _ARABIC_SUPPORT = True
except ImportError:
    logger_tmp = logging.getLogger(__name__)
    logger_tmp.warning("⚠️ arabic_reshaper/bidi not installed — Arabic chart text will not be shaped correctly")
    _ARABIC_SUPPORT = False
    def arabic_reshaper_stub(t): return t
    def get_display(t): return t  # noqa: F811
    class arabic_reshaper:  # noqa: N801
        @staticmethod
        def reshape(t): return t

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

# الحالات (محفوظة للتوافق — لم تعد الآلة الجديدة تعتمد على ConversationHandler)
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


# =============================================================================
# ✅ إعادة تصميم — نظام تحليل بيانات (BI) احترافي بفلاتر ديناميكية متسلسلة
# =============================================================================
#
# من هنا فصاعداً: تصميم جديد بالكامل يعتمد على services/reports_repository.py
# (get_reports, get_hospitals_in_scope, get_departments_in_scope,
#  get_doctors_in_scope, get_actions_in_scope, aggregate_by_*, compute_stats,
#  aggregate_cross, get_earliest_report_dates) بدل استعلامات SQLAlchemy
# مكررة مباشرة — بنفس النمط المُثبت اليوم في admin_comprehensive_report.py
# (فترة → مستشفيات → أقسام → أطباء → إجراءات، اختيار متعدد بالفهرسة).
#
# ✅ لا ConversationHandler هنا (بنفس سبب admin_evaluation_menu.py وغيره
# اليوم: تفادي "العلوق" في حالة لا تُطابقها أي ضغطة زر). الحالة تُدار
# بالكامل عبر context.user_data[_KEY].
#
# ✅ دوال الذكاء الاصطناعي أعلاه (generate_patient_ai_insights وغيرها)
# محفوظة كما هي دون حذف — لم تعد مربوطة بمسار "📝 تحليل المرضى" الجديد
# (فهي مصمَّمة أصلاً لتحليل عميق لمريض واحد، بينما التصميم الجديد لهذا
# النوع هو ملخص تجميعي متعدد المرضى حسب الفلاتر) — تبقى مُستخدَمة حصرياً
# عبر أمر /analyze_patient الذي لم يتغير إطلاقاً.

from calendar import monthrange
from datetime import date

_PFX = "da"
_KEY = "da_filters"

_MONTH_AR = {
    1: "يناير", 2: "فبراير", 3: "مارس",    4: "أبريل",
    5: "مايو",  6: "يونيو",  7: "يوليو",   8: "أغسطس",
    9: "سبتمبر",10: "أكتوبر",11: "نوفمبر", 12: "ديسمبر",
}

_TYPE_META = {
    "dashboard":   {"title": "لوحة المعلومات",       "emoji": "📊"},
    "hospitals":   {"title": "تحليل المستشفيات",      "emoji": "🏥"},
    "departments": {"title": "تحليل الأقسام",         "emoji": "🏢"},
    "doctors":     {"title": "تحليل الأطباء",         "emoji": "👨‍⚕️"},
    "patients":    {"title": "تحليل المرضى",          "emoji": "📝"},
    "actions":     {"title": "تحليل الإجراءات",       "emoji": "🩺"},
    "system":      {"title": "التحليل الشامل للنظام", "emoji": "🌐"},
}

_TIERS = ["hospitals", "departments", "doctors", "actions"]
_TIER_META = {
    "hospitals":   {"cb": "hsel",  "title": "المستشفيات"},
    "departments": {"cb": "dsel",  "title": "الأقسام"},
    "doctors":     {"cb": "dosel", "title": "الأطباء"},
    "actions":     {"cb": "asel",  "title": "أنواع الإجراءات"},
}
_TIER_ORDER = {name: i for i, name in enumerate(_TIERS)}


def _new_filters() -> dict:
    return {
        "analysis_type": None,
        "start": None, "end": None, "period_label": None,
        "hospitals": [], "departments": [], "doctors": [], "actions": [],
        "hospitals_all": True, "departments_all": True,
        "doctors_all": True, "actions_all": True,
        "_options": [], "_page": 0,
        "_year_center": date.today().year,
    }


def _f(context: ContextTypes.DEFAULT_TYPE) -> dict:
    return context.user_data.setdefault(_KEY, _new_filters())


# ── Keyboards ────────────────────────────────────────────────────────────────

def _main_menu_kb() -> InlineKeyboardMarkup:
    rows = []
    for key in ["dashboard", "hospitals", "departments", "doctors", "patients", "actions", "system"]:
        meta = _TYPE_META[key]
        rows.append([InlineKeyboardButton(f"{meta['emoji']} {meta['title']}", callback_data=f"{_PFX}:type:{key}")])
    rows.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")])
    return InlineKeyboardMarkup(rows)


def _period_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 شهر كامل", callback_data=f"{_PFX}:period:month")],
        [InlineKeyboardButton("📆 فترة مخصصة (من - إلى)", callback_data=f"{_PFX}:period:custom")],
        [InlineKeyboardButton("🔙 رجوع للقائمة", callback_data=f"{_PFX}:back_menu")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")],
    ])


def _year_kb(center_year: int) -> InlineKeyboardMarkup:
    years = [center_year - 1, center_year, center_year + 1]
    row = [InlineKeyboardButton(str(y), callback_data=f"{_PFX}:yr:pick:{y}") for y in years]
    nav = [
        InlineKeyboardButton("◀️ سنوات أقدم", callback_data=f"{_PFX}:yr:nav:{center_year - 3}"),
        InlineKeyboardButton("أحدث ▶️", callback_data=f"{_PFX}:yr:nav:{center_year + 3}"),
    ]
    return InlineKeyboardMarkup([
        row, nav,
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"{_PFX}:period:back")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")],
    ])


def _month_kb(year: int) -> InlineKeyboardMarkup:
    today = date.today()
    buttons, row = [], []
    for m in range(1, 13):
        disabled = (year, m) > (today.year, today.month)
        label = _MONTH_AR[m] if not disabled else f"· {_MONTH_AR[m]} ·"
        cb = f"{_PFX}:noop" if disabled else f"{_PFX}:mo:pick:{year}:{m}"
        row.append(InlineKeyboardButton(label, callback_data=cb))
        if len(row) == 3:
            buttons.append(row); row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 رجوع للسنوات", callback_data=f"{_PFX}:period:month")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")])
    return InlineKeyboardMarkup(buttons)


def _calendar_kb(year: int, month: int, step: str) -> InlineKeyboardMarkup:
    from calendar import monthcalendar

    today = date.today()
    buttons = []
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    nav_row = [
        InlineKeyboardButton("◀️", callback_data=f"{_PFX}:cal:{step}:navmonth:{prev_year}-{prev_month}"),
        InlineKeyboardButton(f"{_MONTH_AR[month]} {year}", callback_data=f"{_PFX}:noop"),
    ]
    if (year, month) < (today.year, today.month):
        nav_row.append(InlineKeyboardButton("▶️", callback_data=f"{_PFX}:cal:{step}:navmonth:{next_year}-{next_month}"))
    buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(d, callback_data=f"{_PFX}:noop") for d in ["إ", "ث", "ع", "خ", "ج", "س", "ح"]])

    for week in monthcalendar(year, month):
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(" ", callback_data=f"{_PFX}:noop"))
                continue
            d = date(year, month, day_num)
            if d > today:
                row.append(InlineKeyboardButton(" ", callback_data=f"{_PFX}:noop"))
            else:
                label = f"⭐{day_num}" if d == today else str(day_num)
                row.append(InlineKeyboardButton(label, callback_data=f"{_PFX}:cal:{step}:select:{d.isoformat()}"))
        buttons.append(row)

    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"{_PFX}:period:back")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")])
    return InlineKeyboardMarkup(buttons)


def _tier_kb(tier: str, filt: dict, page: int) -> InlineKeyboardMarkup:
    cb = _TIER_META[tier]["cb"]
    options = filt["_options"]
    selected = set(filt[tier])
    per_page = 8
    total_pages = max(1, (len(options) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    page_items = options[page * per_page: (page + 1) * per_page]

    buttons = [[InlineKeyboardButton(
        ("✅ " if filt[f"{tier}_all"] else "☑️ ") + "جميع " + _TIER_META[tier]["title"],
        callback_data=f"{_PFX}:{cb}:all",
    )]]
    for local_idx, opt in enumerate(page_items):
        global_idx = page * per_page + local_idx
        checked = "✅" if opt["name"] in selected else "◻️"
        label = f"{checked} {opt['name']} ({opt['count']})"
        if len(label) > 60:
            label = label[:57] + "…"
        buttons.append([InlineKeyboardButton(label, callback_data=f"{_PFX}:{cb}:toggle:{global_idx}")])

    nav = []
    if total_pages > 1 and page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"{_PFX}:{cb}:page:{page - 1}"))
    if total_pages > 1:
        nav.append(InlineKeyboardButton(f"📄 {page + 1}/{total_pages}", callback_data=f"{_PFX}:noop"))
    if total_pages > 1 and page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"{_PFX}:{cb}:page:{page + 1}"))
    if nav:
        buttons.append(nav)

    n_selected = len(selected)
    continue_label = "➡️ متابعة" if filt[f"{tier}_all"] or n_selected == 0 else f"➡️ متابعة ({n_selected} محدد)"
    buttons.append([InlineKeyboardButton(continue_label, callback_data=f"{_PFX}:{cb}:done")])
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"{_PFX}:{cb}:back")])
    buttons.append([InlineKeyboardButton("❌ إلغاء", callback_data=f"{_PFX}:cancel")])
    return InlineKeyboardMarkup(buttons)


# ── Entry point ────────────────────────────────────────────────────────────────

async def start_data_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """نقطة الدخول: زر '📊 تحليل البيانات'."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return
    context.user_data[_KEY] = _new_filters()
    try:
        await update.message.reply_text(
            "📊 *تحليل البيانات*\n\nاختر نوع التحليل:",
            reply_markup=_main_menu_kb(), parse_mode="Markdown",
        )
    except Exception as exc:
        logger.error(f"[data_analysis] Failed to show menu: {exc}")


async def _show_period_menu(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    filt = _f(context)
    atype = _TYPE_META.get(filt["analysis_type"], {}).get("title", "")
    try:
        await query.edit_message_text(
            f"📊 *{atype}*\n\n📅 اختر الفترة الزمنية:",
            reply_markup=_period_kb(), parse_mode="Markdown",
        )
    except Exception as exc:
        logger.error(f"[data_analysis] period menu render failed: {exc}")


async def _show_calendar(query, step: str, year: int | None = None, month: int | None = None) -> None:
    today = date.today()
    year = year or today.year
    month = month or today.month
    label = "تاريخ البداية" if step == "start" else "تاريخ النهاية"
    try:
        await query.edit_message_text(
            f"📆 فترة مخصصة — اختر {label}:",
            reply_markup=_calendar_kb(year, month, step), parse_mode="Markdown",
        )
    except Exception as exc:
        logger.error(f"[data_analysis] calendar render failed: {exc}")


# ── Cascading filter tiers (نفس فكرة admin_comprehensive_report.py) ───────────

async def _fetch_tier_options(tier: str, filt: dict) -> list[dict]:
    from services.reports_repository import (
        get_hospitals_in_scope, get_departments_in_scope,
        get_doctors_in_scope, get_actions_in_scope,
    )
    start, end = filt["start"], filt["end"]
    hospitals = None if filt["hospitals_all"] else filt["hospitals"]
    departments = None if filt["departments_all"] else filt["departments"]
    doctors = None if filt["doctors_all"] else filt["doctors"]

    if tier == "hospitals":
        return await get_hospitals_in_scope(start, end)
    if tier == "departments":
        return await get_departments_in_scope(start, end, hospitals=hospitals)
    if tier == "doctors":
        return await get_doctors_in_scope(start, end, hospitals=hospitals, departments=departments)
    if tier == "actions":
        return await get_actions_in_scope(start, end, hospitals=hospitals, departments=departments, doctors=doctors)
    return []


async def _show_tier(query, context: ContextTypes.DEFAULT_TYPE, tier: str, page: int = 0) -> None:
    filt = _f(context)
    options = await _fetch_tier_options(tier, filt)

    if not options:
        filt[f"{tier}_all"] = True
        filt[tier] = []
        await _advance_after_tier(query, context, tier)
        return

    filt["_options"] = options
    filt["_page"] = page
    title = _TIER_META[tier]["title"]
    atype = _TYPE_META.get(filt["analysis_type"], {}).get("title", "")
    text = f"📊 *{atype}*\n\n🔎 اختر {title} (يظهر عدد الحالات بجانب كل خيار):"
    try:
        await query.edit_message_text(text, reply_markup=_tier_kb(tier, filt, page), parse_mode="Markdown")
    except Exception as exc:
        logger.error(f"[data_analysis] tier render failed ({tier}): {exc}")


async def _advance_after_tier(query, context: ContextTypes.DEFAULT_TYPE, tier: str) -> None:
    idx = _TIER_ORDER[tier]
    if idx + 1 < len(_TIERS):
        await _show_tier(query, context, _TIERS[idx + 1])
    else:
        await _run_analysis(query, context)


async def _back_before_tier(query, context: ContextTypes.DEFAULT_TYPE, tier: str) -> None:
    idx = _TIER_ORDER[tier]
    if idx == 0:
        await _show_period_menu(query, context)
    else:
        await _show_tier(query, context, _TIERS[idx - 1])


# ── Analysis renderers ──────────────────────────────────────────────────────────

def _distinct_patients_by(reports: list[dict], key: str) -> dict[str, int]:
    """عدد المرضى الفريدين (وليس عدد التقارير) مُجمَّعاً حسب حقل معيّن."""
    groups: dict[str, set] = defaultdict(set)
    for r in reports:
        pid = r.get("patient_id")
        if not pid:
            continue
        val = (r.get(key) or "غير محدد").strip() or "غير محدد"
        groups[val].add(pid)
    return dict(sorted(((k, len(v)) for k, v in groups.items()), key=lambda x: -x[1]))


async def _run_analysis(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """بعد اكتمال كل الفلاتر: يجلب البيانات ويبني ملخص تيليجرام + يخزّن كل ما يلزم لتصدير PDF لاحقاً."""
    filt = _f(context)
    atype = filt["analysis_type"]
    meta = _TYPE_META[atype]

    try:
        await query.edit_message_text("⏳ جارٍ إعداد التحليل...", parse_mode="Markdown")
    except Exception:
        pass

    try:
        from services.reports_repository import (
            get_reports, compute_stats, aggregate_by_hospital, aggregate_by_department,
            aggregate_by_doctor, aggregate_by_action, aggregate_cross, get_earliest_report_dates,
        )

        hospitals = None if filt["hospitals_all"] else filt["hospitals"]
        departments = None if filt["departments_all"] else filt["departments"]
        doctors = None if filt["doctors_all"] else filt["doctors"]
        actions = None if filt["actions_all"] else filt["actions"]

        reports = await get_reports(
            filt["start"], filt["end"],
            depts=departments, actions=actions, hospitals=hospitals, doctors=doctors,
        )

        if not reports:
            await query.edit_message_text(
                f"⚠️ لا توجد بيانات مطابقة لمعايير البحث المحددة.\n\n📅 الفترة: {filt['period_label']}",
                parse_mode="Markdown",
            )
            context.user_data.pop(_KEY, None)
            return

        stats_raw = compute_stats(reports)
        n_doctors = len({r["doctor_name"] for r in reports if r.get("doctor_name")})

        text_lines = [f"{meta['emoji']} *{meta['title']}*", f"📅 الفترة: {filt['period_label']}", ""]
        pdf_stats: dict[str, int] = {}
        pdf_sections: list[dict] = []

        if atype == "dashboard":
            pdf_stats = {
                "إجمالي الحالات": stats_raw["total"],
                "المرضى": stats_raw["unique_patients"],
                "المستشفيات": stats_raw["unique_hospitals"],
                "الأقسام": stats_raw["unique_depts"],
                "الأطباء": n_doctors,
                "أنواع الإجراءات": stats_raw["unique_actions"],
            }
            for label, val in pdf_stats.items():
                text_lines.append(f"• {label}: {val}")

        elif atype == "hospitals":
            hosp = aggregate_by_hospital(reports)
            pdf_stats = {"إجمالي الحالات": stats_raw["total"], "عدد المستشفيات": len(hosp)}
            pdf_sections.append({"type": "ranked_table", "title": "المستشفيات", "data": hosp,
                                  "chart": "bar", "columns": ("المستشفى", "عدد الحالات")})
            top3 = list(hosp.items())[:3]
            text_lines.append(f"📊 عدد المستشفيات النشطة: {len(hosp)}")
            text_lines.append("🏆 الأنشط:")
            for name, cnt in top3:
                pct = cnt / stats_raw["total"] * 100 if stats_raw["total"] else 0
                text_lines.append(f"  • {name}: {cnt} ({pct:.1f}%)")

        elif atype == "departments":
            dept = aggregate_by_department(reports)
            cross = aggregate_cross(reports, "department", "medical_action")
            pdf_stats = {"إجمالي الحالات": stats_raw["total"], "عدد الأقسام": len(dept)}
            pdf_sections.append({"type": "ranked_table", "title": "الأقسام", "data": dept,
                                  "chart": "pie", "columns": ("القسم", "عدد الحالات")})
            pdf_sections.append({"type": "cross_table", "title": "توزيع الإجراءات حسب القسم", "data": cross,
                                  "col1_title": "القسم", "col2_title": "الإجراء", "top_n": 3})
            top3 = list(dept.items())[:3]
            text_lines.append(f"📊 عدد الأقسام النشطة: {len(dept)}")
            text_lines.append("🏆 الأنشط:")
            for name, cnt in top3:
                pct = cnt / stats_raw["total"] * 100 if stats_raw["total"] else 0
                text_lines.append(f"  • {name}: {cnt} ({pct:.1f}%)")

        elif atype == "doctors":
            doc = aggregate_by_doctor(reports)
            cross = aggregate_cross(reports, "doctor_name", "medical_action")
            pdf_stats = {"إجمالي الحالات": stats_raw["total"], "عدد الأطباء": len(doc)}
            pdf_sections.append({"type": "ranked_table", "title": "الأطباء", "data": doc,
                                  "chart": "bar", "columns": ("الطبيب", "عدد الحالات")})
            pdf_sections.append({"type": "cross_table", "title": "توزيع الإجراءات حسب الطبيب", "data": cross,
                                  "col1_title": "الطبيب", "col2_title": "الإجراء", "top_n": 3})
            top5 = list(doc.items())[:5]
            text_lines.append(f"📊 عدد الأطباء: {len(doc)}")
            text_lines.append("🏆 الأنشط ترتيباً:")
            for i, (name, cnt) in enumerate(top5, 1):
                text_lines.append(f"  {i}. {name}: {cnt} حالة")

        elif atype == "patients":
            patient_ids = list({r["patient_id"] for r in reports if r.get("patient_id")})
            earliest = await get_earliest_report_dates(patient_ids)
            new_count = sum(1 for pid in patient_ids if earliest.get(pid) and earliest[pid] >= filt["start"])
            returning_count = len(patient_ids) - new_count
            by_hosp = _distinct_patients_by(reports, "hospital_name")
            by_dept = _distinct_patients_by(reports, "department")

            pdf_stats = {
                "إجمالي المرضى": len(patient_ids),
                "مرضى جدد": new_count,
                "مرضى متكررون": returning_count,
                "إجمالي الحالات": stats_raw["total"],
            }
            pdf_sections.append({"type": "ranked_table", "title": "توزيع المرضى حسب المستشفى", "data": by_hosp,
                                  "chart": "bar", "columns": ("المستشفى", "عدد المرضى")})
            pdf_sections.append({"type": "ranked_table", "title": "توزيع المرضى حسب القسم", "data": by_dept,
                                  "chart": "pie", "columns": ("القسم", "عدد المرضى")})

            text_lines.append(f"👥 إجمالي المرضى: {len(patient_ids)}")
            text_lines.append(f"🆕 مرضى جدد (أول تقرير ضمن الفترة): {new_count}")
            text_lines.append(f"🔁 مرضى متكررون: {returning_count}")

        elif atype == "actions":
            act = aggregate_by_action(reports)
            cross_hosp = aggregate_cross(reports, "medical_action", "hospital_name")
            cross_doc = aggregate_cross(reports, "medical_action", "doctor_name")
            pdf_stats = {"إجمالي الحالات": stats_raw["total"], "عدد أنواع الإجراءات": len(act)}
            pdf_sections.append({"type": "ranked_table", "title": "أنواع الإجراءات", "data": act,
                                  "chart": "bar", "columns": ("نوع الإجراء", "عدد الحالات")})
            pdf_sections.append({"type": "cross_table", "title": "أكثر المستشفيات لكل إجراء", "data": cross_hosp,
                                  "col1_title": "الإجراء", "col2_title": "المستشفى", "top_n": 3})
            pdf_sections.append({"type": "cross_table", "title": "أكثر الأطباء لكل إجراء", "data": cross_doc,
                                  "col1_title": "الإجراء", "col2_title": "الطبيب", "top_n": 3})
            top5 = list(act.items())[:5]
            text_lines.append(f"📊 عدد أنواع الإجراءات: {len(act)}")
            for name, cnt in top5:
                pct = cnt / stats_raw["total"] * 100 if stats_raw["total"] else 0
                text_lines.append(f"  • {name}: {cnt} ({pct:.1f}%)")

        elif atype == "system":
            hosp = aggregate_by_hospital(reports)
            dept = aggregate_by_department(reports)
            doc = aggregate_by_doctor(reports)
            act = aggregate_by_action(reports)
            pdf_stats = {
                "إجمالي الحالات": stats_raw["total"], "المرضى": stats_raw["unique_patients"],
                "المستشفيات": stats_raw["unique_hospitals"], "الأقسام": stats_raw["unique_depts"],
                "الأطباء": n_doctors, "أنواع الإجراءات": stats_raw["unique_actions"],
            }
            pdf_sections.append({"type": "ranked_table", "title": "المستشفيات", "data": hosp, "chart": "bar",
                                  "columns": ("المستشفى", "عدد الحالات")})
            pdf_sections.append({"type": "ranked_table", "title": "الأقسام", "data": dept, "chart": "pie",
                                  "columns": ("القسم", "عدد الحالات")})
            pdf_sections.append({"type": "ranked_table", "title": "الأطباء الأنشط", "data": doc, "chart": None,
                                  "columns": ("الطبيب", "عدد الحالات")})
            pdf_sections.append({"type": "ranked_table", "title": "أنواع الإجراءات", "data": act, "chart": "bar",
                                  "columns": ("نوع الإجراء", "عدد الحالات")})
            for label, val in pdf_stats.items():
                text_lines.append(f"• {label}: {val}")

        # حفظ كل ما يلزم لتصدير PDF بنفس الفلاتر لاحقاً
        context.user_data["_da_pdf_payload"] = {
            "title": f"{meta['emoji']} {meta['title']}",
            "period_label": filt["period_label"],
            "filters_summary": {
                "hospitals": [] if filt["hospitals_all"] else filt["hospitals"],
                "departments": [] if filt["departments_all"] else filt["departments"],
                "doctors": [] if filt["doctors_all"] else filt["doctors"],
                "actions": [] if filt["actions_all"] else filt["actions"],
                "generated_at": datetime.now(),
            },
            "stats": pdf_stats,
            "sections": pdf_sections,
        }

        text_lines.append("\n📄 لتصدير تقرير PDF احترافي بنفس هذه الفلاتر، اضغط الزر أدناه.")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 تصدير PDF", callback_data=f"{_PFX}:export_pdf")],
            [InlineKeyboardButton("🔙 قائمة جديدة", callback_data=f"{_PFX}:back_menu")],
        ])
        await query.edit_message_text("\n".join(text_lines), reply_markup=kb, parse_mode="Markdown")

    except Exception:
        logger.exception("[data_analysis] analysis run failed")
        try:
            await query.edit_message_text("❌ حدث خطأ أثناء إعداد التحليل.", parse_mode="Markdown")
        except Exception:
            pass


async def _export_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    payload = context.user_data.get("_da_pdf_payload")
    if not payload:
        try:
            await query.answer("⚠️ انتهت صلاحية الجلسة، أعد إنشاء التحليل من جديد.", show_alert=True)
        except Exception:
            pass
        return

    try:
        await query.edit_message_text("⏳ جارٍ إنشاء ملف PDF...", parse_mode="Markdown")
    except Exception:
        pass

    try:
        from services.data_analysis_pdf import build_analysis_pdf

        pdf_buf = build_analysis_pdf(
            title=payload["title"], period_label=payload["period_label"],
            filters_summary=payload["filters_summary"], stats=payload["stats"],
            sections=payload["sections"],
        )
        filename = f"Analysis_{payload['title'].split(' ', 1)[-1]}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        caption = f"{payload['title']}\n📅 {payload['period_label']}"

        await context.bot.send_document(
            chat_id=update.effective_chat.id, document=pdf_buf,
            filename=filename, caption=caption, parse_mode="Markdown",
        )
        logger.info(f"[data_analysis] PDF exported  title={payload['title']!r}")
    except Exception:
        logger.exception("[data_analysis] PDF export failed")
        try:
            await query.edit_message_text("❌ حدث خطأ أثناء إنشاء ملف PDF.", parse_mode="Markdown")
        except Exception:
            pass


# ── Main callback dispatcher ────────────────────────────────────────────────────

@require_admin
async def handle_data_analysis_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data or ""
    parts = data[len(_PFX) + 1:].split(":")  # strip "da:"
    action = parts[0]

    if action == "cancel":
        try:
            await query.edit_message_text("✅ تم الإلغاء.")
        except Exception:
            pass
        context.user_data.pop(_KEY, None)
        context.user_data.pop("_da_pdf_payload", None)
        return

    if action == "noop":
        return

    if action == "back_menu":
        context.user_data[_KEY] = _new_filters()
        try:
            await query.edit_message_text(
                "📊 *تحليل البيانات*\n\nاختر نوع التحليل:",
                reply_markup=_main_menu_kb(), parse_mode="Markdown",
            )
        except Exception:
            pass
        return

    if action == "export_pdf":
        await _export_pdf(update, context)
        return

    if action == "type":
        atype = parts[1]
        filt = _f(context)
        filt["analysis_type"] = atype
        if atype == "dashboard":
            # لوحة المعلومات: تحتاج الفترة فقط، بدون تصفية بالمستشفى/القسم/الطبيب/الإجراء
            filt["hospitals_all"] = filt["departments_all"] = filt["doctors_all"] = filt["actions_all"] = True
        await _show_period_menu(query, context)
        return

    if action == "period":
        sub = parts[1] if len(parts) > 1 else ""
        filt = _f(context)
        if sub == "back":
            await _show_period_menu(query, context)
        elif sub == "month":
            await query.edit_message_text(
                "📊 *تحليل البيانات*\n\n📅 اختر السنة:",
                reply_markup=_year_kb(filt["_year_center"]), parse_mode="Markdown",
            )
        elif sub == "custom":
            await _show_calendar(query, step="start")
        return

    if action == "yr":
        sub = parts[1]
        filt = _f(context)
        if sub == "nav":
            year = int(parts[2])
            filt["_year_center"] = year
            await query.edit_message_text(
                "📊 *تحليل البيانات*\n\n📅 اختر السنة:",
                reply_markup=_year_kb(year), parse_mode="Markdown",
            )
        elif sub == "pick":
            year = int(parts[2])
            await query.edit_message_text(
                f"📊 *تحليل البيانات*\n\n📅 اختر الشهر — {year}:",
                reply_markup=_month_kb(year), parse_mode="Markdown",
            )
        return

    if action == "mo" and parts[1] == "pick":
        year, month = int(parts[2]), int(parts[3])
        start = date(year, month, 1)
        end = min(date(year, month, monthrange(year, month)[1]), date.today())
        filt = _f(context)
        filt["start"], filt["end"] = start, end
        filt["period_label"] = f"{_MONTH_AR[month]} {year}"
        if filt["analysis_type"] == "dashboard":
            await _run_analysis(query, context)
        else:
            await _show_tier(query, context, _TIERS[0])
        return

    if action == "cal":
        step, sub = parts[1], parts[2]
        filt = _f(context)
        if sub == "navmonth":
            y_str, m_str = parts[3].split("-")
            await _show_calendar(query, step=step, year=int(y_str), month=int(m_str))
        elif sub == "select":
            selected = date.fromisoformat(parts[3])
            if step == "start":
                filt["start"] = selected
                await _show_calendar(query, step="end", year=selected.year, month=selected.month)
            else:
                start_d = filt.get("start") or selected
                end_d = selected
                if end_d < start_d:
                    start_d, end_d = end_d, start_d
                end_d = min(end_d, date.today())
                filt["start"], filt["end"] = start_d, end_d
                filt["period_label"] = f"{start_d.strftime('%d/%m/%Y')} إلى {end_d.strftime('%d/%m/%Y')}"
                if filt["analysis_type"] == "dashboard":
                    await _run_analysis(query, context)
                else:
                    await _show_tier(query, context, _TIERS[0])
        return

    tier_by_cb = {meta["cb"]: name for name, meta in _TIER_META.items()}
    if action in tier_by_cb:
        tier = tier_by_cb[action]
        sub = parts[1] if len(parts) > 1 else ""
        filt = _f(context)

        if sub == "all":
            filt[f"{tier}_all"] = True
            filt[tier] = []
            await _advance_after_tier(query, context, tier)
        elif sub == "toggle":
            idx = int(parts[2])
            options = filt["_options"]
            if 0 <= idx < len(options):
                name = options[idx]["name"]
                current = set(filt[tier])
                if name in current:
                    current.discard(name)
                else:
                    current.add(name)
                filt[tier] = list(current)
                filt[f"{tier}_all"] = False
            await _show_tier(query, context, tier, page=filt.get("_page", 0))
        elif sub == "page":
            page = int(parts[2])
            await _show_tier(query, context, tier, page=page)
        elif sub == "done":
            if not filt[tier]:
                filt[f"{tier}_all"] = True
            await _advance_after_tier(query, context, tier)
        elif sub == "back":
            await _back_before_tier(query, context, tier)
        return


# ── Registration ───────────────────────────────────────────────────────────────

def register(app):
    """تسجيل نظام تحليل البيانات (بدون ConversationHandler — بنفس نمط admin_comprehensive_report.py)."""
    app.add_handler(
        MessageHandler(filters.Regex("^📊 تحليل البيانات$"), start_data_analysis)
    )
    app.add_handler(
        CallbackQueryHandler(handle_data_analysis_callback, pattern=rf"^{_PFX}:")
    )
    # أمر التحليل المباشر لمريض محدد — محفوظ دون أي تعديل
    app.add_handler(CommandHandler("analyze_patient", handle_analyze_patient_command))

    logger.info("[data_analysis] Handlers registered  prefix=da:  +/analyze_patient")
