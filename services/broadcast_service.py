# =============================
# services/broadcast_service.py
# 📢 نظام البث المحسّن للتقارير - إرسال للمجموعة
# =============================

from db.session import SessionLocal
from db.models import Translator
from config.settings import ADMIN_IDS
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
import logging
import os

logger = logging.getLogger(__name__)

# إعدادات المجموعة
REPORTS_GROUP_ID = os.getenv("REPORTS_GROUP_ID", "")  # معرف المجموعة الخاصة بالتقارير
USE_GROUP_BROADCAST = os.getenv("USE_GROUP_BROADCAST", "true").lower() == "true"  # تفعيل الإرسال للمجموعة


async def broadcast_new_report(bot: Bot, report_data: dict):
    """
    بث تقرير جديد - محسّن للأداء العالي

    إذا كانت المجموعة مفعّلة: يرسل للمجموعة فقط
    إلا: يرسل للمستخدمين الفرديين (الطريقة القديمة)

    Args:
        bot: كائن البوت
        report_data: بيانات التقرير كـ dictionary
    """
    logger.info(f"📤 broadcast_new_report: بدء البث - report_id={report_data.get('report_id')}, medical_action={report_data.get('medical_action')}")
    logger.info(f"📤 broadcast_new_report: USE_GROUP_BROADCAST={USE_GROUP_BROADCAST}, REPORTS_GROUP_ID={REPORTS_GROUP_ID}")
    
    # تنسيق الرسالة
    try:
        message = format_report_message(report_data)
        logger.info(f"✅ broadcast_new_report: تم تنسيق الرسالة بنجاح (طول: {len(message)} حرف)")
    except Exception as format_error:
        logger.error(f"❌ broadcast_new_report: خطأ في تنسيق الرسالة: {format_error}", exc_info=True)
        return

    # 🚀 الطريقة الجديدة: إرسال للمجموعة المنفصلة
    if USE_GROUP_BROADCAST and REPORTS_GROUP_ID:
        logger.info(f"📤 broadcast_new_report: محاولة الإرسال للمجموعة {REPORTS_GROUP_ID}")
        try:
            # إرسال للمجموعة
            # إضافة زر تفاعلي لعرض سبب التأجيل إذا كان التقرير من نوع "تأجيل موعد"
            reply_markup = None
            try:
                # نحاول الحصول على معرف التقرير إن لم يكن موجوداً
                report_id = report_data.get('report_id')
                if not report_id:
                    try:
                        from db.session import SessionLocal
                        from db.models import Report
                        with SessionLocal() as s:
                            q = s.query(Report)
                            # حاول البحث حسب patient_name + hospital + medical_action كقرب
                            patient_name = report_data.get('patient_name')
                            hospital_name = report_data.get('hospital_name')
                            medical_action = report_data.get('medical_action')
                            if patient_name:
                                q = q.filter(Report.patient_name == patient_name)
                            if hospital_name:
                                q = q.filter(Report.hospital_name == hospital_name)
                            if medical_action:
                                q = q.filter(Report.medical_action == medical_action)
                            found = q.order_by(Report.created_at.desc()).first()
                            if found:
                                report_id = found.id
                                logger.info(f"✅ broadcast_service: resolved report_id via DB lookup: {report_id}")
                    except Exception as e:
                        logger.debug(f"broadcast_service: failed to resolve report_id via DB: {e}")

                if report_data.get('medical_action') == 'تأجيل موعد' and report_id:
                    btn = InlineKeyboardButton("📅 عرض سبب التأجيل", callback_data=f"view_reschedule:{report_id}")
                    reply_markup = InlineKeyboardMarkup([[btn]])
            except Exception:
                reply_markup = None

            logger.info(f"📤 broadcast_new_report: محاولة إرسال الرسالة للمجموعة (طول الرسالة: {len(message)} حرف)")
            sent_message = await bot.send_message(
                chat_id=REPORTS_GROUP_ID,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            group_message_id = sent_message.message_id
            logger.info(f"✅ broadcast_new_report: تم إرسال التقرير للمجموعة: {REPORTS_GROUP_ID}, message_id: {group_message_id}")
            
            # إرجاع معرف الرسالة لحفظه في قاعدة البيانات
            report_id = report_data.get('report_id')
            if report_id and group_message_id:
                try:
                    from db.session import SessionLocal
                    from db.models import Report
                    with SessionLocal() as s:
                        report = s.query(Report).filter_by(id=report_id).first()
                        if report:
                            report.group_message_id = group_message_id
                            s.commit()
                            logger.info(f"✅ تم حفظ معرف الرسالة {group_message_id} للتقرير {report_id}")
                except Exception as e:
                    logger.error(f"❌ فشل حفظ معرف الرسالة في قاعدة البيانات: {e}")

            # إرسال التقرير أيضاً للمستخدم الذي أنشأه في محادثته مع البوت
            user_id = report_data.get('user_id') or report_data.get('translator_id')
            if user_id:
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    logger.info(f"✅ تم إرسال التقرير للمستخدم في البوت: {user_id}")
                except Exception as e:
                    logger.warning(f"⚠️ فشل إرسال التقرير للمستخدم {user_id}: {e}")

            # إرسال التقرير للأدمن في محادثتهم مع البوت
            if ADMIN_IDS:
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        logger.info(f"✅ تم إرسال التقرير للأدمن في البوت: {admin_id}")
                    except Exception as e:
                        logger.warning(f"⚠️ فشل إرسال التقرير للأدمن {admin_id}: {e}")

            # إرسال تنبيه للمستخدم عن التقرير الجديد
            await send_user_notification(bot, report_data)
            logger.info(f"✅ broadcast_new_report: اكتمل البث للمجموعة بنجاح")
            return

        except Exception as e:
            logger.error(f"❌ broadcast_new_report: فشل إرسال التقرير للمجموعة: {e}", exc_info=True)
            # في حالة فشل الإرسال للمجموعة، نعود للطريقة القديمة

    # 🏠 الطريقة القديمة: إرسال فردي (احتياطي أو عند عدم تفعيل المجموعة)
    logger.info("📤 استخدام الإرسال الفردي (الطريقة القديمة)")

    # الحصول على جميع المستخدمين المعتمدين
    with SessionLocal() as s:
        approved_users = s.query(Translator).filter_by(
            is_approved=True,
            is_suspended=False
        ).all()

        # إرسال للمستخدمين (مع تحسينات الأداء)
        successful_sends = 0
        failed_sends = 0

        for user in approved_users:
            try:
                await bot.send_message(
                    chat_id=user.tg_user_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )
                successful_sends += 1
                logger.debug(f"✅ تم إرسال التقرير إلى {user.full_name}")
            except Exception as e:
                failed_sends += 1
                logger.error(f"❌ فشل إرسال إلى {user.full_name}: {e}")

        logger.info(f"📊 إرسال فردي مكتمل: {successful_sends} نجح، {failed_sends} فشل")

    # إرسال للأدمن دائماً
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info(f"تم ارسال التقرير الى الادمن {admin_id}")
        except Exception as e:
            logger.error(f"فشل ارسال الى الادمن {admin_id}: {e}")


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
    
    # نوع الإجراء - في نفس السطر
    if data.get('medical_action'):
        message += f"📌 نوع الإجراء: {data['medical_action']}\n\n"
    
    # معالجة خاصة لـ "تأجيل موعد" - عرض الحقول المحددة فقط
    if data.get('medical_action') == 'تأجيل موعد':
        logger.info(f"📅 broadcast_service: معالجة تقرير 'تأجيل موعد'")
        logger.info(f"📅 broadcast_service: data keys = {list(data.keys())}")
        logger.info(f"📅 broadcast_service: app_reschedule_reason من data = {repr(data.get('app_reschedule_reason'))}")
        
        # ✅ سبب تأجيل الموعد - استخدام app_reschedule_reason مع fallback ذكي
        app_reschedule_reason = data.get('app_reschedule_reason', '')
        logger.info(f"📅 broadcast_service: app_reschedule_reason من data = {repr(app_reschedule_reason)}")
        
        # ✅ إذا لم يكن موجوداً، محاولة استخراجه من doctor_decision
        if not app_reschedule_reason or not str(app_reschedule_reason).strip():
            logger.warning(f"⚠️ broadcast_service: app_reschedule_reason فارغ، محاولة استخراجه من doctor_decision")
            doctor_decision = data.get('doctor_decision', '')
            if doctor_decision:
                # محاولة استخراج "سبب تأجيل الموعد" من نص قرار الطبيب
                if 'سبب تأجيل الموعد:' in str(doctor_decision):
                    # استخراج النص بعد "سبب تأجيل الموعد:"
                    parts = str(doctor_decision).split('سبب تأجيل الموعد:', 1)
                    if len(parts) > 1:
                        extracted_reason = parts[1].strip()
                        # إزالة أي نص إضافي بعد السطر الأول
                        if '\n' in extracted_reason:
                            extracted_reason = extracted_reason.split('\n')[0].strip()
                        app_reschedule_reason = extracted_reason
                        logger.info(f"✅ broadcast_service: تم استخراج app_reschedule_reason من doctor_decision = {repr(app_reschedule_reason)}")
        
        # ✅ التحقق من أن app_reschedule_reason موجود وليس فارغاً
        if app_reschedule_reason and str(app_reschedule_reason).strip():
            message += f"📅 **سبب تأجيل الموعد:** {str(app_reschedule_reason).strip()}\n\n"
            logger.info(f"✅ broadcast_service: تم إضافة سبب تأجيل الموعد إلى الرسالة = {repr(app_reschedule_reason)}")
        else:
            logger.warning(f"⚠️ broadcast_service: سبب تأجيل الموعد فارغ أو None، لن يظهر في الرسالة")
        
        # تاريخ العودة (موعد العودة)
        return_date = data.get('app_reschedule_return_date') or data.get('followup_date')
        if return_date and return_date != 'لا يوجد':
            from datetime import datetime
            try:
                if isinstance(return_date, str):
                    # محاولة تحليل التاريخ من النص
                    if ' - ' in return_date:
                        # التاريخ بصيغة: "21 نوفمبر 2025 (الجمعة) - 7:00 مساءً"
                        message += f"📅🕐 **موعد العودة:** {return_date}\n\n"
                    else:
                        message += f"📅 **موعد العودة:** {return_date}\n\n"
                else:
                    # كائن datetime
                    date_obj = return_date
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
                        message += f"📅🕐 **موعد العودة:** {date_str} - {time_display}\n\n"
                    else:
                        message += f"📅 **موعد العودة:** {date_str}\n\n"
            except:
                message += f"📅 **موعد العودة:** {return_date}\n\n"
        
        # سبب العودة - استخدام app_reschedule_return_reason فقط (لا تكرار)
        return_reason = data.get('app_reschedule_return_reason', '')
        if return_reason and str(return_reason).strip() and str(return_reason) != 'لا يوجد':
            message += f"✍️ **سبب العودة:** {str(return_reason).strip()}\n\n"
            logger.info(f"✅ broadcast_service: عرض سبب العودة = {repr(return_reason)}")
        else:
            logger.warning(f"⚠️ broadcast_service: سبب العودة فارغ أو مفقود")
            logger.warning(f"   - app_reschedule_return_reason = {repr(data.get('app_reschedule_return_reason'))}")
            logger.warning(f"   - followup_reason = {repr(data.get('followup_reason'))}")
        
        # المترجم
        if data.get('translator_name'):
            message += f"👨‍⚕️ **المترجم:** {data['translator_name']}"
        
        return message
    
    # عرض الحقول الفردية لـ "استشارة مع قرار عملية" بشكل منفصل ومنظم
    if data.get('medical_action') == 'استشارة مع قرار عملية':
        # شكوى المريض
        if data.get('complaint_text') and data.get('complaint_text').strip():
            message += f"💬 شكوى المريض: {data['complaint_text']}\n\n"
        
        # التشخيص
        if data.get('diagnosis') and data.get('diagnosis').strip():
            message += f"🔬 التشخيص: {data['diagnosis']}\n\n"
        
        # قرار الطبيب
        if data.get('decision') and data.get('decision').strip():
            message += f"📝 قرار الطبيب: {data['decision']}\n\n"
        
        # اسم العملية بالإنجليزي
        if data.get('operation_name_en') and data.get('operation_name_en').strip():
            message += f"🔤 اسم العملية بالإنجليزي: {data['operation_name_en']}\n\n"
        
        # نسبة نجاح العملية
        if data.get('success_rate') and data.get('success_rate').strip():
            message += f"📊 نسبة نجاح العملية: {data['success_rate']}\n\n"
        
        # نسبة الاستفادة من العملية
        if data.get('benefit_rate') and data.get('benefit_rate').strip():
            message += f"💡 نسبة الاستفادة من العملية: {data['benefit_rate']}\n\n"
        
        # الفحوصات والأشعة - في سطر منفصل مع ترقيم وتنظيم
        if data.get('tests') and data.get('tests').strip() and data.get('tests') != 'لا يوجد':
            tests_text = data['tests'].strip()
            # تقسيم النص إلى أسطر إذا كان يحتوي على فواصل
            if '\n' in tests_text or ',' in tests_text or '،' in tests_text:
                # تقسيم النص
                if '\n' in tests_text:
                    lines = [line.strip() for line in tests_text.split('\n') if line.strip()]
                elif ',' in tests_text:
                    lines = [line.strip() for line in tests_text.split(',') if line.strip()]
                else:
                    lines = [line.strip() for line in tests_text.split('،') if line.strip()]
                
                # ترقيم وتنظيم الأسطر
                message += "🧪 الفحوصات والأشعة:\n"
                for i, line in enumerate(lines, 1):
                    message += f"{i}. {line}\n"
                message += "\n"
            else:
                # إذا كان نص واحد، نعرضه في سطر منفصل
                message += f"🧪 الفحوصات والأشعة:\n{tests_text}\n\n"
    
    # معالجة الحقول الأخرى - ترتيب منظم
    else:
        # شكوى المريض - فقط إذا كانت موجودة وغير فارغة
        if data.get('complaint_text') and data.get('complaint_text').strip():
            message += f"💬 شكوى المريض: {data['complaint_text']}\n\n"
        
        # قرار الطبيب - التحقق من نوع المحتوى (للأنواع الأخرى)
        if data.get('doctor_decision') and data.get('doctor_decision').strip():
            doctor_decision_text = data['doctor_decision']
            
            # تحليل النص وتنظيمه - تحويل من صيغة متعددة الأسطر إلى صيغة منظمة
            lines = doctor_decision_text.split('\n')
            organized_lines = []
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # إذا كان السطر يحتوي على ":"، ننظمه
                if ':' in line:
                    # تقسيم السطر إلى عنوان ومحتوى
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        title = parts[0].strip()
                        content = parts[1].strip()
                        # إزالة العلامات الزائدة مثل **
                        title = title.replace('**', '').strip()
                        # إضافة emoji مناسب حسب العنوان
                        emoji_map = {
                            'قرار الطبيب': '📝',
                            'التشخيص': '🔬',
                            'التشخيص النهائي': '🔬',
                            'الفحوصات المطلوبة': '🧪',
                            'تفاصيل العملية': '⚕️',
                            'سبب الرقود': '🏥',
                            'اسم العملية بالإنجليزي': '🔤',
                            'ملاحظات': '📝',
                            'سبب تأجيل الموعد': '📅',
                            'تاريخ العودة الجديد': '📅',
                            'سبب العودة': '✍️',
                            'ملخص الرقود': '📋',
                            'تفاصيل الجلسة': '🏃',
                            'تفاصيل الجهاز': '🦾',
                            'نوع الأشعة والفحوصات': '🔬',
                            'التوصيات الطبية': '💡',
                            'وضع الحالة': '📌'
                        }
                        emoji = emoji_map.get(title, '📌')
                        organized_lines.append(f"{emoji} {title}: {content}")
                    else:
                        organized_lines.append(line)
                else:
                    # إذا كان السطر عادي، نضيفه كما هو
                    organized_lines.append(line)
            
            # التحقق من نوع الإجراء
            medical_action = data.get('medical_action', '')
            if medical_action in ['علاج طبيعي وإعادة تأهيل', 'علاج طبيعي', 'أجهزة تعويضية', 'أشعة وفحوصات', 'تأجيل موعد', 'خروج من المستشفى', 'خروج', 'ترقيد', 'عملية جراحية', 'عملية', 'استشارة نهائية']:
                # هذه الأنواع لا تحتوي على "قرار الطبيب" - نعرض النص مباشرة
                message += '\n'.join(organized_lines) + '\n\n'
            else:
                # التحقق من وجود "قرار الطبيب" في النص
                if not any('قرار الطبيب' in line for line in organized_lines):
                    # إذا لم يكن موجوداً، نضيفه في البداية
                    if organized_lines:
                        message += f"📝 قرار الطبيب: {organized_lines[0]}\n\n"
                        if len(organized_lines) > 1:
                            message += '\n'.join(organized_lines[1:]) + '\n\n'
                    else:
                        message += f"📝 قرار الطبيب: {doctor_decision_text}\n\n"
                else:
                    message += '\n'.join(organized_lines) + '\n\n'
    
    # حالة الحالة (إذا كانت موجودة) - فقط إذا لم تكن جزءاً من قرار الطبيب
    if data.get('case_status') and data.get('case_status') != 'لا يوجد':
        case_status_text = data['case_status']
        # التحقق من أن case_status ليس جزءاً من doctor_decision
        doctor_decision = data.get('doctor_decision', '')
        if not (doctor_decision and case_status_text in doctor_decision):
            message += f"📌 الإجراء الذي تم: {case_status_text}\n\n"
    
    # بيانات الأشعة (إذا كانت موجودة) - النص في سطر منفصل مع ترقيم
    if data.get('radiology_type') and data.get('radiology_type') != 'لا يوجد':
        radiology_text = data['radiology_type'].strip()
        # تقسيم النص إلى أسطر إذا كان يحتوي على فواصل أو أسطر متعددة
        if '\n' in radiology_text or ',' in radiology_text or '،' in radiology_text:
            # تقسيم النص
            if '\n' in radiology_text:
                lines = [line.strip() for line in radiology_text.split('\n') if line.strip()]
            elif ',' in radiology_text:
                lines = [line.strip() for line in radiology_text.split(',') if line.strip()]
            else:
                lines = [line.strip() for line in radiology_text.split('،') if line.strip()]
            
            # ترقيم وتنظيم الأسطر
            message += "🔬 **نوع الأشعة والفحوصات:**\n"
            for i, line in enumerate(lines, 1):
                message += f"{i}. {line}\n"
            message += "\n"
        else:
            # إذا كان نص واحد، نعرضه في سطر منفصل
            message += f"🔬 **نوع الأشعة والفحوصات:**\n{radiology_text}\n\n"
        
        if data.get('radiology_delivery_date') and data.get('radiology_delivery_date') != 'لا يوجد':
            message += f"📅 تاريخ التسليم: {data['radiology_delivery_date']}\n\n"
        
        # ✅ لمسار الأشعة: نعرض المترجم مباشرة بدون موعد العودة وسبب العودة
        if data.get('translator_name'):
            message += f"👨‍⚕️ المترجم: {data['translator_name']}"
        return message
    
    # ✅ لمسار "استشارة أخيرة": نعرض المترجم مباشرة بدون موعد العودة وسبب العودة
    if data.get('medical_action') == 'استشارة أخيرة':
        if data.get('translator_name'):
            message += f"👨‍⚕️ المترجم: {data['translator_name']}"
        return message
    
    # موعد العودة - تنسيق محسّن (فقط إذا كان موجوداً وليس None)
    if data.get('followup_date') and data.get('followup_date') != 'لا يوجد':
        from datetime import datetime
        try:
            # دالة مساعدة لتحويل الوقت لصيغة 12 ساعة
            def format_time_12h(time_str):
                if not time_str:
                    return None
                try:
                    hour, minute = time_str.split(':')
                    hour_int = int(hour)
                    if hour_int == 0:
                        return f"12:{minute} صباحاً"
                    elif hour_int < 12:
                        return f"{hour_int}:{minute} صباحاً"
                    elif hour_int == 12:
                        return f"12:{minute} ظهراً"
                    else:
                        return f"{hour_int-12}:{minute} مساءً"
                except:
                    return time_str
            
            if isinstance(data['followup_date'], str):
                # النص قد يحتوي على التاريخ فقط أو التاريخ + الوقت
                date_text = data['followup_date']
                
                # إذا كان هناك followup_time منفصل، نضيفه بصيغة 12 ساعة
                if data.get('followup_time'):
                    time_display = format_time_12h(data['followup_time'])
                    if time_display:
                        # إزالة "الساعة XX:XX" إذا كانت موجودة في النص
                        if ' الساعة ' in date_text:
                            date_text = date_text.split(' الساعة ')[0]
                        message += f"📅🕐 موعد العودة: {date_text} - {time_display}\n\n"
                    else:
                        message += f"📅 موعد العودة: {date_text}\n\n"
                elif ' - ' in date_text:
                    # التاريخ بصيغة: "21 نوفمبر 2025 (الجمعة) - 7:00 مساءً"
                    message += f"📅🕐 موعد العودة: {date_text}\n\n"
                else:
                    message += f"📅 موعد العودة: {date_text}\n\n"
            else:
                # كائن datetime
                date_obj = data['followup_date']
                days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
                MONTH_NAMES_AR = {1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"}
                day_name = days_ar.get(date_obj.weekday(), '')
                date_str = f"{date_obj.strftime('%d')} {MONTH_NAMES_AR.get(date_obj.month, date_obj.month)} {date_obj.year} ({day_name})"
                
                if data.get('followup_time'):
                    time_display = format_time_12h(data['followup_time'])
                    if time_display:
                        message += f"📅🕐 موعد العودة: {date_str} - {time_display}\n\n"
                    else:
                        message += f"📅 موعد العودة: {date_str}\n\n"
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
                logger.info(f"✅ تم إرسال الجدول إلى {user.full_name}")
            except Exception as e:
                logger.error(f"❌ فشل إرسال الجدول إلى {user.full_name}: {e}")
    
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
        except Exception as e:
            logger.error(f"❌ فشل إرسال الجدول للأدمن {admin_id}: {e}")


async def send_user_notification(bot: Bot, report_data: dict):
    """
    إرسال تنبيه للمستخدم عند إنشاء تقرير جديد

    Args:
        bot: كائن البوت
        report_data: بيانات التقرير
    """
    try:
        translator_id = report_data.get('translator_id')
        patient_name = report_data.get('patient_name', 'غير محدد')

        if translator_id:
            # إرسال تنبيه سريع للمستخدم
            notification_message = f"""
🔔 **تقرير جديد تم إنشاؤه**

👤 **المريض:** {patient_name}
📅 **التاريخ:** {report_data.get('report_date', 'غير محدد')}

✅ تم إرسال التقرير للمجموعة المخصصة
🔗 يمكنك مراجعة جميع التقارير في المجموعة

💡 **نصيحة:** لتجنب الضغط، تتم مراجعة التقارير في المجموعة بدلاً من الإرسال الفردي
"""

            await bot.send_message(
                chat_id=translator_id,
                text=notification_message,
                parse_mode=ParseMode.MARKDOWN
            )

            logger.info(f"✅ تم إرسال تنبيه للمستخدم: {translator_id}")

    except Exception as e:
        logger.error(f"❌ فشل إرسال التنبيه للمستخدم: {e}")


async def setup_reports_group(bot: Bot, group_invite_link: str = None):
    """
    إعداد مجموعة التقارير وإرسال الدعوة للمستخدمين

    Args:
        bot: كائن البوت
        group_invite_link: رابط دعوة المجموعة (اختياري)
    """
    if not REPORTS_GROUP_ID:
        logger.warning("⚠️ REPORTS_GROUP_ID غير محدد في متغيرات البيئة")
        return

    try:
        # إرسال رسالة تعريفية للمجموعة
        welcome_message = """
🏥 **مجموعة تقارير المستشفى**

📋 **كيفية عمل النظام:**
• جميع التقارير الجديدة تُرسل هنا تلقائياً
• يمكنك مراجعة التقارير في أي وقت
• النظام يوفر الضغط على البوت الفردي
• إشعارات سريعة تُرسل لك عند إنشاء تقرير جديد

📱 **للانضمام:** إذا لم تكن عضواً، ستتلقى دعوة تلقائية

⚠️ **ملاحظة:** هذا النظام يحسن الأداء عند وجود عدد كبير من المستخدمين
"""

        await bot.send_message(
            chat_id=REPORTS_GROUP_ID,
            text=welcome_message,
            parse_mode=ParseMode.MARKDOWN
        )

        logger.info("✅ تم إعداد مجموعة التقارير")

        # إرسال دعوات للمستخدمين إذا كان هناك رابط دعوة
        if group_invite_link:
            await send_group_invitations(bot, group_invite_link)

    except Exception as e:
        logger.error(f"❌ فشل إعداد مجموعة التقارير: {e}")


async def send_group_invitations(bot: Bot, invite_link: str):
    """
    إرسال دعوات الانضمام للمجموعة لجميع المستخدمين

    Args:
        bot: كائن البوت
        invite_link: رابط دعوة المجموعة
    """
    try:
        with SessionLocal() as s:
            approved_users = s.query(Translator).filter_by(
                is_approved=True,
                is_suspended=False
            ).all()

            invitation_message = f"""
🎉 **دعوة خاصة: مجموعة تقارير المستشفى**

📋 **لماذا هذه المجموعة مهمة:**
• جميع التقارير الجديدة تُرسل هنا
• أداء أفضل تحت الضغط العالي
• تنظيم أفضل للتقارير
• إشعارات فورية للتقارير الجديدة

🔗 **رابط الانضمام:** {invite_link}

⚡ **نصيحة:** انضم للمجموعة لمتابعة جميع التقارير بسهولة
"""

            sent_count = 0
            for user in approved_users:
                try:
                    await bot.send_message(
                        chat_id=user.tg_user_id,
                        text=invitation_message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    sent_count += 1
                except Exception as e:
                    logger.error(f"فشل إرسال الدعوة لـ {user.full_name}: {e}")

            logger.info(f"✅ تم إرسال {sent_count} دعوة انضمام للمجموعة")

    except Exception as e:
        logger.error(f"❌ فشل إرسال دعوات المجموعة: {e}")


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


