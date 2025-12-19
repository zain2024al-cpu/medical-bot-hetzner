# ================================================
# 🚀 سكريبت النشر الكامل - Medical Reports Bot
# ================================================

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "🚀 بدء عملية النشر الكاملة" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# التحقق من gcloud
Write-Host "📋 التحقق من gcloud..." -ForegroundColor Yellow
try {
    $gcloudVersion = gcloud --version 2>&1 | Select-Object -First 1
    Write-Host "✅ gcloud مثبت: $gcloudVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ gcloud غير مثبت!" -ForegroundColor Red
    Write-Host "📥 حمّل من: https://cloud.google.com/sdk/docs/install" -ForegroundColor Yellow
    exit 1
}

# التحقق من تسجيل الدخول
Write-Host ""
Write-Host "🔐 التحقق من تسجيل الدخول..." -ForegroundColor Yellow
try {
    $currentAccount = gcloud config get-value account 2>&1
    if ($currentAccount -and $currentAccount -notmatch "unset") {
        Write-Host "✅ مسجل دخول كـ: $currentAccount" -ForegroundColor Green
    } else {
        Write-Host "⚠️ غير مسجل دخول، جاري تسجيل الدخول..." -ForegroundColor Yellow
        gcloud auth login
    }
} catch {
    Write-Host "❌ خطأ في التحقق من تسجيل الدخول" -ForegroundColor Red
    exit 1
}

# ضبط المشروع
Write-Host ""
Write-Host "🎯 ضبط المشروع..." -ForegroundColor Yellow
$PROJECT_ID = "lunar-standard-477302-a6"
gcloud config set project $PROJECT_ID
Write-Host "✅ المشروع: $PROJECT_ID" -ForegroundColor Green

# تفعيل APIs المطلوبة
Write-Host ""
Write-Host "🔧 تفعيل APIs المطلوبة..." -ForegroundColor Yellow
gcloud services enable cloudbuild.googleapis.com --quiet
gcloud services enable run.googleapis.com --quiet
gcloud services enable storage-api.googleapis.com --quiet
gcloud services enable storage-component.googleapis.com --quiet
gcloud services enable iam.googleapis.com --quiet
Write-Host "✅ APIs مفعّلة" -ForegroundColor Green

# إنشاء Service Account لقاعدة البيانات
Write-Host ""
Write-Host "🔐 إنشاء Service Account لقاعدة البيانات..." -ForegroundColor Yellow
$SERVICE_ACCOUNT_NAME = "medical-bot-sa"
$SERVICE_ACCOUNT_EMAIL = "$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"

# التحقق من وجود Service Account
try {
    $existingAccount = gcloud iam service-accounts describe $SERVICE_ACCOUNT_EMAIL 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Service Account موجود: $SERVICE_ACCOUNT_EMAIL" -ForegroundColor Green
    }
} catch {
    Write-Host "📝 إنشاء Service Account جديد..." -ForegroundColor Yellow
    gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME --description="Service Account for Medical Bot Database Access" --display-name="Medical Bot SA"
    Write-Host "✅ تم إنشاء Service Account" -ForegroundColor Green
}

# منح صلاحيات Storage Admin
Write-Host "🔑 منح صلاحيات Storage Admin..." -ForegroundColor Yellow
gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" --role="roles/storage.admin"
Write-Host "✅ تم منح الصلاحيات" -ForegroundColor Green

# إنشاء مفتاح Service Account
Write-Host "🗝️ إنشاء مفتاح Service Account..." -ForegroundColor Yellow
$KEY_FILE = "service-account-key.json"
if (Test-Path $KEY_FILE) {
    Write-Host "⚠️ ملف المفتاح موجود مسبقاً، سيتم الكتابة عليه" -ForegroundColor Yellow
}
gcloud iam service-accounts keys create $KEY_FILE --iam-account=$SERVICE_ACCOUNT_EMAIL
Write-Host "✅ تم إنشاء مفتاح Service Account: $KEY_FILE" -ForegroundColor Green

# التحقق من ملف env.yaml
Write-Host ""
Write-Host "📄 التحقق من ملف env.yaml..." -ForegroundColor Yellow
if (Test-Path "env.yaml") {
    Write-Host "✅ ملف env.yaml موجود" -ForegroundColor Green
} else {
    Write-Host "❌ ملف env.yaml غير موجود!" -ForegroundColor Red
    exit 1
}

# التحقق من Dockerfile
Write-Host ""
Write-Host "🐳 التحقق من Dockerfile..." -ForegroundColor Yellow
if (Test-Path "Dockerfile") {
    Write-Host "✅ Dockerfile موجود" -ForegroundColor Green
} else {
    Write-Host "❌ Dockerfile غير موجود!" -ForegroundColor Red
    exit 1
}

# التحقق من requirements.txt
Write-Host ""
Write-Host "📦 التحقق من requirements.txt..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    Write-Host "✅ requirements.txt موجود" -ForegroundColor Green
} else {
    Write-Host "❌ requirements.txt غير موجود!" -ForegroundColor Red
    exit 1
}

# النشر
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "🚀 بدء النشر إلى Cloud Run..." -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

$SERVICE_NAME = "medical-bot"
$REGION = "asia-south1"

