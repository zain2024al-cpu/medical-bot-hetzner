# ================================================
# bot/handlers/user/user_shortcuts.py
# ⚡ اختصارات الأوامر للوصول السريع
# ================================================

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from bot.shared_auth import is_user_approved
from bot.keyboards import user_main_inline_kb
from db.session import SessionLocal
from db.models import Report, Translator
from datetime import datetime, timedelta
from sqlalchemy import func

try:
    from bot.handlers.user.user_reports_add_new_system.date_time_handlers import start_report as _start_report
except ImportError:
    _start_report = None


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    اختصار /add - إضافة تقرير مباشرة
    """
    user = update.effective_user

    if not is_user_approved(user.id):
        await update.message.reply_text("⏳ بانتظار موافقة الإدارة.")
        return

    if _start_report:
        return await _start_report(update, context)

    # fallback
    await update.message.reply_text(
        "📝 **إضافة تقرير جديد**\n\nاضغط على الزر في لوحة الأزرار الرئيسية.",
        parse_mode="Markdown",
        reply_markup=user_main_inline_kb()
    )


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    اختصار /search - بحث مباشر
    """
    user = update.effective_user
    
    if not is_user_approved(user.id):
        await update.message.reply_text("⏳ بانتظار موافقة الإدارة.")
        return
    
    await update.message.reply_text(
        "🔍 **البحث السريع**\n\n"
        "للبحث، اضغط على الزر:\n"
        "👉 **\"🔍 بحث عن حالة\"** من لوحة الأزرار الرئيسية",
        parse_mode="Markdown",
        reply_markup=user_main_inline_kb()
    )


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    اختصار /today - عرض تقارير اليوم
    """
    user = update.effective_user
    tg_id = user.id
    
    if not is_user_approved(tg_id):
        await update.message.reply_text("⏳ بانتظار موافقة الإدارة.")
        return
    
    with SessionLocal() as s:
        translator = s.query(Translator).filter_by(tg_user_id=tg_id).first()
        if not translator:
            await update.message.reply_text("❌ لم يتم العثور على بياناتك")
            return
        
        # today = datetime.now().date()
        
        # ✅ إصلاح مشكلة التوقيت: توسيع النطاق ليشمل 24 ساعة الماضية + 12 ساعة قادمة
        now_utc = datetime.utcnow()
        today_start = now_utc - timedelta(hours=24)
        today_end = now_utc + timedelta(hours=12)

        reports = s.query(Report).filter(
            Report.translator_id == translator.id,
            Report.report_date >= today_start,
            Report.report_date <= today_end
        ).order_by(Report.report_date.desc()).all()
        
        if not reports:
            text = f"""
📅 **تقارير اليوم**

⚠️ لم تقم بإضافة أي تقارير اليوم بعد.

💡 اضغط "📝 إضافة تقرير" للبدء!
            """
        else:
            from db.models import Hospital, Department
            
            text = f"""
