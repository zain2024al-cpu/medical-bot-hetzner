# ================================================
# bot/shared_navigation.py
# 🎯 نظام زر الرجوع الذكي الموحد
# نظام قوي وموحد للتنقل بين الشاشات بدون لخبطة
# ================================================

import logging
from typing import Optional, Dict, Callable, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

logger = logging.getLogger(__name__)


class SmartNavigationManager:
    """
    مدير التنقل الذكي الموحد
    - يتتبع تاريخ التنقل بشكل صحيح
    - يمنع الرجوع العشوائي
    - يعمل في جميع ملفات المستخدم
    """
    
    def __init__(self):
        # Stack لتاريخ التنقل (LIFO - Last In First Out)
        self._navigation_stack = []
        # معلومات إضافية لكل state (مثل البيانات المؤقتة)
        self._state_data = {}
    
    def push_state(self, state: Any, state_data: Optional[Dict] = None):
        """
        إضافة state جديد إلى المكدس
        - يمنع التكرار المتتالي
        - يحفظ البيانات المرتبطة بالـ state
        """
        # منع التكرار المتتالي
        if self._navigation_stack and self._navigation_stack[-1] == state:
            logger.debug(f"⚠️ State {state} already at top, skipping push")
            return
        
        self._navigation_stack.append(state)
        
        # حفظ البيانات المرتبطة إذا كانت موجودة
        if state_data:
            self._state_data[state] = state_data.copy()
        
        logger.info(f"✅ Pushed state: {state}, Stack size: {len(self._navigation_stack)}")
        logger.debug(f"📋 Full stack: {self._navigation_stack}")
    
    def pop_state(self) -> Optional[Any]:
        """
        إزالة وإرجاع آخر state من المكدس
        """
        if not self._navigation_stack:
            logger.warning("⚠️ Navigation stack is empty")
            return None
        
        popped = self._navigation_stack.pop()
        
        # تنظيف البيانات المرتبطة
        self._state_data.pop(popped, None)
        
        logger.info(f"✅ Popped state: {popped}, Remaining stack size: {len(self._navigation_stack)}")
        return popped
    
    def peek_state(self) -> Optional[Any]:
        """
        رؤية آخر state بدون إزالته
        """
        if self._navigation_stack:
            return self._navigation_stack[-1]
        return None
    
    def get_previous_state(self) -> Optional[Any]:
        """
        الحصول على الـ state السابق (قبل الأخير)
        """
        if len(self._navigation_stack) >= 2:
            return self._navigation_stack[-2]
        elif len(self._navigation_stack) == 1:
            # إذا كان هناك state واحد فقط، نرجع None للرجوع للبداية
            return None
        return None
    
    def clear_history(self):
        """
        تنظيف كامل للمكدس والبيانات
        """
        self._navigation_stack.clear()
        self._state_data.clear()
        logger.info("✅ Navigation history cleared")
    
    def get_history(self) -> list:
        """
        الحصول على نسخة من المكدس الكامل
        """
        return self._navigation_stack.copy()
    
    def has_history(self) -> bool:
        """
        التحقق من وجود تاريخ تنقل
        """
        return len(self._navigation_stack) > 0
    
    def get_state_count(self) -> int:
        """
        عدد الـ states في المكدس
        """
        return len(self._navigation_stack)
    
    @staticmethod
    def get_manager(context: ContextTypes.DEFAULT_TYPE, namespace: str = "default") -> 'SmartNavigationManager':
        """
        الحصول على مدير التنقل من context
        - namespace: لتحديد سياق مختلف (مثل 'reports', 'initial_case', إلخ)
        """
        nav_key = f"_navigation_manager_{namespace}"
        
        if nav_key not in context.user_data:
            context.user_data[nav_key] = SmartNavigationManager()
            logger.info(f"✅ Created new navigation manager for namespace: {namespace}")
        
        return context.user_data[nav_key]
    
    @staticmethod
    def clear_manager(context: ContextTypes.DEFAULT_TYPE, namespace: str = "default"):
        """
        تنظيف مدير التنقل من context
        """
        nav_key = f"_navigation_manager_{namespace}"
        if nav_key in context.user_data:
            manager = context.user_data[nav_key]
            manager.clear_history()
            context.user_data.pop(nav_key, None)
            logger.info(f"✅ Cleared navigation manager for namespace: {namespace}")


