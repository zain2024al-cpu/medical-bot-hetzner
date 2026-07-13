# ================================================
# diagnose_bot.py - تشخيص مشاكل البوت
# ================================================

import sys
import os
if sys.platform == 'win32':
    os.system('chcp 65001 >nul')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

print("=" * 60)
print("MEDICAL BOT DIAGNOSTICS")
print("=" * 60)

# 1. Check basic imports
try:
    import requests
    print("✅ requests: OK")
except Exception as e:
    print(f"❌ requests: {e}")

try:
    from config.settings import BOT_TOKEN
    print(f"✅ BOT_TOKEN: OK (length: {len(BOT_TOKEN)})")
except Exception as e:
    print(f"❌ BOT_TOKEN: {e}")

# 2. Check internet connectivity
try:
    import requests
    response = requests.get('https://www.google.com', timeout=5)
    print("✅ Internet: Connected")
except Exception as e:
    print(f"❌ Internet: {e}")

# 3. Check Telegram API connectivity
try:
    import requests
    import json
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/getMe'
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        data = response.json()
        if data.get('ok'):
            bot_info = data['result']
            print(f"✅ Telegram API: Connected")
            print(f"   Bot Name: {bot_info.get('first_name')}")
            print(f"   Username: @{bot_info.get('username')}")
            print(f"   Bot ID: {bot_info.get('id')}")
        else:
            print(f"❌ Telegram API: {data.get('description')}")
    else:
        print(f"❌ HTTP Status: {response.status_code}")
except Exception as e:
    print(f"❌ Telegram API: {e}")

# 4. Check proxy settings
import urllib.request
proxy_handler = urllib.request.getproxies()
if proxy_handler:
    print(f"📡 Proxy detected: {proxy_handler}")
else:
    print("📡 No proxy detected")

# 5. Check environment variables
print("\n📋 Environment Variables:")
print(f"   PYTHONIOENCODING: {os.environ.get('PYTHONIOENCODING', 'Not set')}")
print(f"   HTTP_PROXY: {os.environ.get('HTTP_PROXY', 'Not set')}")
print(f"   HTTPS_PROXY: {os.environ.get('HTTPS_PROXY', 'Not set')}")

# 6. Network test to different Telegram endpoints
endpoints = [
    'https://api.telegram.org',
    'https://api.telegram.org/bot' + BOT_TOKEN[:10] + '.../getMe'
]

print("\n🌐 Network Connectivity Test:")
for endpoint in endpoints:
    try:
        import requests
        response = requests.get(endpoint, timeout=5)
        print(f"   ✅ {endpoint}: {response.status_code}")
    except Exception as e:
        print(f"   ❌ {endpoint}: {str(e)[:50]}...")

print("\n" + "=" * 60)
print("DIAGNOSTICS COMPLETE")
print("=" * 60)
print("\n🔧 Solutions if bot doesn't work:")
print("1. Check internet connection")
print("2. Check firewall settings (port 443, 80, 5222)")
print("3. Try disabling VPN or proxy")
print("4. Check antivirus blocking")
print("5. Try different network (mobile hotspot)")
print("=" * 60)