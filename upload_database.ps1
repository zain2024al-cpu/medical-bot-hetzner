# ================================================
# رفع قاعدة البيانات المحلية إلى Railway
# ================================================

Write-Host "`n📤 رفع قاعدة البيانات المحلية إلى Railway..." -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Gray

# 1. التحقق من وجود قاعدة البيانات المحلية
$dbPath = "db/medical_reports.db"

if (-not (Test-Path $dbPath)) {
    Write-Host "`n❌ قاعدة البيانات غير موجودة: $dbPath" -ForegroundColor Red
    Write-Host "   تأكد من وجود قاعدة البيانات المحلية" -ForegroundColor Yellow
    exit 1
}

# معلومات قاعدة البيانات
$dbSize = (Get-Item $dbPath).Length / 1MB
Write-Host "`n✅ قاعدة البيانات موجودة: $dbPath" -ForegroundColor Green
Write-Host "   الحجم: $([math]::Round($dbSize, 2)) MB" -ForegroundColor Gray

# 2. محاولة الرفع إلى Cloud Storage
Write-Host "`n🔄 جاري رفع قاعدة البيانات إلى Cloud Storage..." -ForegroundColor Yellow

try {
    # استخدام Python script للرفع
    python upload_database_to_cloud.py
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✅ تم رفع قاعدة البيانات بنجاح!" -ForegroundColor Green
        Write-Host "`n💡 الخطوات التالية:" -ForegroundColor Cyan
        Write-Host "   1. اذهب إلى Railway" -ForegroundColor White
        Write-Host "   2. اضغط 'Deploy' لإعادة النشر" -ForegroundColor White
        Write-Host "   3. قاعدة البيانات ستُستعاد تلقائياً" -ForegroundColor White
    } else {
        Write-Host "`n⚠️ فشل رفع قاعدة البيانات" -ForegroundColor Yellow
        Write-Host "`n💡 الحل البديل:" -ForegroundColor Cyan
        Write-Host "   1. استخدم services/sqlite_backup.py" -ForegroundColor White
        Write-Host "   2. أو رفع قاعدة البيانات يدوياً" -ForegroundColor White
    }
}
catch {
    Write-Host "`n❌ خطأ في رفع قاعدة البيانات: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "`n💡 الحل البديل:" -ForegroundColor Cyan
    Write-Host "   1. استخدم services/sqlite_backup.py" -ForegroundColor White
    Write-Host "   2. أو رفع قاعدة البيانات يدوياً" -ForegroundColor White
}

Write-Host "`n" + ("=" * 60) -ForegroundColor Gray

