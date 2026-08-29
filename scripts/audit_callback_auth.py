"""تدقيق الصلاحيات: هل كل معالِج كولباك يتحقّق من هوية الضاغط؟

⚠️ لماذا هذا أهم فحص أمني لبوت تلغرام:
`callback_data` نصّ يظهر في الرسالة نفسها. أي شخص في **أي مجموعة** أُعيد
توجيه رسالة منها — أو أي مستخدم يجرّب — يستطيع إرسال الكولباك مباشرة لواجهة
البوت. فالمعالِج غير المحميّ = زرّ إداري متاح للجميع.
"""
import ast
import io
import pathlib

# ⚠️ جذر المشروع يُشتَقّ من موقع السكربت نفسه.
# كان مساراً ثابتاً لويندوز، فعلى الخادم لا يجد أي ملف و**يطبع أصفاراً
# بلا أي رسالة خطأ** — أداة تدقيق تبدو "نظيفة" وهي عمياء تماماً،
# وهذا أسوأ من غيابها لأنها تمنح ثقة كاذبة.
ROOT = pathlib.Path(__file__).resolve().parent.parent

# مؤشّرات وجود حارس صلاحية داخل الدالة أو كديكوريتر
GUARD_CALLS = {
    "is_admin", "_is_admin", "_is_authorized", "user_has_module",
    "require_admin", "admin_only", "_check_admin", "is_authorized",
    # ⚠️ `ensure_approved` كان ناقصاً فظهرت معالِجات محميّة فعلاً ضمن
    # "بلا حارس" (مثل `start_report`) — أُثبِت بالتجربة أنه يمنع غير
    # المعتمَد. أي حارس جديد يجب أن يُضاف هنا وإلا صارت الأداة تُنذِر كذباً.
    "ensure_approved", "is_user_approved", "_owns_report",
}
GUARD_DECOS = {"require_admin", "admin_only", "admin_required"}

# ⚠️ `venv` **داخل المستودع على الخادم** — بلا استثنائه يمشي الفحص في
# عشرات آلاف ملفات المكتبات ويحلّلها بـ`ast`، فيبدو **معلّقاً بلا نهاية**.
# لم يظهر العطل على جهاز التطوير لأن البيئة الافتراضية خارج المجلد هناك.
# الفحص يخصّ شيفرة المشروع وحدها، فاستثناؤها صحيح لا مجرد تسريع.
SKIP_DIRS = (
    "Archive", "_archive", "scripts", "tests",
    "venv", ".venv", "env", ".git", "node_modules",
    "site-packages", "__pycache__", "backups", "uploads", "logs",
)


def _skipped(rel: str) -> bool:
    """أي مسار يقع تحت أحد المجلدات المستثناة — لا بدايته فحسب."""
    parts = rel.split("/")
    return any(part in SKIP_DIRS for part in parts)


cold = []


def collect():
    handlers, funcs = [], {}
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        if _skipped(rel):
            continue
        try:
            src = io.open(p, encoding="utf-8").read()
            tree = ast.parse(src)
        except Exception:
            continue
        for n in ast.walk(tree):
            # تعريفات الدوال + هل فيها حارس
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decos = {getattr(d, "id", getattr(getattr(d, "attr", None), "__str__", lambda: "")())
                         for d in n.decorator_list}
                decos |= {getattr(d, "attr", "") for d in n.decorator_list}
                names = set()
                for c in ast.walk(n):
                    if isinstance(c, ast.Call):
                        f = c.func
                        names.add(getattr(f, "id", "") or getattr(f, "attr", ""))
                guarded = bool(decos & GUARD_DECOS) or bool(names & GUARD_CALLS)
                funcs[(rel, n.name)] = guarded
            # تسجيل CallbackQueryHandler
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "CallbackQueryHandler":
                if n.args:
                    a = n.args[0]
                    cbname = getattr(a, "id", None) or getattr(a, "attr", None)
                    pat = ""
                    for kw in n.keywords:
                        if kw.arg == "pattern" and isinstance(kw.value, ast.Constant):
                            pat = str(kw.value.value)
                    if cbname:
                        handlers.append((rel, n.lineno, cbname, pat))

            # ⚠️ **الرقم الذي يهمّ**: ما يُبلَغ "بارداً" — أي بلا اجتياز أي
            # بوّابة. معالِج داخل `states` لا يُبلَغ إلا بعد نقطة الدخول
            # فحمايته منها؛ أما `entry_points` والتسجيل المباشر فيصلهما أي
            # مستخدم بإرسال الكولباك. خلطهما يُنتِج رقماً مفزعاً بلا معنى.
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "ConversationHandler":
                for kw in n.keywords:
                    if kw.arg == "entry_points" and isinstance(kw.value, ast.List):
                        for e in kw.value.elts:
                            if (isinstance(e, ast.Call)
                                    and getattr(e.func, "id", "") == "CallbackQueryHandler"
                                    and e.args):
                                nm = (getattr(e.args[0], "id", None)
                                      or getattr(e.args[0], "attr", None))
                                if nm:
                                    cold.append((rel, e.lineno, nm, "entry_point"))
            if (isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "add_handler"
                    and n.args and isinstance(n.args[0], ast.Call)
                    and getattr(n.args[0].func, "id", "") == "CallbackQueryHandler"
                    and n.args[0].args):
                nm = (getattr(n.args[0].args[0], "id", None)
                      or getattr(n.args[0].args[0], "attr", None))
                if nm:
                    cold.append((rel, n.lineno, nm, "direct"))
    return handlers, funcs


