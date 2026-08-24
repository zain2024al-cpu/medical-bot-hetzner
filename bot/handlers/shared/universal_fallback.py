# ================================================
# bot/handlers/shared/universal_fallback.py
# 🛡️ معالج شامل لجميع الرسائل والأزرار غير المعالجة
# ================================================

import logging
import asyncio
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters
from telegram.error import TimedOut, NetworkError, BadRequest
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

# قائمة الـ callbacks المعروفة التي يتم معالجتها بواسطة handlers أخرى
KNOWN_CALLBACKS = [
    # ===========================
    # نظام إضافة التقارير (ConversationHandler)
    # ===========================
    r"^patient_idx:",     # اختيار المريض
    r"^user_patient_page:", # صفحات المرضى
    r"^hospital_idx:",    # اختيار المستشفى
    r"^dept_idx:",        # اختيار القسم
    r"^subdept_idx:",     # اختيار القسم الفرعي
    r"^doctor_idx:",      # اختيار الطبيب
    r"^doctor_page:",     # صفحات الأطباء
    r"^action_idx:",      # اختيار نوع الإجراء
    r"^hospital_page:",   # صفحات المستشفيات
    r"^hosp_page:",       # صفحات المستشفيات (بديل)
    r"^dept_page:",       # صفحات الأقسام
    r"^subdept_page:",    # صفحات الأقسام الفرعية
    r"^date:",            # اختيار التاريخ
    r"^main_cal_",        # التقويم الرئيسي
    r"^time_hour:",       # اختيار الساعة
    r"^time_minute:",     # اختيار الدقائق
    r"^time_skip",        # تخطي الوقت
    r"^doctor_manual",    # إدخال الطبيب يدوياً
    r"^simple_translator:", # اختيار المترجم البسيط
    r"^nav:",             # أزرار التنقل
    r"^noop$",            # زر لا يفعل شيء
    r"^abort$",           # إلغاء
    r"^skip",             # تخطي
    r"^medrep:",          # بوابة التقرير الطبي
    r"^medrep_done:",     # تأكيد رفع التقرير الطبي
    
    # التدفقات (flows) - نظام التقارير
    r"^new_consult",
    r"^followup",
    r"^emergency",
    r"^admission",
    r"^surgery",
    r"^operation",
    r"^final_consult",
    r"^discharge",
    r"^rehab",
    r"^radiology",
    r"^app_reschedule",
    r"^flow_",
    r"^save_report",
    r"^edit_before_save",
    r"^edit_draft:",
    r"^edit_field:",
    r"^draft_field:",
    r"^confirm_save",
    
    # ===========================
    # Admin
    # ===========================
    r"^admin:",
    r"^aa:",               # إدارة الأدمنين
    r"^remove_admin:",     # حذف أدمن
    r"^confirm_remove:",   # تأكيد حذف أدمن
    r"^um:",               # إدارة المستخدمين
    r"^aum:",              # إدارة المستخدمين الجديدة
    r"^suspend_reason:",   # أسباب التجميد
    r"^confirm_delete:",   # تأكيد الحذف
    r"^back_to_admin$",
    r"^back_to_main$",
    r"^back_to_schedule$",
    r"^has_tests:",        # إضافة حالة (Admin)
    r"^action:",           # إجراءات التأكيد (Admin)
    r"^proc:",             # إجراءات (Admin)
    r"^proc_select:",      # اختيار إجراء (Admin)
    r"^skip:",             # تخطي (Admin),
    
    # إدارة الجدول (Admin)
    r"^upload_schedule$",
    r"^view_schedule$",
    r"^track_reports$",
    r"^send_notifications$",
    r"^confirm_schedule$",
    r"^cancel_upload$",
    
    # إدارة المرضى (Admin)
    r"^manage_patients$",
    r"^view_patient_names$",
    r"^add_patient_name$",
    r"^edit_patient_name$",
    r"^delete_patient_name$",
    r"^confirm_delete:\d+$",
    r"^select_edit:\d+$",
    r"^sched_patient_page:",
    r"^delete_patient_page:",
    r"^edit_patient_page:",
    r"^view_patients_page:",
    
    # إدارة المستشفيات (Admin)
    r"^manage_hospitals$",
    r"^view_hospitals$",
    r"^add_hospital$",
    r"^edit_hospital$",
    r"^delete_hospital$",
    r"^sync_hospitals$",
    r"^confirm_delete_hosp:\d+$",
    r"^select_edit_hosp:\d+$",
    r"^delete_hosp_page:",
    r"^edit_hosp_page:",
    r"^view_hospitals_page:",
    
    # إدارة المترجمين (Admin)
    r"^manage_translators$",
    r"^view_translators$",
    r"^add_translator$",
    r"^edit_translator$",
    r"^delete_translator$",
    r"^sync_translators$",
    r"^confirm_delete_trans:\d+$",
    r"^select_edit_trans:\d+$",
    r"^delete_trans_page:",
    r"^edit_trans_page:",
    r"^view_translators_page:",
    r"^cancel_translator_input$",
    r"^cancel_hospital_input$",
    r"^detect_dup_translators$",
    r"^dup_del_trans:\d+$",
    r"^onc_toggle:",
    r"^onc_next$",
    r"^onc_delivery:",

    # ✅ أنماط مُسجَّلة فعلاً في ConversationHandler لكنها كانت غائبة عن هذه
    # القائمة، فيُطلق الفلبَك (المجموعة 999) تحذير "زر غير متاح" لكل ضغطة
    # رغم نجاحها — ضوضاء تُخفي الأعطال الحقيقية في السجل.
    r"^hcity:(default|chennai)$",
    r"^reschedule_cal_day:",
    r"^reschedule_cal_nav:",
    r"^patient:show_list:",
    r"^patient:back_to_menu$",
    r"^translator_page:",

    # ===========================
    # نظام تعديل وحذف التقارير للمستخدمين
    # ===========================
    r"^edit_report:",        # تعديل تقرير محدد
    r"^edit_field:",         # تعديل حقل محدد (مكرر لكن للتوضيح)
    r"^edit_republish$",     # إعادة نشر التقرير
    r"^edit_back",           # رجوع في نظام التعديل
    r"^edit_cancel$",        # إلغاء التعديل
    r"^edit_confirm_save$",  # تأكيد حفظ التعديل
    r"^edit_save_and_publish$",  # حفظ ونشر التقرير بعد التعديل
    r"^edit_followup:",      # تعديل موعد المتابعة
    r"^edit_time:",          # تعديل الوقت
    r"^edit_translator:",    # تعديل المترجم
    r"^edit_back_to_fields$", # رجوع لقائمة الحقول
    # ⚠️ أُضيف هذا الزر لاحقاً ("تأكيد حفظ حقل نصي بعد المعاينة") ولم
    # تُحدَّث هذه القائمة معه، فكان يُسجَّل ٣ مرات يومياً كزرّ مجهول رغم
    # وجود معالِجه — وهو مقيَّد بحالة CONFIRM_EDIT بلا pattern فلا يمكن
    # اشتقاقه آلياً. يصل هنا فقط حين تكون المحادثة قد انتهت (زر قديم).
    r"^edit_confirm_save_text$",
    r"^delete_report:",      # حذف تقرير محدد
    r"^delete_confirm$",     # تأكيد الحذف
    r"^delete_back$",        # رجوع في نظام الحذف
    r"^delete_cancel$",      # إلغاء الحذف
    
    # ===========================
    # واجهة المستخدم الأخرى
    # ===========================
    r"^ma:",            # المرفقات الطبية
    r"^ma_cal:",        # تقويم المرفقات الطبية
    r"^user_action:",   # أزرار actions المستخدم
    r"^start_report$",
    r"^user_action:add_report$",
    r"^admin:paste_full_report$",
    r"^paste_report:",
    r"^add_report$",
    r"^edit_reports$",
    r"^start_main_menu$",
    
    # الجدول
    r"^upload_schedule$",
    r"^view_schedule$",
    r"^track_reports$",
    r"^send_notifications$",
    r"^daily_patients$",
    
    # أخرى
    r"^cancel",
    r"^save:",
    r"^publish:",
    r"^step:",          # أزرار خطوات قديمة (غير مستخدمة حالياً)
    r"^edit:",
    r"^um:",
    r"^back_",
    r"^approve:",
    r"^reject:",

    # التقارير والتصدير (admin_reports & admin_printing)
    # ===========================
    r"^filter:",              # فلترة (patient, patient_text, hospital, department, date, all)
    r"^action_type:",         # نوع الإجراء (all, etc.)
    r"^add_date_filter:",     # فلترة التاريخ (yes, no)
    r"^print_patient:",       # طباعة مريض محدد
    r"^patient_page:",        # صفحات المرضى
    r"^print_type:",          # نوع الطباعة
    r"^period:",              # الفترة الزمنية
    r"^perf_period:",         # فترة أداء المترجمين
    r"^export:",              # تصدير التقارير
    r"^opt:",                 # خيارات الطباعة
    r"^generate:",            # توليد التقارير
    r"^back:",                # أزرار الرجوع (جديد)
    r"^print:",               # أوامر الطباعة (cancel)
    r"^abort$",               # إلغاء المحادثة (جديد)
    r"^year:",                # اختيار السنة
    r"^month:",               # اختيار الشهر
    r"^select_hospital:",     # اختيار مستشفى
    r"^select_dept:",         # اختيار قسم
    r"^dept_option:",         # خيارات القسم
    r"^hospital:",            # خيارات المستشفى
    r"^dept:",                # خيارات القسم
    r"^separator$",           # فاصل

    # ===========================
    # ملخص الحالة (case summary)
    # ===========================
    r"^cs_patient:\d+$",
    r"^cs_page:\d+$",
    r"^cs_rep:\d+:\d+$",
    r"^cs_back_to_list$",
    r"^cs_cancel$",
    r"^cs_noop$",

    # Healthcare module — all sub-module prefixes handled in group 1/2.
    # The fallback (group 999) still receives them due to PTB propagation,
    # so list them here to suppress false "unhandled" warnings.
    r"^hc:",       # shared healthcare navigation
    r"^wca:",      # woundcare flow
    r"^hcfu:",     # medical follow-up flow
    r"^hcmed:",    # medications / pharmacy flow
    r"^hcsup:",    # medical supplies flow
    r"^hcoth:",    # other healthcare flow
    r"^hceval:",   # healthcare evaluation PDF report
    r"^hcphfin:",  # pharmacy financial report
    r"^hcphprint:", # pharmacy evacuation ledger print
    # Shared platform infrastructure
    r"^sel_pat:",
    r"^msel:",
    r"^upl:",

    # General services module — handled in group 15.
    r"^gs:",
    r"^gsa:",
    r"^gsd:",
    r"^gsp:",

    # Residency module — handled in groups 16 and 20.
    r"^rn:",
    r"^rna:",
    r"^rnf:",
    r"^rnr:",

    # Admin module access management — handled in group 1.
    r"^amod:",

    # Delete reports module — all delrep:* callbacks.
    r"^delrep:",

    # Daily patients from schedule management — dp_*_from_schedule callbacks.
    r"^dp_add_from_schedule$",
    r"^dp_view_from_schedule$",
    r"^dp_delete_from_schedule$",
    r"^dp_confirm_delete_from_schedule$",
    r"^dp_save_from_schedule$",

    # Translator status dashboard — translator:* callbacks.
    r"^translator:",

    # Reports recovery ConversationHandler — recovery:* and entry callback.
    r"^recovery:",
    r"^admin:reports_recovery$",

    # Admin notes ConversationHandler — inline cancel button.
    r"^admin_cancel$",

    # New reporting system (admin_reports_menu + patient + comprehensive)
    r"^report_menu:",      # Main reports menu dispatcher
    r"^pr:",               # Patient report (v1 - deprecated)
    r"^pr2:",              # Patient report v2 with patient_selector
    r"^cr:",               # Comprehensive report — cr:* callbacks

    # Appointments system
    r"^apt:",              # Upcoming appointments — apt:* callbacks

    # Evaluation menu system
    r"^eval_menu:",        # Evaluation menu dispatcher — eval_menu:* callbacks
    r"^admin:evaluation$", # Translator evaluation entry point (triggered from eval_menu button)

    # Delete reports menu system
    r"^del_menu:",         # Delete reports menu dispatcher — del_menu:* callbacks
    r"^del_hc:",           # Healthcare reports deletion — del_hc:* callbacks
    r"^del_svc:",          # Services reports deletion — del_svc:* callbacks

    # System management menu (admin_system_menu.py) — groups hospitals/patients/
    # schedule/accounts/appointments under "🛠️ إدارة النظام".
    r"^sys_menu:",         # System menu dispatcher — sys_menu:* callbacks
    r"^goto:",             # Direct entry points reused by the system menu (goto:schedule, goto:appointments)

    r"^medfiles:",         # Medical files quick-access button — medfiles:{report_id}
    r"^pndrep:",           # Pending medical reports screen (system menu) — pndrep:*
]

