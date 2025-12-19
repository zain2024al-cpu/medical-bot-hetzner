# ================================================
# bot/handlers/admin/admin_printing.py
# 🖨️ نظام الطباعة الاحترافي المتكامل
# ================================================

import asyncio
import os
import io
import uuid
from datetime import datetime, date, timedelta, time

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode
from db.session import SessionLocal
from db.models import Report, Patient, Hospital, Department, Translator
from bot.shared_auth import is_admin
from sqlalchemy import func, extract
import matplotlib
matplotlib.use('Agg')  # استخدام backend بدون GUI
import matplotlib.pyplot as plt

# محاولة استيراد مكتبات العربية (اختيارية)
try:
    from arabic_reshaper import reshape
    from bidi.algorithm import get_display
    ARABIC_SUPPORT = True
except ImportError:
    ARABIC_SUPPORT = False
    print("⚠️ مكتبات العربية غير متوفرة - سيعمل النظام بدونها")

# حالات المحادثة
PRINT_SELECT_TYPE, PRINT_SELECT_PERIOD, PRINT_SELECT_OPTIONS, PRINT_CONFIRM = range(4)

# المجلدات
EXPORTS_DIR = "exports"
os.makedirs(EXPORTS_DIR, exist_ok=True)

# ================================================
# دوال مساعدة للرسوم البيانية
# ================================================

def setup_arabic_plot():
    """إعداد matplotlib للعربية"""
    plt.rcParams['font.family'] = 'DejaVu Sans'
    plt.rcParams['axes.unicode_minus'] = False

def format_arabic_text(text):
    """تنسيق النص العربي للعرض الصحيح"""
    if ARABIC_SUPPORT:
        try:
            reshaped_text = reshape(text)
            return get_display(reshaped_text)
        except:
            return text
    return text


def normalize_date_range(start_date, end_date):
    """تحويل قيم date إلى DateTime لضمان شمول اليوم بالكامل"""
    start_dt = None
    end_dt = None
    
    if start_date:
        if isinstance(start_date, datetime):
            start_dt = start_date
        else:
            start_dt = datetime.combine(start_date, time.min)
    
    if end_date:
        if isinstance(end_date, datetime):
            end_dt = end_date
        else:
            end_dt = datetime.combine(end_date, time.max)
    
    return start_dt, end_dt

# ================================================
# بدء نظام الطباعة
# ================================================

async def start_professional_printing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء نظام الطباعة الاحترافي"""
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
        return ConversationHandler.END
    
    context.user_data.clear()
    
    welcome_text = """
🖨️ **نظام الطباعة الاحترافي**