📅 **تقارير اليوم** ({len(reports)} تقرير)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
            for idx, r in enumerate(reports, 1):
                hospital = s.get(Hospital, r.hospital_id) if r.hospital_id else None
                department = s.get(Department, r.department_id) if r.department_id else None
                
                text += f"""
**{idx}. تقرير #{r.id}**
   🕐 الوقت: {r.report_date.strftime('%H:%M')}
   👤 المريض: {r.patient_name or '—'}
   🏥 المستشفى: {hospital.name if hospital else '—'}
   🩺 القسم: {department.name if department else '—'}

"""
            
            text += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n✅ **المجموع:** {len(reports)} تقرير"
    
    await update.message.reply_text(
        text,
        reply_markup=user_main_inline_kb(),
        parse_mode="Markdown"
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    اختصار /stats - إحصائياتي
    """
    user = update.effective_user
    tg_id = user.id
    
    if not is_user_approved(tg_id):
        await update.message.reply_text("⏳ بانتظار موافقة الإدارة.")
        return
    
    with SessionLocal() as s:
        from db.models import Hospital
        
        translator = s.query(Translator).filter_by(tg_user_id=tg_id).first()
        if not translator:
            await update.message.reply_text("❌ لم يتم العثور على بياناتك")
            return
        
        # حساب الإحصائيات
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        total_reports = s.query(Report).filter_by(translator_id=translator.id).count()
        today_reports = s.query(Report).filter(
            Report.translator_id == translator.id,
            func.date(Report.report_date) == today
        ).count()
        week_reports = s.query(Report).filter(
            Report.translator_id == translator.id,
            func.date(Report.report_date) >= week_ago
        ).count()
        month_reports = s.query(Report).filter(
            Report.translator_id == translator.id,
            func.date(Report.report_date) >= month_ago
        ).count()
        
        daily_avg = round(month_reports / 30, 1) if month_reports > 0 else 0
        
        # أفضل يوم
        best_day = s.query(
            func.date(Report.report_date).label('date'),
            func.count(Report.id).label('count')
        ).filter(
            Report.translator_id == translator.id
        ).group_by(
            func.date(Report.report_date)
        ).order_by(
            func.count(Report.id).desc()
        ).first()
        
        best_day_str = "لا توجد بيانات"
        best_count = 0
        if best_day:
            best_day_str = str(best_day.date)
            best_count = best_day.count
        
        # المستشفيات الأكثر
        top_hospitals = s.query(
            Hospital.name,
            func.count(Report.id).label('count')
        ).join(
            Report, Report.hospital_id == Hospital.id
        ).filter(
            Report.translator_id == translator.id
        ).group_by(
            Hospital.name
        ).order_by(
            func.count(Report.id).desc()
        ).limit(3).all()
        
        top_hospitals_list = "\n".join([
            f"   {i+1}. {h.name} ({h.count} تقرير)"
            for i, h in enumerate(top_hospitals)
        ]) if top_hospitals else "   لا توجد بيانات"
    
    # بناء الرسالة
    text = f"""
📊 **إحصائياتك الشاملة**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 **المترجم:** {translator.full_name}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 **التقارير:**
   • اليوم: {today_reports} تقرير
   • هذا الأسبوع: {week_reports} تقرير
   • هذا الشهر: {month_reports} تقرير
   • الإجمالي: {total_reports} تقرير

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⭐ **الأداء:**
   • المعدل اليومي: {daily_avg} تقرير/يوم
   • أفضل يوم: {best_day_str} ({best_count} تقرير)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏥 **المستشفيات الأكثر:**
{top_hospitals_list}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 **استمر في العمل الرائع!**
    """
    
    await update.message.reply_text(
        text,
        reply_markup=user_main_inline_kb(),
        parse_mode="Markdown"
    )


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    اختصار /menu - عرض القائمة الرئيسية
    """
    user = update.effective_user
    tg_id = user.id
    
    if not is_user_approved(tg_id):
        await update.message.reply_text("⏳ بانتظار موافقة الإدارة.")
        return
    
    with SessionLocal() as s:
        translator = s.query(Translator).filter_by(tg_user_id=tg_id).first()
        name = translator.full_name if translator else "المستخدم"
    
    await update.message.reply_text(
        f"👋 **أهلاً {name}!**\n\n"
        "اختر العملية المطلوبة:",
        reply_markup=user_main_inline_kb(),
        parse_mode="Markdown"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    اختصار /help - المساعدة
    """
    text = """
ℹ️ **دليل الاستخدام السريع**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**الأوامر المتاحة:**

📝 **/add** - إضافة تقرير جديد
📅 **/today** - تقارير اليوم
📊 **/stats** - إحصائياتي الشاملة
📋 **/menu** - القائمة الرئيسية
ℹ️ **/help** - هذه الرسالة

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**نصائح:**

💡 استخدم الأزرار المضمنة للتنقل السريع
💡 استخدم الأوامر للوصول المباشر
💡 اضغط /menu لعرض القائمة في أي وقت

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**للمساعدة:**
تواصل مع الإدارة
    """
    
    await update.message.reply_text(
        text,
        reply_markup=user_main_inline_kb(),
        parse_mode="Markdown"
    )


# ================================================
# تسجيل جميع الاختصارات
# ================================================

def register(app):
    """تسجيل جميع اختصارات الأوامر"""
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("help", cmd_help))
    
    print("✅ تم تسجيل اختصارات الأوامر (Command Shortcuts)")














