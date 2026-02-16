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
from datetime import datetime
import requests as http_requests

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


# ===== KEEP ALIVE + AUTO RESET =====
last_reset_date = datetime.now().strftime('%Y-%m-%d')

def keep_alive_and_reset():
    global last_reset_date
    while True:
        time.sleep(300)  # Kiểm tra mỗi 5 phút

        try:
            # Keep alive ping
            url = config.RENDER_URL or 'https://booking-bot-df6q.onrender.com'
            http_requests.get(url, timeout=10)

            # Kiểm tra reset hàng ngày (lúc 00:00 - 00:10)
            now = datetime.now()
            today = now.strftime('%Y-%m-%d')
            hour = now.hour
            minute = now.minute

            if today != last_reset_date and hour == 0 and minute < 10:
                print(f"=== DAILY RESET: {today} ===")

                # Gửi tổng kết ngày cũ cho admin
                try:
                    summary = sheets.get_daily_summary()
                    if summary:
                        send_daily_summary(summary)
                except Exception as e:
                    print(f"Summary error: {e}")

                # Xóa dữ liệu cũ
                try:
                    result = sheets.clear_old_data()
                    print(f"Clear result: {result}")
                except Exception as e:
                    print(f"Clear error: {e}")

                last_reset_date = today
                print(f"=== RESET DONE ===")

        except Exception as e:
            print(f"Keep-alive/reset error: {e}")

def send_daily_summary(summary):
    """Gửi báo cáo tổng kết ngày qua Telegram"""
    msg = (
        f"📊 <b>BÁO CÁO CUỐI NGÀY</b>\n"
        f"📅 <b>Ngày:</b> {summary['date']}\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📋 Tổng đơn: <b>{summary['total']}</b>\n"
        f"✅ Hoàn thành: <b>{summary['completed']}</b>\n"
        f"✔️ Đã xác nhận: <b>{summary['confirmed']}</b>\n"
        f"❌ Từ chối: <b>{summary['rejected']}</b>\n"
        f"⏳ Chưa xử lý: <b>{summary['pending']}</b>\n"
    )

    if summary['customers']:
        msg += "\n📋 <b>Chi tiết:</b>\n"
        for c in summary['customers']:
            msg += f"• {c['id']} | {c['name']} | {c['service']} | {c['time']} | {c['status']}\n"

    msg += f"\n━━━━━━━━━━━━━━━\n🗑 <i>Dữ liệu sẽ được xóa để bắt đầu ngày mới.</i>"

    telegram_bot.send_message(config.TELEGRAM_CHAT_ID, msg)

# Chạy background thread
bg_thread = threading.Thread(target=keep_alive_and_reset, daemon=True)
bg_thread.start()


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
    if request.method == 'OPTIONS':
        response = jsonify({'ok': True})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Accept')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        return response

    try:
        print(f"=== NEW BOOKING REQUEST ===")
        print(f"Content-Type: {request.content_type}")

        raw_body = request.get_data(as_text=True)
        print(f"Raw body: {raw_body}")

        # Parse dữ liệu
        data = None

        try:
            data = request.get_json(force=True, silent=True)
            if data:
                print(f"Parsed JSON: {data}")
        except:
            pass

        if not data or not isinstance(data, dict):
            try:
                data = request.form.to_dict()
                if data:
                    print(f"Parsed form: {data}")
            except:
                pass

        if not data or not isinstance(data, dict) or len(data) == 0:
            try:
                data = json.loads(raw_body)
                print(f"Parsed raw: {data}")
            except:
                pass

        if not data or not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'Không nhận được dữ liệu!'}), 400

        fullname = data.get('fullname', '')
        phone = data.get('phone', '')
        service = data.get('service', '')
        date_val = data.get('date', '')
        time_val = data.get('time', '')

        print(f"fullname='{fullname}' phone='{phone}' service='{service}' date='{date_val}' time='{time_val}'")

        if not fullname or not phone or not service or not date_val or not time_val:
            missing = []
            if not fullname: missing.append('Họ tên')
            if not phone: missing.append('SĐT')
            if not service: missing.append('Dịch vụ')
            if not date_val: missing.append('Ngày')
            if not time_val: missing.append('Giờ')
            return jsonify({'success': False, 'message': f"Thiếu: {', '.join(missing)}"}), 400

        data['source'] = 'Website'

        booking_id, date_formatted = sheets.add_booking(data)
        print(f"Saved: {booking_id}")

        try:
            telegram_bot.notify_new_booking(booking_id, data, date_formatted)
            print("Telegram notified")
        except Exception as e:
            print(f"Telegram error: {e}")

        return jsonify({
            'success': True,
            'message': 'Đặt lịch thành công!',
            'booking_id': booking_id
        })

    except Exception as e:
        print(f"Booking error: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'message': 'Lỗi hệ thống!'}), 500


# ===== TELEGRAM WEBHOOK =====
@app.route('/telegram', methods=['POST'])
def handle_telegram():
    try:
        update = request.get_json(force=True, silent=True)
        if not update:
            return jsonify({'ok': True})

        print(f"Telegram: {json.dumps(update, ensure_ascii=False)[:500]}")

        if 'callback_query' in update:
            threading.Thread(target=telegram_bot.handle_callback, args=(update['callback_query'],)).start()
        elif 'message' in update and 'text' in update.get('message', {}):
            threading.Thread(target=telegram_bot.handle_command, args=(update['message'],)).start()

        return jsonify({'ok': True})

    except Exception as e:
        print(f"Telegram error: {e}")
        return jsonify({'ok': True})


# ===== ZALO WEBHOOK =====
@app.route('/zalo', methods=['POST'])
def handle_zalo():
    try:
        secret = request.headers.get('X-Bot-Api-Secret-Token', '')
        print(f"Zalo secret: '{secret}'")

        data = request.get_json(force=True, silent=True)
        print(f"Zalo update: {data}")

        if data:
            threading.Thread(target=zalo_bot.handle_zalo_update, args=(data,)).start()

        return jsonify({'ok': True})

    except Exception as e:
        print(f"Zalo error: {e}")
        return jsonify({'ok': True})


# ===== SETUP WEBHOOKS =====
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


# ===== DEBUG =====
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
        'last_reset_date': last_reset_date,
        'telegram_webhook': tg_info,
        'zalo_webhook': zalo_info,
        'zalo_sessions': len(zalo_bot.user_sessions)
    })


# ===== TEST BOOKING =====
@app.route('/test-booking', methods=['GET'])
def test_booking():
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
            'telegram_result': tg_result
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'traceback': traceback.format_exc()})


# ===== XÓA DỮ LIỆU THỦ CÔNG =====
@app.route('/reset', methods=['GET'])
def manual_reset():
    """Admin có thể truy cập để xóa dữ liệu thủ công"""
    try:
        summary = sheets.get_daily_summary()
        if summary:
            send_daily_summary(summary)

        result = sheets.clear_old_data()
        return jsonify({
            'success': True,
            'result': result,
            'message': 'Đã gửi tổng kết và xóa dữ liệu!'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config.PORT, debug=False)
