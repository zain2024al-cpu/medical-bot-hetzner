# ================================================
# سكريبت النشر السريع - رفع التحديثات إلى GitHub ثم Hetzner
# استخدم هذا السكريبت من داخل مجلد botuser@
# ================================================

$ErrorActionPreference = "Stop"

Write-Host "🚀 بدء عملية النشر..." -ForegroundColor Green
Write-Host ""

# معلومات Hetzner
$HETZNER_IP = "5.223.58.71"
$HETZNER_USER = "root"
$REMOTE_PATH = "/root/medical-bot-hetzner"
$SERVICE_NAME = "medical-bot"

# ================================================
# الخطوة 1: إضافة الملفات المحدثة
# ================================================
Write-Host "📦 الخطوة 1: إضافة الملفات المحدثة..." -ForegroundColor Yellow

git add bot/handlers/user/user_reports_add_new_system.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ فشل إضافة الملفات" -ForegroundColor Red
    exit 1
}

Write-Host "✅ تم إضافة الملفات" -ForegroundColor Green
Write-Host ""

# ================================================
# الخطوة 2: إنشاء Commit
# ================================================
Write-Host "💾 الخطوة 2: إنشاء Commit..." -ForegroundColor Yellow

$commitMessage = "Fix: إصلاح مشكلة البحث عن الأطباء والمترجمين وإصلاح تعديل التقرير قبل الحفظ`n`n- إصلاح unified_inline_query_handler للتحقق من search_type أولاً`n- إضافة handle_edit_field_selection إلى جميع CONFIRM states`n- إصلاح زر الرجوع في شاشة التعديل`n- تحسين معالجة edit_field callbacks"

git commit -m $commitMessage

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  قد تكون التغييرات موجودة بالفعل في Commit سابق" -ForegroundColor Yellow
    Write-Host "   هل تريد المتابعة؟ (Y/N): " -NoNewline
    $response = Read-Host
    if ($response -ne "Y" -and $response -ne "y") {
        Write-Host "❌ تم إلغاء العملية" -ForegroundColor Red
        exit 0
    }
} else {
    Write-Host "✅ تم إنشاء Commit بنجاح" -ForegroundColor Green
}

Write-Host ""

# ================================================
# الخطوة 3: رفع إلى GitHub
# ================================================
Write-Host "☁️  الخطوة 3: رفع التحديثات إلى GitHub..." -ForegroundColor Yellow

git push origin main

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ فشل الرفع إلى GitHub" -ForegroundColor Red
    Write-Host "   يرجى التحقق من الاتصال والصلاحيات" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ تم الرفع إلى GitHub بنجاح" -ForegroundColor Green
Write-Host ""

# ================================================
# الخطوة 4: النشر على Hetzner
# ================================================
Write-Host "🌐 الخطوة 4: النشر على Hetzner..." -ForegroundColor Yellow

Write-Host "   🔍 التحقق من الاتصال..." -ForegroundColor Cyan
$testResult = ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP "echo 'OK'" 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ فشل الاتصال بالسيرفر" -ForegroundColor Red
    Write-Host "   $testResult" -ForegroundColor Yellow
    exit 1
}

Write-Host "   ✅ الاتصال ناجح" -ForegroundColor Green
Write-Host ""

Write-Host "   📥 جلب التحديثات من GitHub..." -ForegroundColor Cyan

$deployCommands = @"
cd $REMOTE_PATH
git stash
git fetch origin main
git pull origin main
echo '✅ تم جلب التحديثات'
"@

ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $deployCommands

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ فشل جلب التحديثات على السيرفر" -ForegroundColor Red
    exit 1
}

Write-Host "   ✅ تم جلب التحديثات" -ForegroundColor Green
Write-Host ""

# ================================================
# الخطوة 5: إعادة تشغيل الخدمة
# ================================================
Write-Host "🔄 الخطوة 5: إعادة تشغيل الخدمة..." -ForegroundColor Yellow

$restartCommands = @"
systemctl restart $SERVICE_NAME
sleep 3
if systemctl is-active --quiet $SERVICE_NAME; then
    echo '✅ الخدمة تعمل بنجاح'
    systemctl status $SERVICE_NAME --no-pager -l | head -n 10
else
    echo '❌ فشل تشغيل الخدمة!'
    systemctl status $SERVICE_NAME --no-pager -l
    exit 1
fi
"@

ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $restartCommands

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ فشل إعادة تشغيل الخدمة" -ForegroundColor Red
    exit 1
}

Write-Host "   ✅ تم إعادة تشغيل الخدمة بنجاح" -ForegroundColor Green
Write-Host ""

# ================================================
# الخطوة 6: التحقق النهائي
# ================================================
Write-Host "✅ الخطوة 6: التحقق النهائي..." -ForegroundColor Yellow

$checkCommands = @"
echo '📋 حالة الخدمة:'
systemctl is-active $SERVICE_NAME && echo '✅ الخدمة نشطة' || echo '❌ الخدمة غير نشطة'
echo ''
echo '📝 آخر 5 أسطر من السجلات:'
journalctl -u $SERVICE_NAME -n 5 --no-pager
"@

ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $checkCommands

Write-Host ""
Write-Host "════════════════════════════════════════" -ForegroundColor Green
Write-Host "✅ تم النشر بنجاح!" -ForegroundColor Green
Write-Host "════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "💡 للتحقق من السجلات:" -ForegroundColor Cyan
Write-Host "   ssh $HETZNER_USER@$HETZNER_IP 'journalctl -u $SERVICE_NAME -f'" -ForegroundColor Gray
Write-Host ""


