from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timezone, timedelta
import threading, time, os, json, traceback
import requests as http_requests
import config, sheets, telegram_bot

app = Flask(__name__)
CORS(app)

VN_TZ = timezone(timedelta(hours=7))

def vn_now():
    return datetime.now(VN_TZ)

# ===== KEEP-ALIVE & DAILY RESET =====
def keep_alive_and_reset():
    last_reset = ''
    while True:
        time.sleep(300)  # 5 phút
        try:
            url = config.RENDER_URL or 'https://booking-bot-df6q.onrender.com'
            http_requests.get(url, timeout=10)
            print(f"Keep-alive OK at {vn_now().strftime('%H:%M %d/%m/%Y')} VN")
        except Exception as e:
            print(f"Keep-alive error: {e}")

        now = vn_now()
        today_str = now.strftime('%Y-%m-%d')
        hour = now.hour
        minute = now.minute

        # Reset lúc 00:00-00:10 giờ VN
        if hour == 0 and minute < 10 and last_reset != today_str:
            last_reset = today_str
            print(f"=== DAILY RESET at {now.strftime('%H:%M %d/%m/%Y')} VN ===")
            try:
                send_daily_summary()
            except Exception as e:
                print(f"Summary error: {e}")
            try:
                result = sheets.clear_old_data()
                print(f"Clear result: {result}")
            except Exception as e:
                print(f"Clear error: {e}")

threading.Thread(target=keep_alive_and_reset, daemon=True).start()

def send_daily_summary():
    summary = sheets.get_daily_summary()
    if not summary:
        telegram_bot.send_message(
            config.TELEGRAM_CHAT_ID,
            f"📋 <b>BÁO CÁO CUỐI NGÀY</b>\n📅 {sheets.get_today_str()}\n\nKhông có đơn hôm nay."
        )
        return
    msg = (
        f"📋 <b>BÁO CÁO CUỐI NGÀY</b>\n"
        f"📅 {summary['date']}\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"📊 Tổng: <b>{summary['total']}</b>\n"
        f"✅ Hoàn thành: <b>{summary['completed']}</b>\n"
        f"✔️ Xác nhận: <b>{summary['confirmed']}</b>\n"
        f"⏳ Chờ: <b>{summary['pending']}</b>\n"
        f"❌ Từ chối: <b>{summary['rejected']}</b>\n\n"
    )
    for c in summary['customers']:
        msg += f"🆔 {c['id']} | {c['name']} | 🕐 {c['time']} | {c['status']}\n"
    msg += f"\n━━━━━━━━━━━━━━━\n⏰ {vn_now().strftime('%H:%M %d/%m/%Y')} (VN)"
    telegram_bot.send_message(config.TELEGRAM_CHAT_ID, msg)

# ===== ROUTES =====
@app.route('/')
def home():
    return jsonify({
        'service': 'BarberShop Booking Bot',
        'status': 'running',
        'endpoints': ['/booking', '/telegram', '/zalo', '/setup', '/debug'],
        'server_time_vn': vn_now().strftime('%H:%M:%S %d/%m/%Y'),
        'timezone': 'UTC+7 (Vietnam/Hanoi)'
    })

