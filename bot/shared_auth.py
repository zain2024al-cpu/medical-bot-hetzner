# ================================================
# bot/shared_auth.py
# 🔹 التحقق من صلاحيات المستخدم والإدمن
# ================================================

from config.settings import ADMIN_IDS
from db.session import SessionLocal
from db.models import Translator
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import logging

logger = logging.getLogger(__name__)


# ✅ التحقق إن كان المستخدم إدمن
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# إنشاء سجل للمستخدم إن لم يكن موجوداً — **بلا موافقة تلقائية**.
#
# ⚠️ كانت تُنشئ المستخدم بـ`is_approved=True`: أي شخص يصل للبوت يصبح
# معتمداً فوراً ويرى بيانات المرضى. لم تكن مُستدعاة من أي مكان (مستورَدة
# في user_start.py وغير مستعملة) فلم يظهر أثرها — لكنها لغم: أول استدعاء
# لها كان سيفتح البوت للجميع بصمت، ولن يكشفه شيء لأن لا خطأ يقع.
#
# المسار الصحيح هو register_pending_user أدناه (وهو ما يفعله /start فعلاً):
# يُنشئ بـis_approved=False ويُشعر الأدمن ليوافق يدوياً.
def ensure_translator_record(tg_id, full_name=None):
    with SessionLocal() as s:
        t = s.query(Translator).filter_by(tg_user_id=tg_id).first()
        if not t:
            t = Translator(
                tg_user_id=tg_id,
                full_name=full_name or "بدون اسم",
                is_active=True,
                is_approved=False,   # ← الاعتماد بيد الأدمن وحده
            )
            s.add(t)
            s.commit()
        else:
            # تحديث الاسم إذا تغيّر
            if full_name and t.full_name != full_name:
                t.full_name = full_name
                s.commit()
    return True


# ✅ فحص إن كان المستخدم معتمد (مقبول من الأدمن)
def is_user_approved(tg_user_id: int) -> bool:
    with SessionLocal() as s:
        tr = s.query(Translator).filter_by(tg_user_id=tg_user_id).first()
        # التحقق من أنه معتمد وليس مجمد
        return bool(tr and tr.is_approved and not tr.is_suspended)


# ✅ تسجيل مستخدم جديد في انتظار موافقة الأدمن
async def register_pending_user(user_id: int, full_name: str, phone: str, bot):
    """إرسال إشعار للأدمن بمستخدم جديد"""
    
    # التحقق من وجود المستخدم (للتحديث إذا لزم الأمر)
    with SessionLocal() as s:
        tr = s.query(Translator).filter_by(tg_user_id=user_id).first()
        if not tr:
            # إنشاء المستخدم إذا لم يكن موجوداً
            tr = Translator(
                tg_user_id=user_id,
                full_name=full_name,
                phone_number=phone,
                is_active=True,
                is_approved=False
            )
            s.add(tr)
            s.commit()
            print(f"✅ تم إنشاء مستخدم في register_pending_user: {full_name}")

    # إعداد رسالة الإشعار
    text = f"📝 **مستخدم جديد بانتظار الموافقة:**\n\n👤 **الاسم:** {full_name}\n📱 **الهاتف:** {phone}\n🆔 **Telegram ID:** {user_id}"

    # أزرار الموافقة أو الرفض
    buttons = [
        [
            InlineKeyboardButton("✅ قبول", callback_data=f"approve:{user_id}"),
            InlineKeyboardButton("❌ رفض", callback_data=f"reject:{user_id}")
        ]
    ]

    # التحقق من وجود أدمن
    if not ADMIN_IDS:
        print("⚠️ تحذير: لا يوجد أدمن محدد في ADMIN_IDS!")
        return
    
    print(f"📨 إرسال إشعار إلى {len(ADMIN_IDS)} أدمن...")
    
    # إرسال الرسالة إلى جميع الأدمن
    success_count = 0
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=aid,
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="Markdown"
            )
            success_count += 1
            print(f"✅ تم إرسال الإشعار للأدمن {aid}")
        except Exception as e:
            print(f"❌ فشل إرسال الإشعار للأدمن {aid}: {e}")
    
    print(f"📊 تم إرسال الإشعار بنجاح إلى {success_count} من {len(ADMIN_IDS)} أدمن")


# ✅ التحقق من أن المستخدم معتمد أو إدمن (مع cache)
async def ensure_approved(update, context) -> bool:
    user = update.effective_user
    if not user:
        return False

    # التحقق من الأدمن (سريع - لا يحتاج DB)
    if is_admin(user.id):
        return True

    # التحقق من cache أولاً
    cached_approved = context.user_data.get("_is_approved")
    if cached_approved is not None:
        if not cached_approved:
            try:
                await update.message.reply_text(
                    "🚫 لا يمكنك استخدام البوت قبل موافقة الإدارة."
                )
            except Exception:
                logger.debug("تم تجاهل استثناء في ensure_approved", exc_info=True)
        return cached_approved

    # الاستعلام من قاعدة البيانات وحفظ في cache
    approved = is_user_approved(user.id)
    context.user_data["_is_approved"] = approved
    
    if not approved:
        try:
            await update.message.reply_text(
                "🚫 لا يمكنك استخدام البوت قبل موافقة الإدارة."
            )
        except Exception:
            logger.debug("تم تجاهل استثناء في ensure_approved", exc_info=True)
        return False

    return True


def can_modify_report(report, actor_id: int, session) -> bool:
    """
    هل يحقّ لهذا المستخدم تعديل/حذف هذا التقرير؟

    ⚠️ **يرفض افتراضياً** (fail-closed). الفحص السابق كان يرفض بشرطٍ موجب:

        translator = session.query(Translator).filter_by(tg_user_id=actor_id).first()
        if translator and report.translator_id != translator.id:
            → رفض

    فإذا لم يكن للمستخدم صفٌّ في `users` إطلاقاً صارت `translator = None`،
    فلا يتحقّق الشرط ولا يُرفض شيء — **فيمرّ الحذف**. أي أن مستخدماً غير
    مسجَّل كان يستطيع حذف أي تقرير قديم (submitted_by_user_id = NULL)
    لأي مترجم. أُثبِت بالتشغيل قبل الإصلاح.

    القاعدة الآن:
      • الأدمن                     ⇒ مسموح
      • تقرير حديث (له مالك مصرَّح) ⇒ يجب أن يطابق المالك
      • تقرير قديم (بلا مالك)      ⇒ يجب أن يكون المستخدم مسجَّلاً **و**
                                     يطابق translator_id للتقرير
      • ما عدا ذلك                 ⇒ مرفوض
    """
    if actor_id is None or report is None:
        return False
    if is_admin(actor_id):
        return True

    owner = getattr(report, "submitted_by_user_id", None)
    if owner is not None:
        return owner == actor_id

    # تقرير قديم: لا يُسمح إلا لمترجم مسجَّل يطابق معرّفه معرّف التقرير
    translator = session.query(Translator).filter_by(tg_user_id=actor_id).first()
    if translator is None:
        return False
    return report.translator_id == translator.id
