# ================================================
# bot/handlers/admin/admin_evaluation.py
# 🔹 نظام تقييم المترجمين
# ================================================

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler, filters, CommandHandler
from telegram.constants import ParseMode
import os
from datetime import datetime, date, time
from db.session import SessionLocal
from db.models import (
    TranslatorEvaluation, MonthlyEvaluation, Report, Translator,
    DailyReportTracking
)
from bot.shared_auth import is_admin
from bot.keyboards import admin_main_kb
import logging

logger = logging.getLogger(__name__)

# حالات المحادثة
SELECT_EVALUATION_TYPE, SELECT_TRANSLATOR, SELECT_MONTH, CONFIRM_EVALUATION, MANUAL_EVALUATION = range(5)

async def start_evaluation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء نظام التقييم"""
    user = update.effective_user
    
    # التحقق من أن المستخدم أدمن
    if not is_admin(user.id):
        await update.message.reply_text("🚫 هذه الخاصية مخصصة للإدمن فقط.")
        return ConversationHandler.END

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 تقييم شهري تلقائي", callback_data="eval:monthly_auto")],
        [InlineKeyboardButton("📝 تقييم يدوي", callback_data="eval:manual")],
        [InlineKeyboardButton("📈 عرض التقييمات", callback_data="eval:view")],
        [InlineKeyboardButton("🏆 ترتيب المترجمين", callback_data="eval:ranking")]
    ])

    await update.message.reply_text(
        "📊 **نظام تقييم المترجمين**\n\n"
        "اختر نوع التقييم:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def generate_monthly_evaluation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """توليد التقييم الشهري التلقائي"""
    query = update.callback_query
    await query.answer()
    
    # إنشاء الجداول إذا لم تكن موجودة
    try:
        from db.models import Base
        from db.session import engine
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"⚠️ تحذير في إنشاء الجداول: {e}")
    
    current_date = date.today()
    current_year = current_date.year
    
    # عرض السنوات المتاحة (آخر 3 سنوات)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📅 {current_year}", callback_data=f"year:{current_year}")],
        [InlineKeyboardButton(f"📅 {current_year-1}", callback_data=f"year:{current_year-1}")],
        [InlineKeyboardButton(f"📅 {current_year-2}", callback_data=f"year:{current_year-2}")],
        [InlineKeyboardButton("📄 الكل", callback_data="year:all")],
        [InlineKeyboardButton("🔙 العودة", callback_data="back_to_eval")]
    ])
    
    await query.edit_message_text(
        f"📊 **التقييم الشهري التلقائي**\n\n"
        f"اختر السنة المراد تقييمها:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_year_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار السنة"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_eval":
        return await start_evaluation(update, context)
    
    parts = query.data.split(":")
    year_choice = parts[1]
    
    if year_choice == "all":
        # عرض جميع السنوات المتاحة
        await show_all_years_evaluation(update, context)
    else:
        year = int(year_choice)
        # عرض شهور السنة المختارة
        await show_year_months(update, context, year)

async def show_year_months(update: Update, context: ContextTypes.DEFAULT_TYPE, year: int):
    """عرض شهور السنة المختارة"""
    query = update.callback_query
    
    # أسماء الشهور بالعربية
    month_names = {
        1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل",
        5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس",
        9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"
    }
    
    # إنشاء لوحة الشهور في صفوف من 3 أشهر
    keyboard = []
    for i in range(0, 12, 3):  # كل 3 أشهر في صف
        row = []
        for j in range(3):
            month_num = i + j + 1
            if month_num <= 12:
                month_name = month_names[month_num]
                row.append(InlineKeyboardButton(
                    f"📅 {month_name}", 
                    callback_data=f"month:{year}:{month_num}"
                ))
        keyboard.append(row)
    
    # إضافة خيار "الكل" للشهور
    keyboard.append([InlineKeyboardButton("📄 الكل", callback_data=f"month:{year}:all")])
    keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="back_to_eval")])
    
    await query.edit_message_text(
        f"📊 **التقييم الشهري - {year}**\n\n"
        f"اختر الشهر المراد تقييمه:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def show_all_years_evaluation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض تقييم جميع السنوات"""
    query = update.callback_query
    
    with SessionLocal() as s:
        # جلب جميع السنوات المتاحة
        years = s.query(MonthlyEvaluation.year).distinct().order_by(MonthlyEvaluation.year.desc()).all()
        
        if not years:
            await query.edit_message_text("⚠️ لا توجد تقييمات متاحة.")
            return
        
        # إنشاء لوحة السنوات
        keyboard = []
        for year_tuple in years:
            year = year_tuple[0]
            keyboard.append([InlineKeyboardButton(
                f"📅 {year}", 
                callback_data=f"year:{year}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="back_to_eval")])
        
        await query.edit_message_text(
            f"📊 **التقييم الشهري - جميع السنوات**\n\n"
            f"اختر السنة المراد تقييمها:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_month_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار الشهر"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_eval":
        return await start_evaluation(update, context)
    
    parts = query.data.split(":")
    year = int(parts[1])
    month_choice = parts[2]
    
    if month_choice == "all":
        # توليد التقييم لجميع شهور السنة
        await generate_yearly_report(update, context, year)
    else:
        month = int(month_choice)
        # توليد التقييم الشهري
        await generate_monthly_report(update, context, year, month)

async def generate_monthly_report(update: Update, context: ContextTypes.DEFAULT_TYPE, year: int, month: int):
    """توليد تقرير التقييم الشهري"""
    query = update.callback_query
    
    with SessionLocal() as s:
        # جلب جميع المترجمين من الجدول
        from sqlalchemy import func
        translator_names = s.query(DailyReportTracking.translator_name).filter(
            DailyReportTracking.date >= date(year, month, 1),
            DailyReportTracking.date < date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)
        ).distinct().all()
        
        # تحويل إلى قائمة أسماء
        translator_names_list = [name[0] for name in translator_names if name[0]]
        
        if not translator_names_list:
            await query.edit_message_text("⚠️ لا توجد بيانات للمترجمين في هذا الشهر.")
            return
        
        # محاولة إضافة translator_id إذا لم يكن موجوداً
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(s.bind)
            drt_columns = [col['name'] for col in inspector.get_columns('daily_report_tracking')]
            if 'translator_id' not in drt_columns:
                try:
                    s.execute(text("ALTER TABLE daily_report_tracking ADD COLUMN translator_id INTEGER"))
                    s.commit()
                    logger.info("✅ Added translator_id column to daily_report_tracking")
                except Exception as alter_error:
                    logger.warning(f"⚠️ Could not add translator_id: {alter_error}")
                    s.rollback()
        except Exception as inspect_error:
            logger.warning(f"⚠️ Could not inspect daily_report_tracking: {inspect_error}")
        
        # جلب سجلات لكل مترجم - استخدام query محدود
        translators = []
        for name in translator_names_list:
            try:
                # استخدام query محدود بدون translator_id
                record = s.query(
                    DailyReportTracking.id,
                    DailyReportTracking.translator_name,
                    DailyReportTracking.date,
                    DailyReportTracking.expected_reports,
                    DailyReportTracking.actual_reports,
                    DailyReportTracking.is_completed,
                    DailyReportTracking.reminder_sent,
                    DailyReportTracking.created_at
                ).filter(
                    DailyReportTracking.translator_name == name,
                    DailyReportTracking.date >= date(year, month, 1),
                    DailyReportTracking.date < date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)
                ).first()
                if record:
                    # إنشاء كائن بسيط
                    class SimpleRecord:
                        def __init__(self, translator_name):
                            self.translator_name = translator_name
                    translators.append(SimpleRecord(name))
            except Exception as query_error:
                logger.warning(f"⚠️ Error querying translator {name}: {query_error}")
                # استخدام كائن بسيط
                class SimpleRecord:
                    def __init__(self, translator_name):
                        self.translator_name = translator_name
                translators.append(SimpleRecord(name))
        
        evaluation_results = []
        
        for translator_record in translators:
            translator_name = translator_record.translator_name
            
            # جلب جميع سجلات المترجم في الشهر
            monthly_records = s.query(DailyReportTracking).filter(
                DailyReportTracking.translator_name == translator_name,
                DailyReportTracking.date >= date(year, month, 1),
                DailyReportTracking.date < date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)
            ).all()
            
            # جلب التقارير الفعلية للمترجم
            # Translator هو alias لـ User
            translator = s.query(Translator).filter_by(full_name=translator_name).first()
            if translator:
                reports = s.query(Report).filter(
                    Report.translator_id == translator.id,
                    Report.report_date >= datetime(year, month, 1),
                    Report.report_date < datetime(year, month + 1, 1) if month < 12 else datetime(year + 1, 1, 1)
                ).all()
            else:
                # محاولة البحث باستخدام translator_name مباشرة من DailyReportTracking
                reports = []
            
            # حساب النقاط
            total_reports = len(monthly_records)
            on_time_reports = sum(1 for r in monthly_records if r.is_completed and not r.reminder_sent)
            late_reports = total_reports - on_time_reports
            
            # نقاط التوقيت (40%)
            if total_reports > 0:
                timing_ratio = on_time_reports / total_reports
                if timing_ratio >= 0.9:
                    timing_points = 10
                elif timing_ratio >= 0.7:
                    timing_points = 7
                elif timing_ratio >= 0.5:
                    timing_points = 5
                else:
                    timing_points = 2
            else:
                timing_points = 0
            
            # نقاط الانتظام (30%)
            if total_reports > 0:
                regularity_ratio = sum(1 for r in monthly_records if r.is_completed) / total_reports
                if regularity_ratio >= 0.9:
                    regularity_points = 10
                elif regularity_ratio >= 0.8:
                    regularity_points = 7
                elif regularity_ratio >= 0.6:
                    regularity_points = 5
                else:
                    regularity_points = 2
            else:
                regularity_points = 0
            
            # نقاط الجودة (30%) - افتراضياً 7 نقاط، يمكن تعديلها يدوياً
            quality_points = 7
            
            total_points = timing_points + quality_points + regularity_points
            
            # تحديد التقييم النهائي
            if total_points >= 27:
                final_rating = 5
                performance_level = "ممتاز"
            elif total_points >= 24:
                final_rating = 4
                performance_level = "جيد جداً"
            elif total_points >= 21:
                final_rating = 3
                performance_level = "جيد"
            elif total_points >= 18:
                final_rating = 2
                performance_level = "مقبول"
            else:
                final_rating = 1
                performance_level = "ضعيف"
            
            # حفظ التقييم الشهري
            existing_eval = s.query(MonthlyEvaluation).filter_by(
                translator_name=translator_name,
                year=year,
                month=month
            ).first()
            
            if existing_eval:
                # تحديث التقييم الموجود
                existing_eval.total_reports = total_reports
                existing_eval.on_time_reports = on_time_reports
                existing_eval.late_reports = late_reports
                existing_eval.timing_points = timing_points
                existing_eval.quality_points = quality_points
                existing_eval.regularity_points = regularity_points
                existing_eval.total_points = total_points
                existing_eval.final_rating = final_rating
                existing_eval.performance_level = performance_level
                existing_eval.updated_at = datetime.now()
            else:
                # إنشاء تقييم جديد
                monthly_eval = MonthlyEvaluation(
                    translator_name=translator_name,
                    year=year,
                    month=month,
                    total_reports=total_reports,
                    on_time_reports=on_time_reports,
                    late_reports=late_reports,
                    timing_points=timing_points,
                    quality_points=quality_points,
                    regularity_points=regularity_points,
                    total_points=total_points,
                    final_rating=final_rating,
                    performance_level=performance_level
                )
                s.add(monthly_eval)
            
            evaluation_results.append({
                'name': translator_name,
                'total_points': total_points,
                'rating': final_rating,
                'level': performance_level,
                'timing': timing_points,
                'quality': quality_points,
                'regularity': regularity_points
            })
        
        s.commit()
        
        # حفظ النتائج في context للتصدير لاحقاً
        context.user_data['last_evaluation_results'] = evaluation_results
        context.user_data['last_evaluation_year'] = year
        context.user_data['last_evaluation_month'] = month
        context.user_data['last_evaluation_type'] = 'monthly'
        
        # عرض النتائج
        await display_evaluation_results(update, context, evaluation_results, year, month)

async def generate_yearly_report(update: Update, context: ContextTypes.DEFAULT_TYPE, year: int):
    """توليد تقرير التقييم السنوي"""
    query = update.callback_query
    
    with SessionLocal() as s:
        # جلب جميع التقييمات الشهرية للسنة
        monthly_evaluations = s.query(MonthlyEvaluation).filter_by(year=year).all()
        
        if not monthly_evaluations:
            await query.edit_message_text(f"⚠️ لا توجد تقييمات متاحة للسنة {year}.")
            return
        
        # تجميع النتائج حسب المترجم
        translator_stats = {}
        
        for eval in monthly_evaluations:
            translator_name = eval.translator_name or 'غير محدد'
            
            if translator_name not in translator_stats:
                translator_stats[translator_name] = {
                    'name': translator_name,
                    'months': 0,
                    'total_points': 0,
                    'total_reports': 0,
                    'on_time_reports': 0,
                    'late_reports': 0,
                    'ratings': []
                }
            
            stats = translator_stats[translator_name]
            stats['months'] += 1
            # استخدام getattr للتحقق من وجود الحقول
            stats['total_points'] += getattr(eval, 'total_points', 0) or 0
            stats['total_reports'] += getattr(eval, 'total_reports', 0) or 0
            stats['on_time_reports'] += getattr(eval, 'on_time_reports', 0) or 0
            stats['late_reports'] += getattr(eval, 'late_reports', 0) or 0
            final_rating = getattr(eval, 'final_rating', 0) or 0
            if final_rating:
                stats['ratings'].append(final_rating)
        
        # حساب المتوسطات
        evaluation_results = []
        for translator_name, stats in translator_stats.items():
            avg_points = stats['total_points'] / stats['months']
            avg_rating = sum(stats['ratings']) / len(stats['ratings'])
            
            # تحديد مستوى الأداء السنوي
            if avg_points >= 27:
                performance_level = "ممتاز"
            elif avg_points >= 24:
                performance_level = "جيد جداً"
            elif avg_points >= 21:
                performance_level = "جيد"
            elif avg_points >= 18:
                performance_level = "مقبول"
            else:
                performance_level = "ضعيف"
            
            evaluation_results.append({
                'name': translator_name,
                'total_points': round(avg_points, 1),
                'rating': round(avg_rating, 1),
                'level': performance_level,
                'months': stats['months'],
                'total_reports': stats['total_reports'],
                'on_time_reports': stats['on_time_reports'],
                'late_reports': stats['late_reports']
            })
        
        # حفظ النتائج في context للتصدير لاحقاً
        context.user_data['last_evaluation_results'] = evaluation_results
        context.user_data['last_evaluation_year'] = year
        context.user_data['last_evaluation_type'] = 'yearly'
        
        # عرض النتائج السنوية
        await display_yearly_results(update, context, evaluation_results, year)

async def display_evaluation_results(update: Update, context: ContextTypes.DEFAULT_TYPE, results: list, year: int, month: int):
    """عرض نتائج التقييم"""
    query = update.callback_query
    
    # ترتيب النتائج حسب النقاط
    results.sort(key=lambda x: x['total_points'], reverse=True)
    
    report_text = f"📊 **تقرير التقييم الشهري - {year}/{month}**\n\n"
    
    for i, result in enumerate(results, 1):
        stars = "⭐" * result['rating']
        report_text += f"**{i}. {result['name']}**\n"
        report_text += f"🏆 التقييم: {stars} ({result['level']})\n"
        report_text += f"📊 النقاط الإجمالية: {result['total_points']}/30\n"
        report_text += f"⏰ التوقيت: {result['timing']}/10 | 📝 الجودة: {result['quality']}/10 | 📅 الانتظام: {result['regularity']}/10\n\n"
    
    # إحصائيات عامة
    total_translators = len(results)
    excellent = sum(1 for r in results if r['rating'] >= 4)
    good = sum(1 for r in results if r['rating'] == 3)
    poor = sum(1 for r in results if r['rating'] <= 2)
    
    report_text += f"📈 **إحصائيات عامة:**\n"
    report_text += f"👥 إجمالي المترجمين: {total_translators}\n"
    report_text += f"⭐ ممتاز (4-5 نجوم): {excellent}\n"
    report_text += f"⭐ جيد (3 نجوم): {good}\n"
    report_text += f"⭐ ضعيف (1-2 نجوم): {poor}\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 تصدير التقرير", callback_data="export_report")],
        [InlineKeyboardButton("🔙 العودة", callback_data="back_to_eval")]
    ])
    
    await query.edit_message_text(
        report_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def display_yearly_results(update: Update, context: ContextTypes.DEFAULT_TYPE, results: list, year: int):
    """عرض نتائج التقييم السنوي"""
    query = update.callback_query
    
    # ترتيب النتائج حسب النقاط
    results.sort(key=lambda x: x['total_points'], reverse=True)
    
    report_text = f"📊 **تقرير التقييم السنوي - {year}**\n\n"
    
    for i, result in enumerate(results, 1):
        stars = "⭐" * int(result['rating'])
        report_text += f"**{i}. {result['name']}**\n"
        report_text += f"🏆 التقييم: {stars} ({result['level']})\n"
        report_text += f"📊 متوسط النقاط: {result['total_points']}/30\n"
        report_text += f"📅 عدد الشهور: {result['months']}\n"
        report_text += f"📝 إجمالي التقارير: {result['total_reports']}\n"
        report_text += f"⏰ في الوقت: {result['on_time_reports']} | 🔴 متأخر: {result['late_reports']}\n\n"
    
    # إحصائيات عامة
    total_translators = len(results)
    excellent = sum(1 for r in results if r['rating'] >= 4)
    good = sum(1 for r in results if 3 <= r['rating'] < 4)
    poor = sum(1 for r in results if r['rating'] < 3)
    
    report_text += f"📈 **إحصائيات عامة للسنة {year}:**\n"
    report_text += f"👥 إجمالي المترجمين: {total_translators}\n"
    report_text += f"⭐ ممتاز (4+ نجوم): {excellent}\n"
    report_text += f"⭐ جيد (3 نجوم): {good}\n"
    report_text += f"⭐ ضعيف (<3 نجوم): {poor}\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 تصدير التقرير", callback_data="export_yearly_report")],
        [InlineKeyboardButton("🔙 العودة", callback_data="back_to_eval")]
    ])
    
    await query.edit_message_text(
        report_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def start_manual_evaluation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء التقييم اليدوي"""
    query = update.callback_query
    await query.answer()
    
    with SessionLocal() as s:
        # محاولة إضافة translator_id إذا لم يكن موجوداً
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(s.bind)
            columns = [col['name'] for col in inspector.get_columns('daily_report_tracking')]
            
            if 'translator_id' not in columns:
                try:
                    s.execute(text("ALTER TABLE daily_report_tracking ADD COLUMN translator_id INTEGER"))
                    s.commit()
                    logger.info("✅ Added translator_id column to daily_report_tracking")
                except Exception as alter_error:
                    logger.warning(f"⚠️ Could not add translator_id column: {alter_error}")
                    s.rollback()
        except Exception as inspect_error:
            logger.warning(f"⚠️ Could not inspect table: {inspect_error}")
        
        # جلب المترجمين من الجدول
        try:
            from sqlalchemy import func
            translator_names = s.query(DailyReportTracking.translator_name).distinct().all()
            translator_names_list = [name[0] for name in translator_names if name[0]]
            
            if not translator_names_list:
                await query.edit_message_text("⚠️ لا توجد بيانات للمترجمين.")
                return
            
            # جلب سجل واحد لكل مترجم للعرض - استخدام query محدود بدون translator_id
            translators = []
            for name in translator_names_list[:10]:  # أول 10 مترجمين
                try:
                    record = s.query(
                        DailyReportTracking.id,
                        DailyReportTracking.translator_name,
                        DailyReportTracking.date,
                        DailyReportTracking.expected_reports,
                        DailyReportTracking.actual_reports,
                        DailyReportTracking.is_completed,
                        DailyReportTracking.reminder_sent,
                        DailyReportTracking.created_at
                    ).filter_by(translator_name=name).first()
                    if record:
                        # إنشاء كائن وهمي يحتوي على translator_name فقط
                        class SimpleRecord:
                            def __init__(self, translator_name):
                                self.translator_name = translator_name
                        translators.append(SimpleRecord(name))
                except Exception as query_error:
                    logger.warning(f"⚠️ Error querying translator {name}: {query_error}")
                    # استخدام كائن بسيط
                    class SimpleRecord:
                        def __init__(self, translator_name):
                            self.translator_name = translator_name
                    translators.append(SimpleRecord(name))
        except Exception as e:
            logger.error(f"❌ Error in start_manual_evaluation: {e}", exc_info=True)
            await query.edit_message_text("❌ خطأ في قاعدة البيانات. يرجى المحاولة مرة أخرى.")
            return
        
        keyboard = []
        for translator in translators[:10]:  # عرض أول 10 مترجمين
            keyboard.append([InlineKeyboardButton(
                translator.translator_name, 
                callback_data=f"manual_eval:{translator.translator_name}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 العودة", callback_data="back_to_eval")])
        
        await query.edit_message_text(
            "📝 **التقييم اليدوي**\n\n"
            "اختر المترجم المراد تقييمه:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

async def view_evaluations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض التقييمات"""
    query = update.callback_query
    await query.answer()
    
    with SessionLocal() as s:
        # محاولة إضافة الأعمدة المفقودة أولاً
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(s.bind)
            columns = [col['name'] for col in inspector.get_columns('monthly_evaluations')]
            
            # إضافة translator_id إذا لم يكن موجوداً
            if 'translator_id' not in columns:
                try:
                    s.execute(text("ALTER TABLE monthly_evaluations ADD COLUMN translator_id INTEGER"))
                    s.commit()
                    logger.info("✅ Added translator_id column to monthly_evaluations")
                except Exception as alter_error:
                    logger.warning(f"⚠️ Could not add translator_id column: {alter_error}")
                    s.rollback()
            
            # إضافة الحقول الأخرى إذا لم تكن موجودة
            missing_fields = {
                'on_time_reports': 'INTEGER',
                'late_reports': 'INTEGER',
                'timing_points': 'REAL',
                'quality_points': 'REAL',
                'regularity_points': 'REAL',
                'total_points': 'REAL',
                'final_rating': 'INTEGER',
                'performance_level': 'TEXT',
                'updated_at': 'DATETIME'
            }
            
            for field_name, field_type in missing_fields.items():
                if field_name not in columns:
                    try:
                        s.execute(text(f"ALTER TABLE monthly_evaluations ADD COLUMN {field_name} {field_type}"))
                        s.commit()
                        logger.info(f"✅ Added {field_name} column to monthly_evaluations")
                    except Exception as alter_error:
                        logger.warning(f"⚠️ Could not add {field_name} column: {alter_error}")
                        s.rollback()
        except Exception as inspect_error:
            logger.warning(f"⚠️ Could not inspect table: {inspect_error}")
        
        # جلب آخر التقييمات الشهرية
        try:
            evaluations = s.query(MonthlyEvaluation).order_by(
                MonthlyEvaluation.year.desc(),
                MonthlyEvaluation.month.desc()
            )
            # محاولة إضافة ترتيب حسب total_points إذا كان موجوداً
            if hasattr(MonthlyEvaluation, 'total_points'):
                try:
                    evaluations = evaluations.order_by(MonthlyEvaluation.total_points.desc())
                except:
                    pass
            evaluations = evaluations.limit(10).all()
        except Exception as e:
            logger.error(f"❌ Error querying evaluations: {e}", exc_info=True)
            # استخدام query بسيط بدون total_points
            try:
                evaluations = s.query(MonthlyEvaluation).order_by(
                    MonthlyEvaluation.year.desc(),
                    MonthlyEvaluation.month.desc()
                ).limit(10).all()
            except Exception as e2:
                logger.error(f"❌ Error in fallback query: {e2}", exc_info=True)
                await query.edit_message_text("❌ خطأ في قاعدة البيانات. يرجى المحاولة مرة أخرى.")
                return
        
        if not evaluations:
            await query.edit_message_text("⚠️ لا توجد تقييمات متاحة.")
            return
        
        report_text = "📊 **آخر التقييمات الشهرية**\n\n"
        
        for eval in evaluations:
            # استخدام getattr للتحقق من وجود الحقول
            final_rating = getattr(eval, 'final_rating', 0) or 0
            performance_level = getattr(eval, 'performance_level', 'غير محدد') or 'غير محدد'
            total_points = getattr(eval, 'total_points', 0) or 0
            
            stars = "⭐" * int(final_rating) if final_rating else "⭐"
            report_text += f"**{eval.translator_name or 'غير محدد'}**\n"
            report_text += f"📅 {eval.year}/{eval.month} | {stars} ({performance_level})\n"
            report_text += f"📊 {total_points}/30 نقطة\n\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 العودة", callback_data="back_to_eval")]
        ])
        
        await query.edit_message_text(
            report_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

async def show_ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض ترتيب المترجمين"""
    query = update.callback_query
    await query.answer()
    
    with SessionLocal() as s:
        # جلب متوسط النقاط لكل مترجم
        from sqlalchemy import func
        
        # استخدام getattr للتحقق من وجود الحقل total_points
        if hasattr(MonthlyEvaluation, 'total_points'):
            rankings = s.query(
                MonthlyEvaluation.translator_name,
                func.avg(MonthlyEvaluation.total_points).label('avg_points'),
                func.count(MonthlyEvaluation.id).label('months_count')
            ).group_by(MonthlyEvaluation.translator_name).order_by(
                func.avg(MonthlyEvaluation.total_points).desc()
            ).limit(10).all()
        else:
            # استخدام total_reports كبديل
            rankings = s.query(
                MonthlyEvaluation.translator_name,
                func.avg(MonthlyEvaluation.total_reports).label('avg_points'),
                func.count(MonthlyEvaluation.id).label('months_count')
            ).group_by(MonthlyEvaluation.translator_name).order_by(
                func.avg(MonthlyEvaluation.total_reports).desc()
            ).limit(10).all()
        
        if not rankings:
            await query.edit_message_text("⚠️ لا توجد بيانات كافية للترتيب.")
            return
        
        report_text = "🏆 **ترتيب المترجمين (متوسط النقاط)**\n\n"
        
        for i, ranking in enumerate(rankings, 1):
            avg_points = round(ranking.avg_points, 1)
            months = ranking.months_count
            
            if avg_points >= 27:
                level = "ممتاز"
            elif avg_points >= 24:
                level = "جيد جداً"
            elif avg_points >= 21:
                level = "جيد"
            elif avg_points >= 18:
                level = "مقبول"
            else:
                level = "ضعيف"
            
            report_text += f"**{i}. {ranking.translator_name}**\n"
            report_text += f"📊 متوسط النقاط: {avg_points}/30 ({level})\n"
            report_text += f"📅 عدد الشهور: {months}\n\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 العودة", callback_data="back_to_eval")]
        ])
        
        await query.edit_message_text(
            report_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )

async def back_to_evaluation_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """العودة لقائمة التقييم"""
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 تقييم شهري تلقائي", callback_data="eval:monthly_auto")],
        [InlineKeyboardButton("📝 تقييم يدوي", callback_data="eval:manual")],
        [InlineKeyboardButton("📈 عرض التقييمات", callback_data="eval:view")],
        [InlineKeyboardButton("🏆 ترتيب المترجمين", callback_data="eval:ranking")]
    ])

    await query.edit_message_text(
        "📊 **نظام تقييم المترجمين**\n\n"
        "اختر نوع التقييم:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

def register(app):
    """تسجيل الهاندلرز"""
    # إضافة الهاندلرز المنفصلة بدلاً من ConversationHandler
    app.add_handler(MessageHandler(filters.Regex("^📊 تقييم المترجمين$"), start_evaluation))
    
    # دالة موحدة لمعالجة جميع callback queries
    async def handle_all_evaluation_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data.startswith("eval:"):
                choice = query.data.split(":")[1]
                if choice == "monthly_auto":
                    await generate_monthly_evaluation(update, context)
                elif choice == "manual":
                    await start_manual_evaluation(update, context)
                elif choice == "view":
                    await view_evaluations(update, context)
                elif choice == "ranking":
                    await show_ranking(update, context)
            elif query.data.startswith("year:"):
                await handle_year_selection(update, context)
            elif query.data.startswith("month:"):
                await handle_month_selection(update, context)
            elif query.data == "back_to_eval":
                await back_to_evaluation_menu(update, context)
            elif query.data.startswith("manual_eval:"):
                await start_manual_evaluation(update, context)
            elif query.data == "export_report":
                # استرجاع البيانات المحفوظة
                results = context.user_data.get('last_evaluation_results')
                year = context.user_data.get('last_evaluation_year')
                month = context.user_data.get('last_evaluation_month')
                if results and year and month:
                    await display_evaluation_results(update, context, results, year, month)
                else:
                    await query.edit_message_text("⚠️ لا توجد بيانات للتصدير.")
            elif query.data == "export_yearly_report":
                # استرجاع البيانات المحفوظة
                results = context.user_data.get('last_evaluation_results')
                year = context.user_data.get('last_evaluation_year')
                if results and year:
                    await display_yearly_results(update, context, results, year)
                else:
                    await query.edit_message_text("⚠️ لا توجد بيانات للتصدير.")
        except Exception as e:
            logger.error(f"❌ Error in handle_all_evaluation_callbacks: {e}", exc_info=True)
            try:
                await query.edit_message_text(
                    f"❌ **حدث خطأ غير متوقع**\n\n"
                    f"الخطأ: {str(e)[:100]}\n\n"
                    f"يرجى المحاولة مرة أخرى أو التواصل مع المطور.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
    
    app.add_handler(CallbackQueryHandler(handle_all_evaluation_callbacks, pattern="^(eval:|year:|month:|back_to_eval$|manual_eval:|export_report$|export_yearly_report$)"))