gcloud run deploy $SERVICE_NAME `
    --source . `
    --region $REGION `
    --platform managed `
    --allow-unauthenticated `
    --memory 1Gi `
    --cpu 1 `
    --timeout 300 `
    --concurrency 80 `
    --min-instances 0 `
    --max-instances 10 `
    --cpu-boost `
    --env-vars-file env.yaml

Write-Host ""
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ النشر نجح!" -ForegroundColor Green
    Write-Host ""
    
    # الحصول على Service URL
    Write-Host "🔗 جاري الحصول على Service URL..." -ForegroundColor Yellow
    $SERVICE_URL = gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)' 2>&1
    
    if ($SERVICE_URL -and $SERVICE_URL -notmatch "error") {
        Write-Host "✅ Service URL: $SERVICE_URL" -ForegroundColor Green
        Write-Host ""
        
        # تحديث env.yaml بـ URL الجديد
        Write-Host "📝 تحديث env.yaml بـ URL الجديد..." -ForegroundColor Yellow
        $envContent = Get-Content env.yaml -Raw
        if ($envContent -match 'SERVICE_URL:\s*"[^"]*"') {
            $envContent = $envContent -replace 'SERVICE_URL:\s*"[^"]*"', "SERVICE_URL: `"$SERVICE_URL`""
            Set-Content env.yaml -Value $envContent -NoNewline
            Write-Host "✅ تم تحديث env.yaml" -ForegroundColor Green
        }
        
        # ضبط Webhook
        Write-Host ""
        Write-Host "🔗 ضبط Telegram Webhook..." -ForegroundColor Yellow
        $BOT_TOKEN = "8309645711:AAHr2ObgOWG1H_MHo3t1ijRl90r4gpPVcEo"
        $webhookUrl = "$SERVICE_URL/$BOT_TOKEN"
        
        try {
            $response = Invoke-RestMethod -Uri "https://api.telegram.org/bot$BOT_TOKEN/setWebhook" -Method Post -Body @{url=$webhookUrl} -ErrorAction Stop
            if ($response.ok) {
                Write-Host "✅ Webhook تم ضبطه بنجاح!" -ForegroundColor Green
                Write-Host "   URL: $webhookUrl" -ForegroundColor Cyan
            } else {
                Write-Host "⚠️ Webhook لم يتم ضبطه: $($response.description)" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "⚠️ خطأ في ضبط Webhook تلقائياً" -ForegroundColor Yellow
            Write-Host "📋 استخدم هذا الأمر يدوياً:" -ForegroundColor Yellow
            Write-Host "curl -X POST `"https://api.telegram.org/bot$BOT_TOKEN/setWebhook`" -d `"url=$webhookUrl`"" -ForegroundColor White
        }
        
        Write-Host ""
        Write-Host "================================================" -ForegroundColor Green
        Write-Host "🎉 البوت منشور بنجاح!" -ForegroundColor Green
        Write-Host "================================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "📊 معلومات النشر:" -ForegroundColor Cyan
        Write-Host "   Service Name: $SERVICE_NAME" -ForegroundColor White
        Write-Host "   Region: $REGION" -ForegroundColor White
        Write-Host "   URL: $SERVICE_URL" -ForegroundColor White
        Write-Host ""
        Write-Host "🧪 اختبر البوت:" -ForegroundColor Cyan
        Write-Host "   1. افتح Telegram" -ForegroundColor White
        Write-Host "   2. ابحث عن البوت" -ForegroundColor White
        Write-Host "   3. أرسل: /start" -ForegroundColor White
        Write-Host ""
        Write-Host "📋 أوامر مفيدة:" -ForegroundColor Cyan
        Write-Host "   مشاهدة Logs: gcloud run logs tail $SERVICE_NAME --region $REGION" -ForegroundColor White
        Write-Host "   معلومات الخدمة: gcloud run services describe $SERVICE_NAME --region $REGION" -ForegroundColor White
        Write-Host ""
        
    } else {
        Write-Host "⚠️ لم يتم الحصول على Service URL" -ForegroundColor Yellow
        Write-Host "📋 استخدم هذا الأمر للحصول على URL:" -ForegroundColor Yellow
        Write-Host "gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)'" -ForegroundColor White
    }
    
} else {
    Write-Host "❌ فشل النشر!" -ForegroundColor Red
    Write-Host ""
    Write-Host "📋 جاري عرض آخر 50 سطر من Logs..." -ForegroundColor Yellow
    gcloud run services logs read $SERVICE_NAME --region $REGION --limit 50
    Write-Host ""
    Write-Host "💡 نصائح لحل المشاكل:" -ForegroundColor Yellow
    Write-Host "   1. تحقق من أن جميع الملفات موجودة" -ForegroundColor White
    Write-Host "   2. تحقق من محتوى env.yaml" -ForegroundColor White
    Write-Host "   3. تحقق من Dockerfile و requirements.txt" -ForegroundColor White
    Write-Host "   4. راجع Logs أعلاه للتفاصيل" -ForegroundColor White
    exit 1
}
Write-Host ""
Write-Host "✅ اكتمل النشر!" -ForegroundColor Green
Write-Host ""