class NavigationRenderer:
    """
    مسؤول عن عرض الشاشات عند الرجوع
    - يربط كل state بدالة العرض المناسبة
    """
    
    def __init__(self):
        self._renderers: Dict[Any, Callable] = {}
        self._state_names: Dict[Any, str] = {}
    
    def register_state(self, state: Any, renderer: Callable, state_name: str = None):
        """
        تسجيل state مع دالة العرض الخاصة به
        """
        self._renderers[state] = renderer
        if state_name:
            self._state_names[state] = state_name
        logger.info(f"✅ Registered renderer for state: {state} ({state_name or 'unnamed'})")
    
    def get_renderer(self, state: Any) -> Optional[Callable]:
        """
        الحصول على دالة العرض للـ state
        """
        return self._renderers.get(state)
    
    def get_state_name(self, state: Any) -> str:
        """
        الحصول على اسم الـ state
        """
        return self._state_names.get(state, f"State {state}")
    
    def has_renderer(self, state: Any) -> bool:
        """
        التحقق من وجود renderer للـ state
        """
        return state in self._renderers


# ================================================
# دالة الرجوع الذكية الموحدة
# ================================================

async def handle_smart_back(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    namespace: str = "default",
    renderer: Optional[NavigationRenderer] = None,
    fallback_handler: Optional[Callable] = None
):
    """
    معالج زر الرجوع الذكي الموحد
    
    Args:
        update: Telegram update object
        context: Context object
        namespace: سياق التنقل (مثل 'reports', 'initial_case')
        renderer: NavigationRenderer مسجل به renderers
        fallback_handler: دالة احتياطية إذا لم يكن هناك renderer
    
    Returns:
        State للرجوع إليه أو ConversationHandler.END
    """
    query = update.callback_query
    
    if not query:
        logger.error("❌ handle_smart_back: No callback_query found")
        return ConversationHandler.END
    
    await query.answer()
    
    try:
        # الحصول على مدير التنقل
        nav_manager = SmartNavigationManager.get_manager(context, namespace)
        
        # التحقق من وجود تاريخ
        if not nav_manager.has_history():
            logger.warning("⚠️ No navigation history available")
            await query.answer("⚠️ لا يمكن الرجوع - أنت في البداية", show_alert=True)
            return ConversationHandler.END
        
        # الحصول على الـ state السابق
        previous_state = nav_manager.get_previous_state()
        current_state = nav_manager.peek_state()
        
        logger.info(f"🔙 Back navigation: Current={current_state}, Previous={previous_state}")
        logger.info(f"🔙 Stack: {nav_manager.get_history()}")
        
        # إذا لم يكن هناك state سابق، نرجع للبداية
        if previous_state is None:
            logger.info("🔙 No previous state, going to start")
            nav_manager.clear_history()
            
            if fallback_handler:
                await fallback_handler(update, context)
            else:
                await query.answer("🏠 العودة للقائمة الرئيسية", show_alert=False)
            
            return ConversationHandler.END
        
        # إزالة الـ state الحالي من المكدس
        popped = nav_manager.pop_state()
        logger.info(f"🔙 Popped state: {popped}, Going back to: {previous_state}")
        
        # تحديث conversation state
        context.user_data['_conversation_state'] = previous_state
        
        # محاولة عرض الشاشة السابقة
        if renderer and renderer.has_renderer(previous_state):
            # استخدام renderer مسجل
            render_func = renderer.get_renderer(previous_state)
            state_name = renderer.get_state_name(previous_state)
            
            logger.info(f"🔙 Rendering state: {previous_state} ({state_name})")
            
            try:
                # حذف الرسالة الحالية
                await query.message.delete()
            except Exception as e:
                logger.warning(f"⚠️ Could not delete message: {e}")
            
            # استدعاء دالة العرض
            await render_func(query.message, context)
            
            await query.answer(f"🔙 تم الرجوع لـ: {state_name}", show_alert=False)
            return previous_state
        
        elif fallback_handler:
            # استخدام fallback handler
            logger.info("🔙 Using fallback handler")
            await fallback_handler(update, context)
            return previous_state
        
        else:
            # لا يوجد renderer ولا fallback
            logger.warning(f"⚠️ No renderer or fallback for state: {previous_state}")
            await query.answer("⚠️ لا يمكن الرجوع - خطأ في النظام", show_alert=True)
            return previous_state
    
    except Exception as e:
        logger.error(f"❌ Error in handle_smart_back: {e}", exc_info=True)
        await query.answer("❌ حدث خطأ أثناء الرجوع", show_alert=True)
        return ConversationHandler.END


