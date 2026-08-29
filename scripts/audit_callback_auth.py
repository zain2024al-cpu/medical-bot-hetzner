"""تدقيق الصلاحيات: هل كل معالِج كولباك يتحقّق من هوية الضاغط؟

⚠️ لماذا هذا أهم فحص أمني لبوت تلغرام:
`callback_data` نصّ يظهر في الرسالة نفسها. أي شخص في **أي مجموعة** أُعيد
توجيه رسالة منها — أو أي مستخدم يجرّب — يستطيع إرسال الكولباك مباشرة لواجهة
البوت. فالمعالِج غير المحميّ = زرّ إداري متاح للجميع.
"""
import ast
import io
import pathlib

ROOT = pathlib.Path(r"C:\Users\nalgu\medical-bot-clean")

# مؤشّرات وجود حارس صلاحية داخل الدالة أو كديكوريتر
GUARD_CALLS = {
    "is_admin", "_is_admin", "_is_authorized", "user_has_module",
    "require_admin", "admin_only", "_check_admin", "is_authorized",
}
GUARD_DECOS = {"require_admin", "admin_only", "admin_required"}

SKIP_DIRS = ("Archive", "_archive", "scripts", "tests")


def collect():
    handlers, funcs = [], {}
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        if any(rel.startswith(d) for d in SKIP_DIRS):
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

print(f"معالِجات الكولباك المسجَّلة: {len(handlers)}")
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
