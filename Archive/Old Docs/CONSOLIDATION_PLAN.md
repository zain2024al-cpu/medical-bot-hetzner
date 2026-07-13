# خطة توحيد الكود المكرر

## الهدف
توحيد الدوال المكررة بين الملفات لتسهيل الصيانة والتعديل.

## الملفات المعنية
- `bot/handlers/user/user_reports_add_new_system.py` (~12,000 سطر) - الملف الرئيسي
- `bot/handlers/user/user_reports_add_new_system/flows/shared.py` (~2,100 سطر) - المشترك
- `bot/handlers/user/user_reports_add_new_system/utils.py` (~263 سطر) - أدوات

## النسخ الاحتياطية
تم إنشاء نسخ احتياطية بتاريخ 2026-01-18:
- `user_reports_add_new_system.py.backup_2026_01_18`
- `flows/shared.py.backup_2026_01_18`
- `utils.py.backup_2026_01_18`

---

## الحالة الحالية

### ✅ المرحلة 1: الأدوات البسيطة (مكتملة)
| الدالة | المصدر | الحالة |
|--------|--------|--------|
| `_chunked()` | utils.py | ✅ موحدة |
| `_cancel_kb()` | utils.py | ✅ موحدة |

### ✅ المرحلة 2: دوال التنقل (مكتملة)
| الدالة | المصدر | الحالة |
|--------|--------|--------|
| `_nav_buttons()` | utils.py | ✅ موحدة |

### ✅ المرحلة 3: دوال الحالات (مكتملة)
| الدالة | المصدر | الحالة |
|--------|--------|--------|
| `get_translator_state()` | flows/shared.py | ✅ موحدة |
| `get_confirm_state()` | flows/shared.py | ✅ موحدة |

### ✅ المرحلة 4: دوال الحقول (مكتملة)
| الدالة | المصدر | الحالة |
|--------|--------|--------|
| `format_field_value()` | flows/shared.py | ✅ موحدة |
| `get_field_display_name()` | flows/shared.py | ✅ موحدة |

### ✅ المرحلة 5: دوال المترجمين (مكتملة)
| الدالة | المصدر | الحالة |
|--------|--------|--------|
| `show_translator_selection()` | flows/shared.py | ✅ موحدة |
| `handle_simple_translator_choice()` | flows/shared.py | ✅ موحدة |
| `load_translator_names()` | flows/shared.py | ✅ موحدة |

### ✅ المرحلة 6: دوال حقول التعديل (مكتملة)
| الدالة | المصدر | الحالة |
|--------|--------|--------|
| `get_editable_fields_by_flow_type()` | flows/shared.py | ✅ موحدة |

---

## ما تم إنجازه

### الاستيرادات الجديدة في الملف الرئيسي:
```python
# من utils.py
from .utils import _chunked, _cancel_kb, _nav_buttons

# من flows/shared.py
from .flows.shared import (
    handle_final_confirm,
    get_translator_state,
    get_confirm_state,
    format_field_value,
    get_field_display_name,
    show_translator_selection,
    handle_simple_translator_choice,
    load_translator_names,
    get_editable_fields_by_flow_type
)
```

### الدوال المحذوفة/المُعدلة:
1. `_chunked()` - تم تحويلها لاستيراد مع fallback
2. `_cancel_kb()` - تم تحويلها لاستيراد مع fallback
3. `_nav_buttons()` - تم تحويلها لاستيراد مع fallback
4. `get_translator_state()` (نسختين!) - تم حذف كلاهما واستيراد من shared.py
5. `get_confirm_state()` - تم حذفها واستيراد من shared.py
6. `format_field_value()` - تم تحويلها لاستيراد مع fallback
7. `get_field_display_name()` - تم تحويلها لاستيراد مع fallback
8. `show_translator_selection()` - تم تحويلها لاستيراد من shared.py
9. `handle_simple_translator_choice()` - تم تحويلها لاستيراد من shared.py
10. `load_translator_names()` - تم تحويلها لاستيراد مع fallback
11. `get_editable_fields_by_flow_type()` - تم تحويلها لاستيراد مع fallback

---

## المراحل المتبقية (للمستقبل)

### المرحلة المستقبلية 1: دوال الوقت
- `format_time_12h()` - موجودة في 3 أماكن بتوقيعات مختلفة
- تحتاج دراسة أكثر قبل التوحيد

### المرحلة المستقبلية 2: دوال keyboards
- `_build_hour_keyboard()`
- `_build_minute_keyboard()`

---

## ملاحظات مهمة

1. **الأمان**: كل دالة تم توحيدها لها fallback محلي في حالة فشل الاستيراد
2. **التوافق**: لم يتم تغيير أي واجهات (signatures) للدوال
3. **الاختبار**: يجب اختبار البوت بعد كل مرحلة

---

## ملخص النتائج

تم توحيد **11 دالة** بنجاح:
- 3 دوال في `utils.py`
- 8 دوال في `flows/shared.py`

**الفوائد:**
- تقليل التكرار في الكود
- سهولة الصيانة والتعديل
- مكان واحد للإصلاح عند حدوث أخطاء
- تناسق في السلوك بين جميع المسارات

---

تاريخ التحديث: 2026-01-18
