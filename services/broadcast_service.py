# =============================
# services/broadcast_service.py
# 📢 نظام البث المحسّن للتقارير - إرسال للمجموعة
# =============================

from db.session import SessionLocal
from db.models import Translator
from config.settings import ADMIN_IDS
from telegram import Bot
from telegram.constants import ParseMode
import logging
import os

logger = logging.getLogger(__name__)

# إعدادات المجموعة - استخدام GROUP_CHAT_ID من settings
try:
    from config.settings import GROUP_CHAT_ID
    REPORTS_GROUP_ID = GROUP_CHAT_ID if GROUP_CHAT_ID else os.getenv("REPORTS_GROUP_ID", "")
except ImportError:
    REPORTS_GROUP_ID = os.getenv("REPORTS_GROUP_ID", "")

# تفعيل الإرسال للمجموعة فقط (افتراضياً مفعّل)
USE_GROUP_BROADCAST = os.getenv("USE_GROUP_BROADCAST", "true").lower() == "true"

# طباعة معلومات المجموعة عند التحميل (للمساعدة في التشخيص)
if REPORTS_GROUP_ID:
    logger.info(f"📢 تم تحميل GROUP_CHAT_ID: {REPORTS_GROUP_ID}")
else:
    logger.warning("⚠️ GROUP_CHAT_ID غير محدد - سيتم إرسال التقارير للأدمن فقط!")


async def broadcast_new_report(bot: Bot, report_data: dict):
    """
    بث تقرير جديد - إرسال للمجموعة فقط (محسّن للأداء)
    
    ⚡ يرسل التقرير للمجموعة فقط - لا يرسل للمستخدمين الفرديين
    هذا يحسن الأداء ويقلل الضغط على البوت

    Args:
        bot: كائن البوت
        report_data: بيانات التقرير كـ dictionary
    
    Returns:
        tuple: (success: bool, error_message: str) - True إذا نجح الإرسال للمجموعة، False إذا فشل
    """
    # تنسيق الرسالة
    message = format_report_message(report_data)

    # 🚀 إرسال للمجموعة فقط (الطريقة المفضلة)
    if REPORTS_GROUP_ID:
        try:
            # تحويل GROUP_CHAT_ID إلى int إذا كان string
            group_id = int(REPORTS_GROUP_ID) if isinstance(REPORTS_GROUP_ID, str) and REPORTS_GROUP_ID.lstrip('-').isdigit() else REPORTS_GROUP_ID
            
            logger.info(f"📤 محاولة إرسال التقرير للمجموعة: {group_id}")
            
            await bot.send_message(
                chat_id=group_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            logger.info(f"✅ تم إرسال التقرير بنجاح للمجموعة: {group_id}")
            
            # إرسال التقرير للأدمن أيضاً (بالإضافة للمجموعة)
            try:
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=message,
                            parse_mode=ParseMode.MARKDOWN,
                            disable_web_page_preview=True
                        )
                        logger.info(f"✅ تم إرسال التقرير إلى الأدمن {admin_id}")
                    except Exception as admin_error:
                        logger.error(f"❌ فشل إرسال إلى الأدمن {admin_id}: {admin_error}")
            except Exception as admin_fallback_error:
                logger.error(f"❌ فشل في الإرسال للأدمن: {admin_fallback_error}")
            
            # إرسال تنبيه للمستخدم أن التقرير تم إرساله بنجاح
            try:
                await send_user_notification(bot, report_data)
            except Exception as e:
                logger.debug(f"⚠️ لم يتم إرسال تنبيه للمستخدم: {e}")
            
            return True, None

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ فشل إرسال التقرير للمجموعة {REPORTS_GROUP_ID}: {error_msg}", exc_info=True)
            logger.error(f"❌ نوع الخطأ: {type(e).__name__}")
            logger.error(f"❌ تفاصيل الخطأ: {error_msg}")
            
            # في حالة فشل الإرسال للمجموعة، نرسل للأدمن فقط كاحتياطي
            logger.warning("⚠️ محاولة إرسال للأدمن كاحتياطي")
            # محاولة إرسال احتياطي للأدمن
            try:
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        logger.info(f"✅ تم إرسال التقرير إلى الأدمن {admin_id} (احتياطي)")
                    except Exception as admin_error:
                        logger.error(f"❌ فشل إرسال إلى الأدمن {admin_id}: {admin_error}")
            except Exception as admin_fallback_error:
                logger.error(f"❌ فشل في الإرسال الاحتياطي للأدمن: {admin_fallback_error}")
            
            return False, error_msg
    else:
        logger.warning("⚠️ REPORTS_GROUP_ID غير محدد - سيتم الإرسال للأدمن فقط")
        # إرسال للأدمن فقط (في حالة عدم وجود معرف المجموعة)
        try:
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    logger.info(f"✅ تم إرسال التقرير إلى الأدمن {admin_id}")
                except Exception as e:
                    logger.error(f"❌ فشل إرسال إلى الأدمن {admin_id}: {e}")
        except Exception as admin_error:
            logger.error(f"❌ فشل في الإرسال للأدمن: {admin_error}")
        
        return False, "GROUP_CHAT_ID غير محدد في config.env"