# ================================================
# Safe Keyboard Builder
# ================================================

def get_back_keyboard(callback_data="back_to_main"):
    """إنشاء لوحة مفاتيح رجوع آمنة"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data=callback_data)]
    ])

# ================================================
# Universal Fallback Handler for Callbacks
# ================================================

# ✅ أنماط مُشتقّة آلياً من المعالِجات المسجَّلة فعلياً وقت الإقلاع — تُملأ
# في register(app) أدناه. سبب وجودها: KNOWN_CALLBACKS أعلاه كانت **نسخة
# يدوية مكرَّرة** من تسجيلات المعالِجات الحقيقية، وأي نمط جديد يُضاف للبوت
# ويُنسى هنا يُنتج تحذير "زر غير متاح" كاذباً لكل ضغطة رغم نجاح الزر فعلاً
# (نفس نمط "المنطق نفسه في مكانين يتباعدان" المتكرر في هذا المشروع).
# وقع هذا فعلياً مع `medrep_count:` — زر عدد الفحوصات المنتظرة، مسجَّل
# بمعالِج حقيقي في conversation_handler.py لكنه غائب عن القائمة اليدوية،
# فظهر 28 مرة في تقرير أخطاء 2026-08-18 كـ"غير معالَج" رغم عمله السليم.
# الاشتقاق الآلي يُنهي هذا الانحراف نهائياً: أي معالِج له pattern يُسكَت
# تلقائياً بلا أي تعديل هنا.
_REGISTERED_PATTERNS: list[str] = []


def _snapshot_registered_patterns(app) -> None:
    """يلتقط أنماط كل CallbackQueryHandler مسجَّل فعلاً (عدا معالِج الفلبَك
    نفسه) — بما فيها المتداخلة داخل ConversationHandler.

    ⚠️ يُستدعى من register() الذي يُسجَّل **آخر شيء** في handlers_registry.py،
    فكل المعالِجات الأخرى موجودة على app وقت الالتقاط."""
    from telegram.ext import CallbackQueryHandler as _CQH

    collected: set[str] = set()

    def _collect(h):
        if isinstance(h, _CQH):
            p = getattr(h, "pattern", None)
            if p is None:
                return  # بلا نمط = قنّاص شامل أو معالِج مقيَّد بحالة محادثة
            pat = p.pattern if hasattr(p, "pattern") else str(p)
            if pat and pat not in (".*", ".+", "^.*$", "^.+$"):
                collected.add(pat)

    for group, handlers in app.handlers.items():
        if group == 999:      # لا نلتقط الفلبَك نفسه
            continue
        for h in handlers:
            _collect(h)
            if hasattr(h, "states"):
                for hlist in h.states.values():
                    for hh in hlist:
                        _collect(hh)
                for hh in getattr(h, "entry_points", []):
                    _collect(hh)
                for hh in getattr(h, "fallbacks", []):
                    _collect(hh)

    _REGISTERED_PATTERNS.clear()
    _REGISTERED_PATTERNS.extend(sorted(collected))
    logger.info(
        f"🔎 التقاط {len(_REGISTERED_PATTERNS)} نمط callback مسجَّل فعلياً "
        f"(إسكات تلقائي للفلبَك، بلا صيانة يدوية)"
    )


def is_known_callback(callback_data: str) -> bool:
    """التحقق مما إذا كان الـ callback معروفاً ومعالجاً بواسطة handler آخر.

    مصدران: الأنماط المُشتقّة آلياً من التسجيل الفعلي (الأساس)، ثم القائمة
    اليدوية KNOWN_CALLBACKS (تكملة للمعالِجات المقيَّدة بحالة محادثة بلا
    pattern، والتي لا يمكن اشتقاقها آلياً)."""
    for pattern in _REGISTERED_PATTERNS:
        try:
            if re.match(pattern, callback_data):
                return True
        except re.error:
            continue
    for pattern in KNOWN_CALLBACKS:
        if re.match(pattern, callback_data):
            return True
    return False

async def handle_any_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج شامل لأي callback query - يضمن عدم تعليق البوت أبداً
    هذا الـ handler يعمل فقط على الـ callbacks غير المعروفة
    """
    query = update.callback_query
    
    if not query:
        return
    
    callback_data = query.data or ""
    
    # تجاهل الـ callbacks المعروفة - ستتم معالجتها بواسطة handlers أخرى
    if is_known_callback(callback_data):
        # حتى لو كانت معرفة، أحيانًا لا يوجد handler مطابق (مثل فشل تسجيل الهاندلرز أونلاين).
        # نعمل `answer` لتفادي صمت/تحميل تيليجرام.
        try:
            await query.answer()
        except Exception:
            logger.debug("تم تجاهل استثناء في handle_any_callback", exc_info=True)
        return
    
    try:
        # الرد على الـ callback لمنع التعليق (loading indicator)
        try:
            await query.answer()
        except Exception:
            logger.debug("تم تجاهل استثناء في handle_any_callback", exc_info=True)
        
        # ✅ ERROR لا warning — WARNING لا يصل لتقرير الأخطاء اليومي
        # (services/error_digest.py يلتقط ERROR فأعلى فقط)، فكان هذا
        # المسار — "زر ضُغِط ولا معالِج مختص له" بالضبط ما طلب المستخدم
        # مراقبته — غير مرئي بصمت رغم وجود الكود الذي يكتشفه أصلاً. دُقِّق
        # KNOWN_CALLBACKS مقابل كل نمط callback_data حرفي حقيقي مُستخدَم
        # في المشروع قبل هذا التغيير (بلا أي فجوة موجودة) لتفادي إغراق
        # التقرير اليومي بإيجابيات كاذبة فور التفعيل.
        logger.error(f"⚠️ Unhandled callback received: {callback_data}")
        
        # للـ callbacks غير المعروفة، نرسل رسالة بسيطة فقط
        # بدون محاولة تخمين نوع الـ callback
        try:
            await query.answer("⚠️ هذا الزر غير متاح حالياً", show_alert=False)
        except Exception:
            logger.debug("تم تجاهل استثناء في handle_any_callback", exc_info=True)
        
    except Exception as e:
        logger.error(f"❌ Error in handle_any_callback: {e}")

