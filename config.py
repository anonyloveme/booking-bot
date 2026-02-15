import os

# Telegram
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8237526835:AAHQmibNAOsMyuAzAc-kDlRojh8FOW2oPlM')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '7026021540')

# Zalo Bot
ZALO_BOT_TOKEN = os.environ.get('ZALO_BOT_TOKEN', '1791525309981773257:OJLOWtxoMNhZyegQfKderfWZibbBmjbhhNvZZRRUQgvuDgymEpPzhxGfnYajHKeE')

# Google Sheets
SHEET_ID = os.environ.get('SHEET_ID', '1V0KtvRjKn1sNLXgHEHs3Q0a2mz1y_HP9-evKU2CUyiw')

# Server
PORT = int(os.environ.get('PORT', 10000))
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', '')