# ================================================
# دالة مساعدة للانتقال إلى state جديد
# ================================================

def navigate_to_state(
    context: ContextTypes.DEFAULT_TYPE,
    new_state: Any,
    namespace: str = "default",
    state_data: Optional[Dict] = None
):
    """
    الانتقال إلى state جديد مع حفظه في التاريخ
    
    Args:
        context: Context object
        new_state: الـ state الجديد
        namespace: سياق التنقل
        state_data: بيانات إضافية للـ state
    """
    nav_manager = SmartNavigationManager.get_manager(context, namespace)
    nav_manager.push_state(new_state, state_data)
    context.user_data['_conversation_state'] = new_state
    
    logger.info(f"✅ Navigated to state: {new_state} (namespace: {namespace})")


# ================================================
# دالة مساعدة لإضافة زر الرجوع إلى لوحة المفاتيح
# ================================================

def add_back_button(keyboard: list, callback_data: str = "nav:back") -> list:
    """
    إضافة زر الرجوع إلى لوحة المفاتيح
    
    Args:
        keyboard: قائمة الأزرار الحالية
        callback_data: callback_data للزر (افتراضي: "nav:back")
    
    Returns:
        قائمة الأزرار المحدثة
    """
    # التحقق من وجود زر رجوع بالفعل
    for row in keyboard:
        for button in row:
            if hasattr(button, 'callback_data') and button.callback_data == callback_data:
                # زر الرجوع موجود بالفعل
                return keyboard
    
    # إضافة زر الرجوع في صف جديد
    keyboard.append([
        InlineKeyboardButton("🔙 رجوع", callback_data=callback_data)
    ])
    
    return keyboard


def create_back_button(callback_data: str = "nav:back") -> InlineKeyboardButton:
    """
    إنشاء زر رجوع فقط
    
    Args:
        callback_data: callback_data للزر
    
    Returns:
        InlineKeyboardButton للرجوع
    """
    return InlineKeyboardButton("🔙 رجوع", callback_data=callback_data)


def create_nav_buttons(
    show_back: bool = True,
    show_cancel: bool = True,
    back_callback: str = "nav:back",
    cancel_callback: str = "nav:cancel"
) -> list:
    """
    إنشاء أزرار التنقل (رجوع + إلغاء)
    
    Args:
        show_back: إظهار زر الرجوع
        show_cancel: إظهار زر الإلغاء
        back_callback: callback_data لزر الرجوع
        cancel_callback: callback_data لزر الإلغاء
    
    Returns:
        قائمة الأزرار
    """
    buttons = []
    
    if show_back and show_cancel:
        buttons.append([
            InlineKeyboardButton("🔙 رجوع", callback_data=back_callback),
            InlineKeyboardButton("❌ إلغاء", callback_data=cancel_callback)
        ])
    elif show_back:
        buttons.append([
            InlineKeyboardButton("🔙 رجوع", callback_data=back_callback)
        ])
    elif show_cancel:
        buttons.append([
            InlineKeyboardButton("❌ إلغاء", callback_data=cancel_callback)
        ])
    
    return buttons