async def _safe_edit_message(query, text, keyboard=None):
    """تعديل الرسالة بشكل آمن مع معالجة جميع الأخطاء"""
    try:
        await query.edit_message_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    except BadRequest as e:
        error_msg = str(e).lower()
        # تجاهل أخطاء "message is not modified" و "message to edit not found"
        if "not modified" in error_msg or "not found" in error_msg:
            pass
        else:
            logger.warning(f"⚠️ BadRequest in _safe_edit_message: {e}")
    except Exception as e:
        logger.warning(f"⚠️ Error in _safe_edit_message: {e}")

# ================================================
# Universal Fallback Handler for Messages
# ================================================

async def handle_any_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    معالج شامل لأي رسالة غير معالجة
    """
    try:
        if not update.message:
            return
        
        message_text = update.message.text or ""
        user = update.effective_user
        
        # ✅ السماح لأزرار ConversationHandlers بالمرور
        # هذه الأزرار يجب أن تصل إلى handlers المخصصة لها
        CONVERSATION_BUTTONS = [
            "✏️ تعديل التقارير",
            "🗑️ حذف التقارير",
            "📝 إضافة تقرير جديد",
            "❌ إلغاء العملية الحالية",
            "📎 المرفقات الطبية",
        ]
        
        if message_text in CONVERSATION_BUTTONS:
            # دع ConversationHandler يتعامل مع هذا
            return
        
        # التحقق من وجود conversation نشط - لا نتدخل
        conversation_keys = [
            'waiting_for_', 'edit_', 'add_', '_state', 'report_tmp',
            'admin_', '_conversation_state'
        ]
        if any(key in str(context.user_data.keys()) for key in conversation_keys):
            # محادثة نشطة - لا نتدخل
            return
        
        # رسائل مساعدة
        if any(word in message_text.lower() for word in ["مساعدة", "help", "مساعده"]):
            await update.message.reply_text(
                "ℹ️ **مساعدة**\n\n"
                "استخدم /start للوصول للقائمة الرئيسية\n"
                "استخدم /cancel لإلغاء أي عملية جارية",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # رسائل إلغاء
        if any(word in message_text.lower() for word in ["إلغاء", "الغاء", "cancel"]):
            context.user_data.clear()
            await update.message.reply_text(
                "✅ **تم الإلغاء**\n\n"
                "استخدم /start للبدء من جديد",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # تجاهل الرسائل الأخرى بصمت
        logger.debug(f"📝 Ignoring message: {message_text[:50]}")
        
    except Exception as e:
        logger.error(f"❌ Error in handle_any_message: {e}")

# ================================================
# Registration
# ================================================

def register(app):
    """تسجيل معالجات الـ fallback الشاملة"""
    logger.info("📋 تسجيل universal fallback handlers...")

    # ✅ يُلتقَط قبل إضافة معالِج الفلبَك نفسه — كل المعالِجات الأخرى مسجَّلة
    # بالفعل في هذه اللحظة (هذا الملف آخر ما يُسجَّل، انظر handlers_registry.py).
    try:
        _snapshot_registered_patterns(app)
    except Exception:
        # فشل الالتقاط لا يجوز أن يمنع إقلاع البوت — تبقى القائمة اليدوية
        logger.warning("⚠️ تعذّر التقاط الأنماط المسجَّلة تلقائياً", exc_info=True)

    # 1. معالج لجميع callback queries غير المعالجة (أولوية منخفضة جداً)
    app.add_handler(
        CallbackQueryHandler(handle_any_callback),
        group=999  # آخر شيء يتم تنفيذه
    )
    
    # 2. ❌ تم تعطيل معالج الرسائل النصية لأنه يتداخل مع ConversationHandlers
    # ConversationHandlers تحتاج أن تلتقط الرسائل النصية للأزرار
    # app.add_handler(
    #     MessageHandler(
    #         filters.TEXT & ~filters.COMMAND,
    #         handle_any_message
    #     ),
    #     group=999
    # )
    
    logger.info("✅ تم تسجيل universal fallback handlers (callbacks فقط) في group 999")

