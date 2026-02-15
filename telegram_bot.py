import requests
import json
from datetime import datetime, timedelta
import config
import sheets

API = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}"

def send_message(chat_id, text, reply_markup=None, parse_mode='HTML'):
    """Gửi tin nhắn Telegram"""
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode
    }
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    resp = requests.post(f"{API}/sendMessage", json=payload, timeout=10)
    return resp.json()

def edit_message(chat_id, message_id, text, reply_markup=None):
    """Chỉnh sửa tin nhắn"""
    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    resp = requests.post(f"{API}/editMessageText", json=payload, timeout=10)
    return resp.json()

def answer_callback(callback_id, text=''):
    """Trả lời callback query"""
    requests.post(f"{API}/answerCallbackQuery", json={
        'callback_query_id': callback_id,
        'text': text
    }, timeout=10)

def notify_new_booking(booking_id, data, date_formatted):
    """Gửi thông báo booking mới cho admin"""
    msg = (
        f"✂️ <b>LỊCH HẸN MỚI</b> ✂️\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"🆔 <b>Mã:</b> {booking_id}\n"
        f"👤 <b>Khách hàng:</b> {data.get('fullname', '')}\n"
        f"📞 <b>SĐT:</b> {data.get('phone', '')}\n"
    )
    if data.get('email'):
        msg += f"📧 <b>Email:</b> {data['email']}\n"
    msg += (
        f"💈 <b>Dịch vụ:</b> {data.get('service', '')}\n"
        f"📅 <b>Ngày:</b> {date_formatted}\n"
        f"🕐 <b>Giờ:</b> {data.get('time', '')}\n"
    )
    if data.get('note'):
        msg += f"📝 <b>Ghi chú:</b> {data['note']}\n"
    msg += (
        f"\n━━━━━━━━━━━━━━━\n"
        f"⏰ <i>Nhận lúc: {datetime.now().strftime('%H:%M %d/%m/%Y')}</i>\n"
        f"📱 <i>Nguồn: {data.get('source', 'Website')}</i>"
    )
    
    keyboard = {
        'inline_keyboard': [
            [
                {'text': '✅ Xác nhận', 'callback_data': f'confirm_{booking_id}'},
                {'text': '❌ Từ chối', 'callback_data': f'reject_{booking_id}'}
            ],
            [
                {'text': f"📞 Gọi {data.get('phone', '')}", 'url': f"tel:{data.get('phone', '')}"}
            ]
        ]
    }
    
    return send_message(config.TELEGRAM_CHAT_ID, msg, keyboard)

def handle_callback(callback):
    """Xử lý nút bấm"""
    data = callback.get('data', '')
    chat_id = callback['message']['chat']['id']
    message_id = callback['message']['message_id']
    original_text = callback['message'].get('text', '')
    
    if data.startswith('confirm_'):
        booking_id = data.replace('confirm_', '')
        row = sheets.update_status(booking_id, '✅ Đã xác nhận')
        answer_callback(callback['id'], '✅ Đã xác nhận!')
        
        new_text = original_text + f"\n\n✅ <b>ĐÃ XÁC NHẬN</b> - {datetime.now().strftime('%H:%M %d/%m/%Y')}"
        keyboard = {
            'inline_keyboard': [
                [{'text': '✂️ Hoàn thành', 'callback_data': f'complete_{booking_id}'}],
                [{'text': f"📞 Gọi khách", 'url': f"tel:{row[2] if row else ''}"}]
            ]
        }
        edit_message(chat_id, message_id, new_text, keyboard)
    
    elif data.startswith('reject_'):
        booking_id = data.replace('reject_', '')
        sheets.update_status(booking_id, '❌ Đã từ chối')
        answer_callback(callback['id'], '❌ Đã từ chối!')
        
        new_text = original_text + f"\n\n❌ <b>ĐÃ TỪ CHỐI</b> - {datetime.now().strftime('%H:%M %d/%m/%Y')}"
        edit_message(chat_id, message_id, new_text)
    
    elif data.startswith('complete_'):
        booking_id = data.replace('complete_', '')
        sheets.update_status(booking_id, '✅ Đã hoàn thành')
        answer_callback(callback['id'], '✅ Đã hoàn thành!')
        
        new_text = original_text + f"\n\n✅ <b>ĐÃ HOÀN THÀNH</b> - {datetime.now().strftime('%H:%M %d/%m/%Y')}"
        edit_message(chat_id, message_id, new_text)