async def send_user_notification(bot: Bot, report_data: dict):
    """
    إرسال تنبيه للمستخدم الذي أنشأ التقرير (اختياري)
    
    Args:
        bot: كائن البوت
        report_data: بيانات التقرير
    """
    try:
        # محاولة استخدام translator_id أولاً (أسرع)
        translator_id = report_data.get('translator_id')
        if translator_id:
            try:
                await bot.send_message(
                    chat_id=translator_id,
                    text="✅ **تم إرسال التقرير بنجاح إلى المجموعة**",
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.debug(f"✅ تم إرسال تنبيه للمترجم (ID: {translator_id})")
                return
            except Exception as e:
                logger.debug(f"⚠️ لم يتم إرسال تنبيه للمترجم (ID: {translator_id}): {e}")
        
        # Fallback: استخدام translator_name
        translator_name = report_data.get('translator_name', '')
        if translator_name and translator_name != 'غير محدد':
            with SessionLocal() as s:
                translator = s.query(Translator).filter_by(full_name=translator_name).first()
                if translator:
                    try:
                        await bot.send_message(
                            chat_id=translator.tg_user_id,
                            text="✅ **تم إرسال التقرير بنجاح إلى المجموعة**",
                            parse_mode=ParseMode.MARKDOWN
                        )
                        logger.debug(f"✅ تم إرسال تنبيه للمترجم {translator_name}")
                    except Exception as e:
                        logger.debug(f"⚠️ لم يتم إرسال تنبيه للمترجم {translator_name}: {e}")
    except Exception as e:
        logger.debug(f"⚠️ خطأ في إرسال التنبيه: {e}")


async def broadcast_initial_case(bot: Bot, case_data: dict):
    """
    بث حالة أولية جديدة لجميع المستخدمين المعتمدين والأدمن
    
    Args:
        bot: كائن البوت
        case_data: بيانات الحالة كـ dictionary
    """
    # تنسيق الرسالة
    message = format_initial_case_message(case_data)
    
    # الحصول على جميع المستخدمين المعتمدين
    with SessionLocal() as s:
        approved_users = s.query(Translator).filter_by(
            is_approved=True, 
            is_suspended=False
        ).all()
        
        # إرسال للمستخدمين
        for user in approved_users:
            try:
                await bot.send_message(
                    chat_id=user.tg_user_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )
                print(f"تم ارسال الحالة الاولية الى {user.full_name}")
            except Exception as e:
                print(f"فشل ارسال الى {user.full_name}: {e}")
    
    # إرسال للأدمن
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
            print(f"تم ارسال الحالة الاولية الى الادمن {admin_id}")
        except Exception as e:
            print(f"فشل ارسال الى الادمن {admin_id}: {e}")


def format_report_message(data: dict) -> str:
    """
    تنسيق رسالة التقرير الجديد
    """
    message = "🆕 **تقرير جديد**\n\n"
    
    # التاريخ - إذا كان مُنسقاً بالفعل (من user_reports_add.py) نستخدمه كما هو
    if data.get('report_date'):
        # إذا كان التاريخ مُنسقاً بالفعل بصيغة 12 ساعة، نستخدمه مباشرة
        if isinstance(data['report_date'], str) and ('صباحاً' in data['report_date'] or 'مساءً' in data['report_date'] or 'ظهراً' in data['report_date']):
            message += f"📅🕐 التاريخ: {data['report_date']}\n\n"
        else:
            # محاولة تحويل التاريخ القديم
            from datetime import datetime
            try:
                if isinstance(data['report_date'], str):
                    date_obj = datetime.strptime(data['report_date'], '%Y-%m-%d %H:%M')
                else:
                    date_obj = data['report_date']
                
                days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
                MONTH_NAMES_AR = {1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"}
                
                # تحويل الوقت إلى صيغة 12 ساعة
                hour = date_obj.hour
                minute = date_obj.minute
                if hour == 0:
                    time_str = f"12:{minute:02d} صباحاً"
                elif hour < 12:
                    time_str = f"{hour}:{minute:02d} صباحاً"
                elif hour == 12:
                    time_str = f"12:{minute:02d} ظهراً"
                else:
                    time_str = f"{hour-12}:{minute:02d} مساءً"
                
                day_name = days_ar.get(date_obj.weekday(), '')
                message += f"📅🕐 التاريخ: {date_obj.strftime('%d')} {MONTH_NAMES_AR.get(date_obj.month, date_obj.month)} {date_obj.year} ({day_name}) - {time_str}\n\n"
            except:
                message += f"📅 التاريخ: {data['report_date']}\n\n"
    
    # اسم المريض
    if data.get('patient_name'):
        message += f"👤 اسم المريض: {data['patient_name']}\n\n"
    
    # المستشفى
    if data.get('hospital_name'):
        message += f"🏥 المستشفى: {data['hospital_name']}\n\n"
    
    # القسم
    if data.get('department_name'):
        message += f"🏷️ القسم: {data['department_name']}\n\n"
    
    # اسم الطبيب
    if data.get('doctor_name') and data.get('doctor_name') != 'لم يتم التحديد':
        message += f"👨‍⚕️ اسم الطبيب: {data['doctor_name']}\n\n"
    
    # نوع الإجراء - بداية التوحيد
    if data.get('medical_action'):
        message += f"📌 نوع الإجراء:\n{data['medical_action']}\n\n"
    
    # شكوى المريض - فقط إذا كانت موجودة وغير فارغة
    if data.get('complaint_text') and data.get('complaint_text').strip():
        message += f"📌 شكوى المريض:\n{data['complaint_text']}\n\n"
    
    # عرض الحقول الفردية لـ "استشارة مع قرار عملية" بشكل منفصل
    if data.get('medical_action') == 'استشارة مع قرار عملية':
        # التشخيص
        if data.get('diagnosis') and data.get('diagnosis').strip():
            message += f"🔬 **التشخيص:**\n{data['diagnosis']}\n\n"
        
        # قرار الطبيب
        if data.get('decision') and data.get('decision').strip():
            message += f"📝 **قرار الطبيب:**\n{data['decision']}\n\n"
        
        # اسم العملية بالإنجليزي
        if data.get('operation_name_en') and data.get('operation_name_en').strip():
            message += f"🔤 **اسم العملية بالإنجليزي:**\n{data['operation_name_en']}\n\n"
        
        # نسبة نجاح العملية
        if data.get('success_rate') and data.get('success_rate').strip():
            message += f"📊 **نسبة نجاح العملية:**\n{data['success_rate']}\n\n"
        
        # نسبة الاستفادة من العملية
        if data.get('benefit_rate') and data.get('benefit_rate').strip():
            message += f"💡 **نسبة الاستفادة من العملية:**\n{data['benefit_rate']}\n\n"
        
        # الفحوصات والأشعة
        if data.get('tests') and data.get('tests').strip() and data.get('tests') != 'لا يوجد':
            message += f"🧪 **الفحوصات والأشعة:**\n{data['tests']}\n\n"
    
    # عرض الحقول الفردية لـ "استشارة أخيرة" (final_consult) بشكل منفصل إذا كان diagnosis موجوداً
    elif data.get('medical_action') == 'استشارة أخيرة' and data.get('diagnosis') and data.get('diagnosis').strip():
        # التشخيص النهائي
        message += f"🔬 **التشخيص النهائي:**\n{data['diagnosis']}\n\n"
        
        # استخراج قرار الطبيب من doctor_decision
        doctor_decision_text = data.get('doctor_decision', '')
        if doctor_decision_text and 'قرار الطبيب:' in doctor_decision_text:
            decision_parts = doctor_decision_text.split('قرار الطبيب:')
            if len(decision_parts) > 1:
                decision = decision_parts[1].split('التوصيات')[0].strip()
                if decision:
                    message += f"📝 **قرار الطبيب:**\n{decision}\n\n"
        
        # التوصيات الطبية - استخدام recommendations من data إذا كان موجوداً، وإلا استخراجه من doctor_decision
        recommendations = data.get('recommendations', '')
        if not recommendations and doctor_decision_text and 'التوصيات الطبية:' in doctor_decision_text:
            recommendations_parts = doctor_decision_text.split('التوصيات الطبية:')
            if len(recommendations_parts) > 1:
                recommendations = recommendations_parts[1].strip()
        if recommendations and recommendations.strip():
            message += f"💡 **التوصيات الطبية:**\n{recommendations}\n\n"
    
    # قرار الطبيب - التحقق من نوع المحتوى (للأنواع الأخرى)
    elif data.get('doctor_decision') and data.get('doctor_decision').strip():
        doctor_decision_text = data['doctor_decision']
        
        # التحقق من نوع المحتوى - إذا كان "تفاصيل الجلسة" أو "تفاصيل الجهاز" أو "نوع الأشعة"، لا نضيف "قرار الطبيب"
        if any(keyword in doctor_decision_text for keyword in ['تفاصيل الجلسة:', 'تفاصيل الجهاز:', 'نوع الأشعة والفحوصات:']):
            # هذه أنواع خاصة من التفاصيل - نعرضها بدون عنوان "قرار الطبيب"
            message += f"📌 {doctor_decision_text}\n\n"
        # التحقق من وجود كلمات مفتاحية معروفة (قرار الطبيب، التشخيص، إلخ)
        elif any(keyword in doctor_decision_text for keyword in [
            'قرار الطبيب:', 'التشخيص:', 'الفحوصات المطلوبة:', 'تفاصيل العملية:', 
            'سبب الرقود:', 'اسم العملية بالإنجليزي:', 'ملاحظات:', 
            'Diagnosis:', 'Decision:', 'Tests:'
        ]):
            # النص منسق مسبقاً - نعرضه مباشرة
            message += f"📌 {doctor_decision_text}\n\n"
        else:
            # النص عادي - نضيف عنوان "قرار الطبيب:" فقط إذا لم يكن نوع إجراء خاص
            # التحقق من نوع الإجراء من medical_action
            medical_action = data.get('medical_action', '')
            if medical_action in ['علاج طبيعي وإعادة تأهيل', 'علاج طبيعي', 'أجهزة تعويضية', 'أشعة وفحوصات']:
                # هذه الأنواع لا تحتوي على "قرار الطبيب" - نعرض النص مباشرة
                message += f"📌 {doctor_decision_text}\n\n"
            else:
                # النص عادي - نضيف عنوان "قرار الطبيب:"
                message += f"📌 قرار الطبيب:\n{doctor_decision_text}\n\n"
    
    # حالة الحالة (إذا كانت موجودة) - فقط إذا لم تكن جزءاً من قرار الطبيب
    if data.get('case_status') and data.get('case_status') != 'لا يوجد':
        case_status_text = data['case_status']
        # التحقق من أن case_status ليس جزءاً من doctor_decision
        doctor_decision = data.get('doctor_decision', '')
        if not (doctor_decision and case_status_text in doctor_decision):
            message += f"📌 الإجراء الذي تم:\n{case_status_text}\n\n"
    
    # بيانات الأشعة (إذا كانت موجودة)
    if data.get('radiology_type') and data.get('radiology_type') != 'لا يوجد':
        message += f"📌 نوع الأشعة:\n{data['radiology_type']}\n\n"
        if data.get('radiology_delivery_date') and data.get('radiology_delivery_date') != 'لا يوجد':
            message += f"📌 تاريخ التسليم:\n{data['radiology_delivery_date']}\n\n"
    
    # موعد العودة - تنسيق محسّن (فقط إذا كان موجوداً وليس None)
    if data.get('followup_date') and data.get('followup_date') != 'لا يوجد':
        from datetime import datetime
        try:
            if isinstance(data['followup_date'], str):
                # محاولة تحليل التاريخ من النص
                if ' - ' in data['followup_date']:
                    # التاريخ بصيغة: "21 نوفمبر 2025 (الجمعة) - 7:00 مساءً"
                    message += f"📅🕐 موعد العودة: {data['followup_date']}\n\n"
                else:
                    message += f"📅 موعد العودة: {data['followup_date']}\n\n"
            else:
                # كائن datetime
                date_obj = data['followup_date']
                days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
                MONTH_NAMES_AR = {1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"}
                day_name = days_ar.get(date_obj.weekday(), '')
                date_str = f"{date_obj.strftime('%d')} {MONTH_NAMES_AR.get(date_obj.month, date_obj.month)} {date_obj.year} ({day_name})"
                
                if data.get('followup_time'):
                    hour, minute = data['followup_time'].split(':')
                    hour_int = int(hour)
                    if hour_int == 0:
                        time_display = f"12:{minute} صباحاً"
                    elif hour_int < 12:
                        time_display = f"{hour_int}:{minute} صباحاً"
                    elif hour_int == 12:
                        time_display = f"12:{minute} ظهراً"
                    else:
                        time_display = f"{hour_int-12}:{minute} مساءً"
                    message += f"📅🕐 موعد العودة: {date_str} - {time_display}\n\n"
                else:
                    message += f"📅 موعد العودة: {date_str}\n\n"
        except:
            message += f"📅 موعد العودة: {data['followup_date']}\n\n"
    
    # سبب العودة (فقط إذا كان موجوداً وليس None أو فارغاً)
    if data.get('followup_reason') and data.get('followup_reason') != 'لا يوجد':
        message += f"✍️ سبب العودة: {data['followup_reason']}\n\n"
    
    # المترجم
    if data.get('translator_name'):
        message += f"👨‍⚕️ المترجم: {data['translator_name']}"
    
    return message


def format_initial_case_message(data: dict) -> str:
    """
    تنسيق رسالة الحالة الأولية
    """
    message = "🆕 **حالة أولية جديدة**\n"
    message += "━━━━━━━━━━━━━━━━\n\n"
    
    if data.get('patient_name'):
        message += f"👤 **اسم المريض:** {data['patient_name']}\n"
    
    if data.get('patient_age'):
        message += f"🎂 **العمر:** {data['patient_age']}\n"
    
    if data.get('main_complaint'):
        message += f"🩺 **الشكوى الرئيسية:** {data['main_complaint']}\n"
    
    message += "\n"
    
    if data.get('current_history'):
        message += f"📋 **التاريخ المرضي:** {data['current_history']}\n"
    
    if data.get('notes'):
        message += f"📝 **ملاحظات:** {data['notes']}\n"
    
    if data.get('previous_procedures'):
        message += f"🏥 **إجراءات سابقة:** {data['previous_procedures']}\n"
    
    if data.get('test_details'):
        message += f"🧪 **الفحوصات:** {data['test_details']}\n"
    
    message += "\n━━━━━━━━━━━━━━━━"
    
    return message


async def broadcast_schedule(bot: Bot, photo_source: str, schedule_data: dict, use_file_id: bool = False):
    """
    بث جدول جديد لجميع المستخدمين المعتمدين والأدمن
    
    Args:
        bot: كائن البوت
        schedule_path: مسار ملف الجدول
        schedule_data: بيانات الجدول كـ dictionary
    """
    # تنسيق الرسالة
    message = format_schedule_message(schedule_data)
    
    # الحصول على جميع المستخدمين المعتمدين
    with SessionLocal() as s:
        approved_users = s.query(Translator).filter_by(
            is_approved=True, 
            is_suspended=False
        ).all()
        
        # إرسال للمستخدمين
        for user in approved_users:
            try:
                if use_file_id:
                    await bot.send_photo(
                        chat_id=user.tg_user_id,
                        photo=photo_source,
                        caption=message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    with open(photo_source, 'rb') as photo:
                        await bot.send_photo(
                            chat_id=user.tg_user_id,
                            photo=photo,
                            caption=message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                print(f"✅ تم إرسال الجدول إلى {user.full_name}")
            except Exception as e:
                print(f"❌ فشل إرسال الجدول إلى {user.full_name}: {e}")
    
    # إرسال للأدمن
    for admin_id in ADMIN_IDS:
        try:
            if use_file_id:
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=photo_source,
                    caption=message + "\n\n👑 **نسخة الأدمن**",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                with open(photo_source, 'rb') as photo:
                    await bot.send_photo(
                        chat_id=admin_id,
                        photo=photo,
                        caption=message + "\n\n👑 **نسخة الأدمن**",
                        parse_mode=ParseMode.MARKDOWN
                    )
            print(f"✅ تم إرسال الجدول إلى الأدمن {admin_id}")
        except Exception as e:
            print(f"❌ فشل إرسال الجدول إلى الأدمن {admin_id}: {e}")


def format_schedule_message(data: dict) -> str:
    """
    تنسيق رسالة الجدول الجديد
    """
    message = "📅 **جدول جديد متاح!**\n"
    message += "━━━━━━━━━━━━━━━━\n\n"
    
    if data.get('date'):
        message += f"📆 **التاريخ:** {data['date']}\n"
    
    if data.get('day_name'):
        message += f"📅 **اليوم:** {data['day_name']}\n"
    
    if data.get('upload_time'):
        message += f"🕐 **وقت الرفع:** {data['upload_time']}\n"
    
    message += "\n"
    message += "💡 **ملاحظة:** تم رفع جدول جديد من قبل الإدارة.\n"
    message += "يمكنك عرضه في أي وقت من خلال الضغط على:\n"
    message += "👉 **📅 جدول اليوم**\n"
    
    message += "\n━━━━━━━━━━━━━━━━"
    
    return message


