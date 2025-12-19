# ================================================
# update_and_deploy_render.ps1
# 🔹 تحديث البيانات وإعادة النشر على Render
# ================================================

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "🔄 تحديث البيانات وإعادة النشر على Render" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# التحقق من Git
Write-Host "📦 التحقق من Git..." -ForegroundColor Yellow
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Git غير مثبت!" -ForegroundColor Red
    exit 1
}

# التحقق من قاعدة البيانات
Write-Host ""
Write-Host "💾 التحقق من قاعدة البيانات..." -ForegroundColor Yellow
$dbExists = Test-Path "db/medical_reports.db"
$dbInitialExists = Test-Path "db/medical_reports_initial.db"

if ($dbExists) {
    $dbSize = (Get-Item "db/medical_reports.db").Length / 1MB
    $dbDate = (Get-Item "db/medical_reports.db").LastWriteTime
    Write-Host "  ✅ قاعدة البيانات موجودة" -ForegroundColor Green
    Write-Host "     📊 الحجم: $([math]::Round($dbSize, 2)) MB" -ForegroundColor Cyan
    Write-Host "     📅 آخر تعديل: $($dbDate.ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor Cyan
    Write-Host ""
    
    # مقارنة مع النسخة الأولية إذا كانت موجودة
    if ($dbInitialExists) {
        $initialDate = (Get-Item "db/medical_reports_initial.db").LastWriteTime
        if ($dbDate -gt $initialDate) {
            Write-Host "  ⚠️ قاعدة البيانات المحلية أحدث من النسخة الأولية" -ForegroundColor Yellow
            Write-Host "     📅 قاعدة البيانات المحلية: $($dbDate.ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor Cyan
            Write-Host "     📅 النسخة الأولية: $($initialDate.ToString('yyyy-MM-dd HH:mm:ss'))" -ForegroundColor Cyan
        }
    }
    
    Write-Host ""
    $updateDb = Read-Host "هل تريد تحديث قاعدة البيانات على Render؟ (y/n)"
    if ($updateDb -eq "y" -or $updateDb -eq "Y") {
        Write-Host "  📋 نسخ قاعدة البيانات..." -ForegroundColor Yellow
        Copy-Item "db/medical_reports.db" "db/medical_reports_initial.db" -Force
        Write-Host "  ✅ تم نسخ قاعدة البيانات" -ForegroundColor Green
        
        # إضافة إلى Git
        git add db/medical_reports_initial.db
        Write-Host "  ✅ تم إضافة قاعدة البيانات إلى Git" -ForegroundColor Green
    }
} else {
    Write-Host "  ⚠️ قاعدة البيانات غير موجودة محلياً" -ForegroundColor Yellow
    Write-Host "  ℹ️ سيتم استخدام قاعدة البيانات الموجودة على Render" -ForegroundColor Cyan
}

# التحقق من التغييرات في الكود
Write-Host ""
Write-Host "📝 التحقق من التغييرات في الكود..." -ForegroundColor Yellow
$gitStatus = git status --porcelain

if ($gitStatus) {
    Write-Host "  📋 التغييرات الموجودة:" -ForegroundColor Cyan
    $gitStatus | ForEach-Object { Write-Host "     $_" -ForegroundColor White }
    Write-Host ""
    
    $confirm = Read-Host "هل تريد حفظ هذه التغييرات وإعادة النشر؟ (y/n)"
    if ($confirm -ne "y" -and $confirm -ne "Y") {
        Write-Host "❌ تم الإلغاء" -ForegroundColor Red
        exit 1
    }
    
    # إضافة وحفظ التغييرات
    Write-Host ""
    Write-Host "💾 حفظ التغييرات..." -ForegroundColor Yellow
    git add .
    
    $commitMessage = Read-Host "رسالة الـ Commit (اتركه فارغاً للاستخدام الافتراضي)"
    if ([string]::IsNullOrWhiteSpace($commitMessage)) {
        $commitMessage = "تحديث البيانات وإعادة نشر على Render"
    }
    
    git commit -m $commitMessage
    Write-Host "  ✅ تم حفظ التغييرات" -ForegroundColor Green
} else {
    Write-Host "  ℹ️ لا توجد تغييرات في الكود" -ForegroundColor Cyan
    
    if ($updateDb -eq "y" -or $updateDb -eq "Y") {
        # إذا كانت قاعدة البيانات فقط
        $commitMessage = "تحديث قاعدة البيانات على Render"
        git commit -m $commitMessage -a
        Write-Host "  ✅ تم حفظ تحديث قاعدة البيانات" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "  ⚠️ لا توجد تغييرات لحفظها" -ForegroundColor Yellow
        $forcePush = Read-Host "هل تريد إعادة النشر بدون تغييرات؟ (y/n)"
        if ($forcePush -ne "y" -and $forcePush -ne "Y") {
            Write-Host "❌ تم الإلغاء" -ForegroundColor Red
            exit 1
        }
    }
}

