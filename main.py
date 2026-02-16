from flask import Flask, request, jsonify
from flask_cors import CORS
import config
import sheets
import telegram_bot
import zalo_bot
import threading
import time
import json
import traceback
import requests as http_requests

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


# ===== KEEP ALIVE =====
def keep_alive():
    while True:
        time.sleep(600)
        try:
            url = config.RENDER_URL or 'https://booking-bot-df6q.onrender.com'
            http_requests.get(url, timeout=10)
            print("Keep-alive ping OK")
        except Exception as e:
            print(f"Keep-alive error: {e}")

keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
keep_alive_thread.start()


# ===== TRANG CHỦ =====
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'running',
        'service': 'BarberShop Booking Bot',
        'endpoints': ['/booking', '/telegram', '/zalo']
    })


# ===== NHẬN BOOKING TỪ WEBSITE =====
@app.route('/booking', methods=['POST', 'OPTIONS'])
def handle_booking():
    # Xử lý CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({'ok': True})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Accept')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response

    try:
        # Debug log
        print(f"=== NEW BOOKING REQUEST ===")
        print(f"Content-Type: {request.content_type}")

        raw_body = request.get_data(as_text=True)
        print(f"Raw body: {raw_body}")

        # Parse dữ liệu - thử nhiều cách
        data = None

        # Cách 1: JSON
        try:
            data = request.get_json(force=True, silent=True)
            if data:
                print(f"Parsed as JSON: {data}")
        except Exception as e:
            print(f"JSON parse failed: {e}")

        # Cách 2: Form data
        if not data or not isinstance(data, dict):
            try:
                data = request.form.to_dict()
                if data:
                    print(f"Parsed as form: {data}")
            except Exception as e:
                print(f"Form parse failed: {e}")

        # Cách 3: Parse raw body thủ công
        if not data or not isinstance(data, dict) or len(data) == 0:
            try:
                data = json.loads(raw_body)
                print(f"Parsed raw body: {data}")
            except Exception as e:
                print(f"Raw parse failed: {e}")

        # Kiểm tra dữ liệu
        if not data or not isinstance(data, dict):
            print("ERROR: No data received")
            return jsonify({'success': False, 'message': 'Không nhận được dữ liệu!'}), 400

        # Log từng field
        fullname = data.get('fullname', '')
        phone = data.get('phone', '')
        email = data.get('email', '')
        service = data.get('service', '')
        date = data.get('date', '')
        time_val = data.get('time', '')
        note = data.get('note', '')

        print(f"fullname: '{fullname}'")
        print(f"phone: '{phone}'")
        print(f"email: '{email}'")
        print(f"service: '{service}'")
        print(f"date: '{date}'")
        print(f"time: '{time_val}'")
        print(f"note: '{note}'")

        # Validate
        if not fullname or not phone or not service or not date or not time_val:
            missing = []
            if not fullname: missing.append('Họ tên')
            if not phone: missing.append('SĐT')
            if not service: missing.append('Dịch vụ')
            if not date: missing.append('Ngày')
            if not time_val: missing.append('Giờ')
            msg = f"Thiếu thông tin: {', '.join(missing)}"
            print(f"Validation failed: {msg}")
            return jsonify({'success': False, 'message': msg}), 400

        data['source'] = 'Website'

        # Lưu vào Google Sheets
        booking_id, date_formatted = sheets.add_booking(data)
        print(f"Saved to sheet: {booking_id}")

        # Gửi thông báo Telegram
        try:
            tg_result = telegram_bot.notify_new_booking(booking_id, data, date_formatted)
            print(f"Telegram notify result: {tg_result}")
        except Exception as e:
            print(f"Telegram notify error: {e}")

        print(f"=== BOOKING SUCCESS: {booking_id} ===")
        return jsonify({
            'success': True,
            'message': 'Đặt lịch thành công!',
            'booking_id': booking_id
        })

    except Exception as e:
        print(f"=== BOOKING ERROR ===")
        print(f"Error: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'message': 'Lỗi hệ thống, vui lòng thử lại!'}), 500


# ===== TELEGRAM WEBHOOK =====
@app.route('/telegram', methods=['POST'])
def handle_telegram():
    try:
        update = request.get_json(force=True, silent=True)
        if not update:
            return jsonify({'ok': True})

        print(f"Telegram update: {json.dumps(update, ensure_ascii=False)[:500]}")

        if 'callback_query' in update:
            threading.Thread(target=telegram_bot.handle_callback, args=(update['callback_query'],)).start()
        elif 'message' in update and 'text' in update.get('message', {}):
            threading.Thread(target=telegram_bot.handle_command, args=(update['message'],)).start()

        return jsonify({'ok': True})

    except Exception as e:
        print(f"Telegram webhook error: {e}")
        print(traceback.format_exc())
        return jsonify({'ok': True})


# ===== ZALO WEBHOOK =====
@app.route('/zalo', methods=['POST'])
def handle_zalo():
    try:
        # Log header để debug
        secret = request.headers.get('X-Bot-Api-Secret-Token', '')
        print(f"Zalo secret received: '{secret}'")
        print(f"Zalo secret expected: '{config.ZALO_SECRET_TOKEN}'")

        # Tạm tắt xác thực để debug
        # if secret != config.ZALO_SECRET_TOKEN:
        #     print(f"Zalo: Invalid secret token")
        #     return jsonify({'ok': False}), 401

        data = request.get_json(force=True, silent=True)
        print(f"Zalo update: {data}")

        if data:
            threading.Thread(target=zalo_bot.handle_zalo_update, args=(data,)).start()

        return jsonify({'ok': True})

    except Exception as e:
        print(f"Zalo webhook error: {e}")
        print(traceback.format_exc())
        return jsonify({'ok': True})


# ===== CÀI ĐẶT WEBHOOK =====
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


# ===== DEBUG INFO =====
@app.route('/debug', methods=['GET'])
def debug_info():
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


# ===== TEST BOOKING (GET - dùng trình duyệt) =====
@app.route('/test-booking', methods=['GET'])
def test_booking():
    """Test thử tạo booking bằng trình duyệt"""
    try:
        test_data = {
            'fullname': 'Test User',
            'phone': '0901234567',
            'email': 'test@test.com',
            'service': 'Combo VIP - 350K',
            'date': '2026-02-20',
            'time': '14:00',
            'note': 'Test từ trình duyệt',
            'source': 'Test'
        }

        booking_id, date_formatted = sheets.add_booking(test_data)
        tg_result = telegram_bot.notify_new_booking(booking_id, test_data, date_formatted)

        return jsonify({
            'success': True,
            'booking_id': booking_id,
            'date_formatted': date_formatted,
            'telegram_result': tg_result,
            'message': 'Test booking created! Check Google Sheet and Telegram.'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config.PORT, debug=False)
