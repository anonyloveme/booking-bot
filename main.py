from flask import Flask, request, jsonify
from flask_cors import CORS
import config
import sheets
import telegram_bot
import zalo_bot
import threading
import time
import requests as http_requests

app = Flask(__name__)
CORS(app)

# ===== KEEP ALIVE - Giữ Render không ngủ =====
def keep_alive():
    """Ping server mỗi 10 phút để Render không ngủ"""
    while True:
        time.sleep(600)  # 10 phút
        try:
            url = config.RENDER_URL or 'https://booking-bot-df6q.onrender.com'
            http_requests.get(url, timeout=10)
            print("Keep-alive ping OK")
        except Exception as e:
            print(f"Keep-alive error: {e}")

# Chạy keep-alive trong background thread
keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
keep_alive_thread.start()


@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'running',
        'service': 'BarberShop Booking Bot',
        'endpoints': ['/booking', '/telegram', '/zalo']
    })

@app.route('/booking', methods=['POST', 'OPTIONS'])
def handle_booking():
    if request.method == 'OPTIONS':
        return jsonify({'ok': True})
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        data['source'] = 'Website'

        booking_id, date_formatted = sheets.add_booking(data)
        telegram_bot.notify_new_booking(booking_id, data, date_formatted)

        return jsonify({'success': True, 'message': 'Đặt lịch thành công!', 'booking_id': booking_id})

    except Exception as e:
        print(f"Booking error: {e}")
        return jsonify({'success': False, 'message': 'Lỗi hệ thống, vui lòng thử lại!'}), 500

@app.route('/telegram', methods=['POST'])
def handle_telegram():
    try:
        update = request.get_json()
        print(f"Telegram update: {update}")

        if 'callback_query' in update:
            telegram_bot.handle_callback(update['callback_query'])
        elif 'message' in update and 'text' in update['message']:
            telegram_bot.handle_command(update['message'])

        return jsonify({'ok': True})

    except Exception as e:
        print(f"Telegram webhook error: {e}")
        return jsonify({'ok': True})

@app.route('/zalo', methods=['POST'])
def handle_zalo():
    try:
        # Xác thực Secret Token
        secret = request.headers.get('X-Bot-Api-Secret-Token', '')
        if secret != config.ZALO_SECRET_TOKEN:
            print(f"Zalo: Invalid secret token: '{secret}'")
            return jsonify({'ok': False, 'message': 'Unauthorized'}), 401

        data = request.get_json()
        print(f"Zalo update: {data}")

        threading.Thread(target=zalo_bot.handle_zalo_update, args=(data,)).start()

        return jsonify({'ok': True})

    except Exception as e:
        print(f"Zalo webhook error: {e}")
        return jsonify({'ok': True})

@app.route('/setup', methods=['GET'])
def setup_webhooks():
    base_url = config.RENDER_URL or request.host_url.rstrip('/')

    tg_result = telegram_bot.set_webhook(base_url)
    zalo_result = zalo_bot.set_webhook(base_url)

    return jsonify({
        'telegram_webhook': tg_result,
        'zalo_webhook': zalo_result,
        'base_url': base_url
    })

# ===== ENDPOINT DEBUG =====
@app.route('/debug', methods=['GET'])
def debug_info():
    """Kiểm tra trạng thái hệ thống"""
    try:
        tg_info = http_requests.get(
            f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/getWebhookInfo",
            timeout=10
        ).json()
    except:
        tg_info = {'error': 'failed'}

    try:
        zalo_info = http_requests.get(
            f"https://bot-api.zaloplatforms.com/bot{config.ZALO_BOT_TOKEN}/getWebhookInfo",
            timeout=10
        ).json()
    except:
        zalo_info = {'error': 'failed'}

    return jsonify({
        'server': 'running',
        'telegram_webhook': tg_info,
        'zalo_webhook': zalo_info,
        'zalo_sessions': len(zalo_bot.user_sessions),
        'config': {
            'RENDER_URL': config.RENDER_URL,
            'TELEGRAM_CHAT_ID': config.TELEGRAM_CHAT_ID,
            'SHEET_ID': config.SHEET_ID
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config.PORT, debug=False)
