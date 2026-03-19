# ================================================
# bot/handlers/admin/admin_printing.py
# 🖨️ نظام الطباعة الاحترافي المتكامل
# ================================================

import asyncio
import os
import io
import uuid
import traceback
from datetime import datetime, date, timedelta, time
import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode
from db.session import SessionLocal
from db.models import Report, Patient, Hospital, Department, Translator, TranslatorDirectory
from bot.shared_auth import is_admin
from bot.decorators import admin_handler
from sqlalchemy import func, extract, or_
import matplotlib
matplotlib.use('Agg')  # استخدام backend بدون GUI
import matplotlib.pyplot as plt
from collections import defaultdict

# محاولة استيراد مكتبات العربية (اختيارية)
try:
    from arabic_reshaper import reshape
    from bidi.algorithm import get_display
    ARABIC_SUPPORT = True
except ImportError:
    ARABIC_SUPPORT = False
    print("⚠️ مكتبات العربية غير متوفرة - سيعمل النظام بدونها")

# حالات المحادثة
PRINT_SELECT_TYPE, PRINT_SELECT_PERIOD, PRINT_SELECT_OPTIONS, PRINT_CONFIRM, PRINT_SELECT_PATIENT = range(5)

# المجلدات
EXPORTS_DIR = "exports"
try:
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    # التأكد من أن المجلد قابل للكتابة
    test_file = os.path.join(EXPORTS_DIR, '.test_write')
    try:
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
    except Exception as e:
        print(f"⚠️ تحذير: لا يمكن الكتابة في مجلد {EXPORTS_DIR}: {e}")
except Exception as e:
    print(f"⚠️ تحذير: فشل إنشاء مجلد {EXPORTS_DIR}: {e}")

logger = logging.getLogger(__name__)

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