@app.route('/booking', methods=['POST', 'OPTIONS'])
def handle_booking():
    if request.method == 'OPTIONS':
        return jsonify({'ok': True})
    try:
        print(f"=== BOOKING REQUEST at {vn_now().strftime('%H:%M:%S %d/%m/%Y')} VN ===")
        print(f"Content-Type: {request.content_type}")
        raw = request.get_data(as_text=True)
        print(f"Raw data: {raw}")

        data = None
        try:
            data = request.get_json(force=True)
        except:
            pass
        if not data:
            data = request.form.to_dict()
        if not data:
            try:
                data = json.loads(raw)
            except:
                pass
        if not data:
            return jsonify({'success': False, 'message': 'Dữ liệu trống!'}), 400

        print(f"Parsed data: {data}")

        booking_id = 'ERR'
        date_formatted = ''
        try:
            booking_id, date_formatted = sheets.add_booking(data)
            print(f"Sheet OK: {booking_id}")
        except Exception as e:
            print(f"Sheet ERROR: {e}")
            traceback.print_exc()

        try:
            data['source'] = data.get('source', 'Website')
            tg_result = telegram_bot.notify_new_booking(booking_id, data, date_formatted)
            print(f"Telegram notify: {tg_result}")
        except Exception as e:
            print(f"Telegram ERROR: {e}")
            traceback.print_exc()

        if booking_id == 'ERR':
            return jsonify({'success': False, 'message': 'Lỗi lưu dữ liệu!'}), 500

        return jsonify({
            'success': True,
            'message': 'Đặt lịch thành công!',
            'booking_id': booking_id
        })
    except Exception as e:
        print(f"Booking error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Lỗi hệ thống!'}), 500

@app.route('/telegram', methods=['POST'])
def handle_telegram():
    try:
        update = request.get_json()
        print(f"Telegram update at {vn_now().strftime('%H:%M:%S')} VN: {json.dumps(update, ensure_ascii=False)[:500]}")
        if 'callback_query' in update:
            telegram_bot.handle_callback(update['callback_query'])
        elif 'message' in update and 'text' in update['message']:
            telegram_bot.handle_command(update['message'])
    except Exception as e:
        print(f"Telegram error: {e}")
        traceback.print_exc()
    return jsonify({'ok': True})

@app.route('/zalo', methods=['POST'])
def handle_zalo():
    try:
        import zalo_bot
        data = request.get_json()
        print(f"Zalo update at {vn_now().strftime('%H:%M:%S')} VN: {json.dumps(data, ensure_ascii=False)[:500]}")
        secret = request.headers.get('X-ZaloOA-Secret', '')
        if secret != config.ZALO_SECRET_TOKEN:
            print(f"Zalo: Invalid secret token")
            return jsonify({'error': 'invalid token'}), 403
        threading.Thread(target=zalo_bot.handle_zalo_update, args=(data,)).start()
    except Exception as e:
        print(f"Zalo error: {e}")
    return jsonify({'ok': True})

@app.route('/setup')
def setup():
    base = config.RENDER_URL or request.host_url.rstrip('/')
    results = {'base_url': base, 'server_time_vn': vn_now().strftime('%H:%M:%S %d/%m/%Y')}
    try:
        results['telegram_webhook'] = telegram_bot.set_webhook(base)
    except Exception as e:
        results['telegram_webhook'] = {'error': str(e)}
    try:
        import zalo_bot
        results['zalo_webhook'] = zalo_bot.set_webhook(base)
    except Exception as e:
        results['zalo_webhook'] = {'error': str(e)}
    return jsonify(results)

@app.route('/debug')
def debug():
    now = vn_now()
    info = {
        'server': 'running',
        'server_time_utc': datetime.now(timezone.utc).strftime('%H:%M:%S %d/%m/%Y'),
        'server_time_vn': now.strftime('%H:%M:%S %d/%m/%Y'),
        'timezone': 'UTC+7 (Vietnam/Hanoi)',
        'last_reset_date': now.strftime('%Y-%m-%d')
    }
    try:
        import requests
        tg = requests.get(f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/getWebhookInfo", timeout=10).json()
        info['telegram_webhook'] = tg
    except:
        pass
    return jsonify(info)

@app.route('/test-booking')
def test_booking():
    test_data = {
        'fullname': 'Test User',
        'phone': '0901234567',
        'email': 'test@test.com',
        'service': 'Combo VIP - 350K',
        'date': '2026-02-20',
        'time': '14:00',
        'note': f'Test lúc {vn_now().strftime("%H:%M %d/%m/%Y")} VN',
        'source': 'Test'
    }
    try:
        booking_id, date_formatted = sheets.add_booking(test_data)
        tg = telegram_bot.notify_new_booking(booking_id, test_data, date_formatted)
        return jsonify({
            'success': True,
            'booking_id': booking_id,
            'date_formatted': date_formatted,
            'server_time_vn': vn_now().strftime('%H:%M:%S %d/%m/%Y'),
            'telegram': tg
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/reset')
def reset():
    try:
        send_daily_summary()
        result = sheets.clear_old_data()
        return jsonify({
            'success': True,
            'cleared': result,
            'time_vn': vn_now().strftime('%H:%M:%S %d/%m/%Y')
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config.PORT, debug=True)
