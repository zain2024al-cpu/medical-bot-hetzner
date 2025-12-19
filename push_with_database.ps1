# ================================================
# رفع المشروع مع قاعدة البيانات إلى GitHub
# ================================================

Write-Host "`n📤 رفع المشروع مع قاعدة البيانات إلى GitHub..." -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Gray

# التحقق من وجود قاعدة البيانات الأولية
if (-not (Test-Path "db/medical_reports_initial.db")) {
    Write-Host "`n❌ قاعدة البيانات الأولية غير موجودة!" -ForegroundColor Red
    Write-Host "   المسار المتوقع: db/medical_reports_initial.db" -ForegroundColor Yellow
    exit 1
}

$size = (Get-Item "db/medical_reports_initial.db").Length / 1MB
Write-Host "`n✅ قاعدة البيانات الأولية موجودة" -ForegroundColor Green
Write-Host "📊 الحجم: $([math]::Round($size, 2)) MB" -ForegroundColor Cyan

# إضافة الملفات
Write-Host "`n📋 إضافة الملفات إلى Git..." -ForegroundColor Yellow

git add db/medical_reports_initial.db
git add app.py
git add .gitignore
git add .dockerignore

Write-Host "✅ تم إضافة الملفات" -ForegroundColor Green

# Commit
Write-Host "`n💾 حفظ التغييرات..." -ForegroundColor Yellow

$commitMessage = "Add initial database from local files"
git commit -m $commitMessage

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ تم حفظ التغييرات" -ForegroundColor Green
} else {
    Write-Host "⚠️ لا توجد تغييرات جديدة للرفع" -ForegroundColor Yellow
}

# Push
Write-Host "`n🚀 رفع المشروع إلى GitHub..." -ForegroundColor Yellow

git push

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ تم رفع المشروع بنجاح!" -ForegroundColor Green
    Write-Host "`n📋 الخطوات التالية:" -ForegroundColor Cyan
    Write-Host "   1. في Railway، سيكتشف التغييرات تلقائياً" -ForegroundColor White
    Write-Host "   2. أو اضغط 'Deploy' يدوياً" -ForegroundColor White
    Write-Host "   3. تحقق من Logs:" -ForegroundColor White
    Write-Host "      - '✅ تم نسخ قاعدة البيانات الأولية بنجاح'" -ForegroundColor Gray
}
else {
    Write-Host "`n❌ فشل رفع المشروع" -ForegroundColor Red
    Write-Host "   تحقق من اتصال GitHub" -ForegroundColor Yellow
    exit 1
}

Write-Host "`n" + ("=" * 60) -ForegroundColor Gray

