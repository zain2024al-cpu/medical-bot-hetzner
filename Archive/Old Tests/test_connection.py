import sys
import os
if sys.platform == 'win32':
    os.system('chcp 65001 >nul')
    os.environ['PYTHONIOENCODING'] = 'utf-8'

import requests

try:
    url = 'https://api.telegram.org/bot8309645711:AAHr2ObgOWG1H_MHo3t1ijRl90r4gpPVcEo/getMe'
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        data = response.json()
        if data.get('ok'):
            bot_info = data['result']
            print('SUCCESS: Bot connection works!')
            print('Bot name:', bot_info.get('first_name', 'Unknown'))
            print('Bot username:', '@' + bot_info.get('username', 'unknown'))
        else:
            print('ERROR: Bot API error:', data.get('description', 'Unknown error'))
    else:
        print('ERROR: HTTP error:', response.status_code)
except Exception as e:
    print('ERROR: Connection error:', str(e))