اختر نوع التقرير المطلوب:
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 تقرير شامل مع إحصائيات", callback_data="print_type:full_stats")],
        [InlineKeyboardButton("📈 تقرير رسوم بيانية فقط", callback_data="print_type:charts_only")],
        [InlineKeyboardButton("📋 تقرير تفصيلي للتقارير", callback_data="print_type:detailed")],
        [InlineKeyboardButton("👤 تقرير مريض محدد", callback_data="print_type:patient")],
        [InlineKeyboardButton("🏥 تقرير مستشفى محدد", callback_data="print_type:hospital")],
        [InlineKeyboardButton("👨‍⚕️ تقرير مترجم محدد", callback_data="print_type:translator")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="print:cancel")]
    ])

    await update.message.reply_text(welcome_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return PRINT_SELECT_TYPE

# ================================================
# معالجة اختيار نوع التقرير
# ================================================

async def handle_print_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار نوع التقرير"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "print:cancel":
        await query.edit_message_text("❌ تم إلغاء الطباعة")
        return ConversationHandler.END
    
    print_type = query.data.split(":")[1]
    context.user_data['print_type'] = print_type
    
    # عرض خيارات الفترة الزمنية
    period_text = """
📅 **اختر الفترة الزمنية:**
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 اليوم", callback_data="period:today")],
        [InlineKeyboardButton("📅 هذا الأسبوع", callback_data="period:week")],
        [InlineKeyboardButton("📅 هذا الشهر", callback_data="period:month")],
        [InlineKeyboardButton("📅 آخر 3 أشهر", callback_data="period:3months")],
        [InlineKeyboardButton("📅 هذه السنة", callback_data="period:year")],
        [InlineKeyboardButton("📅 الكل", callback_data="period:all")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back:type")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="print:cancel")]
    ])
    
    await query.edit_message_text(period_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return PRINT_SELECT_PERIOD

# ================================================
# معالجة اختيار الفترة
# ================================================

async def handle_period_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار الفترة الزمنية"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back:type":
        # العودة لاختيار النوع
        welcome_text = """
🖨️ **نظام الطباعة الاحترافي**

اختر نوع التقرير المطلوب:
"""
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 تقرير شامل مع إحصائيات", callback_data="print_type:full_stats")],
            [InlineKeyboardButton("📈 تقرير رسوم بيانية فقط", callback_data="print_type:charts_only")],
            [InlineKeyboardButton("📋 تقرير تفصيلي للتقارير", callback_data="print_type:detailed")],
            [InlineKeyboardButton("👤 تقرير مريض محدد", callback_data="print_type:patient")],
            [InlineKeyboardButton("🏥 تقرير مستشفى محدد", callback_data="print_type:hospital")],
            [InlineKeyboardButton("👨‍⚕️ تقرير مترجم محدد", callback_data="print_type:translator")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="print:cancel")]
        ])

        await query.edit_message_text(welcome_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        return PRINT_SELECT_TYPE
    
    if query.data == "print:cancel":
        await query.edit_message_text("❌ تم إلغاء الطباعة")
        return ConversationHandler.END
    
    period = query.data.split(":")[1]
    context.user_data['period'] = period
    
    # تحديد نطاق التواريخ
    today = date.today()
    
    if period == "today":
        start_date = today
        end_date = today
        period_name = "اليوم"
    elif period == "week":
        start_date = today - timedelta(days=today.weekday())
        end_date = today
        period_name = "هذا الأسبوع"
    elif period == "month":
        start_date = today.replace(day=1)
        end_date = today
        period_name = "هذا الشهر"
    elif period == "3months":
        start_date = today - timedelta(days=90)
        end_date = today
        period_name = "آخر 3 أشهر"
    elif period == "year":
        start_date = today.replace(month=1, day=1)
        end_date = today
        period_name = "هذه السنة"
    else:  # all
        start_date = None
        end_date = None
        period_name = "جميع الفترات"
    
    context.user_data['start_date'] = start_date
    context.user_data['end_date'] = end_date
    context.user_data['period_name'] = period_name
    
    # عرض خيارات إضافية
    await show_print_options(query, context)
    return PRINT_SELECT_OPTIONS

async def show_print_options(query, context):
    """عرض خيارات الطباعة الإضافية"""
    
    options_text = f"""
⚙️ **خيارات الطباعة:**

📅 الفترة: **{context.user_data.get('period_name')}**

اختر ما تريد تضمينه:
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 إحصائيات عامة", callback_data="opt:toggle_stats")],
        [InlineKeyboardButton("📈 رسوم بيانية", callback_data="opt:toggle_charts")],
        [InlineKeyboardButton("📋 قائمة التقارير التفصيلية", callback_data="opt:toggle_details")],
        [InlineKeyboardButton("🏥 تقسيم حسب المستشفى", callback_data="opt:toggle_hospital")],
        [InlineKeyboardButton("👨‍⚕️ تقسيم حسب المترجم", callback_data="opt:toggle_translator")],
        [InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━", callback_data="separator")],
        [InlineKeyboardButton("✅ إنشاء التقرير الآن", callback_data="generate:now")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back:period")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="print:cancel")]
    ])
    
    await query.edit_message_text(options_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

# ================================================
# معالجة الخيارات وإنشاء التقرير
# ================================================

async def handle_print_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة خيارات الطباعة"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back:period":
        # العودة لاختيار الفترة
        period_text = """
📅 **اختر الفترة الزمنية:**
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 اليوم", callback_data="period:today")],
            [InlineKeyboardButton("📅 هذا الأسبوع", callback_data="period:week")],
            [InlineKeyboardButton("📅 هذا الشهر", callback_data="period:month")],
            [InlineKeyboardButton("📅 آخر 3 أشهر", callback_data="period:3months")],
            [InlineKeyboardButton("📅 هذه السنة", callback_data="period:year")],
            [InlineKeyboardButton("📅 الكل", callback_data="period:all")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="print:cancel")]
        ])
        await query.edit_message_text(period_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        return PRINT_SELECT_PERIOD
    
    if query.data == "print:cancel":
        await query.edit_message_text("❌ تم إلغاء الطباعة")
        return ConversationHandler.END
    
    if query.data == "generate:now":
        # إنشاء التقرير
        await query.edit_message_text("⏳ **جاري إنشاء التقرير...**\n\nقد يستغرق هذا بضع ثوانٍ...")
        return await generate_professional_report(query, context)
    
    if query.data == "separator":
        # زر فاصل - لا يفعل شيء
        await query.answer()
        return PRINT_SELECT_OPTIONS
    
    # معالجة toggle للخيارات (سيتم إضافتها لاحقاً)
    await query.answer("✅ تم")
    return PRINT_SELECT_OPTIONS

# ================================================
# إنشاء التقرير
# ================================================

async def generate_professional_report(query, context):
    """إنشاء التقرير الاحترافي"""
    
    start_date = context.user_data.get('start_date')
    end_date = context.user_data.get('end_date')
    period_name = context.user_data.get('period_name')
    start_dt, end_dt = normalize_date_range(start_date, end_date)
    
    loop = asyncio.get_running_loop()
    
    try:
        result = await loop.run_in_executor(
            None,
            _build_report_package,
            start_dt,
            end_dt,
            period_name,
        )
    except Exception as exc:
        import traceback
        traceback.print_exc()
        await query.edit_message_text(
            f"❌ **فشل إنشاء التقرير**\n\n{exc}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    
    if result.get("empty"):
        await query.edit_message_text(
            f"⚠️ **لا توجد تقارير**\n\n"
            f"لا توجد تقارير في الفترة: {period_name}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    
    success_text = f"""
✅ **تم إنشاء التقرير بنجاح!**

📊 **الإحصائيات:**
• عدد التقارير: {result['report_count']}
• الفترة: {period_name}
• التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}
• نوع الملف: {result['file_type']}

📎 **سيتم إرسال الملف الآن...**
"""
    await query.edit_message_text(success_text, parse_mode=ParseMode.MARKDOWN)
    
    with open(result['file_path'], 'rb') as report_file:
        await query.message.reply_document(
            document=report_file,
            filename=result['filename'],
            caption=f"📊 التقرير الطبي - {period_name}\n"
                    f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                    f"📄 النوع: {result['file_type']}"
        )
    
    _cleanup_export_files(result.get("cleanup_paths", []))
    return ConversationHandler.END


def _build_report_package(start_dt, end_dt, period_name):
    """تشغيل جميع عمليات إنشاء التقرير في خيط منفصل"""
    cleanup_paths = []
    
    with SessionLocal() as s:
        query_reports = s.query(Report)
        if start_dt and end_dt:
            query_reports = query_reports.filter(
                Report.report_date >= start_dt,
                Report.report_date <= end_dt
            )
        
        reports = query_reports.all()
        if not reports:
            return {"empty": True, "period_name": period_name}
        
        stats = generate_statistics(s, reports, start_dt, end_dt)
        charts_paths = generate_charts(s, reports, start_dt, end_dt)
        cleanup_paths.extend(charts_paths)
        
        html_content = generate_html_report(reports, stats, charts_paths, period_name)
        unique_key = _unique_export_basename()
        html_path = os.path.join(EXPORTS_DIR, f'report_{unique_key}.html')
        
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        cleanup_paths.append(html_path)
        
        pdf_created, pdf_path = _render_pdf_from_html(html_path)
        if pdf_created:
            cleanup_paths.append(pdf_path)
            final_path = pdf_path
            file_type = "PDF"
            filename = f'تقرير_طبي_{unique_key}.pdf'
        else:
            final_path = html_path
            file_type = "HTML"
            filename = f'تقرير_طبي_{unique_key}.html'
        
    return {
        "empty": False,
        "report_count": len(reports),
        "period_name": period_name,
        "file_path": final_path,
        "file_type": file_type,
        "filename": filename,
        "cleanup_paths": cleanup_paths,
    }


def _render_pdf_from_html(html_path):
    """تحويل ملف HTML إلى PDF إن أمكن"""
    pdf_path = os.path.splitext(html_path)[0] + ".pdf"
    
    try:
        from weasyprint import HTML, CSS
        
        rtl_css = CSS(string='''
            @page {
                size: A4;
                margin: 1.5cm;
            }
            body {
                direction: rtl;
                font-family: 'Arial', 'Tahoma', sans-serif;
                text-align: right;
            }
        ''')
        
        HTML(filename=html_path).write_pdf(pdf_path, stylesheets=[rtl_css])
        return True, pdf_path
    except ImportError:
        # محاولة استخدام pdfkit
        try:
            import pdfkit
            options = {
                'encoding': 'UTF-8',
                'page-size': 'A4',
                'margin-top': '1.5cm',
                'margin-right': '1.5cm',
                'margin-bottom': '1.5cm',
                'margin-left': '1.5cm',
                'no-outline': None
            }
            pdfkit.from_file(html_path, pdf_path, options=options)
            return True, pdf_path
        except Exception as pdf_error:
            print(f"⚠️ فشل إنشاء PDF عبر pdfkit: {pdf_error}")
    except Exception as e:
        print(f"⚠️ خطأ في إنشاء PDF: {e}")
    
    return False, html_path


def _unique_export_basename():
    """اسم فريد للملفات المصدرة"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    unique_suffix = uuid.uuid4().hex[:6]
    return f"{timestamp}_{unique_suffix}"


def _cleanup_export_files(paths):
    """حذف الملفات والرسوم المؤقتة"""
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as cleanup_error:
            print(f"⚠️ تعذر حذف الملف المؤقت {path}: {cleanup_error}")

# ================================================
# إنشاء الإحصائيات
# ================================================

def generate_statistics(session, reports, start_date, end_date):
    """إنشاء إحصائيات شاملة"""
    
    stats = {}
    
    # إحصائيات عامة
    stats['total_reports'] = len(reports)
    stats['unique_patients'] = len(set(r.patient_id for r in reports if r.patient_id))
    
    # حساب الحالات الجديدة (استشارات جديدة)
    new_cases = sum(1 for r in reports if r.medical_action and 'استشارة جديدة' in r.medical_action)
    stats['new_cases'] = new_cases
    
    # حساب العمليات
    operations = sum(1 for r in reports if r.medical_action and ('عملية' in r.medical_action or 'جراحة' in r.medical_action))
    stats['operations'] = operations
    
    # حساب المتابعات
    followups = sum(1 for r in reports if r.medical_action and ('متابعة' in r.medical_action or 'مراجعة' in r.medical_action))
    stats['followups'] = followups
    
    # التقسيم حسب النوع
    report_types = {}
    for report in reports:
        report_type = report.medical_action or 'غير محدد'
        report_types[report_type] = report_types.get(report_type, 0) + 1
    stats['by_type'] = report_types
    
    # التقسيم حسب المستشفى
    hospitals = {}
    for report in reports:
        if report.hospital_id:
            hospital_obj = session.query(Hospital).filter_by(id=report.hospital_id).first()
            hospital = hospital_obj.name if hospital_obj else 'غير محدد'
        else:
            hospital = 'غير محدد'
        hospitals[hospital] = hospitals.get(hospital, 0) + 1
    stats['by_hospital'] = hospitals
    
    # التقسيم حسب المترجم
    translators = {}
    for report in reports:
        if report.translator_id:
            translator_obj = session.query(Translator).filter_by(id=report.translator_id).first()
            translator = translator_obj.full_name if translator_obj else 'غير محدد'
        else:
            translator = 'غير محدد'
        translators[translator] = translators.get(translator, 0) + 1
    stats['by_translator'] = translators
    
    # التقسيم حسب التاريخ (يومي/شهري)
    dates = {}
    for report in reports:
        date_str = report.report_date.strftime('%Y-%m-%d') if report.report_date else 'غير محدد'
        dates[date_str] = dates.get(date_str, 0) + 1
    stats['by_date'] = dates
    
    return stats

# ================================================
# إنشاء الرسوم البيانية
# ================================================

def generate_charts(session, reports, start_date, end_date):
    """إنشاء رسوم بيانية احترافية"""
    
    setup_arabic_plot()
    charts_paths = []
    
    try:
        # 1. رسم بياني: التقارير حسب النوع
        report_types = {}
        for report in reports:
            report_type = report.report_type or 'غير محدد'
            report_types[report_type] = report_types.get(report_type, 0) + 1
        
        if report_types:
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # تنسيق النصوص العربية
            labels = [format_arabic_text(label) for label in report_types.keys()]
            values = list(report_types.values())
            
            colors = ['#4CAF50', '#2196F3', '#FF9800', '#F44336', '#9C27B0']
            ax.bar(range(len(labels)), values, color=colors[:len(labels)])
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=0)
            ax.set_ylabel(format_arabic_text('عدد التقارير'))
            ax.set_title(format_arabic_text('التقارير حسب النوع'), pad=20, fontsize=14, fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
            
            # حفظ
            chart_path = os.path.join(EXPORTS_DIR, 'chart_types.png')
            plt.tight_layout()
            plt.savefig(chart_path, dpi=150, bbox_inches='tight')
            plt.close()
            charts_paths.append(chart_path)
        
        # 2. رسم دائري: التقارير حسب المستشفى
        hospitals = {}
        for report in reports:
            hospital = report.hospital_name or 'غير محدد'
            hospitals[hospital] = hospitals.get(hospital, 0) + 1
        
        if hospitals:
            fig, ax = plt.subplots(figsize=(10, 8))
            
            labels = [format_arabic_text(label) for label in hospitals.keys()]
            values = list(hospitals.values())
            
            colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40']
            ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors[:len(labels)])
            ax.set_title(format_arabic_text('التوزيع حسب المستشفى'), pad=20, fontsize=14, fontweight='bold')
            
            chart_path = os.path.join(EXPORTS_DIR, 'chart_hospitals.png')
            plt.tight_layout()
            plt.savefig(chart_path, dpi=150, bbox_inches='tight')
            plt.close()
            charts_paths.append(chart_path)
        
        # 3. رسم خطي: التقارير عبر الزمن
        dates = {}
        for report in reports:
            if report.report_date:
                date_str = report.report_date.strftime('%Y-%m-%d')
                dates[date_str] = dates.get(date_str, 0) + 1
        
        if len(dates) > 1:
            fig, ax = plt.subplots(figsize=(12, 6))
            
            sorted_dates = sorted(dates.items())
            x_labels = [item[0] for item in sorted_dates]
            y_values = [item[1] for item in sorted_dates]
            
            ax.plot(x_labels, y_values, marker='o', linewidth=2, markersize=8, color='#2196F3')
            ax.fill_between(range(len(x_labels)), y_values, alpha=0.3, color='#2196F3')
            ax.set_xlabel(format_arabic_text('التاريخ'))
            ax.set_ylabel(format_arabic_text('عدد التقارير'))
            ax.set_title(format_arabic_text('التقارير عبر الزمن'), pad=20, fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            
            # تقليل عدد التواريخ المعروضة إذا كانت كثيرة
            if len(x_labels) > 15:
                step = len(x_labels) // 10
                ax.set_xticks(range(0, len(x_labels), step))
                ax.set_xticklabels([x_labels[i] for i in range(0, len(x_labels), step)], rotation=45)
            else:
                ax.set_xticklabels(x_labels, rotation=45)
            
            chart_path = os.path.join(EXPORTS_DIR, 'chart_timeline.png')
            plt.tight_layout()
            plt.savefig(chart_path, dpi=150, bbox_inches='tight')
            plt.close()
            charts_paths.append(chart_path)
        
    except Exception as e:
        print(f"⚠️ خطأ في إنشاء الرسوم البيانية: {e}")
    
    return charts_paths

# ================================================
# إنشاء HTML للتقرير
# ================================================

def generate_html_report(reports, stats, charts_paths, period_name):
    """إنشاء تقرير HTML احترافي"""
    
    timestamp = datetime.now()
    report_number = f"RPT-{timestamp.strftime('%Y%m%d%H%M')}"
    
    html = f'''
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تقرير طبي شامل - {period_name}</title>
    <style>
        @page {{
            size: A4;
            margin: 2cm 2cm 3cm 2cm;
            
            @top-center {{
                content: "نظام التقارير الطبية الذكي";
                font-family: 'Arial', 'Tahoma', sans-serif;
                font-size: 10pt;
                color: #2c3e50;
                padding-bottom: 5pt;
                border-bottom: 1pt solid #3498db;
            }}
            
            @bottom-right {{
                content: "صفحة " counter(page) " من " counter(pages);
                font-family: 'Arial', 'Tahoma', sans-serif;
                font-size: 9pt;
                color: #7f8c8d;
            }}
            
            @bottom-center {{
                content: "تم إعداد التقرير بواسطة نظام التقارير الطبية © 2025";
                font-family: 'Arial', 'Tahoma', sans-serif;
                font-size: 8pt;
                color: #95a5a6;
            }}
        }}
        
        body {{
            font-family: 'Arial', 'Tahoma', 'Amiri', sans-serif;
            direction: rtl;
            text-align: right;
            color: #2c3e50;
            line-height: 1.8;
            margin: 0;
            padding: 0;
        }}
        
        /* صفحة الغلاف */
        .cover-page {{
            height: 100vh;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            align-items: center;
            text-align: center;
            page-break-after: always;
            padding: 50px;
        }}
        
        .bismillah {{
            font-size: 24pt;
            color: #27ae60;
            font-weight: bold;
            margin-top: 80px;
            font-family: 'Amiri', 'Traditional Arabic', serif;
        }}
        
        .cover-title {{
            margin-top: auto;
            margin-bottom: auto;
        }}
        
        .cover-title h1 {{
            font-size: 36pt;
            color: #2c3e50;
            margin: 20px 0;
            font-weight: bold;
        }}
        
        .cover-title h2 {{
            font-size: 20pt;
            color: #3498db;
            margin: 10px 0;
            font-weight: normal;
        }}
        
        .cover-footer {{
            margin-top: auto;
            color: #7f8c8d;
            font-size: 12pt;
        }}
        
        .cover-footer p {{
            margin: 5px 0;
        }}
        
        /* فاصل بين الأقسام */
        .page-break {{
            page-break-before: always;
        }}
        
        .section {{
            margin: 30px 0;
            page-break-inside: avoid;
        }}
        
        .section-title {{
            font-size: 22pt;
            font-weight: bold;
            color: #2c3e50;
            border-right: 6px solid #3498db;
            padding-right: 15px;
            margin: 30px 0 20px 0;
            page-break-after: avoid;
        }}
        
        /* الإحصائيات */
        .stats-container {{
            background: #f8f9fa;
            padding: 25px;
            border-radius: 8px;
            margin: 20px 0;
            border: 2px solid #e8e8e8;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin: 20px 0;
        }}
        
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            border-right: 5px solid #3498db;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        
        .stat-card h3 {{
            margin: 0 0 10px 0;
            color: #7f8c8d;
            font-size: 12pt;
            font-weight: normal;
        }}
        
        .stat-card .number {{
            font-size: 36pt;
            font-weight: bold;
            color: #2c3e50;
            margin: 0;
        }}
        
        /* الجداول */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            border-radius: 8px;
            overflow: hidden;
        }}
        
        th {{
            background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
            color: white;
            padding: 15px 12px;
            font-weight: bold;
            text-align: right;
            font-size: 11pt;
            border-bottom: 3px solid #2980b9;
        }}
        
        td {{
            padding: 12px;
            border-bottom: 1px solid #ecf0f1;
            text-align: right;
            font-size: 10pt;
        }}
        
        tr:nth-child(even) {{
            background: #f8f9fa;
        }}
        
        tr:hover {{
            background: #e8f4f8;
        }}
        
        /* الرسوم البيانية */
        .chart-container {{
            margin: 30px 0;
            text-align: center;
            page-break-inside: avoid;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        
        .chart-title {{
            font-size: 16pt;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 20px;
            text-align: center;
        }}
        
        .chart-container img {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
        }}
        
        /* الملخص النهائي */
        .summary-box {{
            background: linear-gradient(135deg, #e8f4f8 0%, #f0f7fb 100%);
            padding: 25px;
            border-radius: 10px;
            border: 2px solid #3498db;
            margin: 30px 0;
        }}
        
        .summary-box h3 {{
            color: #2c3e50;
            font-size: 18pt;
            margin: 0 0 20px 0;
            text-align: center;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }}
        
        .summary-item {{
            background: white;
            padding: 15px;
            border-radius: 6px;
            border-right: 4px solid #3498db;
        }}
        
        .summary-item .label {{
            font-size: 10pt;
            color: #7f8c8d;
            margin-bottom: 5px;
        }}
        
        .summary-item .value {{
            font-size: 24pt;
            font-weight: bold;
            color: #2c3e50;
        }}
        
        /* تحسينات الطباعة */
        @media print {{
            .page-break {{
                page-break-before: always;
            }}
            
            .section {{
                page-break-inside: avoid;
            }}
        }}
    </style>
</head>
<body>'''
    
    # الصفحة الأولى: العنوان + معلومات التقرير
    html += f'''
    
<!-- الصفحة الأولى: العنوان الواضح -->
<div style="text-align: center; margin: 40px 0 50px 0;">
    <div class="bismillah">بسم الله الرحمن الرحيم</div>
    <h1 style="font-size: 32pt; color: #2c3e50; margin: 40px 0 20px 0; font-weight: bold;">
        📊 التقرير الطبي الشامل
    </h1>
    <h2 style="font-size: 18pt; color: #3498db; margin: 10px 0 30px 0;">
        نظام التقارير الذكي - الفترة: {period_name}
    </h2>
    <p style="font-size: 12pt; color: #7f8c8d; margin: 5px 0;">
        <strong>رقم التقرير:</strong> {report_number} | 
        <strong>تاريخ الإنشاء:</strong> {timestamp.strftime('%Y-%m-%d %H:%M')}
    </p>
</div>

<!-- الجدول التفصيلي للتقارير -->
<div class="section">
    <div class="section-title">📋 جدول التقارير التفصيلي</div>
    <table>
        <thead>
            <tr>
                <th>نوع التقرير</th>
                <th>العدد</th>
                <th>النسبة</th>
            </tr>
        </thead>
        <tbody>
'''
    
    for report_type, count in sorted(stats['by_type'].items(), key=lambda x: x[1], reverse=True):
        percentage = (count / stats['total_reports'] * 100) if stats['total_reports'] > 0 else 0
        html += f'''
            <tr>
                <td>{report_type}</td>
                <td>{count}</td>
                <td>{percentage:.1f}%</td>
            </tr>
'''
    
    html += '''
        </tbody>
    </table>
</div>

<!-- جدول الإحصائيات -->
<div class="section" style="margin-top: 40px;">
    <div class="section-title">📊 جدول الإحصائيات الشاملة</div>
    <div class="summary-box">
        <div class="summary-grid">
            <div class="summary-item">
                <div class="label">🩺 إجمالي عدد المرضى</div>
                <div class="value">{stats['unique_patients']}</div>
            </div>
            <div class="summary-item">
                <div class="label">📄 إجمالي التقارير</div>
                <div class="value">{stats['total_reports']}</div>
            </div>
            <div class="summary-item">
                <div class="label">🆕 الحالات الجديدة</div>
                <div class="value">{stats.get('new_cases', 0)}</div>
            </div>
            <div class="summary-item">
                <div class="label">🔪 العمليات</div>
                <div class="value">{stats.get('operations', 0)}</div>
            </div>
            <div class="summary-item">
                <div class="label">🔄 المتابعات</div>
                <div class="value">{stats.get('followups', 0)}</div>
            </div>
            <div class="summary-item">
                <div class="label">🏥 المستشفيات</div>
                <div class="value">{len(stats['by_hospital'])}</div>
            </div>
            <div class="summary-item">
                <div class="label">👨‍⚕️ المترجمين</div>
                <div class="value">{len(stats['by_translator'])}</div>
            </div>
            <div class="summary-item">
                <div class="label">📊 أنواع الإجراءات</div>
                <div class="value">{len(stats['by_type'])}</div>
            </div>
        </div>
    </div>
</div>

<!-- الرسوم البيانية -->
<div class="page-break">
    <div class="section-title">📊 الرسوم البيانية والتحليلات</div>
'''
    
    # إضافة الرسوم البيانية مع عناوين
    chart_titles = [
        '📊 التوزيع حسب نوع التقرير',
        '🏥 التوزيع حسب المستشفيات',
        '📈 التقارير عبر الزمن'
    ]
    
    for i, chart_path in enumerate(charts_paths):
        if os.path.exists(chart_path):
            # قراءة الصورة وتحويلها لـ base64
            import base64
            with open(chart_path, 'rb') as img_file:
                img_data = base64.b64encode(img_file.read()).decode()
            
            chart_title = chart_titles[i] if i < len(chart_titles) else f'رسم بياني {i+1}'
            
            html += f'''
    <div class="chart-container">
        <div class="chart-title">{chart_title}</div>
        <img src="data:image/png;base64,{img_data}" alt="{chart_title}">
    </div>
'''
    
    html += '''
</div>

<!-- جدول التقارير حسب المستشفى -->
<div class="page-break">
    <div class="section-title">🏥 التقارير حسب المستشفى</div>
    <table>
        <thead>
            <tr>
                <th>المستشفى</th>
                <th>عدد التقارير</th>
                <th>النسبة</th>
            </tr>
        </thead>
        <tbody>
'''
    
    for hospital, count in sorted(stats['by_hospital'].items(), key=lambda x: x[1], reverse=True):
        percentage = (count / stats['total_reports'] * 100) if stats['total_reports'] > 0 else 0
        html += f'''
            <tr>
                <td>{hospital}</td>
                <td>{count}</td>
                <td>{percentage:.1f}%</td>
            </tr>
'''
    
    html += '''
        </tbody>
    </table>
</div>

<!-- صفحة التقارير حسب المترجم -->
<div class="page-break">
    <div class="section-title">👨‍⚕️ التقارير حسب المترجم</div>
    <table>
        <thead>
            <tr>
                <th>المترجم</th>
                <th>عدد التقارير</th>
                <th>النسبة</th>
            </tr>
        </thead>
        <tbody>
'''
    
    for translator, count in sorted(stats['by_translator'].items(), key=lambda x: x[1], reverse=True):
        percentage = (count / stats['total_reports'] * 100) if stats['total_reports'] > 0 else 0
        html += f'''
            <tr>
                <td>{translator}</td>
                <td>{count}</td>
                <td>{percentage:.1f}%</td>
            </tr>
'''
    
    # جدول ملخص نهائي
    html += f'''
        </tbody>
    </table>
</div>

<!-- صفحة الملخص النهائي -->
<div class="page-break">
    <div class="section-title">📊 الملخص التنفيذي النهائي</div>
    <div class="summary-box">
        <h3>ملخص شامل للفترة: {period_name}</h3>
        <div class="summary-grid">
            <div class="summary-item">
                <div class="label">🩺 إجمالي عدد المرضى</div>
                <div class="value">{stats['unique_patients']}</div>
            </div>
            <div class="summary-item">
                <div class="label">📄 إجمالي التقارير</div>
                <div class="value">{stats['total_reports']}</div>
            </div>
            <div class="summary-item">
                <div class="label">🆕 عدد الحالات الجديدة</div>
                <div class="value">{stats.get('new_cases', 0)}</div>
            </div>
            <div class="summary-item">
                <div class="label">🔪 عدد العمليات</div>
                <div class="value">{stats.get('operations', 0)}</div>
            </div>
            <div class="summary-item">
                <div class="label">🔄 عدد المتابعات</div>
                <div class="value">{stats.get('followups', 0)}</div>
            </div>
            <div class="summary-item">
                <div class="label">🏥 عدد المستشفيات</div>
                <div class="value">{len(stats['by_hospital'])}</div>
            </div>
            <div class="summary-item">
                <div class="label">👨‍⚕️ عدد المترجمين</div>
                <div class="value">{len(stats['by_translator'])}</div>
            </div>
            <div class="summary-item">
                <div class="label">📊 أنواع الإجراءات</div>
                <div class="value">{len(stats['by_type'])}</div>
            </div>
        </div>
    </div>
    
    <div style="margin-top: 40px; padding: 20px; background: #e8f4f8; border-radius: 8px; text-align: center;">
        <p style="margin: 0; font-size: 11pt; color: #2c3e50;">
            <strong>تاريخ إنشاء التقرير:</strong> {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
        </p>
        <p style="margin: 5px 0 0 0; font-size: 10pt; color: #7f8c8d;">
            رقم التقرير: {report_number}
        </p>
    </div>
</div>

</body>
</html>
'''
    
    return html

# ================================================
# التسجيل
# ================================================

def register(app):
    """تسجيل معالج الطباعة الاحترافي"""
    
    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🖨️ طباعة التقارير$"), start_professional_printing)
        ],
        states={
            PRINT_SELECT_TYPE: [
                CallbackQueryHandler(handle_print_type_selection, pattern="^print_type:|^print:cancel$")
            ],
            PRINT_SELECT_PERIOD: [
                CallbackQueryHandler(handle_period_selection, pattern="^period:|^back:type|^print:cancel$")
            ],
            PRINT_SELECT_OPTIONS: [
                CallbackQueryHandler(handle_print_options, pattern="^opt:|^generate:now|^back:period|^print:cancel$")
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handle_print_options, pattern="^print:cancel$")
        ],
        name="admin_professional_printing",
        per_chat=True,
        per_user=True,
    )
    
    app.add_handler(conv)