def handle_command(message):
    """Xử lý lệnh từ admin"""
    chat_id = message['chat']['id']
    text = message.get('text', '').strip()
    
    if text == '/start' or text == '/help':
        msg = (
            "🏠 <b>BarberShop Manager Bot</b>\n\n"
            "📋 <b>Danh sách lệnh:</b>\n\n"
            "/today — Lịch hẹn hôm nay\n"
            "/tomorrow — Lịch hẹn ngày mai\n"
            "/all — Tất cả đơn chờ xác nhận\n"
            "/done — Đơn đã hoàn thành\n"
            "/find [từ khóa] — Tìm theo SĐT hoặc tên\n"
            "/stats — Thống kê tổng quan\n"
            "/help — Hướng dẫn sử dụng"
        )
        send_message(chat_id, msg)
    
    elif text == '/today':
        today = datetime.now().strftime('%d/%m/%Y')
        bookings = sheets.get_bookings_by_date(today)
        if not bookings:
            send_message(chat_id, f"📅 <b>Hôm nay ({today})</b>\n\nKhông có lịch hẹn nào.")
            return
        msg = f"📅 <b>Lịch hẹn hôm nay ({today})</b>\n━━━━━━━━━━━━━━━\n\n"
        for b in bookings:
            status = b[8] if len(b) > 8 else '?'
            msg += f"🕐 <b>{b[6]}</b> — {b[1]} ({b[2]})\n💈 {b[4]} | {status}\n\n"
        msg += f"📊 Tổng: <b>{len(bookings)}</b> lịch hẹn"
        send_message(chat_id, msg)
    
    elif text == '/tomorrow':
        tmr = (datetime.now() + timedelta(days=1)).strftime('%d/%m/%Y')
        bookings = sheets.get_bookings_by_date(tmr)
        if not bookings:
            send_message(chat_id, f"📅 <b>Ngày mai ({tmr})</b>\n\nKhông có lịch hẹn nào.")
            return
        msg = f"📅 <b>Lịch hẹn ngày mai ({tmr})</b>\n━━━━━━━━━━━━━━━\n\n"
        for b in bookings:
            status = b[8] if len(b) > 8 else '?'
            msg += f"🕐 <b>{b[6]}</b> — {b[1]} ({b[2]})\n💈 {b[4]} | {status}\n\n"
        msg += f"📊 Tổng: <b>{len(bookings)}</b> lịch hẹn"
        send_message(chat_id, msg)
    
    elif text == '/all':
        bookings = sheets.get_bookings_by_status('Chờ')
        if not bookings:
            send_message(chat_id, "✅ Không có đơn nào đang chờ xác nhận!")
            return
        msg = "⏳ <b>Đơn chờ xác nhận</b>\n━━━━━━━━━━━━━━━\n\n"
        for b in bookings:
            msg += f"🆔 {b[0]} | {b[1]} ({b[2]})\n📅 {b[5]} 🕐 {b[6]} | 💈 {b[4]}\n\n"
        msg += f"📊 Tổng: <b>{len(bookings)}</b> đơn"
        send_message(chat_id, msg)
    
    elif text == '/done':
        bookings = sheets.get_bookings_by_status('hoàn thành')
        if not bookings:
            send_message(chat_id, "Chưa có đơn hoàn thành nào.")
            return
        msg = "✅ <b>Đơn đã hoàn thành</b>\n━━━━━━━━━━━━━━━\n\n"
        for b in bookings:
            msg += f"🆔 {b[0]} | {b[1]} ({b[2]})\n📅 {b[5]} 🕐 {b[6]} | 💈 {b[4]}\n\n"
        msg += f"📊 Tổng: <b>{len(bookings)}</b> đơn"
        send_message(chat_id, msg)
    
    elif text.startswith('/find'):
        keyword = text.replace('/find', '').strip()
        if not keyword:
            send_message(chat_id, "⚠️ Nhập từ khóa: /find 0901234567")
            return
        results = sheets.find_booking(keyword)
        if not results:
            send_message(chat_id, f"🔍 Không tìm thấy kết quả cho: <b>{keyword}</b>")
            return
        msg = f"🔍 <b>Kết quả tìm kiếm: {keyword}</b>\n━━━━━━━━━━━━━━━\n\n"
        for b in results:
            status = b[8] if len(b) > 8 else '?'
            msg += f"🆔 {b[0]} | {b[1]} ({b[2]})\n📅 {b[5]} 🕐 {b[6]} | 💈 {b[4]}\n{status}\n\n"
        send_message(chat_id, msg)
    
    elif text == '/stats':
        s = sheets.get_stats()
        msg = (
            "📊 <b>THỐNG KÊ TỔNG QUAN</b>\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"📋 Tổng đơn: <b>{s['total']}</b>\n"
            f"📅 Hôm nay: <b>{s['today']}</b>\n\n"
            f"⏳ Chờ xác nhận: <b>{s['pending']}</b>\n"
            f"✅ Đã xác nhận: <b>{s['confirmed']}</b>\n"
            f"✂️ Đã hoàn thành: <b>{s['completed']}</b>\n"
            f"❌ Đã từ chối: <b>{s['rejected']}</b>"
        )
        send_message(chat_id, msg)

def set_webhook(url):
    """Đặt webhook"""
    resp = requests.post(f"{API}/setWebhook", json={
        'url': f"{url}/telegram",
        'drop_pending_updates': True
    }, timeout=10)
    return resp.json()

def delete_webhook():
    """Xóa webhook"""
    resp = requests.post(f"{API}/deleteWebhook", json={
        'drop_pending_updates': True
    }, timeout=10)
    return resp.json()
