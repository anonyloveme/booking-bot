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

last_reset_date = datetime.now().strftime('%Y-%m-%d')


def keep_alive_and_reset():
    global last_reset_date
    while True:
        time.sleep(300)
        try:
            url = config.RENDER_URL or 'https://booking-bot-df6q.onrender.com'
            http_requests.get(url, timeout=10)

            now = datetime.now()
            today = now.strftime('%Y-%m-%d')
            if today != last_reset_date and now.hour == 0 and now.minute < 10:
                print("=== DAILY RESET ===")
                try:
                    summary = sheets.get_daily_summary()
                    if summary:
                        msg = (
                            f"📊 <b>BÁO CÁO CUỐI NGÀY</b>\n"
                            f"📅 {summary['date']}\n━━━━━━━━━━━━━━━\n\n"
                            f"📋 Tổng: <b>{summary['total']}</b>\n"
                            f"✅ Hoàn thành: <b>{summary['completed']}</b>\n"
                            f"✔️ Xác nhận: <b>{summary['confirmed']}</b>\n"
                            f"❌ Từ chối: <b>{summary['rejected']}</b>\n"
                            f"⏳ Chưa xử lý: <b>{summary['pending']}</b>\n"
                        )
                        for c in summary['customers']:
                            msg += f"\n• {c['id']} | {c['name']} | {c['service']} | {c['status']}"
                        msg += "\n\n🗑 <i>Dữ liệu đã xóa, bắt đầu ngày mới.</i>"
                        telegram_bot.send_message(config.TELEGRAM_CHAT_ID, msg)
                except Exception as e:
                    print(f"Summary error: {e}")

                sheets.clear_old_data()
                last_reset_date = today
                print("=== RESET DONE ===")
        except Exception as e:
            print(f"BG error: {e}")


threading.Thread(target=keep_alive_and_reset, daemon=True).start()


@app.route('/', methods=['GET'])
def home():
    return jsonify({'status': 'running', 'service': 'BarberShop Booking Bot'})