# الحصول على الفرع الحالي
$branch = git branch --show-current
Write-Host ""
Write-Host "📌 الفرع الحالي: $branch" -ForegroundColor Cyan

# رفع إلى GitHub
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "🚀 رفع التغييرات إلى GitHub..." -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

$pushConfirm = Read-Host "هل تريد رفع التغييرات إلى GitHub الآن؟ (y/n)"
if ($pushConfirm -eq "y" -or $pushConfirm -eq "Y") {
    Write-Host "  📤 جاري الرفع..." -ForegroundColor Yellow
    git push origin $branch
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✅ تم الرفع بنجاح!" -ForegroundColor Green
        Write-Host ""
        Write-Host "================================================" -ForegroundColor Cyan
        Write-Host "🎉 Render سيعيد النشر تلقائياً" -ForegroundColor Cyan
        Write-Host "================================================" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "⏳ انتظر بضع دقائق (2-5 دقائق) حتى يكتمل النشر..." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "📊 يمكنك متابعة النشر من:" -ForegroundColor Yellow
        Write-Host "   https://dashboard.render.com" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "🔍 تحقق من Logs للتأكد من:" -ForegroundColor Yellow
        Write-Host "   ✅ تم تحميل X اسم مريض من قاعدة البيانات" -ForegroundColor Green
        Write-Host "   ✅ Database loaded: X KB" -ForegroundColor Green
        Write-Host "   ✅ تم تهيئة أسماء المرضى بنجاح" -ForegroundColor Green
        Write-Host ""
        
        if ($updateDb -eq "y" -or $updateDb -eq "Y") {
            Write-Host "⚠️ بعد اكتمال النشر، احذف قاعدة البيانات من Git:" -ForegroundColor Yellow
            Write-Host "   git rm db/medical_reports_initial.db" -ForegroundColor Cyan
            Write-Host "   git commit -m 'إزالة قاعدة البيانات من Git'" -ForegroundColor Cyan
            Write-Host "   git push origin $branch" -ForegroundColor Cyan
            Write-Host ""
        }
        
        Write-Host "✅ تم!" -ForegroundColor Green
        Write-Host ""
        Write-Host "💡 نصيحة: يمكنك فتح Render Dashboard الآن:" -ForegroundColor Yellow
        Write-Host "   start https://dashboard.render.com" -ForegroundColor Cyan
    } else {
        Write-Host ""
        Write-Host "❌ فشل الرفع!" -ForegroundColor Red
        Write-Host "تحقق من:" -ForegroundColor Yellow
        Write-Host "   - اتصال الإنترنت" -ForegroundColor White
        Write-Host "   - إعدادات Git" -ForegroundColor White
        Write-Host "   - الصلاحيات على GitHub" -ForegroundColor White
    }
} else {
    Write-Host ""
    Write-Host "ℹ️ تم الإلغاء" -ForegroundColor Yellow
    Write-Host "يمكنك رفع التغييرات لاحقاً باستخدام:" -ForegroundColor Yellow
    Write-Host "   git push origin $branch" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan

