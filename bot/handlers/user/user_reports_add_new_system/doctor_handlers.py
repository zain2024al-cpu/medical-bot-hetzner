# =============================
# doctor_handlers.py
# معالجات اختيار الطبيب
# =============================

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import logging

from .states import STATE_SELECT_DOCTOR, R_DOCTOR, R_ACTION_TYPE
from .managers import DoctorDataManager
from ..user_reports_add_helpers import validate_text_input

logger = logging.getLogger(__name__)

# Imports المشتركة
try:
    from db.session import SessionLocal
except ImportError:
    SessionLocal = None

try:
    from db.models import Doctor, Hospital, Department
except ImportError:
    Doctor = Hospital = Department = None


async def render_doctor_selection(message, context):
    """عرض شاشة اختيار الطبيب - عرض قائمة الأطباء المفلترين مباشرة"""
    DoctorDataManager.clear_doctor_data(context)
    context.user_data['_current_search_type'] = 'doctor'

    report_tmp = context.user_data.get("report_tmp", {})
    hospital_name = report_tmp.get("hospital_name", "")
    department_name = report_tmp.get("department_name", "")

    logger.info(f"🎯 render_doctor_selection: hospital='{hospital_name}', department='{department_name}'")

    keyboard = []

    # ✅ جلب الأطباء المفلترين حسب المستشفى والقسم
    doctors_list = []
    doctor_names = []
    
    if hospital_name and department_name:
        try:
            # ✅ أولاً: البحث في قاعدة البيانات مباشرة
            if SessionLocal and Doctor and Hospital and Department:
                try:
                    with SessionLocal() as s:
                        # البحث عن المستشفى والقسم
                        hospital = s.query(Hospital).filter(Hospital.name == hospital_name).first()
                        department = s.query(Department).filter(Department.name == department_name).first()
                        
                        # جلب الأطباء من قاعدة البيانات المربوطة بالمستشفى والقسم
                        query = s.query(Doctor).filter(
                            Doctor.full_name.isnot(None),
                            Doctor.full_name != ""
                        )
                        
                        if hospital:
                            query = query.filter(Doctor.hospital_id == hospital.id)
                        if department:
                            query = query.filter(Doctor.department_id == department.id)
                        
                        db_doctors = query.order_by(Doctor.full_name).all()
                        
                        # استخراج الأسماء من قاعدة البيانات
                        for doc in db_doctors:
                            name = doc.full_name or doc.name
                            if name and name not in doctor_names:
                                doctor_names.append(name)
                        
                        logger.info(f"✅ تم جلب {len(doctor_names)} طبيب من قاعدة البيانات للمستشفى '{hospital_name}' والقسم '{department_name}'")
                except Exception as db_error:
                    logger.error(f"❌ خطأ في جلب الأطباء من قاعدة البيانات: {db_error}", exc_info=True)
            
            # ✅ ثانياً: البحث في services.doctors_smart_search (للبحث عن أطباء إضافيين)
            try:
                from services.doctors_smart_search import get_doctors_for_hospital_dept
                
                # تحويل أسماء المستشفيات المختصرة إلى الأسماء الكاملة
                hospital_mapping = {
                    "Aster CMI": "Aster CMI Hospital, Bangalore",
                    "Aster RV": "Aster RV Hospital, Bangalore",
                    "Aster Whitefield": "Aster Whitefield Hospital, Bangalore",
                    "Manipal Hospital - Old Airport Road": "Manipal Hospital, Old Airport Road, Bangalore",
                    "Manipal Hospital - Millers Road": "Manipal Hospital, Millers Road, Bangalore",
                    "Manipal Hospital - Whitefield": "Manipal Hospital, Whitefield, Bangalore",
                    "Manipal Hospital - Yeshwanthpur": "Manipal Hospital, Yeshwanthpur, Bangalore",
                    "Manipal Hospital - Sarjapur Road": "Manipal Hospital, Sarjapur Road, Bangalore",
                }
                
                full_hospital_name = hospital_mapping.get(hospital_name, hospital_name)
                doctors_list = get_doctors_for_hospital_dept(full_hospital_name, department_name)
                
                # إضافة الأسماء من services إلى القائمة (بدون تكرار)
                for doctor in doctors_list:
                    name = doctor.get('name', '') or doctor.get('full_name', '')
                    if name and name not in doctor_names:
                        doctor_names.append(name)
                
                logger.info(f"✅ تم إضافة {len(doctors_list)} طبيب من services للمستشفى '{hospital_name}' والقسم '{department_name}'")
            except Exception as e:
                logger.error(f"❌ خطأ في جلب الأطباء من services: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"❌ خطأ في جلب الأطباء: {e}", exc_info=True)

    # ✅ إذا كان هناك أطباء، عرضهم كأزرار
    if doctor_names:
        # ترتيب الأسماء أبجدياً
        doctor_names.sort()
        
        # حفظ قائمة الأطباء في context للاسترجاع لاحقاً
        context.user_data["_doctors_list"] = doctor_names
        
        # إضافة أزرار الأطباء (حد أقصى 50 طبيب)
        for idx, name in enumerate(doctor_names[:50]):
            button_text = f"👨‍⚕️ {name}"
            if len(button_text) > 64:
                button_text = f"👨‍⚕️ {name[:60]}..."
            
            keyboard.append([InlineKeyboardButton(
                button_text,
                callback_data=f"doctor_idx:{idx}"
            )])
        
        # ✅ إضافة زر "إدخال يدوي" دائماً (حتى لو كان هناك أطباء في القائمة)
        keyboard.append([InlineKeyboardButton(
            "✏️ إدخال اسم الطبيب يدوياً",
            callback_data="doctor_manual"
        )])
        
        text = f"👨‍⚕️ **اسم الطبيب** (الخطوة 5 من 5)\n\n"
        text += f"🏥 **المستشفى:** {hospital_name}\n"
        text += f"🏷️ **القسم:** {department_name}\n\n"
        text += f"📋 **عدد الأطباء:** {len(doctor_names)}\n\n"
        text += "اختر الطبيب من القائمة أو اضغط على **إدخال يدوي** لإضافة طبيب جديد:"
    else:
        # ✅ إذا لم يوجد أطباء، عرض زر "إدخال يدوي" فقط
        keyboard.append([InlineKeyboardButton(
            "✏️ إدخال يدوي اسم الطبيب",
            callback_data="doctor_manual"
        )])
        
        text = f"👨‍⚕️ **اسم الطبيب** (الخطوة 5 من 5)\n\n"
        if hospital_name and department_name:
            text += f"🏥 **المستشفى:** {hospital_name}\n"
            text += f"🏷️ **القسم:** {department_name}\n\n"
            text += "⚠️ **لم يتم العثور على أطباء** في هذا القسم.\n\n"
            text += "يرجى إدخال اسم الطبيب يدوياً:"
        else:
            text += "⚠️ **تحذير:** يرجى اختيار المستشفى والقسم أولاً.\n\n"
            text += "اضغط على زر '🔙 رجوع' للعودة واختيار المستشفى والقسم."

    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data="go_to_department_selection"),
        InlineKeyboardButton("❌ إلغاء", callback_data="nav:cancel")
    ])

    try:
        await message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"❌ خطأ في عرض قائمة اختيار الطبيب: {e}", exc_info=True)
        try:
            await message.reply_text(
                text.replace("**", ""),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e2:
            logger.error(f"❌ خطأ في المحاولة الثانية: {e2}")


async def show_doctor_selection(message, context, search_query=""):
    """Navigation wrapper - يحدث state ثم يستدعي rendering"""
    context.user_data['last_valid_state'] = 'search_doctor_screen'
    context.user_data['_conversation_state'] = STATE_SELECT_DOCTOR
    logger.info(f"✅ show_doctor_selection: Set _conversation_state to {STATE_SELECT_DOCTOR}")
    await render_doctor_selection(message, context)


async def show_doctor_input(message, context):
    """Navigation wrapper - يحدث state ثم يستدعي rendering"""
    logger.info("🏥 show_doctor_input: Called")
    context.user_data['last_valid_state'] = 'search_doctor_screen'
    context.user_data['_conversation_state'] = STATE_SELECT_DOCTOR
    context.user_data['_current_search_type'] = 'doctor'
    logger.info(f"🏥 show_doctor_input: Set _conversation_state to STATE_SELECT_DOCTOR")
    await render_doctor_selection(message, context)


async def handle_doctor_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيار طبيب من القائمة أو زر الإدخال اليدوي"""
    from .utils import _nav_buttons
    from .action_type_handlers import show_action_type_menu
    
    query = update.callback_query
    await query.answer()
    
    logger.info(f"🔧 handle_doctor_selection: callback_data='{query.data}'")
    logger.info(f"🔧 handle_doctor_selection: Current _conversation_state = {context.user_data.get('_conversation_state', 'NOT SET')}")
    logger.info(f"🔧 handle_doctor_selection: Expected STATE_SELECT_DOCTOR = {STATE_SELECT_DOCTOR}")

    # ✅ معالجة اختيار طبيب من القائمة (باستخدام الفهرس)
    if query.data.startswith("doctor_idx:"):
        try:
            index_str = query.data.split(":", 1)[1]
            doctor_idx = int(index_str)
            
            # استرجاع قائمة الأطباء من context.user_data
            doctors_list = context.user_data.get("_doctors_list", [])
            
            if not doctors_list or doctor_idx < 0 or doctor_idx >= len(doctors_list):
                logger.error(f"❌ فهرس غير صالح: {doctor_idx}, القائمة تحتوي على {len(doctors_list)} عنصر")
                await query.answer("⚠️ حدث خطأ في اختيار الطبيب", show_alert=True)
                return STATE_SELECT_DOCTOR
            
            doctor_name = doctors_list[doctor_idx]
            
            # حفظ اسم الطبيب
            context.user_data.setdefault("report_tmp", {})["doctor_name"] = doctor_name
            context.user_data["report_tmp"].setdefault("step_history", []).append(R_DOCTOR)
            
            # تنظيف البيانات المؤقتة
            context.user_data.pop("_doctors_list", None)
            
            await query.edit_message_text(
                f"✅ **تم اختيار الطبيب**\n\n"
                f"👨‍⚕️ **الطبيب:**\n"
                f"{doctor_name}",
                parse_mode="Markdown"
            )
            
            # الانتقال إلى اختيار نوع الإجراء
            context.user_data['last_valid_state'] = 'action_type_selection'
            context.user_data['_conversation_state'] = R_ACTION_TYPE
            await show_action_type_menu(query.message, context)
            return R_ACTION_TYPE
        except (ValueError, IndexError) as e:
            logger.error(f"❌ خطأ في معالجة اختيار الطبيب (فهرس): {e}", exc_info=True)
            await query.answer("⚠️ حدث خطأ في اختيار الطبيب", show_alert=True)
            return STATE_SELECT_DOCTOR

    if query.data == "doctor_manual":
        if "report_tmp" not in context.user_data:
            context.user_data["report_tmp"] = {}
        
        logger.info("🔧 تم الضغط على زر الإدخال اليدوي للطبيب")
        
        try:
            await query.edit_message_text(
                "👨‍⚕️ **اسم الطبيب**\n\n"
                "✏️ يرجى إدخال اسم الطبيب:",
                reply_markup=_nav_buttons(show_back=False),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"❌ خطأ في تعديل الرسالة: {e}")
            try:
                await query.message.reply_text(
                    "👨‍⚕️ **اسم الطبيب**\n\n"
                    "✏️ يرجى إدخال اسم الطبيب:",
                    reply_markup=_nav_buttons(show_back=False),
                    parse_mode="Markdown"
                )
            except:
                pass
        
        context.user_data["report_tmp"]["doctor_manual_mode"] = True
        logger.info("✅ تم تفعيل وضع الإدخال اليدوي للطبيب")
        return STATE_SELECT_DOCTOR


async def handle_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إدخال اسم الطبيب يدوياً أو اختياره من inline query"""
    from .action_type_handlers import show_action_type_menu
    from .utils import _nav_buttons
    
    text = update.message.text.strip()
    logger.info(f"🔍 handle_doctor: received text='{text}'")
    
    if "report_tmp" not in context.user_data:
        context.user_data["report_tmp"] = {}
    
    # ✅ إزالة دعم inline query - لم نعد نستخدمها

    # التحقق إذا كان في وضع الإدخال اليدوي
    manual_mode = context.user_data.get("report_tmp", {}).get("doctor_manual_mode", False)
    logger.info(f"🔍 handle_doctor: manual_mode={manual_mode}")
    
    if manual_mode:
        valid, msg = validate_text_input(text, min_length=2, max_length=100)
        if not valid:
            await update.message.reply_text(
                f"⚠️ **خطأ: {msg}**\n\n"
                f"يرجى إدخال اسم الطبيب:",
                reply_markup=_nav_buttons(show_back=True, previous_state_name="new_consult_complaint", context=context),
                parse_mode="Markdown"
            )
            return STATE_SELECT_DOCTOR

        context.user_data["report_tmp"]["doctor_name"] = text
        context.user_data["report_tmp"].setdefault("step_history", []).append(R_DOCTOR)
        context.user_data["report_tmp"].pop("doctor_manual_mode", None)
        logger.info(f"✅ تم حفظ اسم الطبيب يدوياً: {text}")
        
        # ✅ حفظ الطبيب في قاعدة البيانات مع المستشفى والقسم
        try:
            from db.session import SessionLocal
            from db.models import Doctor, Hospital, Department
            
            report_tmp = context.user_data.get("report_tmp", {})
            hospital_name = report_tmp.get("hospital_name", "")
            department_name = report_tmp.get("department_name", "")
            
            with SessionLocal() as s:
                # البحث عن الطبيب أولاً (البحث بـ full_name أو name)
                from sqlalchemy import or_
                doctor = s.query(Doctor).filter(
                    or_(
                        Doctor.full_name == text,
                        Doctor.name == text
                    )
                ).first()
                
                if not doctor:
                    # إنشاء طبيب جديد
                    doctor = Doctor(
                        name=text,
                        full_name=text
                    )
                    
                    # محاولة ربطه بالمستشفى إذا كان موجوداً
                    if hospital_name:
                        hospital = s.query(Hospital).filter(Hospital.name == hospital_name).first()
                        if hospital:
                            doctor.hospital_id = hospital.id
                    
                    # محاولة ربطه بالقسم إذا كان موجوداً
                    if department_name:
                        department = s.query(Department).filter(Department.name == department_name).first()
                        if department:
                            doctor.department_id = department.id
                    
                    s.add(doctor)
                    s.commit()
                    logger.info(f"✅ تم حفظ الطبيب في قاعدة البيانات: {text} (مستشفى: {hospital_name}, قسم: {department_name})")
                else:
                    # ✅ تحديث معلومات المستشفى والقسم إذا لم تكن موجودة
                    updated = False
                    if hospital_name and not doctor.hospital_id:
                        hospital = s.query(Hospital).filter(Hospital.name == hospital_name).first()
                        if hospital:
                            doctor.hospital_id = hospital.id
                            updated = True
                    
                    if department_name and not doctor.department_id:
                        department = s.query(Department).filter(Department.name == department_name).first()
                        if department:
                            doctor.department_id = department.id
                            updated = True
                    
                    if updated:
                        s.commit()
                        logger.info(f"✅ تم تحديث معلومات الطبيب: {text}")
                    else:
                        logger.info(f"ℹ️ الطبيب موجود بالفعل في قاعدة البيانات: {text}")
        except Exception as e:
            logger.error(f"❌ خطأ في حفظ الطبيب في قاعدة البيانات: {e}", exc_info=True)

        context.user_data['last_valid_state'] = 'action_type_selection'
        context.user_data['_conversation_state'] = R_ACTION_TYPE
        logger.info(f"📋 Moving to action_type_selection")

        await update.message.reply_text(
            f"✅ **تم حفظ اسم الطبيب**\n\n"
            f"👨‍⚕️ **الطبيب:**\n"
            f"{text}\n\n"
            f"💾 سيظهر هذا الطبيب في القائمة في المرة القادمة.",
            parse_mode="Markdown"
        )
        await show_action_type_menu(update.message, context)
        return R_ACTION_TYPE

    # إذا لم يكن في وضع الإدخال اليدوي، نعيد عرض القائمة
    logger.warning(f"⚠️ handle_doctor: لم يتم التعرف على النص. النص: '{text}'")
    await show_doctor_selection(update.message, context)
    return STATE_SELECT_DOCTOR

