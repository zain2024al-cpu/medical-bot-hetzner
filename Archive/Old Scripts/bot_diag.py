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
    print("SUCCESS: requests imported")
except Exception as e:
    print(f"ERROR: requests - {e}")

try:
    from config.settings import BOT_TOKEN
    print(f"SUCCESS: BOT_TOKEN loaded (length: {len(BOT_TOKEN)})")
except Exception as e:
    print(f"ERROR: BOT_TOKEN - {e}")

# 2. Check internet connectivity
try:
    import requests
    response = requests.get('https://www.google.com', timeout=5)
    print("SUCCESS: Internet connected")
except Exception as e:
    print(f"ERROR: Internet - {e}")

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
            print("SUCCESS: Telegram API connected")
            print(f"   Bot Name: {bot_info.get('first_name')}")
            print(f"   Username: @{bot_info.get('username')}")
            print(f"   Bot ID: {bot_info.get('id')}")
        else:
            print(f"ERROR: Telegram API - {data.get('description')}")
    else:
        print(f"ERROR: HTTP Status - {response.status_code}")
except Exception as e:
    print(f"ERROR: Telegram API - {e}")

# 4. Check proxy settings
import urllib.request
proxy_handler = urllib.request.getproxies()
if proxy_handler:
    print(f"PROXY: {proxy_handler}")
else:
    print("SUCCESS: No proxy detected")

print("\n" + "=" * 60)
print("DIAGNOSTICS COMPLETE")
print("=" * 60)