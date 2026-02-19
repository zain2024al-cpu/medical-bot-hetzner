# =============================
# services/broadcast_service.py
# 📢 نظام البث المحسّن للتقارير - إرسال للمجموعة
# =============================

from db.session import SessionLocal
from db.models import Translator
from config.settings import ADMIN_IDS
from bot.broadcast_control import is_broadcast_enabled
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
import logging
import os

logger = logging.getLogger(__name__)


def escape_markdown(text):
    """تنظيف النص من الأحرف الخاصة بـ Markdown"""
    if not text:
        return text
    text = str(text)
    # الأحرف الخاصة التي تحتاج escape في Markdown
    special_chars = ['*', '_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, '\\' + char)
    return text


def _is_similar_text(text1: str, text2: str, threshold: float = 0.7) -> bool:
    """
    ✅ التحقق من التشابه بين نصين
    - يعيد True إذا كان النصان متشابهين بنسبة أعلى من threshold
    - يستخدم لمنع تكرار التشخيص وقرار الطبيب
    - ✅ محدث: منطق أكثر ذكاءً لتجنب إخفاء قرار الطبيب المفيد
    """
    if not text1 or not text2:
        return False

    t1 = str(text1).strip().lower()
    t2 = str(text2).strip().lower()

    # ✅ تطابق تام فقط (ليس الاحتواء)
    if t1 == t2:
        return True

    # ✅ إذا كان أحدهما قصير جداً (أقل من 10 أحرف)، فقط التطابق التام يُعتبر متشابهاً
    if len(t1) < 10 or len(t2) < 10:
        return t1 == t2

    # ✅ حساب نسبة التشابه بالكلمات المشتركة فقط (بدون الاحتواء البسيط)
    words1 = set(t1.split())
    words2 = set(t2.split())

    if not words1 or not words2:
        return False

    common_words = words1.intersection(words2)
    # ✅ زيادة الحد الأدنى للتشابه إلى 0.85 لتقليل الإيجابيات الكاذبة
    similarity = len(common_words) / max(len(words1), len(words2))

    return similarity >= 0.85  # أكثر صرامة من 0.7


# إعدادات المجموعة
REPORTS_GROUP_ID = os.getenv("REPORTS_GROUP_ID", "")  # معرف المجموعة الخاصة بالتقارير


def _split_telegram_message(text: str, max_len: int = 3500) -> list[str]:
    """
    تقسيم النص الطويل إلى أجزاء آمنة للإرسال في تيليجرام.
    - Telegram limit ~4096 chars; we keep safety margin.
    - Prefer splitting on newline when possible.
    """
    if text is None:
        return [""]

    remaining = str(text).strip()
    if not remaining:
        return [""]

    chunks = []
    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break

        split_at = remaining.rfind("\n", 0, max_len)
        if split_at == -1 or split_at < int(max_len * 0.5):
            split_at = max_len

        chunk = remaining[:split_at].rstrip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].lstrip("\n")

    return chunks or [""]


async def _send_message_in_chunks(bot: Bot, chat_id, text: str, parse_mode=None, reply_markup=None):
    """
    إرسال رسالة (طويلة أو قصيرة) على أجزاء.
    - تُضاف reply_markup للجزء الأخير فقط.
    - تُعاد آخر رسالة مُرسلة (مهم لحفظ message_id).
    """
    chunks = _split_telegram_message(text)
    last_message = None

    for idx, chunk in enumerate(chunks):
        is_last = idx == (len(chunks) - 1)
        last_message = await bot.send_message(
            chat_id=chat_id,
            text=chunk,
            parse_mode=parse_mode,
            reply_markup=reply_markup if is_last else None,
        )

    return last_message



