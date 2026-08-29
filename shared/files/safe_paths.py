# shared/files/safe_paths.py
# تعقيم أسماء الملفات قبل الحفظ على القرص — مصدر واحد لكل المواضع.
#
# ⚠️ الثغرة التي يمنعها (اجتياز المسار / Path Traversal):
# `msg.document.file_name` نصّ **يتحكّم فيه المُرسِل بالكامل** — تيليجرام
# لا يمنع `..` ولا الشرطات المائلة. وبناء المسار بـ
# `os.path.join("uploads/schedules", filename)` مباشرةً يعني أن ملفاً
# اسمه `../../app.py` يُكتَب فوق **شيفرة البوت نفسها**:
#
#   os.path.join("uploads", "schedules", "../../app.py")  ⇒  app.py
#
# وكتابة ملف `.py` يستورده البوت = تنفيذ شيفرة عن بُعد عند إعادة التشغيل.
# الحارس `@require_admin` يقلّل الاحتمال ولا يُلغيه: حساب أدمن مُخترَق،
# أو موظف بصلاحية أدمن، يكفي للتصعيد من "رفع جدول" إلى "السيطرة على
# الخادم". لذلك يُعقَّم الاسم بغضّ النظر عن هوية المُرسِل.

import os
import re
import unicodedata

# ما يُسمَح به في اسم الملف — عربي/لاتيني/أرقام وفواصل بسيطة فقط.
_ALLOWED = re.compile(r"[^\w؀-ۿ.\- ]+", re.UNICODE)
_DOTS = re.compile(r"\.{2,}")           # يمنع ".." مهما تكرّرت
MAX_NAME_LEN = 120


def safe_filename(name: str | None, *, default_ext: str = "", fallback: str = "file") -> str:
    """اسم ملف آمن — بلا مسارات ولا محارف خطرة.

    - يُسقِط أي مكوّن مسار (`os.path.basename` على الفاصلين معاً: تيليجرام
      قد يرسل `\\` من عميل ويندوز و`/` من غيره).
    - يمنع `..` فلا صعود لمجلد أعلى.
    - يقصّ الطول (بعض أنظمة الملفات تسقط عند تجاوز حدّها).
    - يعيد `fallback` إن لم يبقَ شيء صالح (اسم مكوَّن من نقاط مثلاً).
    """
    raw = str(name or "").strip()
    # الفاصلان معاً — `basename` وحدها لا تكفي على لينكس مع "\\"
    raw = raw.replace("\\", "/").split("/")[-1]
    raw = os.path.basename(raw)
    raw = unicodedata.normalize("NFKC", raw)
    raw = _ALLOWED.sub("_", raw)
    raw = _DOTS.sub(".", raw).strip(". ")

    if not raw:
        raw = fallback
    if default_ext and not raw.lower().endswith(default_ext.lower()):
        raw += default_ext

    # ⚠️ القصّ على الطول يجب أن يحفظ الامتداد: `raw[:MAX]` وحده كان يقطعه
    # فيصير الملف بلا امتداد ولا يُفتَح بالتطبيق الصحيح.
    if len(raw) > MAX_NAME_LEN:
        stem, ext = os.path.splitext(raw)
        raw = stem[:max(1, MAX_NAME_LEN - len(ext))] + ext
    return raw


def safe_join(base_dir: str, name: str | None, *, default_ext: str = "",
              fallback: str = "file") -> str:
    """مسار داخل `base_dir` مضمون — يرفع `ValueError` إن خرج عنه.

    التعقيم وحده كافٍ نظرياً، لكن التحقّق بعده شبكة أمان ثانية: أي ثغرة
    مستقبلية في `safe_filename` تُوقَف هنا بدل أن تكتب خارج المجلد.
    """
    base = os.path.abspath(base_dir)
    os.makedirs(base, exist_ok=True)
    target = os.path.abspath(os.path.join(base, safe_filename(
        name, default_ext=default_ext, fallback=fallback)))
    if os.path.commonpath([base, target]) != base:
        raise ValueError(f"مسار غير آمن: {name!r}")
    return target
