# ================================================
# سكريبت النشر الآمن - رفع التحديثات إلى GitHub ثم Hetzner
# ================================================

$ErrorActionPreference = "Stop"

Write-Host "🚀 بدء عملية النشر الآمن..." -ForegroundColor Green
Write-Host ""

# معلومات GitHub
$GITHUB_REPO = "https://github.com/zain2024al-cpu/medical-bot-hetzner.git"

# معلومات Hetzner
$HETZNER_IP = "5.223.58.71"
$HETZNER_USER = "root"
$REMOTE_PATH = "/root/medical-bot-hetzner"
$SERVICE_NAME = "medical-bot"

# الملفات التشغيلية فقط (استثناء الملفات المحلية)
$FILES_TO_DEPLOY = @(
    "bot/handlers/user/user_reports_add_new_system.py"
)

Write-Host "📋 الملفات المحددة للنشر:" -ForegroundColor Yellow
foreach ($file in $FILES_TO_DEPLOY) {
    Write-Host "  - $file" -ForegroundColor Cyan
}
Write-Host ""

# ================================================
# الخطوة 1: التحقق من حالة Git
# ================================================
Write-Host "🔍 الخطوة 1: التحقق من حالة Git..." -ForegroundColor Yellow

try {
    $gitStatus = git status --porcelain
    if ($LASTEXITCODE -ne 0) {
        throw "فشل التحقق من حالة Git"
    }
    
    if ([string]::IsNullOrWhiteSpace($gitStatus)) {
        Write-Host "⚠️  لا توجد تغييرات لإضافتها" -ForegroundColor Yellow
        Write-Host "   هل تريد المتابعة مع الملفات المحددة؟ (Y/N): " -NoNewline
        $response = Read-Host
        if ($response -ne "Y" -and $response -ne "y") {
            Write-Host "❌ تم إلغاء العملية" -ForegroundColor Red
            exit 0
        }
    }
    
    Write-Host "✅ Git يعمل بشكل صحيح" -ForegroundColor Green
} catch {
    Write-Host "❌ خطأ في Git: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ================================================
# الخطوة 2: إضافة الملفات المحددة فقط
# ================================================
Write-Host "📦 الخطوة 2: إضافة الملفات المحددة..." -ForegroundColor Yellow

foreach ($file in $FILES_TO_DEPLOY) {
    if (Test-Path $file) {
        Write-Host "  ➕ إضافة: $file" -ForegroundColor Cyan
        git add $file
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  ❌ فشل إضافة: $file" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "  ⚠️  الملف غير موجود: $file" -ForegroundColor Yellow
    }
}

Write-Host "✅ تم إضافة الملفات" -ForegroundColor Green
Write-Host ""

# ================================================
# الخطوة 3: إنشاء Commit
# ================================================
Write-Host "💾 الخطوة 3: إنشاء Commit..." -ForegroundColor Yellow

$commitMessage = "Fix: إصلاح مشكلة البحث عن الأطباء والمترجمين وإصلاح تعديل التقرير قبل الحفظ

- إصلاح unified_inline_query_handler للتحقق من search_type أولاً
- إضافة handle_edit_field_selection إلى جميع CONFIRM states
- إصلاح زر الرجوع في شاشة التعديل
- تحسين معالجة edit_field callbacks"

Write-Host "📝 رسالة Commit:" -ForegroundColor Cyan
Write-Host $commitMessage -ForegroundColor Gray
Write-Host ""

git commit -m $commitMessage

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ فشل إنشاء Commit" -ForegroundColor Red
    Write-Host "   قد تكون التغييرات موجودة بالفعل في Commit سابق" -ForegroundColor Yellow
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
# الخطوة 4: رفع إلى GitHub
# ================================================
Write-Host "☁️  الخطوة 4: رفع التحديثات إلى GitHub..." -ForegroundColor Yellow

Write-Host "   📤 جارٍ الرفع..." -ForegroundColor Cyan
git push origin main

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ فشل الرفع إلى GitHub" -ForegroundColor Red
    Write-Host "   يرجى التحقق من الاتصال والصلاحيات" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ تم الرفع إلى GitHub بنجاح" -ForegroundColor Green
Write-Host ""

# ================================================
# الخطوة 5: النشر على Hetzner
# ================================================
Write-Host "🌐 الخطوة 5: النشر على Hetzner..." -ForegroundColor Yellow

Write-Host "   🔍 التحقق من الاتصال بالسيرفر..." -ForegroundColor Cyan
$testConnection = ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP "echo 'Connected'" 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ فشل الاتصال بالسيرفر" -ForegroundColor Red
    Write-Host "   $testConnection" -ForegroundColor Yellow
    exit 1
}

