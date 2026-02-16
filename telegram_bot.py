import requests
import json
from datetime import datetime, timedelta
import config
import sheets

API = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}"

# Bàn phím nút bấm cho admin
ADMIN_KEYBOARD = {
    'keyboard': [
        [{'text': '📅 Hôm nay'}, {'text': '📅 Ngày mai'}],
        [{'text': '⏳ Chờ xác nhận'}, {'text': '✅ Hoàn thành'}],
        [{'text': '📊 Thống kê'}, {'text': '❓ Hướng dẫn'}]
    ],
    'resize_keyboard': True,
    'is_persistent': True
}


def send_message(chat_id, text, reply_markup=None, parse_mode='HTML'):
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    else:
        payload['reply_markup'] = json.dumps(ADMIN_KEYBOARD)
    try:
        resp = requests.post(f"{API}/sendMessage", json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        print(f"TG send error: {e}")
        return {}


def send_message_inline(chat_id, text, reply_markup=None):
    """Gửi tin nhắn với inline keyboard (không ghi đè bàn phím chính)"""
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        resp = requests.post(f"{API}/sendMessage", json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        print(f"TG send error: {e}")
        return {}


def edit_message(chat_id, message_id, text, reply_markup=None):
    payload = {'chat_id': chat_id, 'message_id': message_id, 'text': text, 'parse_mode': 'HTML'}
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        resp = requests.post(f"{API}/editMessageText", json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        print(f"TG edit error: {e}")
        return {}


def answer_callback(callback_id, text=''):
    try:
        requests.post(f"{API}/answerCallbackQuery", json={
            'callback_query_id': callback_id, 'text': text
        }, timeout=10)
    except:
        pass


def set_bot_commands():
    """Cài đặt menu lệnh cho bot"""
    commands = [
        {'command': 'start', 'description': '🏠 Bắt đầu'},
        {'command': 'today', 'description': '📅 Lịch hôm nay'},
        {'command': 'tomorrow', 'description': '📅 Lịch ngày mai'},
        {'command': 'all', 'description': '⏳ Đơn chờ xác nhận'},
        {'command': 'done', 'description': '✅ Đơn hoàn thành'},
        {'command': 'stats', 'description': '📊 Thống kê'},
        {'command': 'help', 'description': '❓ Hướng dẫn'}
    ]
    try:
        requests.post(f"{API}/setMyCommands", json={'commands': commands}, timeout=10)
        print("Bot commands set OK")
    except Exception as e:
        print(f"Set commands error: {e}")


def notify_new_booking(booking_id, data, date_formatted):
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
    return send_message_inline(config.TELEGRAM_CHAT_ID, msg, keyboard)


def handle_callback(callback):
    data = callback.get('data', '')
    chat_id = callback['message']['chat']['id']
    message_id = callback['message']['message_id']
    original_text = callback['message'].get('text', '')

    if data.startswith('confirm_'):
        bid = data.replace('confirm_', '')
        row = sheets.update_status(bid, '✅ Đã xác nhận')
        answer_callback(callback['id'], '✅ Đã xác nhận!')
        new_text = original_text + f"\n\n✅ ĐÃ XÁC NHẬN - {datetime.now().strftime('%H:%M %d/%m/%Y')}"
        keyboard = {
            'inline_keyboard': [
                [{'text': '✂️ Hoàn thành', 'callback_data': f'complete_{bid}'}],
                [{'text': '📞 Gọi khách', 'url': f"tel:{row[2] if row and len(row) > 2 else ''}"}]
            ]
        }
        edit_message(chat_id, message_id, new_text, keyboard)

    elif data.startswith('reject_'):
        bid = data.replace('reject_', '')
        sheets.update_status(bid, '❌ Đã từ chối')
        answer_callback(callback['id'], '❌ Đã từ chối!')
        new_text = original_text + f"\n\n❌ ĐÃ TỪ CHỐI - {datetime.now().strftime('%H:%M %d/%m/%Y')}"
        edit_message(chat_id, message_id, new_text)

    elif data.startswith('complete_'):
        bid = data.replace('complete_', '')
        sheets.update_status(bid, '✅ Đã hoàn thành')
        answer_callback(callback['id'], '✅ Đã hoàn thành!')
        new_text = original_text + f"\n\n✅ ĐÃ HOÀN THÀNH - {datetime.now().strftime('%H:%M %d/%m/%Y')}"
        edit_message(chat_id, message_id, new_text)


def handle_command(message):
    chat_id = message['chat']['id']
    text = message.get('text', '').strip()

    # Hỗ trợ cả lệnh / và nút bấm text
    if text in ['/start', '/help', '❓ Hướng dẫn']:
        set_bot_commands()
        send_message(chat_id,
            "🏠 <b>BarberShop Manager</b>\n\n"
            "Bấm nút bên dưới hoặc gõ lệnh:\n\n"
            "📅 <b>Hôm nay</b> — Lịch hẹn hôm nay\n"
            "📅 <b>Ngày mai</b> — Lịch hẹn ngày mai\n"
            "⏳ <b>Chờ xác nhận</b> — Đơn chờ\n"
            "✅ <b>Hoàn thành</b> — Đơn xong\n"
            "📊 <b>Thống kê</b> — Tổng quan\n\n"
            "🔍 Tìm kiếm: /find 0901234567"
        )

    elif text in ['/today', '📅 Hôm nay']:
        today = datetime.now().strftime('%d/%m/%Y')
        bookings = sheets.get_bookings_by_date(today)
        if not bookings:
            send_message(chat_id, f"📅 <b>Hôm nay ({today})</b>\n\nKhông có lịch hẹn.")
            return
        msg = f"📅 <b>Hôm nay ({today})</b>\n━━━━━━━━━━━━━━━\n\n"
        for b in bookings:
            msg += f"🆔 {b[0]} | 🕐 {b[6]} | {b[1]} ({b[2]})\n💈 {b[4]} | {b[8]}\n\n"
        msg += f"📊 Tổng: <b>{len(bookings)}</b>"
        send_message(chat_id, msg)

    elif text in ['/tomorrow', '📅 Ngày mai']:
        tmr = (datetime.now() + timedelta(days=1)).strftime('%d/%m/%Y')
        bookings = sheets.get_bookings_by_date(tmr)
        if not bookings:
            send_message(chat_id, f"📅 <b>Ngày mai ({tmr})</b>\n\nKhông có lịch hẹn.")
            return
        msg = f"📅 <b>Ngày mai ({tmr})</b>\n━━━━━━━━━━━━━━━\n\n"
        for b in bookings:
            msg += f"🆔 {b[0]} | 🕐 {b[6]} | {b[1]} ({b[2]})\n💈 {b[4]} | {b[8]}\n\n"
        msg += f"📊 Tổng: <b>{len(bookings)}</b>"
        send_message(chat_id, msg)

    elif text in ['/all', '⏳ Chờ xác nhận']:
        bookings = sheets.get_bookings_by_status('Chờ')
        if not bookings:
            send_message(chat_id, "✅ Không có đơn chờ xác nhận!")
            return
        msg = "⏳ <b>Đơn chờ xác nhận</b>\n━━━━━━━━━━━━━━━\n\n"
        for b in bookings:
            msg += f"🆔 {b[0]} | {b[1]} ({b[2]})\n📅 {b[5]} 🕐 {b[6]} | 💈 {b[4]}\n\n"
        msg += f"📊 Tổng: <b>{len(bookings)}</b>"
        send_message(chat_id, msg)

    elif text in ['/done', '✅ Hoàn thành']:
        bookings = sheets.get_bookings_by_status('hoàn thành')
        if not bookings:
            send_message(chat_id, "Chưa có đơn hoàn thành.")
            return
        msg = "✅ <b>Đơn hoàn thành</b>\n━━━━━━━━━━━━━━━\n\n"
        for b in bookings:
            msg += f"🆔 {b[0]} | {b[1]} ({b[2]})\n📅 {b[5]} 🕐 {b[6]} | 💈 {b[4]}\n\n"
        msg += f"📊 Tổng: <b>{len(bookings)}</b>"
        send_message(chat_id, msg)

    elif text.startswith('/find'):
        keyword = text.replace('/find', '').strip()
        if not keyword:
            send_message(chat_id, "⚠️ Nhập: /find 0901234567")
            return
        results = sheets.find_booking(keyword)
        if not results:
            send_message(chat_id, f"🔍 Không tìm thấy: <b>{keyword}</b>")
            return
        msg = f"🔍 <b>Kết quả: {keyword}</b>\n━━━━━━━━━━━━━━━\n\n"
        for b in results:
            msg += f"🆔 {b[0]} | {b[1]} ({b[2]})\n📅 {b[5]} 🕐 {b[6]} | {b[8]}\n\n"
        send_message(chat_id, msg)

    elif text in ['/stats', '📊 Thống kê']:
        s = sheets.get_stats()
        send_message(chat_id,
            "📊 <b>THỐNG KÊ</b>\n━━━━━━━━━━━━━━━\n\n"
            f"📋 Tổng: <b>{s['total']}</b>\n"
            f"📅 Hôm nay: <b>{s['today']}</b>\n\n"
            f"⏳ Chờ: <b>{s['pending']}</b>\n"
            f"✅ Xác nhận: <b>{s['confirmed']}</b>\n"
            f"✂️ Hoàn thành: <b>{s['completed']}</b>\n"
            f"❌ Từ chối: <b>{s['rejected']}</b>"
        )

    else:
        send_message(chat_id, "Bấm nút bên dưới hoặc gõ /help để xem hướng dẫn.")


def set_webhook(url):
    resp = requests.post(f"{API}/setWebhook", json={
        'url': f"{url}/telegram",
        'drop_pending_updates': True
    }, timeout=10)
    set_bot_commands()
    return resp.json()


def delete_webhook():
    resp = requests.post(f"{API}/deleteWebhook", json={
        'drop_pending_updates': True
    }, timeout=10)
    return resp.json()
