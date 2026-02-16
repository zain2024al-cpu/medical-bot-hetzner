#!/bin/bash
# سكريبت تحديث السيرفر

echo "🔄 بدء تحديث البوت على السيرفر..."
echo ""

cd /root/real_bot_final || exit 1

echo "📥 جلب آخر التحديثات من GitHub..."
git pull origin main

echo ""
echo "📦 تحديث المتطلبات..."
pip3 install -r requirements.txt --upgrade

echo ""
echo "🗄️ تحديث قاعدة البيانات..."
python3 add_schedule_columns.py

echo ""
echo "🔄 إعادة تشغيل الخدمة..."
systemctl restart medical-bot

echo ""
echo "✅ تم التحديث بنجاح!"
echo ""
sleep 3

echo "📊 حالة الخدمة:"
systemctl status medical-bot --no-pager -l

echo ""
echo "📋 آخر سطور من اللوغات:"
journalctl -u medical-bot -n 20 --no-pager