Write-Host "   ✅ الاتصال ناجح" -ForegroundColor Green
Write-Host ""

Write-Host "   📥 جلب التحديثات من GitHub..." -ForegroundColor Cyan

$deployScript = @"
cd $REMOTE_PATH

# حفظ أي تغييرات محلية
git stash

# جلب التحديثات
git fetch origin main

# عرض التغييرات
echo "📝 التغييرات الجديدة:"
git log HEAD..origin/main --oneline

# سحب التحديثات
git pull origin main

if [ `$? -eq 0 ]; then
    echo "✅ تم جلب التحديثات بنجاح"
else
    echo "❌ فشل جلب التحديثات"
    exit 1
fi
"@

ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $deployScript

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ فشل جلب التحديثات على السيرفر" -ForegroundColor Red
    exit 1
}

Write-Host "   ✅ تم جلب التحديثات" -ForegroundColor Green
Write-Host ""

# ================================================
# الخطوة 6: إعادة تشغيل الخدمة
# ================================================
Write-Host "🔄 الخطوة 6: إعادة تشغيل الخدمة..." -ForegroundColor Yellow

$restartScript = @"
systemctl restart $SERVICE_NAME
sleep 3

# التحقق من الحالة
if systemctl is-active --quiet $SERVICE_NAME; then
    echo "✅ الخدمة تعمل بنجاح"
    echo ""
    echo "📊 حالة الخدمة:"
    systemctl status $SERVICE_NAME --no-pager -l | head -n 15
else
    echo "❌ فشل تشغيل الخدمة!"
    systemctl status $SERVICE_NAME --no-pager -l
    exit 1
fi
"@

ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $restartScript

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ فشل إعادة تشغيل الخدمة" -ForegroundColor Red
    Write-Host "   يرجى التحقق من السجلات يدوياً" -ForegroundColor Yellow
    exit 1
}

Write-Host "   ✅ تم إعادة تشغيل الخدمة بنجاح" -ForegroundColor Green
Write-Host ""

# ================================================
# الخطوة 7: التحقق النهائي
# ================================================
Write-Host "✅ الخطوة 7: التحقق النهائي..." -ForegroundColor Yellow

$checkScript = @"
echo "📋 حالة الخدمة:"
systemctl is-active $SERVICE_NAME && echo "✅ الخدمة نشطة" || echo "❌ الخدمة غير نشطة"

echo ""
echo "📝 آخر 5 أسطر من السجلات:"
journalctl -u $SERVICE_NAME -n 5 --no-pager
"@

ssh -o StrictHostKeyChecking=no $HETZNER_USER@$HETZNER_IP $checkScript

Write-Host ""
Write-Host "════════════════════════════════════════" -ForegroundColor Green
Write-Host "✅ تم النشر بنجاح!" -ForegroundColor Green
Write-Host "════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "💡 للتحقق من السجلات:" -ForegroundColor Cyan
Write-Host "   ssh $HETZNER_USER@$HETZNER_IP 'journalctl -u $SERVICE_NAME -f'" -ForegroundColor Gray
Write-Host ""





