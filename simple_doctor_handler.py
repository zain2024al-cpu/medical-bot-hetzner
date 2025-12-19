#!/usr/bin/env python3
"""
دالة بسيطة للبحث عن الأطباء - تحل محل الدالة المعقدة
"""

from telegram import InlineQueryResultArticle, InputTextMessageContent
from services.doctors_smart_search import search_doctors

async def simple_doctor_inline_query_handler(update, context):
    """Handler بسيط للبحث عن الأطباء"""
    print("🎯 DOCTOR SEARCH STARTED")
    try:
        # الحصول على البيانات
        query_text = update.inline_query.query.strip() if update.inline_query.query else ""
        print(f"Query: '{query_text}'")

        # البحث عن الأطباء
        doctors_results = search_doctors(
            query=query_text if query_text else "",
            hospital=None,  # ابحث في جميع المستشفيات
            department=None,  # ابحث في جميع الأقسام
            limit=10
        )

        print(f"Found {len(doctors_results)} doctors")

        # بناء النتائج
        results = []
        for idx, doctor in enumerate(doctors_results):
            name = doctor.get('name', 'طبيب بدون اسم')
            hospital = doctor.get('hospital', 'مستشفى غير محدد')
            department = doctor.get('department_ar', doctor.get('department_en', 'قسم غير محدد'))

            result = InlineQueryResultArticle(
                id=f"doc_{idx}",
                title=f"👨‍⚕️ {name}",
                description=f"🏥 {hospital[:30]} | 📋 {department[:30]}",
                input_message_content=InputTextMessageContent(
                    message_text=f"__DOCTOR_SELECTED__:{idx}:{name}"
                )
            )
            results.append(result)

        # إرسال النتائج
        await update.inline_query.answer(results, cache_time=1)
        print(f"✅ Sent {len(results)} results to Telegram")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        # إرسال نتائج فارغة في حالة الخطأ
        try:
            await update.inline_query.answer([], cache_time=1)
        except:
            pass

# اختبار الدالة
if __name__ == "__main__":
    import asyncio

    class MockUpdate:
        class MockInlineQuery:
            def __init__(self, query):
                self.query = query

            async def answer(self, results, cache_time=1):
                print(f"Mock answer called with {len(results)} results")
                for r in results[:3]:
                    print(f"  - {r.title}")

        def __init__(self, query):
            self.inline_query = self.MockInlineQuery(query)

    class MockContext:
        def __init__(self):
            self.user_data = {}

    async def test():
        print("Testing simple doctor handler...")

        # اختبار مع استعلام فارغ
        update1 = MockUpdate("")
        context1 = MockContext()
        await simple_doctor_inline_query_handler(update1, context1)

        # اختبار مع استعلام
        update2 = MockUpdate("dr")
        context2 = MockContext()
        await simple_doctor_inline_query_handler(update2, context2)

    asyncio.run(test())