handlers, funcs = collect()
by_name = {}
for (rel, fn), g in funcs.items():
    by_name.setdefault(fn, []).append(g)

unguarded, unknown = [], []
for rel, ln, cb, pat in handlers:
    flags = by_name.get(cb)
    if flags is None:
        unknown.append((rel, ln, cb, pat))
    elif not any(flags):
        unguarded.append((rel, ln, cb, pat))

cold_bad = [c for c in cold if not any(by_name.get(c[2], [False]))]
cold_admin = [c for c in cold_bad if "admin" in c[0]]

print("═" * 62)
print("🎯 الأهمّ — ما يُبلَغ بارداً (بلا اجتياز أي بوّابة):")
print(f"   المجموع: {len(cold)}   ·   بلا حارس: {len(cold_bad)}"
      f"   ·   منها إداريّ: {len(cold_admin)}")
if cold_admin:
    print("   🔴 إداريّ مكشوف — يجب إصلاحه:")
    for rel, ln, nm, kind in sorted(cold_admin):
        print(f"      [{kind}] {nm}()  {rel}:{ln}")
elif cold_bad:
    print("   ✅ لا إداريّ مكشوف. الباقي واجهات مستخدم:")
    for rel, ln, nm, kind in sorted(cold_bad):
        print(f"      [{kind}] {nm}()")
print("═" * 62 + "\n")

print(f"التفصيل الكامل — معالِجات الكولباك المسجَّلة: {len(handlers)}")
print(f"  ✅ محميّة:        {len(handlers) - len(unguarded) - len(unknown)}")
print(f"  ❌ بلا حارس:      {len(unguarded)}")
print(f"  ❔ تعذّر تحديدها: {len(unknown)}")

if unguarded:
    print("\n❌ بلا أي تحقّق من الصلاحية:")
    for rel, ln, cb, pat in sorted(unguarded):
        print(f"   {rel}:{ln}  {cb}()   pattern={pat or '(بلا نمط)'}")
if unknown:
    print("\n❔ لم يُعثَر على تعريفها (مستورَدة من وحدة أخرى):")
    for rel, ln, cb, pat in sorted(unknown)[:15]:
        print(f"   {rel}:{ln}  {cb}()   pattern={pat or '(بلا نمط)'}")


# ── رمز الخروج ───────────────────────────────────────────────────────────────
# 0 = لا مكشوف · 1 = يوجد معالِج بلا حارس · 2 = شُغِّل خارج المستودع
# (الحالة الأخيرة تمنع تكرار العطل الصامت: صفر نتائج ≠ نظافة).
import sys as _sys

if not ROOT.joinpath("bot").is_dir():
    print(f"\n🔴 لم يُعثَر على مجلد 'bot' داخل {ROOT} — شغّل السكربت من داخل المستودع.")
    _sys.exit(2)
# الفشل يعني: إداريّ يُبلَغ بارداً بلا حارس — لا مجرد رقم كبير
_sys.exit(1 if cold_admin else 0)
