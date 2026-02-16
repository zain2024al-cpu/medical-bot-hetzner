# --- Handler خاص بحقل رقم الغرفة والطابق لمسار متابعة في الرقود فقط ---
from telegram import ReplyKeyboardMarkup

async def handle_followup_room_floor(update, context, render_calendar_func, validate_text_input, FOLLOWUP_DATE_TIME, FOLLOWUP_ROOM_FLOOR):
    text = update.message.text.strip()
    if text == "تخطي":
        context.user_data["report_tmp"]["room_number"] = None
        await update.message.reply_text("تم تخطي إدخال رقم الغرفة والطابق.")
        await render_calendar_func(update.message, context)
        context.user_data['_conversation_state'] = FOLLOWUP_DATE_TIME
        return FOLLOWUP_DATE_TIME
    valid, msg = validate_text_input(text, min_length=1)
    if not valid:
        skip_keyboard = ReplyKeyboardMarkup([["تخطي"]], resize_keyboard=True)
        await update.message.reply_text(
            f"⚠️ **خطأ: {msg}**\n\n"
            f"يرجى إدخال رقم الغرفة والطابق أو اضغط تخطي:",
            reply_markup=skip_keyboard,
            parse_mode="Markdown"
        )
        return FOLLOWUP_ROOM_FLOOR
    context.user_data["report_tmp"]["room_number"] = text
    await update.message.reply_text("✅ تم الحفظ")
    await render_calendar_func(update.message, context)
    context.user_data['_conversation_state'] = FOLLOWUP_DATE_TIME
    return FOLLOWUP_DATE_TIME
# منطق مسار متابعة في الرقود (Followup in Admission)

FOLLOWUP_FIELDS = [
    ("complaint", "💬 حالة المريض اليومية"),
    ("diagnosis", "🔬 التشخيص"),
    ("decision", "📝 قرار الطبيب اليومي"),
    ("room_number", "🚪 رقم الغرفة والطابق"),
    ("followup_date", "📅 موعد العودة"),
    ("followup_reason", "✍️ سبب العودة"),
    ("translator_name", "👤 المترجم"),
]

# ... أضف هنا جميع الدوال الخاصة بهذا المسار فقط ...