@app.route('/booking', methods=['POST', 'OPTIONS'])
def handle_booking():
    if request.method == 'OPTIONS':
        r = jsonify({'ok': True})
        r.headers['Access-Control-Allow-Origin'] = '*'
        r.headers['Access-Control-Allow-Headers'] = 'Content-Type,Accept'
        r.headers['Access-Control-Allow-Methods'] = 'POST,OPTIONS'
        return r
    try:
        print("=== NEW BOOKING ===")
        raw = request.get_data(as_text=True)
        print(f"Raw: {raw}")

        data = None
        try:
            data = request.get_json(force=True, silent=True)
        except:
            pass
        if not data or not isinstance(data, dict):
            try:
                data = request.form.to_dict()
            except:
                pass
        if not data or not isinstance(data, dict) or len(data) == 0:
            try:
                data = json.loads(raw)
            except:
                pass
        if not data or not isinstance(data, dict):
            return jsonify({'success': False, 'message': 'Không nhận được dữ liệu!'}), 400

        fullname = data.get('fullname', '')
        phone = data.get('phone', '')
        service = data.get('service', '')
        date_val = data.get('date', '')
        time_val = data.get('time', '')

        if not fullname or not phone or not service or not date_val or not time_val:
            missing = []
            if not fullname: missing.append('Họ tên')
            if not phone: missing.append('SĐT')
            if not service: missing.append('Dịch vụ')
            if not date_val: missing.append('Ngày')
            if not time_val: missing.append('Giờ')
            return jsonify({'success': False, 'message': f"Thiếu: {', '.join(missing)}"}), 400

        data['source'] = 'Website'

        # Lưu Sheet
        booking_id = None
        date_formatted = None
        try:
            booking_id, date_formatted = sheets.add_booking(data)
            print(f"Saved: {booking_id}")
        except Exception as e:
            print(f"Sheet error: {e}")
            print(traceback.format_exc())

        # Gửi Telegram (luôn gửi dù Sheet lỗi)
        try:
            if booking_id:
                tg_result = telegram_bot.notify_new_booking(booking_id, data, date_formatted)
            else:
                # Sheet lỗi nhưng vẫn thông báo Telegram
                booking_id = 'ERR'
                date_parts = date_val.split('-')
                if len(date_parts) == 3:
                    date_formatted = f"{date_parts[2]}/{date_parts[1]}/{date_parts[0]}"
                else:
                    date_formatted = date_val
                tg_result = telegram_bot.notify_new_booking(booking_id, data, date_formatted)
            print(f"Telegram: OK")
        except Exception as e:
            print(f"Telegram error: {e}")
            print(traceback.format_exc())

        if booking_id and booking_id != 'ERR':
            return jsonify({'success': True, 'message': 'Đặt lịch thành công!', 'booking_id': booking_id})
        else:
            return jsonify({'success': False, 'message': 'Lỗi lưu dữ liệu, nhưng đã thông báo cho shop!'}), 500

    except Exception as e:
        print(f"Booking error: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'message': 'Lỗi hệ thống!'}), 500


@app.route('/telegram', methods=['POST'])
def handle_telegram():
    try:
        update = request.get_json(force=True, silent=True)
        if not update:
            return jsonify({'ok': True})

        if 'callback_query' in update:
            threading.Thread(target=telegram_bot.handle_callback, args=(update['callback_query'],)).start()
        elif 'message' in update and 'text' in update.get('message', {}):
            threading.Thread(target=telegram_bot.handle_command, args=(update['message'],)).start()

        return jsonify({'ok': True})
    except Exception as e:
        print(f"Telegram error: {e}")
        return jsonify({'ok': True})


@app.route('/zalo', methods=['POST'])
def handle_zalo():
    try:
        data = request.get_json(force=True, silent=True)
        if data:
            threading.Thread(target=zalo_bot.handle_zalo_update, args=(data,)).start()
        return jsonify({'ok': True})
    except Exception as e:
        print(f"Zalo error: {e}")
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


@app.route('/debug', methods=['GET'])
def debug_info():
    try:
        tg_info = http_requests.get(
            f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/getWebhookInfo", timeout=10
        ).json()
    except:
        tg_info = {'error': 'failed'}
    return jsonify({
        'server': 'running',
        'last_reset_date': last_reset_date,
        'telegram_webhook': tg_info
    })


@app.route('/test-booking', methods=['GET'])
def test_booking():
    try:
        test_data = {
            'fullname': 'Test User', 'phone': '0901234567', 'email': 'test@test.com',
            'service': 'Combo VIP - 350K', 'date': '2026-02-20', 'time': '14:00',
            'note': 'Test từ trình duyệt', 'source': 'Test'
        }
        booking_id, date_formatted = sheets.add_booking(test_data)
        tg_result = telegram_bot.notify_new_booking(booking_id, test_data, date_formatted)
        return jsonify({'success': True, 'booking_id': booking_id, 'telegram': tg_result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'trace': traceback.format_exc()})


@app.route('/reset', methods=['GET'])
def manual_reset():
    try:
        summary = sheets.get_daily_summary()
        if summary:
            msg = (
                f"📊 <b>BÁO CÁO</b>\n📅 {summary['date']}\n━━━━━━━━━━━━━━━\n\n"
                f"📋 Tổng: <b>{summary['total']}</b>\n"
                f"✅ Hoàn thành: <b>{summary['completed']}</b>\n"
                f"✔️ Xác nhận: <b>{summary['confirmed']}</b>\n"
                f"❌ Từ chối: <b>{summary['rejected']}</b>\n"
                f"⏳ Chờ: <b>{summary['pending']}</b>"
            )
            telegram_bot.send_message(config.TELEGRAM_CHAT_ID, msg)
        result = sheets.clear_old_data()
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config.PORT, debug=False)