def generate_simple_html_report(reports, stats, charts_paths, period_name):
    """
    توليد تقرير HTML بسيط يتضمن ملخصًا لأنواع الإجراءات وتقارير المرضى التفصيلية.
    """
    
    # 1. حساب ملخص أنواع الإجراءات
    action_summary = defaultdict(int)
    total_actions = 0
    unique_patients = set()
    unique_hospitals = set()
    
    for report in reports:
        if report.medical_action:
            action_summary[report.medical_action] += 1
            total_actions += 1
        if report.patient_id:
            unique_patients.add(report.patient_id)
        if report.hospital_id:
            unique_hospitals.add(report.hospital_id)
    
    total_patients = len(unique_patients)
    total_hospitals = len(unique_hospitals)
            
    summary_html = f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 12px; margin-bottom: 25px; text-align: center;">
        <h2 style="margin: 0 0 10px 0; color: white;">📊 ملخص التقرير الشامل</h2>
        <div style="display: flex; justify-content: center; gap: 30px; flex-wrap: wrap; margin-top: 15px;">
            <div><strong>إجمالي التقارير:</strong> {len(reports)}</div>
            <div><strong>إجمالي المرضى:</strong> {total_patients}</div>
            <div><strong>عدد المستشفيات:</strong> {total_hospitals}</div>
        </div>
    </div>
    <h2 style="color: #2c3e50;">ملخص الإجراءات الطبية (الإجمالي: {total_actions})</h2>
    """
    if action_summary:
        summary_html += """
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
            <thead>
                <tr style="background-color: #0056b3; color: white;">
                    <th style="padding: 10px; border: 1px solid #ddd; text-align: right;">نوع الإجراء</th>
                    <th style="padding: 10px; border: 1px solid #ddd; text-align: center;">المجموع</th>
                </tr>
            </thead>
            <tbody>
        """
        for action, count in sorted(action_summary.items(), key=lambda x: x[1], reverse=True):
            summary_html += f"""
                <tr>
                    <td style="padding: 10px; border: 1px solid #ddd;">{format_arabic_text(action)}</td>
                    <td style="padding: 10px; border: 1px solid #ddd; text-align: center;"><strong>{count}</strong></td>
                </tr>
            """
        summary_html += "</tbody></table>"
    else:
        summary_html += "<p>لا توجد إجراءات طبية مسجلة في هذه الفترة.</p>"

    # 2. توليد التقارير التفصيلية للمرضى
    detailed_reports_html = "<h2>التقارير التفصيلية للمرضى</h2>"
    if reports:
        for report in reports:
            detailed_reports_html += f"""
            <div style="border: 1px solid #ccc; padding: 10px; margin-bottom: 10px; border-radius: 5px;">
                <h3>تقرير المريض: {format_arabic_text(report.patient_name)}</h3>
                <p><strong>تاريخ التقرير:</strong> {report.report_date.strftime('%Y-%m-%d')}</p>
                <p><strong>الإجراء الطبي:</strong> {format_arabic_text(report.medical_action or 'غير محدد')}</p>
                <p><strong>المستشفى:</strong> {format_arabic_text(report.hospital_name or 'غير محدد')}</p>
                <p><strong>القسم:</strong> {format_arabic_text(report.department_name or 'غير محدد')}</p>
                <p><strong>المترجم:</strong> {format_arabic_text(report.translator_name or 'غير محدد')}</p>
                <p><strong>ملاحظات:</strong> {format_arabic_text(report.notes or 'لا توجد ملاحظات')}</p>
            </div>
            """
    else:
        detailed_reports_html += "<p>لا توجد تقارير مفصلة للمرضى في هذه الفترة.</p>"

    # 3. دمج كل شيء في قالب HTML كامل
    full_html_content = f"""
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>تقرير طبي - {format_arabic_text(period_name)}</title>
        <style>
            body {{ font-family: 'DejaVu Sans', sans-serif; direction: rtl; text-align: right; margin: 20px; background-color: #f4f4f4; color: #333; }}
            h1, h2, h3 {{ color: #0056b3; }}
            .container {{ background-color: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            ul {{ list-style-type: none; padding: 0; }}
            li {{ background-color: #e9ecef; margin-bottom: 5px; padding: 8px; border-radius: 4px; }}
            p strong {{ color: #0056b3; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>تقرير طبي شامل</h1>
            <p><strong>الفترة:</strong> {format_arabic_text(period_name)}</p>
            <p><strong>تاريخ الإنشاء:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            
            {summary_html}
            
            {detailed_reports_html}
            
            <div style="margin-top: 30px; font-size: 0.8em; color: #666;">
                <p>تم إنشاء هذا التقرير بواسطة نظام البوت الآلي.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return full_html_content

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

def generate_statistics(session, reports, start_dt, end_dt):
    """Placeholder for generating statistics."""
    logger.warning("Using placeholder generate_statistics function.")
    return {"total_reports": len(reports), "unique_patients": 0, "total_translators": 0}

def generate_charts(session, reports, start_dt, end_dt):
    """Placeholder for generating charts."""
    logger.warning("Using placeholder generate_charts function.")
    return []

# ================================================
# بدء نظام الطباعة
# ================================================

@admin_handler
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
        [InlineKeyboardButton("🖨️ طباعة حسب المريض", callback_data="print_type:patient_text")],
        [InlineKeyboardButton("🏥 تقرير مستشفى محدد", callback_data="print_type:hospital")],
        [InlineKeyboardButton("👨‍⚕️ تقرير مترجم محدد", callback_data="print_type:translator")],
        [InlineKeyboardButton("📊 تقرير أداء المترجمين", callback_data="print_type:translator_performance")],
        [InlineKeyboardButton("📅 تقرير المواعيد القادمة", callback_data="print_type:upcoming_appointments")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="print:cancel")]
    ])

    await update.message.reply_text(welcome_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return PRINT_SELECT_TYPE

# ================================================
# معالجة اختيار نوع التقرير
# ================================================

@admin_handler
async def handle_print_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار نوع التقرير"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "print:cancel":
        await query.edit_message_text("❌ تم إلغاء الطباعة")
        return ConversationHandler.END
    
    print_type = query.data.split(":")[1]
    context.user_data['print_type'] = print_type

    # ✅ إذا كان النوع هو patient_text، نعرض قائمة المرضى مباشرة
    if print_type == "patient_text":
        context.user_data['print_patient_page'] = 0
        return await show_patient_selection_for_print(query, context)

    # ✅ تقرير أداء المترجمين - ينتقل مباشرة لاختيار الفترة ثم يعرض التقرير
    if print_type == "translator_performance":
        return await show_translator_performance_period(query, context)

    # ✅ تقرير المواعيد القادمة - يعرض مباشرة
    if print_type == "upcoming_appointments":
        return await generate_upcoming_appointments_report(query, context)

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

@admin_handler
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
            [InlineKeyboardButton("🖨️ طباعة حسب المريض", callback_data="print_type:patient_text")],
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

@admin_handler
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
    import logging
    logger = logging.getLogger(__name__)
    
    start_date = context.user_data.get('start_date')
    end_date = context.user_data.get('end_date')
    period_name = context.user_data.get('period_name')
    start_dt, end_dt = normalize_date_range(start_date, end_date)
    
    loop = asyncio.get_running_loop()
    
    try:
        logger.info(f"🖨️ بدء إنشاء التقرير - الفترة: {period_name}, من {start_dt} إلى {end_dt}")
        result = await loop.run_in_executor(
            None,
            _build_report_package,
            start_dt,
            end_dt,
            period_name,
        )
        logger.info(f"✅ تم إنشاء التقرير بنجاح: {result.get('file_path', 'N/A')}")
    except Exception as exc:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"❌ فشل إنشاء التقرير: {exc}\n{error_trace}")
        await query.edit_message_text(
            f"❌ **فشل إنشاء التقرير**\n\n{str(exc)}\n\nيرجى المحاولة مرة أخرى أو التواصل مع الدعم الفني.",
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
        # فلترة حسب المستشفى إذا كان نوع التقرير hospital
        print_type = None
        try:
            import inspect
            frame = inspect.currentframe()
            while frame:
                if 'context' in frame.f_locals:
                    print_type = frame.f_locals['context'].user_data.get('print_type')
                    break
                frame = frame.f_back
        except Exception:
            print_type = None
        # فلترة حسب المستشفى
        if print_type == 'hospital':
            hospital_id = None
            hospital_name = None
            try:
                if 'context' in locals():
                    hospital_id = locals()['context'].user_data.get('hospital_id')
                    hospital_name = locals()['context'].user_data.get('hospital_name')
            except Exception:
                pass
            # إذا كنت تحتاج بيانات من جدول Hospital نفسه (مثلاً تريد استخدام hospital.name من الجدول الأصلي)
            # استخدم join بشكل صحيح مع شرط ON
            need_hospital_fields = False  # غيّر هذا إلى True إذا كنت تحتاج بيانات من جدول Hospital
            if need_hospital_fields:
                query_reports = query_reports.select_from(Report).join(Hospital, Report.hospital_id == Hospital.id)
                if hospital_id:
                    query_reports = query_reports.filter(Hospital.id == hospital_id)
                elif hospital_name:
                    query_reports = query_reports.filter(Hospital.name == hospital_name)
            else:
                if hospital_id:
                    query_reports = query_reports.filter(Report.hospital_id == hospital_id)
                elif hospital_name:
                    query_reports = query_reports.filter(Report.hospital_name == hospital_name)
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
        html_filename = f'report_{unique_key}.html'
        html_path = os.path.join(EXPORTS_DIR, html_filename)
        
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        cleanup_paths.append(html_path)

        return {
            "empty": False,
            "file_path": html_path,
            "filename": html_filename,
            "file_type": "HTML",
            "report_count": len(reports),
            "period_name": period_name,
            "cleanup_paths": cleanup_paths
        }
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
        
        # قراءة محتوى HTML من الملف
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        rtl_css = CSS(string='''
            @page {
                size: A4;
                margin: 1.5cm 2cm 1.5cm 2cm;
            }
            * {
                direction: rtl;
                text-align: right;
            }
            body {
                direction: rtl;
                font-family: 'Arial', 'Tahoma', 'Segoe UI', sans-serif;
                text-align: right;
            }
            table {
                direction: rtl;
                text-align: right;
            }
            th, td {
                text-align: right;
                direction: rtl;
            }
            .stats-grid, .summary-grid {
                direction: rtl;
            }
            .stat-card, .summary-item {
                text-align: right;
                direction: rtl;
            }
        ''')
        
        # استخدام string بدلاً من filename لتجنب مشكلة البحث في templates
        HTML(string=html_content, base_url=os.path.dirname(os.path.abspath(html_path))).write_pdf(pdf_path, stylesheets=[rtl_css])
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
        except ImportError:
            print("⚠️ مكتبة pdfkit غير مثبتة. لتصدير PDF عبر pdfkit، ثبتها بالأمر: pip install pdfkit")
            return False, html_path
        except Exception as pdf_error:
            print(f"⚠️ فشل إنشاء PDF عبر pdfkit: {pdf_error}")
            return False, html_path
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
    
    # التقسيم حسب النوع (الإجراء الطبي)
    medical_actions = {}
    for report in reports:
        action = _infer_medical_action_from_report(report) or 'غير محدد'
        medical_actions[action] = medical_actions.get(action, 0) + 1
    stats['by_action'] = medical_actions
    
    # التقسيم حسب المستشفى
    hospitals = {}
    for report in reports:
        if report.hospital_id:
            hospital_obj = session.query(Hospital).filter_by(id=report.hospital_id).first()
            hospital = hospital_obj.name if hospital_obj and hospital_obj.name else (report.hospital_name or 'غير محدد')
        else:
            hospital = report.hospital_name or 'غير محدد'
        hospitals[hospital] = hospitals.get(hospital, 0) + 1
    stats['by_hospital'] = hospitals
    stats['total_hospitals'] = len(hospitals)
    
    # التقسيم حسب المترجم
    translators = {}
    for report in reports:
        if report.translator_id:
            translator_obj = session.query(Translator).filter_by(id=report.translator_id).first()
            translator = translator_obj.full_name if translator_obj and translator_obj.full_name else (report.translator_name or 'غير محدد')
        else:
            translator = report.translator_name or 'غير محدد'
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
            report_type = _infer_medical_action_from_report(report) or 'غير محدد'
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
            if report.hospital_id:
                hospital_obj = session.query(Hospital).filter_by(id=report.hospital_id).first()
                hospital = hospital_obj.name if hospital_obj and hospital_obj.name else (getattr(report, 'hospital_name', None) or 'غير محدد')
            else:
                hospital = getattr(report, 'hospital_name', None) or 'غير محدد'
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


def _infer_medical_action_from_report(report):
    """حاول استخراج نوع الإجراء من الحقول المتاحة في كائن التقرير.
    الأولوية: الحقل المكرّر `medical_action`، ثم `action` إن وجد، ثم البحث في `doctor_decision` عن كلمات مفتاحية.
    """
    try:
        # حقل مكرّر
        val = None
        if hasattr(report, 'medical_action') and report.medical_action:
            val = str(report.medical_action).strip()
            if val:
                return val

        # بعض الكائنات قد تحتوي على حقل action
        if hasattr(report, 'action') and getattr(report, 'action'):
            val = str(getattr(report, 'action')).strip()
            if val:
                return val

        # محاولة استنتاج من قرار الطبيب
        if hasattr(report, 'doctor_decision') and report.doctor_decision:
            dd = str(report.doctor_decision)
            keywords = ['عملية', 'مراجعة', 'متابعة', 'استشارة', 'ترقيد', 'خروج', 'علاج', 'تنظير']
            for kw in keywords:
                if kw in dd:
                    return kw

    except Exception:
        pass
    return None

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
        
        * {{
            direction: rtl;
            unicode-bidi: embed;
        }}
        
        body {{
            font-family: 'Arial', 'Tahoma', 'Amiri', sans-serif;
            direction: rtl;
            text-align: right;
            color: #2c3e50;
            line-height: 1.8;
            margin: 0;
            padding: 0;
            unicode-bidi: embed;
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
            direction: rtl;
            text-align: right;
        }}
        
        .section-title {{
            font-size: 22pt;
            font-weight: bold;
            color: #2c3e50;
            border-right: 6px solid #3498db;
            border-left: none;
            padding-right: 15px;
            padding-left: 0;
            margin: 30px 0 20px 0;
            page-break-after: avoid;
            text-align: right;
            direction: rtl;
        }}
        
        /* الإحصائيات */
        .stats-container {{
            background: #f8f9fa;
            padding: 25px;
            border-radius: 8px;
            margin: 20px 0;
            border: 2px solid #e8e8e8;
            direction: rtl;
            text-align: right;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin: 20px 0;
            direction: rtl;
        }}
        
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            border-right: 5px solid #3498db;
            border-left: none;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            text-align: right;
            direction: rtl;
        }}
        
        .stat-card h3 {{
            margin: 0 0 10px 0;
            color: #7f8c8d;
            font-size: 12pt;
            font-weight: normal;
            text-align: right;
            direction: rtl;
        }}
        
        .stat-card .number {{
            font-size: 36pt;
            font-weight: bold;
            color: #2c3e50;
            margin: 0;
            text-align: right;
            direction: rtl;
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
            direction: rtl;
        }}
        
        th {{
            background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
            color: white;
            padding: 15px 12px;
            font-weight: bold;
            text-align: right;
            direction: rtl;
            font-size: 11pt;
            border-bottom: 3px solid #2980b9;
        }}
        
        td {{
            padding: 12px;
            border-bottom: 1px solid #ecf0f1;
            text-align: right;
            direction: rtl;
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
            direction: rtl;
        }}
        
        .chart-title {{
            font-size: 16pt;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 20px;
            text-align: center;
            direction: rtl;
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
            direction: rtl;
            text-align: right;
        }}
        
        .summary-box h3 {{
            color: #2c3e50;
            font-size: 18pt;
            margin: 0 0 20px 0;
            text-align: center;
            direction: rtl;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            direction: rtl;
        }}
        
        .summary-item {{
            background: white;
            padding: 15px;
            border-radius: 6px;
            border-right: 4px solid #3498db;
            border-left: none;
            text-align: right;
            direction: rtl;
        }}
        
        .summary-item .label {{
            font-size: 10pt;
            color: #7f8c8d;
            margin-bottom: 5px;
            text-align: right;
            direction: rtl;
        }}
        
        .summary-item .value {{
            font-size: 24pt;
            font-weight: bold;
            color: #2c3e50;
            text-align: right;
            direction: rtl;
        }}
        
        /* كروت تفاصيل التقارير */
        .report-card {
            background: white;
            border: 1px solid #e1e8ed;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 25px;
            page-break-inside: avoid;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            border-right: 6px solid #3498db;
        }
        
        .report-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #f0f4f8;
            padding-bottom: 12px;
            margin-bottom: 15px;
        }
        
        .report-card-title {
            font-size: 14pt;
            font-weight: bold;
            color: #2c3e50;
        }
        
        .report-card-date {
            font-size: 10pt;
            color: #7f8c8d;
        }
        
        .report-card-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }
        
        .report-field {
            font-size: 10pt;
            margin-bottom: 5px;
        }
        
        .report-field strong {
            color: #34495e;
            min-width: 100px;
            display: inline-block;
        }
        
        .report-content {
            margin-top: 15px;
            padding-top: 12px;
            border-top: 1px dashed #ecf0f1;
        }
        
        .report-content h4 {
            margin: 0 0 8px 0;
            color: #2980b9;
            font-size: 11pt;
        }
        
        .report-content p {
            margin: 0;
            white-space: pre-wrap;
            font-size: 10pt;
            color: #34495e;
        }
        
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

<!-- جدول ملخص الإحصائيات حسب نوع الإجراء -->
<div class="section">
    <div class="section-title">📈 ملخص الإحصائيات حسب نوع الإجراء</div>
    <table>
        <thead>
            <tr>
                <th>نوع الإجراء</th>
                <th>العدد</th>
                <th>النسبة المئوية</th>
            </tr>
        </thead>
        <tbody>
'''
    
    for action, count in sorted(stats['by_action'].items(), key=lambda x: x[1], reverse=True):
        percentage = (count / stats['total_reports'] * 100) if stats['total_reports'] > 0 else 0
        html += f'''
            <tr>
                <td>{action}</td>
                <td>{count}</td>
                <td>{percentage:.1f}%</td>
            </tr>
'''
    
    # صف الإجمالي
    html += f'''
            <tr style="background-color: #f1f8ff; font-weight: bold;">
                <td>الإجمالي الكلي</td>
                <td>{stats['total_reports']}</td>
                <td>100%</td>
            </tr>
'''
    
    html += f'''
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
                <div class="value">{len(stats['by_action'])}</div>
            </div>
        </div>
    </div>
</div>
'''

    # إضافة الرسوم البيانية
    html += '''
<!-- الرسوم البيانية -->
<div class="page-break">
    <div class="section-title">📊 الرسوم البيانية والتحليلات</div>
'''
    
    # إضافة الرسوم البيانية مع عناوين
    chart_titles = [
        '📊 التوزيع حسب نوع الإجراء',
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
    
    
    # صفحة تفاصيل التقارير
    html += '''
<div class="page-break">
    <div class="section-title">📋 تفاصيل التقارير الفردية</div>
'''
    
    for i, report in enumerate(reports, 1):
        report_date_str = report.report_date.strftime('%Y-%m-%d %H:%M') if report.report_date else 'غير محدد'
        hospital = report.hospital_name or 'غير محدد'
        translator = report.translator_name or 'غير محدد'
        action = report.medical_action or 'غير محدد'
        patient = report.patient_name or 'غير محدد'
        department = report.department or 'غير محدد'
        doctor = report.doctor_name or 'غير محدد'
        
        html += f'''
    <div class="report-card">
        <div class="report-card-header">
            <div class="report-card-title">#{i} - {patient}</div>
            <div class="report-card-date">{report_date_str}</div>
        </div>
        
        <div class="report-card-grid">
            <div class="report-field"><strong>👤 المريض:</strong> {patient}</div>
            <div class="report-field"><strong>📋 الإجراء:</strong> {action}</div>
            <div class="report-field"><strong>🏥 المستشفى:</strong> {hospital}</div>
            <div class="report-field"><strong>🏢 القسم:</strong> {department}</div>
            <div class="report-field"><strong>👨‍⚕️ الطبيب:</strong> {doctor}</div>
            <div class="report-field"><strong>👨‍⚕️ المترجم:</strong> {translator}</div>
        </div>
'''
        
        # تفاصيل طبية اختيارية
        if report.complaint_text:
            html += f'''
        <div class="report-content">
            <h4>💬 الشكوى:</h4>
            <p>{report.complaint_text}</p>
        </div>
'''
        
        if report.diagnosis:
            html += f'''
        <div class="report-content">
            <h4>🔬 التشخيص:</h4>
            <p>{report.diagnosis}</p>
        </div>
'''

        if report.doctor_decision:
            html += f'''
        <div class="report-content">
            <h4>📝 قرار الطبيب:</h4>
            <p>{report.doctor_decision}</p>
        </div>
'''
            
        if report.treatment_plan:
            html += f'''
        <div class="report-content">
            <h4>💊 خطة العلاج:</h4>
            <p>{report.treatment_plan}</p>
        </div>
'''

        if report.notes:
            html += f'''
        <div class="report-content">
            <h4>📋 ملاحظات إضافية:</h4>
            <p>{report.notes}</p>
        </div>
'''

        html += '    </div>'

    html += '</div>'
    
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
                <div class="value">{len(stats['by_action'])}</div>
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
# طباعة حسب المريض - نظام جديد
# ================================================

async def show_patient_selection_for_print(query, context):
    """عرض قائمة المرضى لاختيار مريض للطباعة"""
    try:
        from services.patients_service import get_all_patients
        
        patients = get_all_patients()
        
        if not patients:
            await query.edit_message_text(
                "⚠️ **لا توجد مرضى في قاعدة البيانات**\n\n"
                "يرجى إضافة مرضى أولاً.",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
        
        # ترتيب المرضى أبجدياً
        patients_sorted = sorted(patients, key=lambda x: x.get('name', ''))
        
        # تقسيم المرضى إلى صفحات (10 لكل صفحة)
        page = context.user_data.get('print_patient_page', 0)
        items_per_page = 10
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        patients_page = patients_sorted[start_idx:end_idx]
        
        keyboard_buttons = []
        
        # أزرار المرضى
        for patient in patients_page:
            patient_name = patient.get('name', 'غير محدد')
            patient_id = patient.get('id')
            keyboard_buttons.append([
                InlineKeyboardButton(
                    f"👤 {patient_name}",
                    callback_data=f"print_patient:{patient_id}"
                )
            ])
        
        # أزرار التنقل
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data="patient_page:prev"))
        if end_idx < len(patients_sorted):
            nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data="patient_page:next"))
        if nav_buttons:
            keyboard_buttons.append(nav_buttons)
        
        # أزرار الإلغاء والرجوع
        # نتحقق من السياق لتحديد نوع الزر (admin_printing أو admin_reports)
        back_callback = "back:type"  # افتراضي لـ admin_printing
        if context.user_data.get("from_admin_reports"):
            back_callback = "back:filter"
        
        keyboard_buttons.append([
            InlineKeyboardButton("🔙 رجوع", callback_data=back_callback),
            InlineKeyboardButton("❌ إلغاء", callback_data="print:cancel")
        ])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        text = f"""
🖨️ **طباعة حسب المريض**

اختر المريض المطلوب:
📊 إجمالي المرضى: {len(patients_sorted)}
📄 الصفحة: {page + 1} من {(len(patients_sorted) + items_per_page - 1) // items_per_page}
"""
        
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        return PRINT_SELECT_PATIENT
        
    except Exception as e:
        logger.error(f"❌ خطأ في عرض قائمة المرضى: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ **حدث خطأ**\n\n{str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END


@admin_handler
async def handle_patient_selection_for_print(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار المريض للطباعة"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back:type":
        # العودة لاختيار النوع (admin_printing)
        welcome_text = """
🖨️ **نظام الطباعة الاحترافي**

اختر نوع التقرير المطلوب:
"""
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 تقرير شامل مع إحصائيات", callback_data="print_type:full_stats")],
            [InlineKeyboardButton("📈 تقرير رسوم بيانية فقط", callback_data="print_type:charts_only")],
            [InlineKeyboardButton("📋 تقرير تفصيلي للتقارير", callback_data="print_type:detailed")],
            [InlineKeyboardButton("👤 تقرير مريض محدد", callback_data="print_type:patient")],
            [InlineKeyboardButton("🖨️ طباعة حسب المريض", callback_data="print_type:patient_text")],
            [InlineKeyboardButton("🏥 تقرير مستشفى محدد", callback_data="print_type:hospital")],
            [InlineKeyboardButton("👨‍⚕️ تقرير مترجم محدد", callback_data="print_type:translator")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="print:cancel")]
        ])

        await query.edit_message_text(welcome_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        return PRINT_SELECT_TYPE
    
    if query.data == "back:filter":
        # العودة لاختيار النوع (admin_reports)
        from bot.handlers.admin.admin_reports import _filters_kb
        await query.edit_message_text("🖨️ اختر نوع الفلترة:", reply_markup=_filters_kb())
        # نستخدم ConversationHandler.END لأن admin_reports سيتعامل مع الحالة
        return ConversationHandler.END
    
    if query.data == "print:cancel":
        await query.edit_message_text("❌ تم إلغاء الطباعة")
        return ConversationHandler.END
    
    if query.data.startswith("patient_page:"):
        # التنقل بين الصفحات
        direction = query.data.split(":")[1]
        current_page = context.user_data.get('print_patient_page', 0)
        if direction == "next":
            context.user_data['print_patient_page'] = current_page + 1
        elif direction == "prev":
            context.user_data['print_patient_page'] = max(0, current_page - 1)
        return await show_patient_selection_for_print(query, context)
    
    if query.data.startswith("print_patient:"):
        # اختيار المريض
        patient_id = int(query.data.split(":")[1])
        context.user_data['selected_patient_id'] = patient_id
        
        await query.edit_message_text("⏳ **جاري تحضير التقرير...**\n\nقد يستغرق هذا بضع ثوانٍ...")
        
        # طباعة تقارير المريض
        return await print_patient_reports_as_text(query, context, patient_id)
    
    return PRINT_SELECT_PATIENT


async def print_patient_reports_as_text(query, context, patient_id):
    """طباعة تقارير المريض كنص منسق داخل Telegram"""
    try:
        with SessionLocal() as session:
            # الحصول على بيانات المريض
            patient = session.query(Patient).filter_by(id=patient_id).first()
            if not patient:
                await query.edit_message_text(
                    "❌ **المريض غير موجود**\n\n"
                    "يرجى المحاولة مرة أخرى.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return ConversationHandler.END
            
            patient_name = patient.full_name or "غير محدد"
            patient_file_number = getattr(patient, 'file_number', None) or getattr(patient, 'file_id', None)
            
            # ✅ الحصول على جميع تقارير المريض - بحث شامل بـ patient_id أو patient_name
            # بعض التقارير قد تحتوي على patient_name فقط بدون patient_id والعكس
            filters_list = [Report.patient_id == patient_id]
            if patient_name and patient_name != "غير محدد":
                # بحث بالاسم الدقيق + بحث بتجاهل المسافات الزائدة
                filters_list.append(Report.patient_name == patient_name)
                filters_list.append(func.trim(Report.patient_name) == patient_name.strip())
            
            reports = session.query(Report).filter(
                or_(*filters_list)
            ).order_by(Report.report_date.desc()).all()
            
            # إزالة التكرار (في حال تطابق أكثر من فلتر لنفس التقرير)
            seen_ids = set()
            unique_reports = []
            for r in reports:
                if r.id not in seen_ids:
                    seen_ids.add(r.id)
                    unique_reports.append(r)
            reports = unique_reports
            
            if not reports:
                await query.edit_message_text(
                    f"⚠️ **لا توجد تقارير**\n\n"
                    f"لا توجد تقارير للمريض: {patient_name}",
                    parse_mode=ParseMode.MARKDOWN
                )
                return ConversationHandler.END
            
            # حساب الإحصائيات
            total_reports = len(reports)
            
            # الفترة الزمنية
            dates = [r.report_date for r in reports if r.report_date]
            if dates:
                first_date = min(dates)
                last_date = max(dates)
                period_text = f"من {first_date.strftime('%d-%m-%Y')} إلى {last_date.strftime('%d-%m-%Y')}"
            else:
                period_text = "غير محدد"
            
            # إحصائيات حسب نوع الإجراء والمستشفى
            action_stats = {}
            hospitals = set()
            for report in reports:
                action = report.medical_action or "غير محدد"
                action_stats[action] = action_stats.get(action, 0) + 1
                if report.hospital_name:
                    hospitals.add(report.hospital_name)
            
            # بناء النص
            text_parts = []

            # 1. رأس التقرير الاحترافي
            header = f"""
╔══════════════════════════════════════╗
        🏥 **التقرير الطبي الشامل**
╚══════════════════════════════════════╝

┌──────── 👤 بيانات المريض ────────┐
│
│  📛 **الاسم:** {patient_name}
"""
            if patient_file_number:
                header += f"│  📁 **رقم الملف:** {patient_file_number}\n"

            header += f"""│
│  📊 **إجمالي التقارير:** {total_reports} تقرير
│  🏥 **عدد المستشفيات:** {len(hospitals)}
│  📅 **الفترة:** {period_text}
│
└─────────────────────────────────────┘
"""
            text_parts.append(header)

            # 2. إحصائيات سريعة بشكل احترافي
            stats_text = """
┌──────── 📈 إحصائيات الإجراءات ────────┐
│
"""
            total_actions_count = 0
            for action, count in sorted(action_stats.items(), key=lambda x: x[1], reverse=True):
                stats_text += f"│  🔹 **{action}:** {count}\n"
                total_actions_count += count
            
            stats_text += f"""│
│  ✅ **الإجمالي:** {total_actions_count} إجراء
└─────────────────────────────────────┘
"""
            text_parts.append(stats_text)
            
            # 3. تفاصيل التقارير (مرتبة زمنياً - الأحدث أولاً)
            text_parts.append("📋 **تفاصيل التقارير:**\n\n")
            
            for idx, report in enumerate(reports, 1):
                report_text = format_report_as_text(report, idx, total_reports)
                text_parts.append(report_text)
                text_parts.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n")
            
            # دمج النصوص وإرسالها
            full_text = "".join(text_parts)
            
            # تقسيم النص إذا كان طويلاً (Telegram limit: 4096 chars)
            max_length = 4000  # ترك هامش للأمان
            
            if len(full_text) <= max_length:
                await query.edit_message_text(full_text, parse_mode=ParseMode.MARKDOWN)
            else:
                # إرسال الرأس والإحصائيات أولاً
                header_and_stats = header + stats_text
                await query.edit_message_text(header_and_stats, parse_mode=ParseMode.MARKDOWN)
                
                # إرسال التقارير في رسائل منفصلة
                current_text = "📋 **تفاصيل التقارير:**\n\n"
                
                for idx, report in enumerate(reports, 1):
                    report_text = format_report_as_text(report, idx, total_reports)
                    
                    # إذا كان النص الحالي + التقرير الجديد > الحد الأقصى، أرسل النص الحالي وابدأ جديد
                    if len(current_text) + len(report_text) + 50 > max_length:
                        await query.message.reply_text(current_text, parse_mode=ParseMode.MARKDOWN)
                        current_text = report_text + "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    else:
                        current_text += report_text + "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                
                # إرسال آخر جزء
                if current_text.strip():
                    await query.message.reply_text(current_text, parse_mode=ParseMode.MARKDOWN)
            
            return ConversationHandler.END
            
    except Exception as e:
        logger.error(f"❌ خطأ في طباعة تقارير المريض: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ **حدث خطأ**\n\n{str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END


def format_report_as_text(report, index, total):
    """تنسيق تقرير واحد كنص احترافي حسب نوع الإجراء - يعرض فقط الحقول المتاحة"""

    # نوع الإجراء مع شارة ملونة
    medical_action = report.medical_action or "غير محدد"

    # اختيار الأيقونة حسب نوع الإجراء
    action_icons = {
        "استشارة جديدة": "🆕",
        "متابعة في الرقود": "🏥",
        "مراجعة / عودة دورية": "🔄",
        "طوارئ": "🚨",
        "عملية": "⚕️",
        "ترقيد": "🛏️",
        "خروج من المستشفى": "🚪",
        "أشعة وفحوصات": "🔬",
        "تأجيل موعد": "📅",
        "علاج طبيعي": "💪",
        "أجهزة تعويضية": "🦿",
    }
    action_icon = action_icons.get(medical_action, "📋")

    # بناء الرأس المميز
    text = f"""
╔══════════════════════════════════════╗
       {action_icon} **تقرير #{index} من {total}**
╚══════════════════════════════════════╝

"""

    # القسم الأول: المعلومات الأساسية
    text += "📌 **المعلومات الأساسية:**\n"
    text += "┌─────────────────────────────────┐\n"
    
    # ✅ اسم المريض - مباشرة من حقل patient_name في التقرير
    if report.patient_name:
        text += f"│ 👤 **اسم المريض:** {report.patient_name}\n"
    
    text += f"│ 📋 **نوع الإجراء:** {medical_action}\n"

    if report.report_date:
        text += f"│ 📅 **التاريخ:** {report.report_date.strftime('%d-%m-%Y')} الساعة {report.report_date.strftime('%H:%M')}\n"

    if report.hospital_name:
        text += f"│ 🏥 **المستشفى:** {report.hospital_name}\n"

    if report.department:
        text += f"│ 🏢 **القسم:** {report.department}\n"

    if report.doctor_name:
        text += f"│ 👨‍⚕️ **الطبيب:** {report.doctor_name}\n"

    text += "└─────────────────────────────────┘\n\n"

    # القسم الثاني: التفاصيل الطبية
    has_medical_details = (report.complaint_text or report.diagnosis or report.doctor_decision)
    if has_medical_details:
        text += "🩺 **التفاصيل الطبية:**\n"
        text += "┌─────────────────────────────────┐\n"

        if report.complaint_text:
            text += f"│ 💬 **الشكوى:**\n│    {report.complaint_text}\n│\n"

        if report.diagnosis:
            text += f"│ 🔬 **التشخيص:**\n│    {report.diagnosis}\n│\n"

        if report.doctor_decision:
            text += f"│ 📝 **قرار الطبيب:**\n│    {report.doctor_decision}\n"

        text += "└─────────────────────────────────┘\n\n"

    # القسم الثالث: معلومات إضافية حسب نوع الإجراء
    action = medical_action
    has_extra = False
    extra_text = ""

    # متابعة في الرقود - رقم الغرفة
    if "متابعة" in action and report.room_number:
        extra_text += f"│ 🚪 **رقم الغرفة/الطابق:** {report.room_number}\n"
        has_extra = True

    # طوارئ - رقم الغرفة
    if "طوارئ" in action and report.room_number:
        extra_text += f"│ 🚪 **رقم غرفة الطوارئ:** {report.room_number}\n"
        has_extra = True

    # حالة المريض
    if report.case_status:
        extra_text += f"│ 📊 **حالة المريض:** {report.case_status}\n"
        has_extra = True

    # خطة العلاج
    if report.treatment_plan:
        extra_text += f"│ 💊 **خطة العلاج:**\n│    {report.treatment_plan}\n"
        has_extra = True

    # الأدوية
    if report.medications:
        extra_text += f"│ 💉 **الأدوية:**\n│    {report.medications}\n"
        has_extra = True

    # ملاحظات عامة
    if report.notes:
        extra_text += f"│ 📋 **ملاحظات:**\n│    {report.notes}\n"
        has_extra = True

    # حقول الأشعة والفحوصات
    if "أشعة" in action or "فحوصات" in action:
        if report.radiology_type:
            extra_text += f"│ 🔬 **نوع الأشعة:** {report.radiology_type}\n"
            has_extra = True
        if report.radiology_delivery_date:
            extra_text += f"│ 📅 **تاريخ الاستلام:** {report.radiology_delivery_date.strftime('%d-%m-%Y')}\n"
            has_extra = True

    # حقول تأجيل الموعد
    if "تأجيل" in action:
        if report.app_reschedule_reason:
            extra_text += f"│ 📝 **سبب التأجيل:** {report.app_reschedule_reason}\n"
            has_extra = True
        if report.app_reschedule_return_date:
            extra_text += f"│ 📅 **الموعد الجديد:** {report.app_reschedule_return_date.strftime('%d-%m-%Y')}\n"
            has_extra = True
        if report.app_reschedule_return_reason:
            extra_text += f"│ ✍️ **سبب العودة:** {report.app_reschedule_return_reason}\n"
            has_extra = True

    if has_extra:
        text += "ℹ️ **معلومات إضافية:**\n"
        text += "┌─────────────────────────────────┐\n"
        text += extra_text
        text += "└─────────────────────────────────┘\n\n"

    # القسم الرابع: موعد المتابعة
    if report.followup_date or report.followup_reason:
        text += "📆 **موعد المتابعة:**\n"
        text += "┌─────────────────────────────────┐\n"

        if report.followup_date:
            text += f"│ 📅 **تاريخ العودة:** {report.followup_date.strftime('%d-%m-%Y')}\n"
            if report.followup_time:
                text += f"│ 🕐 **الوقت:** {report.followup_time}\n"

        if report.followup_reason:
            text += f"│ ✍️ **السبب:** {report.followup_reason}\n"

        text += "└─────────────────────────────────┘\n\n"

    # القسم الأخير: المترجم
    if report.translator_name:
        text += f"👤 **المترجم المسؤول:** {report.translator_name}\n"

    return text


# ================================================
# 📊 تقرير أداء المترجمين
# ================================================

PRINT_TRANSLATOR_PERFORMANCE_PERIOD = 10  # حالة جديدة

async def show_translator_performance_period(query, context):
    """عرض خيارات الفترة الزمنية لتقرير أداء المترجمين"""
    period_text = """
📊 **تقرير أداء المترجمين**

اختر الفترة الزمنية للتقرير:
"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 اليوم", callback_data="perf_period:today")],
        [InlineKeyboardButton("📅 هذا الأسبوع", callback_data="perf_period:week")],
        [InlineKeyboardButton("📅 هذا الشهر", callback_data="perf_period:month")],
        [InlineKeyboardButton("📅 آخر 3 أشهر", callback_data="perf_period:3months")],
        [InlineKeyboardButton("📅 هذه السنة", callback_data="perf_period:year")],
        [InlineKeyboardButton("📅 الكل", callback_data="perf_period:all")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back:type")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="print:cancel")]
    ])

    await query.edit_message_text(period_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return PRINT_TRANSLATOR_PERFORMANCE_PERIOD


@admin_handler
async def handle_translator_performance_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار فترة تقرير أداء المترجمين"""
    query = update.callback_query
    await query.answer()

    if query.data == "print:cancel":
        await query.edit_message_text("❌ تم إلغاء الطباعة")
        return ConversationHandler.END

    if query.data == "back:type":
        # العودة للقائمة الرئيسية
        welcome_text = """
🖨️ **نظام الطباعة الاحترافي**

اختر نوع التقرير المطلوب:
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 تقرير شامل مع إحصائيات", callback_data="print_type:full_stats")],
            [InlineKeyboardButton("📈 تقرير رسوم بيانية فقط", callback_data="print_type:charts_only")],
            [InlineKeyboardButton("📋 تقرير تفصيلي للتقارير", callback_data="print_type:detailed")],
            [InlineKeyboardButton("👤 تقرير مريض محدد", callback_data="print_type:patient")],
            [InlineKeyboardButton("🖨️ طباعة حسب المريض", callback_data="print_type:patient_text")],
            [InlineKeyboardButton("🏥 تقرير مستشفى محدد", callback_data="print_type:hospital")],
            [InlineKeyboardButton("👨‍⚕️ تقرير مترجم محدد", callback_data="print_type:translator")],
            [InlineKeyboardButton("📊 تقرير أداء المترجمين", callback_data="print_type:translator_performance")],
            [InlineKeyboardButton("📅 تقرير المواعيد القادمة", callback_data="print_type:upcoming_appointments")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="print:cancel")]
        ])
        await query.edit_message_text(welcome_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        return PRINT_SELECT_TYPE

    # تحديد الفترة الزمنية
    period = query.data.split(":")[1]
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

    await query.edit_message_text("⏳ **جاري إنشاء تقرير أداء المترجمين...**")

    # إنشاء التقرير
    return await generate_translator_performance_report(query, context, start_date, end_date, period_name)


async def generate_translator_performance_report(query, context, start_date, end_date, period_name):
    """إنشاء تقرير أداء المترجمين - يستخدم stats_service كمصدر وحيد"""
    try:
        from services.stats_service import get_translator_stats

        with SessionLocal() as session:
            # ═══ المصدر الوحيد: stats_service ═══
            if start_date and end_date:
                stats_results = get_translator_stats(session, start_date, end_date)
            else:
                # كل الفترات
                from datetime import datetime as dt
                stats_results = get_translator_stats(session, dt(2020, 1, 1).date(), date.today())

            if not stats_results:
                await query.edit_message_text(
                    f"⚠️ **لا توجد تقارير**\n\n"
                    f"لا توجد تقارير في الفترة: {period_name}",
                    parse_mode=ParseMode.MARKDOWN
                )
                return ConversationHandler.END

            total_reports = sum(s['total_reports'] for s in stats_results)
            total_late = sum(s['late_reports'] for s in stats_results)

            header = f"""
╔══════════════════════════════════════╗
     📊 **تقرير أداء المترجمين**
╚══════════════════════════════════════╝

📅 **الفترة:** {period_name}
📄 **إجمالي التقارير:** {total_reports}
🕐 **تقارير بعد 8 مساءً:** {total_late}
👥 **عدد المترجمين:** {len(stats_results)}

"""

            details = ""
            for rank, s in enumerate(stats_results, 1):
                percentage = (s['total_reports'] / total_reports * 100) if total_reports > 0 else 0
                bar_length = int(percentage / 10)
                bar = "█" * bar_length + "░" * (10 - bar_length)

                # أكثر نوع إجراء
                non_zero_actions = {k: v for k, v in s.get('action_breakdown', {}).items() if v > 0}
                top_action = max(non_zero_actions.items(), key=lambda x: x[1])[0] if non_zero_actions else "—"

                if rank == 1: medal = "🥇"
                elif rank == 2: medal = "🥈"
                elif rank == 3: medal = "🥉"
                else: medal = f"#{rank}"

                details += f"""
┌──────────────────────────────────────
│ {medal} **{s['translator_name']}**
├──────────────────────────────────────
│ 📊 التقارير: **{s['total_reports']}** ({percentage:.1f}%)
│ {bar}
│
│ 📋 أكثر إجراء: {top_action}
│ 📅 أيام الحضور: {s['attendance_days']}/{s['work_days']} يوم
│ 🕐 بعد 8 مساءً: {s['late_reports']}
└──────────────────────────────────────

"""

            full_report = header + details
            max_length = 4000

            if len(full_report) <= max_length:
                await query.edit_message_text(full_report, parse_mode=ParseMode.MARKDOWN)
            else:
                await query.edit_message_text(header, parse_mode=ParseMode.MARKDOWN)

                current_text = ""
                for rank, s in enumerate(stats_results, 1):
                    percentage = (s['total_reports'] / total_reports * 100) if total_reports > 0 else 0
                    bar_length = int(percentage / 10)
                    bar = "█" * bar_length + "░" * (10 - bar_length)
                    non_zero_actions = {k: v for k, v in s.get('action_breakdown', {}).items() if v > 0}
                    top_action = max(non_zero_actions.items(), key=lambda x: x[1])[0] if non_zero_actions else "—"

                    translator_text = f"""
┌──────────────────────────────────────
│ **{s['translator_name']}**
│ 📊 التقارير: **{s['total_reports']}** ({percentage:.1f}%)
│ {bar}
│ 📋 أكثر إجراء: {top_action}
│ 📅 أيام الحضور: {s['attendance_days']}/{s['work_days']} يوم
│ 🕐 بعد 8 مساءً: {s['late_reports']}
└──────────────────────────────────────

"""
                    if len(current_text) + len(translator_text) > max_length:
                        await query.message.reply_text(current_text, parse_mode=ParseMode.MARKDOWN)
                        current_text = translator_text
                    else:
                        current_text += translator_text

                if current_text.strip():
                    await query.message.reply_text(current_text, parse_mode=ParseMode.MARKDOWN)

            return ConversationHandler.END

    except Exception as e:
        logger.error(f"❌ خطأ في تقرير أداء المترجمين: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ **حدث خطأ**\n\n{str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END


# ================================================
# 📅 تقرير المواعيد القادمة
# ================================================

async def generate_upcoming_appointments_report(query, context):
    """إنشاء تقرير المواعيد القادمة"""
    try:
        await query.edit_message_text("⏳ **جاري جلب المواعيد القادمة...**")

        with SessionLocal() as session:
            today = date.today()
            next_30_days = today + timedelta(days=30)

            # جلب التقارير التي لها مواعيد متابعة قادمة
            reports = session.query(Report).filter(
                Report.followup_date.isnot(None),
                Report.followup_date >= today,
                Report.followup_date <= next_30_days
            ).order_by(Report.followup_date.asc()).all()

            if not reports:
                await query.edit_message_text(
                    "⚠️ **لا توجد مواعيد قادمة**\n\n"
                    "لا توجد مواعيد متابعة في الـ 30 يوم القادمة.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return ConversationHandler.END

            # تجميع المواعيد حسب التاريخ
            appointments_by_date = {}
            for report in reports:
                date_key = report.followup_date.strftime('%Y-%m-%d')
                if date_key not in appointments_by_date:
                    appointments_by_date[date_key] = []
                appointments_by_date[date_key].append(report)

            # بناء نص التقرير
            header = f"""
╔══════════════════════════════════════╗
      📅 **المواعيد القادمة**
╚══════════════════════════════════════╝

📊 **إجمالي المواعيد:** {len(reports)} موعد
📆 **الفترة:** من اليوم حتى {next_30_days.strftime('%d-%m-%Y')}

"""

            details = ""

            for date_str, day_reports in sorted(appointments_by_date.items()):
                appointment_date = datetime.strptime(date_str, '%Y-%m-%d')
                day_name = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"][appointment_date.weekday()]

                # حساب عدد الأيام المتبقية
                days_remaining = (appointment_date.date() - today).days

                if days_remaining == 0:
                    remaining_text = "🔴 اليوم"
                elif days_remaining == 1:
                    remaining_text = "🟠 غداً"
                elif days_remaining <= 3:
                    remaining_text = f"🟡 بعد {days_remaining} أيام"
                else:
                    remaining_text = f"🟢 بعد {days_remaining} يوم"

                details += f"""
┌──────── 📅 {day_name} {appointment_date.strftime('%d-%m-%Y')} ────────
│ {remaining_text} - {len(day_reports)} موعد
├─────────────────────────────────────
"""

                for report in day_reports:
                    patient_name = "غير محدد"
                    if report.patient_id:
                        patient = session.query(Patient).filter_by(id=report.patient_id).first()
                        if patient:
                            patient_name = patient.full_name or "غير محدد"

                    time_str = report.followup_time or "—"
                    hospital = report.hospital_name or "—"
                    reason = report.followup_reason or "—"

                    details += f"""│ 👤 {patient_name}
│    🕐 {time_str} | 🏥 {hospital}
│    ✍️ {reason[:50]}{'...' if len(reason) > 50 else ''}
│
"""

                details += "└─────────────────────────────────────\n"

            # دمج التقرير
            full_report = header + details

            # تقسيم الرسالة إذا كانت طويلة
            max_length = 4000

            if len(full_report) <= max_length:
                await query.edit_message_text(full_report, parse_mode=ParseMode.MARKDOWN)
            else:
                await query.edit_message_text(header, parse_mode=ParseMode.MARKDOWN)

                current_text = ""
                for date_str, day_reports in sorted(appointments_by_date.items()):
                    appointment_date = datetime.strptime(date_str, '%Y-%m-%d')
                    day_name = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"][appointment_date.weekday()]
                    days_remaining = (appointment_date.date() - today).days

                    if days_remaining == 0:
                        remaining_text = "🔴 اليوم"
                    elif days_remaining == 1:
                        remaining_text = "🟠 غداً"
                    elif days_remaining <= 3:
                        remaining_text = f"🟡 بعد {days_remaining} أيام"
                    else:
                        remaining_text = f"🟢 بعد {days_remaining} يوم"

                    day_text = f"""
┌──────── 📅 {day_name} {appointment_date.strftime('%d-%m-%Y')} ────────
│ {remaining_text} - {len(day_reports)} موعد
├─────────────────────────────────────
"""
                    for report in day_reports:
                        patient_name = "غير محدد"
                        if report.patient_id:
                            patient = session.query(Patient).filter_by(id=report.patient_id).first()
                            if patient:
                                patient_name = patient.full_name or "غير محدد"

                        time_str = report.followup_time or "—"
                        hospital = report.hospital_name or "—"
                        reason = report.followup_reason or "—"

                        day_text += f"""│ 👤 {patient_name}
│    🕐 {time_str} | 🏥 {hospital}
│    ✍️ {reason[:50]}{'...' if len(reason) > 50 else ''}
│
"""
                    day_text += "└─────────────────────────────────────\n"

                    if len(current_text) + len(day_text) > max_length:
                        await query.message.reply_text(current_text, parse_mode=ParseMode.MARKDOWN)
                        current_text = day_text
                    else:
                        current_text += day_text

                if current_text.strip():
                    await query.message.reply_text(current_text, parse_mode=ParseMode.MARKDOWN)

            return ConversationHandler.END

    except Exception as e:
        logger.error(f"❌ خطأ في تقرير المواعيد القادمة: {e}", exc_info=True)
        await query.edit_message_text(
            f"❌ **حدث خطأ**\n\n{str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END


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
            PRINT_SELECT_PATIENT: [
                CallbackQueryHandler(handle_patient_selection_for_print, pattern="^print_patient:|^patient_page:|^back:type|^print:cancel$")
            ],
            # ✅ حالة تقرير أداء المترجمين
            PRINT_TRANSLATOR_PERFORMANCE_PERIOD: [
                CallbackQueryHandler(handle_translator_performance_period, pattern="^perf_period:|^back:type|^print:cancel$")
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
