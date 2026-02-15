from flask import Flask, request, jsonify
import config
import sheets
import telegram_bot
import zalo_bot
import threading

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'running',
        'service': 'BarberShop Booking Bot',
        'endpoints': ['/booking', '/telegram', '/zalo']
    })

@app.route('/booking', methods=['POST'])
def handle_booking():
    """Nhận booking từ website"""
    try:
        # Hỗ trợ cả JSON và form data
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        data['source'] = 'Website'
        
        # Lưu vào Google Sheets
        booking_id, date_formatted = sheets.add_booking(data)
        
        # Gửi thông báo Telegram cho admin
        telegram_bot.notify_new_booking(booking_id, data, date_formatted)
        
        return jsonify({'success': True, 'message': 'Đặt lịch thành công!', 'booking_id': booking_id})
    
    except Exception as e:
        print(f"Booking error: {e}")
        return jsonify({'success': False, 'message': 'Lỗi hệ thống, vui lòng thử lại!'}), 500

@app.route('/telegram', methods=['POST'])
def handle_telegram():
    """Webhook nhận update từ Telegram"""
    try:
        update = request.get_json()
        
        if 'callback_query' in update:
            telegram_bot.handle_callback(update['callback_query'])
        elif 'message' in update and 'text' in update['message']:
            telegram_bot.handle_command(update['message'])
        
        return jsonify({'ok': True})
    
    except Exception as e:
        print(f"Telegram webhook error: {e}")
        return jsonify({'ok': True})  # Luôn trả 200 để Telegram không retry

@app.route('/zalo', methods=['POST'])
def handle_zalo():
    """Webhook nhận update từ Zalo Bot"""
    try:
        data = request.get_json()
        
        # Xử lý trong thread riêng để trả response nhanh
        threading.Thread(target=zalo_bot.handle_zalo_update, args=(data,)).start()
        
        return jsonify({'ok': True})
    
    except Exception as e:
        print(f"Zalo webhook error: {e}")
        return jsonify({'ok': True})

@app.route('/setup', methods=['GET'])
def setup_webhooks():
    """Cài đặt webhook cho Telegram và Zalo"""
    base_url = config.RENDER_URL or request.host_url.rstrip('/')
    
    tg_result = telegram_bot.set_webhook(base_url)
    zalo_result = zalo_bot.set_webhook(base_url)
    
    return jsonify({
        'telegram_webhook': tg_result,
        'zalo_webhook': zalo_result,
        'base_url': base_url
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config.PORT, debug=False)
