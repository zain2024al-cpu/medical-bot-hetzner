# ================================================
# bot/handlers/user/user_inline_menu.py
# 🎨 معالجة القائمة الـ Inline للمستخدم
# ================================================

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, CallbackQueryHandler
from bot.keyboards import (
    user_main_inline_kb,
    user_compact_inline_kb,
    user_categories_menu,
    reports_submenu,
    analytics_submenu,
    settings_submenu
)
from bot.shared_auth import is_user_approved
from db.session import SessionLocal
from db.models import Report
from datetime import datetime, timedelta
from sqlalchemy import func


async def handle_user_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالجة ضغطات الأزرار في القائمة الـ Inline
    """
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    tg_id = user.id
    
    # التحقق من الموافقة
    if not is_user_approved(tg_id):
        await query.edit_message_text(
            "⏳ **بانتظار الموافقة**\n\n"
            "طلبك قيد المراجعة من قبل الإدارة.",
            parse_mode="Markdown"
        )
        return
    
    action = query.data.split(":", 1)[1] if ":" in query.data else query.data
    
    # ================================================
    # معالجة القوائم الفرعية (Categories)
    # ================================================
    
    if action == "reports":
        # قائمة إدارة التقارير
        await query.edit_message_text(
            "📝 **إدارة التقارير**\n\n"
            "اختر العملية المطلوبة:",
            reply_markup=reports_submenu(),
            parse_mode="Markdown"
        )
        return
    
    elif action == "analytics":
        # قائمة الإحصائيات
        await query.edit_message_text(
            "📊 **الإحصائيات والتحليلات**\n\n"
            "اختر نوع الإحصائيات:",
            reply_markup=analytics_submenu(),
            parse_mode="Markdown"
        )
        return
    
    elif action == "settings":
        # قائمة الإعدادات
        await query.edit_message_text(
            "⚙️ **الإعدادات والمساعدة**\n\n"
            "اختر من القائمة:",
            reply_markup=settings_submenu(),
            parse_mode="Markdown"
        )
        return
    
    # ================================================
    # معالجة الإجراءات الرئيسية
    # ================================================
    
    if action == "add_report":
        # إضافة تقرير جديد - تفعيل النظام الموجود
        await query.edit_message_text(
            "📝 **إضافة تقرير جديد**\n\n"
            "يرجى الضغط على الزر أدناه في لوحة الأزرار:\n"
            "👉 **\"📝 إضافة تقرير جديد\"**\n\n"
            "أو استخدم الأمر: /add"
        )
        # إعادة عرض القائمة
        await query.message.reply_text(
            "اختر العملية:",
            reply_markup=user_main_inline_kb()
        )
    
    elif action == "quick_add":
        # إضافة سريعة - نفس الإضافة العادية
        await query.edit_message_text(
            "⚡ **إضافة سريعة**\n\n"
            "يرجى الضغط على:\n"
            "👉 **\"📝 إضافة تقرير جديد\"** من لوحة الأزرار\n\n"
            "أو استخدم: /add"
        )
    
    elif action == "schedule":
        # عرض الجدول - تفعيل النظام الموجود
        await query.edit_message_text(
            "📅 **جدول اليوم**\n\n"
            "يرجى الضغط على:\n"
            "👉 **\"📅 جدول اليوم\"** من لوحة الأزرار"
        )
    
    elif action == "edit":
        # تعديل التقارير - تفعيل النظام الموجود
        await query.edit_message_text(
            "✏️ **تعديل التقارير**\n\n"
            "يرجى الضغط على:\n"
            "👉 **\"✏️ تعديل التقارير\"** من لوحة الأزرار"
        )
    
    elif action == "history":
        # سجل التقارير
        await query.edit_message_text(
            "📜 **سجل التقارير**\n\n"
            "عرض سجل تقاريرك السابقة.\n\n"
            "💡 ملاحظة: هذه الميزة قيد التطوير"
        )
    
    elif action == "my_stats":
        # عرض إحصائيات المستخدم
        await show_user_statistics(query, tg_id)
    
    elif action == "my_today":
        # تقارير اليوم
        await show_today_reports(query, tg_id)
    
    elif action == "my_week":
        # تقارير الأسبوع
        await show_week_reports(query, tg_id)
    
    elif action == "my_month":
        # تقارير الشهر
        await show_month_reports(query, tg_id)
    
    elif action == "initial_case":
        # التقرير الأولي للمرضى - يتم التعامل معه في ConversationHandler
        await query.edit_message_text(
            "📋 **التقرير الأولي للمرضى**\n\n"
            "جارٍ تحميل قائمة المرضى...",
            parse_mode="Markdown"
        )
        # سيتم التعامل معه في ConversationHandler
        return
    
    elif action == "help":
        # المساعدة
        await query.edit_message_text(
            "ℹ️ **المساعدة**\n\n"
            "**الأوامر المتاحة:**\n"
            "/start - القائمة الرئيسية\n"
            "/add - إضافة تقرير\n"
            "/today - تقارير اليوم\n"
            "/stats - إحصائياتي\n\n"
            "**للمساعدة:**\n"
            "تواصل مع الإدارة",
            reply_markup=user_main_inline_kb()
        )
    
    elif action == "refresh":
        # تحديث الصفحة
        context.user_data.clear()
        await query.edit_message_text(
            "🔄 **تم تحديث الصفحة!**\n\n"
            "✅ تم إلغاء جميع العمليات الجارية\n"
            "✅ الصفحة نظيفة الآن\n\n"
            "اختر عملية جديدة:",
            reply_markup=user_main_inline_kb(),
            parse_mode="Markdown"
        )
    
    elif action == "back_main":
        # العودة للقائمة الرئيسية
        with SessionLocal() as s:
            from db.models import Translator
            translator = s.query(Translator).filter_by(tg_user_id=tg_id).first()
            name = translator.full_name if translator else "المستخدم"
        
        # مسح البيانات المؤقتة لضمان حالة نظيفة عند العودة للقائمة الرئيسية
        context.user_data.pop("report_tmp", None)
        
        await query.edit_message_text(
            f"👋 **أهلاً {name}!**\n\n"
            "اختر العملية المطلوبة:",
            reply_markup=user_main_inline_kb(),
            parse_mode="Markdown"
        )
    
    elif action == "full_menu":
        # القائمة الكاملة
        with SessionLocal() as s:
            from db.models import Translator
            translator = s.query(Translator).filter_by(tg_user_id=tg_id).first()
            name = translator.full_name if translator else "المستخدم"
        
        await query.edit_message_text(
            f"👋 **أهلاً {name}!**\n\n"
            "📋 **القائمة الكاملة:**",
            reply_markup=user_main_inline_kb(),
            parse_mode="Markdown"
        )


# ================================================
# دوال مساعدة للإحصائيات
# ================================================

async def show_user_statistics(query, user_id):
    """عرض إحصائيات شاملة للمستخدم"""
    
    with SessionLocal() as s:
        from db.models import Translator
        
        # جلب بيانات المستخدم
        translator = s.query(Translator).filter_by(tg_user_id=user_id).first()
        if not translator:
            await query.edit_message_text("❌ لم يتم العثور على بياناتك")
            return
        
        # إحصائيات التقارير
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # عدد التقارير
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
        
        # المتوسط اليومي (آخر 30 يوم)
        daily_avg = round(month_reports / 30, 1) if month_reports > 0 else 0
        
        # أفضل يوم (أعلى عدد تقارير)
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
        
        # ترتيب المستخدم بين الزملاء
        all_translators = s.query(
            Translator.id,
            func.count(Report.id).label('report_count')
        ).outerjoin(
            Report, Report.translator_id == Translator.id
        ).group_by(
            Translator.id
        ).order_by(
            func.count(Report.id).desc()
        ).all()
        
        user_rank = 0
        total_users = len(all_translators)
        for idx, (tid, count) in enumerate(all_translators):
            if tid == translator.id:
                user_rank = idx + 1
                break
    
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

🏆 **ترتيبك:** #{user_rank} من {total_users} مترجم

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 **استمر في العمل الرائع!**
    """
    
    # أزرار إضافية
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = [
        [InlineKeyboardButton("📅 تقاريري اليوم", callback_data="user_action:my_today")],
        [InlineKeyboardButton("📈 تقارير الأسبوع", callback_data="user_action:my_week")],
        [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="user_action:back_main")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def show_today_reports(query, user_id):
    """عرض تقارير اليوم للمستخدم"""
    
    with SessionLocal() as s:
        from db.models import Translator, Hospital, Department, Doctor
        
        translator = s.query(Translator).filter_by(tg_user_id=user_id).first()
        if not translator:
            await query.edit_message_text("❌ لم يتم العثور على بياناتك")
            return
        
        today = datetime.now().date()
        
        reports = s.query(Report).filter(
            Report.translator_id == translator.id,
            func.date(Report.report_date) == today
        ).order_by(Report.report_date.desc()).all()
        
        if not reports:
            text = f"""
📅 **تقارير اليوم**

⚠️ لم تقم بإضافة أي تقارير اليوم بعد.

💡 اضغط "📝 إضافة تقرير" للبدء!
            """
        else:
            text = f"""
📅 **تقارير اليوم** ({len(reports)} تقرير)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
            for idx, r in enumerate(reports, 1):
                # جلب بيانات مرتبطة
                hospital = s.get(Hospital, r.hospital_id) if r.hospital_id else None
                department = s.get(Department, r.department_id) if r.department_id else None
                
                text += f"""
**{idx}. تقرير #{r.id}**
   🕐 الوقت: {r.report_date.strftime('%H:%M')}
   👤 المريض: {r.patient_name or '—'}
   🏥 المستشفى: {hospital.name if hospital else '—'}
   🩺 القسم: {department.name if department else '—'}
   📝 الشكوى: {(r.complaint_text or '—')[:50]}...

"""
            
            text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            text += f"✅ **المجموع:** {len(reports)} تقرير اليوم"
    
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات كاملة", callback_data="user_action:my_stats")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="user_action:back_main")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def show_week_reports(query, user_id):
    """عرض تقارير الأسبوع"""
    
    with SessionLocal() as s:
        from db.models import Translator
        
        translator = s.query(Translator).filter_by(tg_user_id=user_id).first()
        if not translator:
            await query.edit_message_text("❌ لم يتم العثور على بياناتك")
            return
        
        week_ago = datetime.now().date() - timedelta(days=7)
        
        count = s.query(Report).filter(
            Report.translator_id == translator.id,
            func.date(Report.report_date) >= week_ago
        ).count()
        
        # إحصائيات يومية
        daily_stats = s.query(
            func.date(Report.report_date).label('date'),
            func.count(Report.id).label('count')
        ).filter(
            Report.translator_id == translator.id,
            func.date(Report.report_date) >= week_ago
        ).group_by(
            func.date(Report.report_date)
        ).order_by(
            func.date(Report.report_date).desc()
        ).all()
        
        text = f"""
📈 **تقارير الأسبوع**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **الإجمالي:** {count} تقرير

📅 **التوزيع اليومي:**

"""
        
        for stat in daily_stats:
            bars = "▓" * min(stat.count, 10)
            text += f"   {stat.date}: {bars} ({stat.count})\n"
        
        if not daily_stats:
            text += "   ⚠️ لا توجد تقارير هذا الأسبوع\n"
        
        text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات كاملة", callback_data="user_action:my_stats")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="user_action:back_main")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def show_month_reports(query, user_id):
    """عرض تقارير الشهر"""
    
    with SessionLocal() as s:
        from db.models import Translator
        
        translator = s.query(Translator).filter_by(tg_user_id=user_id).first()
        if not translator:
            await query.edit_message_text("❌ لم يتم العثور على بياناتك")
            return
        
        month_ago = datetime.now().date() - timedelta(days=30)
        
        count = s.query(Report).filter(
            Report.translator_id == translator.id,
            func.date(Report.report_date) >= month_ago
        ).count()
        
        avg_daily = round(count / 30, 1) if count > 0 else 0
        
        text = f"""
📆 **تقارير الشهر** (آخر 30 يوم)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **الإجمالي:** {count} تقرير

⭐ **المعدل اليومي:** {avg_daily} تقرير/يوم

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 **استمر في الأداء الرائع!**
        """
    
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات كاملة", callback_data="user_action:my_stats")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="user_action:back_main")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# ================================================
# تسجيل الـ Handler
# ================================================

def register(app):
    """تسجيل معالج القائمة الـ Inline"""
    app.add_handler(CallbackQueryHandler(
        handle_user_menu_callback,
        pattern="^(user_action:|category:)"
    ))