async def broadcast_new_report(bot: Bot, report_data: dict):
    """
    بث تقرير جديد - محسّن للأداء العالي

    منطق الإرسال:
    - إرسال للمجموعة: يعتمد على BROADCAST_ENABLED
    - إرسال للأدمن: دائماً مفعل (لا يعتمد على BROADCAST_ENABLED)
    - إرسال للمستخدم: يعتمد على BROADCAST_ENABLED

    Args:
        bot: كائن البوت
        report_data: بيانات التقرير كـ dictionary
    """
    logger.info(f"📤 broadcast_new_report: بدء البث - report_id={report_data.get('report_id')}, medical_action={report_data.get('medical_action')}")
    
    # تنسيق الرسالة
    try:
        message = format_report_message(report_data)
        logger.info(f"✅ broadcast_new_report: تم تنسيق الرسالة بنجاح (طول: {len(message)} حرف)")
    except Exception as format_error:
        logger.error(f"❌ broadcast_new_report: خطأ في تنسيق الرسالة: {format_error}", exc_info=True)
        # ✅ حتى لو فشل التنسيق، نحاول إرسال رسالة بسيطة للأدمن
        message = f"❌ خطأ في تنسيق التقرير\n\nreport_id: {report_data.get('report_id', 'غير محدد')}\npatient: {report_data.get('patient_name', 'غير محدد')}\nخطأ: {str(format_error)[:200]}"
        logger.warning(f"⚠️ broadcast_new_report: استخدام رسالة بديلة بسبب خطأ التنسيق")

    # ✅ حالة البث للمجموعة (لا تؤثر على الأدمن)
    broadcast_enabled = is_broadcast_enabled()
    logger.info(f"📤 broadcast_new_report: BROADCAST_ENABLED={broadcast_enabled}, REPORTS_GROUP_ID='{REPORTS_GROUP_ID}' (len={len(str(REPORTS_GROUP_ID)) if REPORTS_GROUP_ID else 0})")

    # ✅ إرسال للمجموعة (فقط إذا كان البث مفعل)
    if not broadcast_enabled:
        logger.warning(f"⚠️ broadcast_new_report: البث معطل! لن يتم إرسال التقرير للمجموعة")
    if not REPORTS_GROUP_ID:
        logger.warning(f"⚠️ broadcast_new_report: REPORTS_GROUP_ID فارغ! لن يتم إرسال التقرير للمجموعة")

    if broadcast_enabled and REPORTS_GROUP_ID:
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
            logger.info(f"📤 broadcast_new_report: report_id={report_data.get('report_id')}, user_id={report_data.get('user_id')}, translator_id={report_data.get('translator_id')}")
            
            # محاولة إرسال الرسالة للمجموعة
            group_message_id = None
            send_success = False
            
            # المحاولة الأولى: مع Markdown
            try:
                sent_message = await _send_message_in_chunks(
                    bot=bot,
                    chat_id=REPORTS_GROUP_ID,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
                group_message_id = sent_message.message_id
                send_success = True
                logger.info(f"✅ broadcast_new_report: تم إرسال التقرير للمجموعة: {REPORTS_GROUP_ID}, message_id: {group_message_id}")
            except Exception as send_error:
                error_type = type(send_error).__name__
                error_msg = str(send_error)
                logger.warning(f"⚠️ broadcast_new_report: فشل الإرسال مع Markdown للمجموعة {REPORTS_GROUP_ID}")
                logger.warning(f"⚠️ broadcast_new_report: نوع الخطأ: {error_type}")
                logger.warning(f"⚠️ broadcast_new_report: رسالة الخطأ: {error_msg}")
                
                # التحقق من نوع الخطأ
                if "Chat not found" in error_msg or "chat_id is empty" in error_msg:
                    logger.error(f"❌ broadcast_new_report: المجموعة غير موجودة أو معرف المجموعة غير صحيح: {REPORTS_GROUP_ID}")
                    raise  # خطأ لا يمكن إصلاحه
                elif "Not enough rights" in error_msg or "can't send messages" in error_msg.lower():
                    logger.error(f"❌ broadcast_new_report: البوت ليس لديه صلاحيات لإرسال الرسائل في المجموعة {REPORTS_GROUP_ID}")
                    raise  # خطأ لا يمكن إصلاحه
                elif "blocked" in error_msg.lower():
                    logger.error(f"❌ broadcast_new_report: البوت محظور من المجموعة {REPORTS_GROUP_ID}")
                    raise  # خطأ لا يمكن إصلاحه
                elif "Bad Request" in error_msg or "parse" in error_msg.lower() or "markdown" in error_msg.lower():
                    # خطأ في تنسيق Markdown - نحاول بدون Markdown
                    logger.warning(f"⚠️ broadcast_new_report: خطأ في تنسيق Markdown، محاولة الإرسال بدون Markdown...")
                    try:
                        sent_message = await _send_message_in_chunks(
                            bot=bot,
                            chat_id=REPORTS_GROUP_ID,
                            text=message,
                            parse_mode=None,  # بدون Markdown
                            reply_markup=reply_markup
                        )
                        group_message_id = sent_message.message_id
                        send_success = True
                        logger.info(f"✅ broadcast_new_report: تم إرسال التقرير للمجموعة بدون Markdown: {REPORTS_GROUP_ID}, message_id: {group_message_id}")
                    except Exception as fallback_error:
                        logger.error(f"❌ broadcast_new_report: فشل الإرسال بدون Markdown أيضاً: {fallback_error}")
                        raise  # فشل كلا المحاولتين
                else:
                    # خطأ آخر - نحاول بدون Markdown كحل أخير
                    logger.warning(f"⚠️ broadcast_new_report: خطأ غير معروف، محاولة الإرسال بدون Markdown...")
                    try:
                        sent_message = await _send_message_in_chunks(
                            bot=bot,
                            chat_id=REPORTS_GROUP_ID,
                            text=message,
                            parse_mode=None,  # بدون Markdown
                            reply_markup=reply_markup
                        )
                        group_message_id = sent_message.message_id
                        send_success = True
                        logger.info(f"✅ broadcast_new_report: تم إرسال التقرير للمجموعة بدون Markdown: {REPORTS_GROUP_ID}, message_id: {group_message_id}")
                    except Exception as fallback_error:
                        logger.error(f"❌ broadcast_new_report: فشل الإرسال بدون Markdown أيضاً: {fallback_error}")
                        raise  # فشل كلا المحاولتين
            
            # إذا فشل الإرسال، لا نكمل
            if not send_success:
                logger.error(f"❌ broadcast_new_report: فشل إرسال التقرير للمجموعة بعد جميع المحاولات")
                raise Exception("فشل إرسال التقرير للمجموعة")
            
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

            # ✅ إرسال التقرير أيضاً للمستخدم الذي أنشأه (فقط إذا كان البث مفعل)
            user_id = report_data.get('user_id') or report_data.get('translator_id')
            if user_id:
                try:
                    await _send_message_in_chunks(
                        bot=bot,
                        chat_id=user_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    logger.info(f"✅ تم إرسال التقرير للمستخدم في البوت: {user_id}")
                except Exception as e:
                    logger.warning(f"⚠️ فشل إرسال التقرير للمستخدم {user_id}: {e}")

            # ✅ إرسال تنبيه للمستخدم عن التقرير الجديد (فقط إذا كان البث مفعل)
            await send_user_notification(bot, report_data)
            
            # ✅ إرسال للأدمن دائماً (حتى عندما يكون البث للمجموعة مفعل)
            if ADMIN_IDS:
                for admin_id in ADMIN_IDS:
                    try:
                        try:
                            await _send_message_in_chunks(
                                bot=bot,
                                chat_id=admin_id,
                                text=message,
                                parse_mode=ParseMode.MARKDOWN
                            )
                            logger.info(f"✅ تم إرسال التقرير للأدمن: {admin_id}")
                        except Exception as markdown_error:
                            try:
                                await _send_message_in_chunks(
                                    bot=bot,
                                    chat_id=admin_id,
                                    text=message,
                                    parse_mode=None
                                )
                                logger.info(f"✅ تم إرسال التقرير للأدمن {admin_id} بدون Markdown")
                            except Exception as fallback_error:
                                logger.error(f"❌ فشل إرسال التقرير للأدمن {admin_id}: {fallback_error}")
                    except Exception as e:
                        logger.error(f"❌ فشل إرسال التقرير للأدمن {admin_id}: {e}")
            
            logger.info(f"✅ broadcast_new_report: اكتمل البث للمجموعة بنجاح")
            return  # ✅ إنهاء الدالة بعد الإرسال الناجح للمجموعة
            
        except Exception as e:
            logger.error(f"❌ broadcast_new_report: فشل إرسال التقرير للمجموعة: {e}", exc_info=True)
            logger.error(f"❌ broadcast_new_report: نوع الخطأ: {type(e).__name__}")
            logger.error(f"❌ broadcast_new_report: تفاصيل الخطأ: {str(e)}")
            # في حالة فشل الإرسال للمجموعة، نكمل لإرسال للأدمن فقط
    
    # ✅ إرسال للأدمن دائماً (بغض النظر عن حالة BROADCAST_ENABLED)
    # هذا يضمن أن الأدمن يتلقى جميع التقارير حتى لو كان البث للمجموعة معطل
    logger.info(f"📤 broadcast_new_report: إرسال التقرير للأدمن (دائماً مفعل) - BROADCAST_ENABLED={broadcast_enabled}")
    
    if ADMIN_IDS:
        for admin_id in ADMIN_IDS:
            try:
                # المحاولة الأولى: مع Markdown
                try:
                    await _send_message_in_chunks(
                        bot=bot,
                        chat_id=admin_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    logger.info(f"✅ تم إرسال التقرير للأدمن: {admin_id}")
                except Exception as markdown_error:
                    error_msg = str(markdown_error)
                    logger.warning(f"⚠️ فشل الإرسال للأدمن {admin_id} مع Markdown: {error_msg}")
                    # المحاولة الثانية: بدون Markdown
                    try:
                        await _send_message_in_chunks(
                            bot=bot,
                            chat_id=admin_id,
                            text=message,
                            parse_mode=None
                        )
                        logger.info(f"✅ تم إرسال التقرير للأدمن {admin_id} بدون Markdown")
                    except Exception as fallback_error:
                        logger.error(f"❌ فشل إرسال التقرير للأدمن {admin_id} حتى بدون Markdown: {fallback_error}")
            except Exception as e:
                logger.error(f"❌ فشل إرسال التقرير للأدمن {admin_id}: {e}")
    else:
        logger.warning(f"⚠️ broadcast_new_report: ADMIN_IDS فارغ - لن يتم إرسال التقرير للأدمن")


async def broadcast_initial_case(bot: Bot, case_data: dict):
    """
    بث حالة أولية جديدة لجميع المستخدمين المعتمدين والأدمن
    
    Args:
        bot: كائن البوت
        case_data: بيانات الحالة كـ dictionary
    """
    # تنسيق الرسالة
    message = format_initial_case_message(case_data)
    
    # إرسال لجميع المستخدمين المعتمدين
    with SessionLocal() as s:
        approved_users = s.query(Translator).filter_by(
            is_approved=True,
            is_suspended=False
        ).all()
        
        for user in approved_users:
            if user.tg_user_id:
                try:
                    await bot.send_message(
                        chat_id=user.tg_user_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    print(f"تم ارسال الحالة الاولية الى {user.full_name}")
                except Exception as e:
                    print(f"فشل ارسال الحالة الاولية الى {user.full_name}: {e}")
    
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
    ✅ دالة واحدة فقط لبناء نص التقرير (Report Builder)
    - استخدام list + join بدل +=
    - فصل الحقول بشكل صريح
    - عدم استخدام reply_markup قديم
    """
    # ✅ إعادة تهيئة النص دائمًا - استخدام list
    lines = []
    
    # ✅ رأس التقرير
    if data.get('is_edit'):
        lines.append("✏️ **تقرير معدل**")
    else:
        lines.append("🆕 **تقرير جديد**")
    lines.append("")  # سطر فارغ
    
    # ✅ التاريخ
    if data.get('report_date'):
        date_str = _format_report_date(data.get('report_date'))
        if date_str:
            lines.append(f"📅🕐 التاريخ: {date_str}")
            lines.append("")  # سطر فارغ
    
    # ✅ المعلومات الأساسية - مع escape_markdown لمنع أخطاء Markdown
    if data.get('patient_name'):
        lines.append(f"👤 اسم المريض: {escape_markdown(str(data['patient_name']))}")
        lines.append("")

    if data.get('hospital_name'):
        lines.append(f"🏥 المستشفى: {escape_markdown(str(data['hospital_name']))}")
        lines.append("")

    if data.get('department_name'):
        lines.append(f"🏷️ القسم: {escape_markdown(str(data['department_name']))}")
        lines.append("")

    if data.get('doctor_name') and data.get('doctor_name') != 'لم يتم التحديد':
        lines.append(f"👨‍⚕️ اسم الطبيب: {escape_markdown(str(data['doctor_name']))}")
        lines.append("")

    # ✅ نوع الإجراء
    if data.get('medical_action'):
        lines.append(f"📌 نوع الإجراء: {escape_markdown(str(data['medical_action']))}")
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
    
    # ✅ معالجة خاصة لكل نوع إجراء
    medical_action = data.get('medical_action', '')
    
    if medical_action == 'تأجيل موعد':
        lines.extend(_build_appointment_reschedule_fields(data))
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        if data.get('translator_name'):
            lines.append(f"👨‍⚕️ المترجم: {data['translator_name']}")
        return "\n".join(lines)
    
    elif medical_action == 'استشارة مع قرار عملية':
        lines.extend(_build_surgery_consult_fields(data))
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        if data.get('translator_name'):
            lines.append(f"👨‍⚕️ المترجم: {data['translator_name']}")
        return "\n".join(lines)
    
    elif medical_action == 'أشعة وفحوصات':
        lines.extend(_build_radiology_fields(data))
        if data.get('translator_name'):
            lines.append("")
            lines.append(f"👨‍⚕️ المترجم: {data['translator_name']}")
        return "\n".join(lines)
    
    elif medical_action == 'استشارة أخيرة':
        lines.extend(_build_final_consult_fields(data))
        if data.get('translator_name'):
            lines.append("")
            lines.append(f"👨‍⚕️ المترجم: {escape_markdown(str(data['translator_name']))}")
        return "\n".join(lines)
    
    elif medical_action == 'جلسة إشعاعي':
        lines.extend(_build_radiation_therapy_fields(data))
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        if data.get('translator_name'):
            lines.append(f"👨‍⚕️ المترجم: {data['translator_name']}")
        return "\n".join(lines)
    
    else:
        # ✅ معالجة الحقول العامة (new_consult, followup, emergency, etc.)
        lines.extend(_build_general_fields(data))
    
    # ✅ موعد العودة وسبب العودة (للمسارات العامة)
    if medical_action not in ['تأجيل موعد', 'استشارة مع قرار عملية', 'أشعة وفحوصات', 'استشارة أخيرة', 'جلسة إشعاعي']:
        lines.extend(_build_followup_fields(data))
    
    # ✅ خط فاصل نهائي
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    
    # ✅ المترجم
    if data.get('translator_name'):
        lines.append(f"👨‍⚕️ المترجم: {data['translator_name']}")
    
    return "\n".join(lines)


def _format_report_date(report_date):
    """تنسيق تاريخ التقرير"""
    if not report_date:
        return None
    
    # إذا كان مُنسقاً بالفعل بصيغة 12 ساعة، نستخدمه مباشرة
    if isinstance(report_date, str) and ('صباحاً' in report_date or 'مساءً' in report_date or 'ظهراً' in report_date):
        return report_date
    
    # محاولة تحويل التاريخ
    from datetime import datetime
    try:
        if isinstance(report_date, str):
            date_obj = datetime.strptime(report_date, '%Y-%m-%d %H:%M')
        else:
            date_obj = report_date
        
        days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
        MONTH_NAMES_AR = {1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"}
        
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
        return f"{date_obj.strftime('%d')} {MONTH_NAMES_AR.get(date_obj.month, date_obj.month)} {date_obj.year} ({day_name}) - {time_str}"
    except:
        return str(report_date)


def _extract_decision(data: dict) -> str:
    """
    ✅ استخراج قرار الطبيب من عدة مصادر
    - فصل واضح بين diagnosis و decision
    - ✅ منع التكرار: إذا كان decision موجوداً، لا نستخرجه من doctor_decision
    """
    # ✅ المحاولة الأولى: من decision مباشرة (الأولوية الأولى - منع التكرار)
    decision = data.get('decision', '')
    if decision and str(decision).strip():
        # ✅ تنظيف القرار من أي نص "قرار الطبيب:" إذا كان موجوداً (منع التكرار)
        decision_str = str(decision).strip()
        if decision_str.startswith('قرار الطبيب:'):
            decision_str = decision_str.replace('قرار الطبيب:', '', 1).strip()
        # ✅ إذا كان decision موجوداً، نعيده مباشرة ولا نحتاج doctor_decision
        return decision_str

    # ✅ المحاولة الثانية: استخراج من doctor_decision (فقط إذا لم يكن decision موجوداً)
    doctor_decision = data.get('doctor_decision', '')
    if doctor_decision:
        doctor_decision_str = str(doctor_decision).strip()

        # ✅ التحقق من أن doctor_decision ليس نفس diagnosis (منع التكرار)
        diagnosis = data.get('diagnosis', '')
        if diagnosis and _is_similar_text(diagnosis, doctor_decision_str):
            return None  # ✅ doctor_decision متشابه مع diagnosis، لا نعيده

        # ✅ إذا كان doctor_decision يحتوي على "قرار الطبيب:"، نستخرج القرار فقط
        if 'قرار الطبيب:' in doctor_decision_str:
            parts = doctor_decision_str.split('قرار الطبيب:', 1)
            if len(parts) > 1:
                extracted = parts[1].strip()
                # ✅ تنظيف النص من أي حقول إضافية
                if '\n\n' in extracted:
                    extracted = extracted.split('\n\n')[0].strip()
                # ✅ إزالة أي نص بعد سطر جديد واحد إذا كان يحتوي على عناوين أخرى
                for marker in ['الفحوصات:', 'وضع الحالة:', 'موعد العودة:', 'سبب العودة:']:
                    if marker in extracted:
                        extracted = extracted.split(marker)[0].strip()
                if extracted and len(extracted) > 0:
                    return extracted

        # ✅ إذا كان يحتوي على "التشخيص:" فقط، لا نعيد شيء (التشخيص يُعرض منفصلاً)
        if 'التشخيص:' in doctor_decision_str and 'قرار الطبيب:' not in doctor_decision_str:
            return None

        # ✅ إذا لم يكن يحتوي على "قرار الطبيب:" أو "التشخيص:"، نستخدمه كاملاً
        if 'التشخيص:' not in doctor_decision_str and 'قرار الطبيب:' not in doctor_decision_str:
            return doctor_decision_str

    return None


def _build_appointment_reschedule_fields(data: dict) -> list:
    """بناء حقول تأجيل موعد"""
    lines = []
    
    # سبب تأجيل الموعد
    app_reschedule_reason = data.get('app_reschedule_reason', '')
    if not app_reschedule_reason or not str(app_reschedule_reason).strip():
        # محاولة استخراجه من doctor_decision
        doctor_decision = data.get('doctor_decision', '')
        if doctor_decision and 'سبب تأجيل الموعد:' in str(doctor_decision):
            parts = str(doctor_decision).split('سبب تأجيل الموعد:', 1)
            if len(parts) > 1:
                extracted_reason = parts[1].strip()
                if '\n' in extracted_reason:
                    extracted_reason = extracted_reason.split('\n')[0].strip()
                app_reschedule_reason = extracted_reason
    
    if app_reschedule_reason and str(app_reschedule_reason).strip():
        lines.append(f"📅 **سبب تأجيل الموعد:** {str(app_reschedule_reason).strip()}")
        lines.append("")
    
    # موعد العودة
    return_date = data.get('app_reschedule_return_date') or data.get('followup_date')
    if return_date and return_date != 'لا يوجد':
        date_str = _format_followup_date(return_date, data.get('followup_time'))
        if date_str:
            lines.append(f"📅🕐 **موعد العودة:** {date_str}")
            lines.append("")
    
    # سبب العودة
    return_reason = data.get('app_reschedule_return_reason', '')
    if return_reason and str(return_reason).strip() and str(return_reason) != 'لا يوجد':
        lines.append(f"✍️ **سبب العودة:** {str(return_reason).strip()}")
        lines.append("")
    
    return lines


def _build_surgery_consult_fields(data: dict) -> list:
    """بناء حقول استشارة مع قرار عملية"""
    lines = []
    
    # ✅ شكوى المريض
    if data.get('complaint_text') and str(data.get('complaint_text')).strip():
        lines.append(f"💬 شكوى المريض: {escape_markdown(str(data['complaint_text']))}")
        lines.append("")
    
    # ✅ التشخيص - حقل منفصل
    diagnosis = data.get('diagnosis', '')
    if diagnosis and str(diagnosis).strip():
        lines.append(f"🔬 التشخيص: {escape_markdown(str(diagnosis))}")
        lines.append("")
    
    # ✅ قرار الطبيب - حقل منفصل تماماً
    # ✅ منع التكرار: إذا كان decision موجوداً مباشرة، نستخدمه ولا نستخرجه من doctor_decision
    decision = None
    if data.get('decision') and str(data.get('decision')).strip():
        # ✅ استخدام decision مباشرة (الأولوية الأولى)
        decision = str(data.get('decision')).strip()
        # ✅ تنظيف من أي نص "قرار الطبيب:" إذا كان موجوداً (منع التكرار)
        if decision.startswith('قرار الطبيب:'):
            decision = decision.replace('قرار الطبيب:', '', 1).strip()
    else:
        # ✅ فقط إذا لم يكن decision موجوداً، نحاول استخراجه من doctor_decision
        decision = _extract_decision(data)

    # ✅ تم تعطيل منطق منع التكرار - عرض قرار الطبيب دائماً
    # ✅ السبب: المستخدم يريد دائماً رؤية قرار الطبيب في التقرير المنشور

    if decision and str(decision).strip():
        lines.append(f"📝 قرار الطبيب: {escape_markdown(str(decision))}")
        lines.append("")

    # ✅ اسم العملية بالإنجليزي - حقل منفصل
    if data.get('operation_name_en') and str(data.get('operation_name_en')).strip():
        lines.append(f"🔤 اسم العملية بالإنجليزي: {escape_markdown(str(data['operation_name_en']))}")
        lines.append("")
    
    # ✅ نسبة نجاح العملية - حقل منفصل
    if data.get('success_rate') and str(data.get('success_rate')).strip():
        lines.append(f"📊 نسبة نجاح العملية: {escape_markdown(str(data['success_rate']))}")
        lines.append("")
    
    # ✅ نسبة الاستفادة من العملية - حقل منفصل
    if data.get('benefit_rate') and str(data.get('benefit_rate')).strip():
        lines.append(f"💡 نسبة الاستفادة من العملية: {escape_markdown(str(data['benefit_rate']))}")
        lines.append("")
    
    # ✅ الفحوصات والأشعة - حقل منفصل
    if data.get('tests') and str(data.get('tests')).strip() and str(data.get('tests')) != 'لا يوجد':
        tests_text = str(data['tests']).strip()
        lines.append("🧪 الفحوصات والأشعة:")
        # تقسيم النص إذا كان يحتوي على فواصل
        if '\n' in tests_text or ',' in tests_text or '،' in tests_text:
            if '\n' in tests_text:
                test_lines = [line.strip() for line in tests_text.split('\n') if line.strip()]
            elif ',' in tests_text:
                test_lines = [line.strip() for line in tests_text.split(',') if line.strip()]
            else:
                test_lines = [line.strip() for line in tests_text.split('،') if line.strip()]
            
            for i, line in enumerate(test_lines, 1):
                lines.append(f"{i}. {escape_markdown(line)}")
        else:
            lines.append(escape_markdown(tests_text))
        lines.append("")
    
    # ✅ موعد العودة
    if data.get('followup_date') and data.get('followup_date') != 'لا يوجد':
        date_str = _format_followup_date(data.get('followup_date'), data.get('followup_time'))
        if date_str:
            lines.append(f"📅🕐 موعد العودة: {date_str}")
            lines.append("")
    
    # ✅ سبب العودة
    if data.get('followup_reason') and str(data.get('followup_reason')).strip() != 'لا يوجد':
        lines.append(f"✍️ **سبب العودة:**")
        lines.append(escape_markdown(str(data['followup_reason'])))
        lines.append("")
    
    return lines


def _build_radiology_fields(data: dict) -> list:
    """بناء حقول الأشعة والفحوصات"""
    lines = []
    
    # نوع الأشعة والفحوصات
    if data.get('radiology_type') and str(data.get('radiology_type')).strip() != 'لا يوجد':
        radiology_text = str(data['radiology_type']).strip()
        lines.append("🔬 **نوع الأشعة والفحوصات:**")
        
        # تقسيم النص
        if '\n' in radiology_text or ',' in radiology_text or '،' in radiology_text:
            if '\n' in radiology_text:
                rad_lines = [line.strip() for line in radiology_text.split('\n') if line.strip()]
            elif ',' in radiology_text:
                rad_lines = [line.strip() for line in radiology_text.split(',') if line.strip()]
            else:
                rad_lines = [line.strip() for line in radiology_text.split('،') if line.strip()]
            
            for i, line in enumerate(rad_lines, 1):
                lines.append(f"{i}. {escape_markdown(line)}")
        else:
            lines.append(escape_markdown(radiology_text))
        lines.append("")
    
    # تاريخ التسليم
    if data.get('radiology_delivery_date') and str(data.get('radiology_delivery_date')).strip() not in ['لا يوجد', 'None', '', 'null']:
        delivery_date = data['radiology_delivery_date']
        # تنسيق التاريخ إذا كان datetime/date object
        if hasattr(delivery_date, 'strftime'):
            # تنسيق بسيط للتاريخ (بدون وقت)
            try:
                from datetime import date, datetime
                if isinstance(delivery_date, datetime):
                    date_obj = delivery_date.date()
                elif isinstance(delivery_date, date):
                    date_obj = delivery_date
                else:
                    date_obj = delivery_date
                
                # تنسيق التاريخ بالعربية
                days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 
                          4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
                MONTH_NAMES_AR = {1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو",
                                 7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"}
                
                day_name = days_ar.get(date_obj.weekday(), '')
                date_str = f"{date_obj.strftime('%d')} {MONTH_NAMES_AR.get(date_obj.month, date_obj.month)} {date_obj.year} ({day_name})"
                lines.append(f"📅 تاريخ التسليم: {escape_markdown(date_str)}")
                lines.append("")
            except Exception as e:
                # fallback: تنسيق بسيط
                try:
                    date_str = delivery_date.strftime('%Y-%m-%d')
                    lines.append(f"📅 تاريخ التسليم: {escape_markdown(date_str)}")
                    lines.append("")
                except:
                    lines.append(f"📅 تاريخ التسليم: {escape_markdown(str(delivery_date))}")
                    lines.append("")
        else:
            # إذا كان string، استخدامه مباشرة
            date_str = str(delivery_date).strip()
            if date_str:
                lines.append(f"📅 تاريخ التسليم: {escape_markdown(date_str)}")
                lines.append("")
    
    return lines


def _build_final_consult_fields(data: dict) -> list:
    """بناء حقول استشارة أخيرة"""
    lines = []
    
    # ✅ التشخيص - حقل منفصل
    if data.get('diagnosis') and str(data.get('diagnosis')).strip():
        lines.append(f"🔬 **التشخيص:**")
        lines.append(escape_markdown(str(data['diagnosis'])))
        lines.append("")
    
    # ✅ قرار الطبيب - حقل منفصل
    # ✅ منع التكرار: إذا كان decision موجوداً مباشرة، نستخدمه ولا نستخرجه من doctor_decision
    decision = None
    if data.get('decision') and str(data.get('decision')).strip():
        # ✅ استخدام decision مباشرة (الأولوية الأولى)
        decision = str(data.get('decision')).strip()
        # ✅ تنظيف من أي نص "قرار الطبيب:" إذا كان موجوداً (منع التكرار)
        if decision.startswith('قرار الطبيب:'):
            decision = decision.replace('قرار الطبيب:', '', 1).strip()
    else:
        # ✅ فقط إذا لم يكن decision موجوداً، نحاول استخراجه من doctor_decision
        decision = _extract_decision(data)

    # ✅ تم تعطيل منطق منع التكرار - عرض قرار الطبيب دائماً
    # ✅ السبب: المستخدم يريد دائماً رؤية قرار الطبيب في التقرير المنشور

    if decision and str(decision).strip():
        lines.append(f"📝 **قرار الطبيب:**")
        lines.append(escape_markdown(str(decision)))
        lines.append("")

    # ✅ التوصيات
    recommendations = data.get('recommendations') or data.get('treatment_plan') or data.get('notes')
    if recommendations and str(recommendations).strip():
        lines.append(f"💊 **التوصيات:**")
        lines.append(escape_markdown(str(recommendations)))
        lines.append("")
    
    return lines


def _build_radiation_therapy_fields(data: dict) -> list:
    """بناء حقول جلسة إشعاعي"""
    lines = []
    
    # ✅ نوع الإشعاعي
    radiation_type = data.get('radiation_therapy_type', '')
    if radiation_type and str(radiation_type).strip():
        lines.append(f"☢️ **نوع الإشعاعي:** {escape_markdown(str(radiation_type).strip())}")
        lines.append("")
    
    # ✅ رقم الجلسة
    session_number = data.get('radiation_therapy_session_number', '')
    if session_number and str(session_number).strip():
        lines.append(f"🔢 **رقم الجلسة:** {escape_markdown(str(session_number).strip())}")
        lines.append("")
    
    # ✅ الجلسات المتبقية
    remaining = data.get('radiation_therapy_remaining', '')
    if remaining and str(remaining).strip():
        lines.append(f"📊 **الجلسات المتبقية:** {escape_markdown(str(remaining).strip())}")
        lines.append("")
    
    # ✅ ملاحظات / توصيات
    recommendations = data.get('radiation_therapy_recommendations', '')
    if recommendations and str(recommendations).strip():
        lines.append(f"📝 **ملاحظات / توصيات:** {escape_markdown(str(recommendations).strip())}")
        lines.append("")
    
    # ✅ موعد العودة
    return_date = data.get('radiation_therapy_return_date') or data.get('followup_date')
    if return_date and return_date != 'لا يوجد' and return_date != 'غير محدد':
        date_str = _format_followup_date(return_date, data.get('followup_time'))
        if date_str:
            lines.append(f"📅🕐 **موعد العودة:** {date_str}")
            lines.append("")
    
    # ✅ سبب العودة أو الملاحظات النهائية
    return_reason = data.get('radiation_therapy_return_reason') or data.get('followup_reason') or data.get('radiation_therapy_final_notes', '')
    if return_reason and str(return_reason).strip() and str(return_reason) != 'لا يوجد':
        # التحقق من اكتمال الجلسات
        completed = data.get('radiation_therapy_completed', False)
        if completed:
            lines.append(f"📝 **ملاحظات نهائية:** {escape_markdown(str(return_reason).strip())}")
        else:
            lines.append(f"✍️ **سبب العودة:** {escape_markdown(str(return_reason).strip())}")
        lines.append("")
    
    return lines


def _build_general_fields(data: dict) -> list:
    """بناء الحقول العامة (new_consult, followup, emergency, etc.)"""
    lines = []
    medical_action = (data.get('medical_action', '') or '').strip()

    # ✅ المسارات التي لا تحتوي على شكوى وتشخيص وقرار طبيب
    # تعرض فقط الحقول الخاصة بها + موعد العودة وسبب العودة
    flows_without_complaint_diagnosis = [
        'عملية', 'علاج طبيعي', 'علاج طبيعي وإعادة تأهيل', 'أجهزة تعويضية', 'ترقيد', 'خروج من المستشفى'
    ]

    # ✅ المسارات التي لا تحتوي على تشخيص
    flows_without_diagnosis = [
        'عملية', 'علاج طبيعي', 'علاج طبيعي وإعادة تأهيل', 'أجهزة تعويضية', 'ترقيد', 'خروج من المستشفى',
        'متابعة في الرقود'  # ✅ لا يحتوي على تشخيص
    ]

    # ✅ شكوى المريض / حالة المريض اليومية - حقل منفصل (لا يظهر في المسارات المحددة)
    if medical_action not in flows_without_complaint_diagnosis:
        if data.get('complaint_text') and str(data.get('complaint_text')).strip():
            # ✅ تسمية مختلفة لـ "متابعة في الرقود"
            if medical_action == 'متابعة في الرقود':
                lines.append(f"🛏️ **حالة المريض اليومية:**")
            else:
                lines.append(f"💬 **شكوى المريض:**")
            lines.append(escape_markdown(str(data['complaint_text'])))
            lines.append("")

    # ✅ التشخيص - حقل منفصل تماماً (لا يظهر في المسارات المحددة)
    # ✅ "متابعة في الرقود" لا يحتوي على تشخيص
    if medical_action not in flows_without_diagnosis:
        if data.get('diagnosis') and str(data.get('diagnosis')).strip():
            lines.append(f"🔬 **التشخيص:**")
            lines.append(escape_markdown(str(data['diagnosis'])))
            lines.append("")
    
    # ✅ قرار الطبيب - حقل منفصل تماماً
    # ✅ المسارات التي تحتوي على حقل "قرار الطبيب":
    # - استشارة جديدة، متابعة في الرقود، مراجعة / عودة دورية، طوارئ
    # ✅ المسارات التي لا تحتوي على حقل "قرار الطبيب":
    # - عملية، علاج طبيعي، أجهزة تعويضية، ترقيد، خروج من المستشفى
    flows_with_decision = [
        'استشارة جديدة', 'متابعة في الرقود', 'مراجعة / عودة دورية',
        'طوارئ', 'استشارة مع قرار عملية', 'استشارة أخيرة'
    ]
    flows_without_decision = [
        'عملية', 'علاج طبيعي', 'علاج طبيعي وإعادة تأهيل', 'أجهزة تعويضية', 'ترقيد',
        'خروج من المستشفى', 'أشعة وفحوصات', 'تأجيل موعد'
    ]

    # ✅ التحقق من نوع الإجراء قبل عرض قرار الطبيب
    should_show_decision = medical_action in flows_with_decision

    if should_show_decision:
        decision = None
        if data.get('decision') and str(data.get('decision')).strip():
            # ✅ استخدام decision مباشرة (الأولوية الأولى)
            decision = str(data.get('decision')).strip()
            # ✅ تنظيف من أي نص "قرار الطبيب:" إذا كان موجوداً (منع التكرار)
            if decision.startswith('قرار الطبيب:'):
                decision = decision.replace('قرار الطبيب:', '', 1).strip()
        else:
            # ✅ فقط إذا لم يكن decision موجوداً، نحاول استخراجه من doctor_decision
            decision = _extract_decision(data)

        if decision and str(decision).strip():
            # ✅ تسمية مختلفة لـ "متابعة في الرقود"
            if medical_action == 'متابعة في الرقود':
                lines.append(f"📝 **قرار الطبيب اليومي:**")
            else:
                lines.append(f"📝 **قرار الطبيب:**")
            lines.append(escape_markdown(str(decision)))
            lines.append("")

    # ✅ حالة الحالة (إذا كانت موجودة)
    if data.get('case_status') and str(data.get('case_status')) != 'لا يوجد':
        case_status_text = str(data['case_status'])
        # التحقق من أن case_status ليس جزءاً من doctor_decision
        doctor_decision = data.get('doctor_decision', '')
        if not (doctor_decision and case_status_text in str(doctor_decision)):
            lines.append(f"📌 الإجراء الذي تم: {escape_markdown(case_status_text)}")
            lines.append("")
    
    # ✅ رقم الغرفة والطابق (فقط لـ emergency, admission, و "متابعة في الرقود")
    # ✅ لا يُعرض لـ "مراجعة / عودة دورية" أو "استشارة جديدة"
    # حماية مركزية: لا تعرض رقم الغرفة إلا للمسارات التي تحتاجها فعلاً
    flows_with_room = ['متابعة في الرقود', 'طوارئ', 'ترقيد']
    # ✅ استخدام medical_action فقط (القيم العربية) وليس current_flow
    flows_without_room = ['مراجعة / عودة دورية', 'عودة دورية', 'استشارة جديدة']

    # ✅ التحقق: هل المسار يحتاج رقم غرفة؟
    should_show_room = medical_action in flows_with_room
    # ✅ التحقق من التطابق الكامل أو الجزئي
    should_hide_room = medical_action in flows_without_room or any(flow in str(medical_action) for flow in flows_without_room)

    if should_show_room and not should_hide_room:
        room_info = data.get('room_number') or data.get('room_floor') or data.get('room')
        if room_info and str(room_info).strip() and str(room_info).strip() != 'لم يتم التحديد':
            lines.append(f"🏥 **رقم الغرفة والطابق:** {escape_markdown(str(room_info).strip())}")
            lines.append("")
    
    # ✅ الفحوصات المطلوبة (لـ new_consult فقط)
    if medical_action == 'استشارة جديدة':
        tests = data.get('tests') or data.get('medications') or ''
        if tests and str(tests).strip() and str(tests).strip() != 'لا يوجد':
            tests_text = str(tests).strip()
            lines.append("🧪 **الفحوصات المطلوبة:**")
            # تقسيم النص إذا كان يحتوي على فواصل
            if '\n' in tests_text or ',' in tests_text or '،' in tests_text:
                if '\n' in tests_text:
                    test_lines = [line.strip() for line in tests_text.split('\n') if line.strip()]
                elif ',' in tests_text:
                    test_lines = [line.strip() for line in tests_text.split(',') if line.strip()]
                else:
                    test_lines = [line.strip() for line in tests_text.split('،') if line.strip()]
                
                for i, line in enumerate(test_lines, 1):
                    lines.append(f"{i}. {escape_markdown(line)}")
            else:
                lines.append(escape_markdown(tests_text))
            lines.append("")
    
    # ✅ الحقول الخاصة للمسارات المختلفة
    if medical_action == 'طوارئ':
        # ✅ حقول خاصة بمسار الطوارئ
        # وضع الحالة (تم الخروج / تم الترقيد / تم إجراء عملية)
        case_status = data.get('status') or data.get('case_status') or ''
        if case_status and str(case_status).strip():
            lines.append(f"🏥 **وضع الحالة:** {escape_markdown(str(case_status).strip())}")
            lines.append("")

        # إذا كان "تم الترقيد" - عرض ملاحظات الرقود ونوع الترقيد
        if 'ترقيد' in str(case_status):
            # ملاحظات الرقود
            admission_notes = data.get('admission_notes') or ''
            if admission_notes and str(admission_notes).strip():
                lines.append(f"📝 **ملاحظات الرقود:** {escape_markdown(str(admission_notes).strip())}")
                lines.append("")
            # نوع الترقيد (العناية المركزة / الرقود)
            admission_type = data.get('admission_type') or ''
            if admission_type and str(admission_type).strip():
                lines.append(f"🛏️ **نوع الترقيد:** {escape_markdown(str(admission_type).strip())}")
                lines.append("")

        # إذا كان "تم إجراء عملية" - عرض تفاصيل العملية
        elif 'عملية' in str(case_status):
            operation_details = data.get('operation_details') or ''
            if operation_details and str(operation_details).strip():
                lines.append(f"⚕️ **تفاصيل العملية:** {escape_markdown(str(operation_details).strip())}")
                lines.append("")

    elif medical_action == 'عملية':
        # تفاصيل العملية بالعربي - محاولة من عدة حقول
        operation_details = data.get('operation_details') or data.get('complaint_text') or ''
        if operation_details and str(operation_details).strip():
            lines.append(f"⚕️ **تفاصيل العملية:** {escape_markdown(str(operation_details).strip())}")
            lines.append("")
        # اسم العملية بالإنجليزي - محاولة من operation_name_en أو notes
        operation_name_en = data.get('operation_name_en') or ''
        # إذا لم يوجد، محاولة استخراجه من notes إذا كان يبدو كاسم إنجليزي
        if not operation_name_en and data.get('notes'):
            notes_val = str(data.get('notes', '')).strip()
            # تحقق إذا كان notes يحتوي على نص إنجليزي فقط (اسم العملية)
            if notes_val and all(c.isascii() or c.isspace() for c in notes_val):
                operation_name_en = notes_val
        if operation_name_en and str(operation_name_en).strip():
            lines.append(f"🔤 **اسم العملية بالإنجليزي:** {escape_markdown(str(operation_name_en).strip())}")
            lines.append("")
        # ملاحظات - فقط إذا لم يكن هو نفسه اسم العملية بالإنجليزي
        notes = data.get('notes') or ''
        if notes and str(notes).strip() and notes != operation_name_en:
            lines.append(f"📝 **ملاحظات:** {escape_markdown(str(notes).strip())}")
            lines.append("")
    
    elif medical_action == 'ترقيد':
        # سبب الرقود - محاولة من admission_reason أولاً ثم complaint_text
        admission_reason = data.get('admission_reason') or data.get('complaint_text') or ''
        if admission_reason and str(admission_reason).strip():
            lines.append(f"🛏️ **سبب الرقود:** {escape_markdown(str(admission_reason).strip())}")
            lines.append("")
        # ملاحظات
        if data.get('notes') and str(data.get('notes')).strip():
            lines.append(f"📝 **ملاحظات:** {escape_markdown(str(data['notes']))}")
            lines.append("")
    
    elif medical_action in ['علاج طبيعي', 'علاج طبيعي وإعادة تأهيل']:
        # تفاصيل جلسة العلاج الطبيعي - محاولة من therapy_details أولاً ثم complaint_text
        therapy_details = data.get('therapy_details') or data.get('complaint_text') or ''
        if therapy_details and str(therapy_details).strip():
            lines.append(f"🏃 **تفاصيل جلسة العلاج الطبيعي:** {escape_markdown(str(therapy_details).strip())}")
            lines.append("")

    elif medical_action == 'أجهزة تعويضية':
        # تفاصيل الجهاز - محاولة من عدة حقول
        device_info = data.get('device_details') or data.get('device_name') or data.get('complaint_text') or ''
        if device_info and str(device_info).strip():
            lines.append(f"🦾 **تفاصيل الجهاز:** {escape_markdown(str(device_info))}")
            lines.append("")
    
    elif medical_action == 'خروج من المستشفى':
        # نوع الخروج وملخص الرقود/العملية
        if data.get('discharge_type') == 'admission' and data.get('admission_summary'):
            lines.append(f"📋 **ملخص الرقود:** {escape_markdown(str(data['admission_summary']))}")
            lines.append("")
        elif data.get('operation_details') and str(data.get('operation_details')).strip():
            lines.append(f"⚕️ **تفاصيل العملية:** {escape_markdown(str(data['operation_details']))}")
            lines.append("")
            if data.get('operation_name_en') and str(data.get('operation_name_en')).strip():
                lines.append(f"🔤 **اسم العملية بالإنجليزي:** {escape_markdown(str(data['operation_name_en']))}")
                lines.append("")
    
    return lines


def _build_followup_fields(data: dict) -> list:
    """بناء حقول موعد العودة وسبب العودة"""
    lines = []
    
    # موعد العودة
    if data.get('followup_date') and data.get('followup_date') != 'لا يوجد':
        date_str = _format_followup_date(data.get('followup_date'), data.get('followup_time'))
        if date_str:
            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("")
            lines.append(f"📅 موعد العودة: {date_str}")
            lines.append("")
    
    # سبب العودة
    if data.get('followup_reason') and str(data.get('followup_reason')).strip() != 'لا يوجد':
        lines.append(f"✍️ **سبب العودة:**")
        lines.append(escape_markdown(str(data['followup_reason'])))
        lines.append("")
    
    return lines


def _format_followup_date(followup_date, followup_time):
    """تنسيق تاريخ العودة"""
    if not followup_date:
        return None
    
    from datetime import datetime, date
    try:
        if isinstance(followup_date, str):
            if ' ' in followup_date:
                date_obj = datetime.strptime(followup_date, '%Y-%m-%d %H:%M')
            else:
                date_obj = datetime.strptime(followup_date, '%Y-%m-%d')
        elif isinstance(followup_date, datetime):
            date_obj = followup_date
        elif isinstance(followup_date, date):
            date_obj = datetime.combine(followup_date, datetime.min.time())
        else:
            return str(followup_date)
        
        days_ar = {0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'}
        MONTH_NAMES_AR = {1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو", 7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر"}
        
        day_name = days_ar.get(date_obj.weekday(), '')
        date_str = f"{date_obj.strftime('%d')} {MONTH_NAMES_AR.get(date_obj.month, date_obj.month)} {date_obj.year} ({day_name})"
        
        if followup_time:
            if ':' in str(followup_time):
                parts = str(followup_time).split(':')
                hour = int(parts[0])
                minute = parts[1] if len(parts) > 1 else '00'
            else:
                hour = int(followup_time)
                minute = '00'
            
            if hour == 0:
                time_str = f"12:{minute} صباحاً"
            elif hour < 12:
                time_str = f"{hour}:{minute} صباحاً"
            elif hour == 12:
                time_str = f"12:{minute} ظهراً"
            else:
                time_str = f"{hour-12}:{minute} مساءً"
            
            date_str += f" - {time_str}"
        
        return date_str
    except:
        return str(followup_date)


def format_initial_case_message(case_data: dict) -> str:
    """تنسيق رسالة الحالة الأولية"""
    lines = []
    lines.append("🆕 **حالة جديدة**")
    lines.append("")
    
    if case_data.get('patient_name'):
        lines.append(f"👤 المريض: {escape_markdown(str(case_data['patient_name']))}")
        lines.append("")
    
    if case_data.get('hospital_name'):
        lines.append(f"🏥 المستشفى: {escape_markdown(str(case_data['hospital_name']))}")
        lines.append("")
    
    if case_data.get('complaint'):
        lines.append(f"💬 الشكوى: {escape_markdown(str(case_data['complaint']))}")
        lines.append("")
    
    return "\n".join(lines)
