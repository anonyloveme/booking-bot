import requests
import json
from datetime import datetime, timedelta
import config
import sheets

API = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}"

ADMIN_KEYBOARD = {
    'keyboard': [
        [{'text': '📅 Hôm nay'}, {'text': '📅 Ngày mai'}],
        [{'text': '✔️ Xác nhận đơn'}, {'text': '✂️ Hoàn thành đơn'}],
        [{'text': '❌ Từ chối đơn'}, {'text': '📊 Thống kê'}],
        [{'text': '✅ Xác nhận tất cả'}, {'text': '🏁 Hoàn thành tất cả'}]
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
    commands = [
        {'command': 'start', 'description': '🏠 Bắt đầu'},
        {'command': 'today', 'description': '📅 Lịch hôm nay'},
        {'command': 'tomorrow', 'description': '📅 Lịch ngày mai'},
        {'command': 'find', 'description': '🔍 Tìm đơn'},
        {'command': 'stats', 'description': '📊 Thống kê'},
        {'command': 'help', 'description': '❓ Trợ giúp'}
    ]
    try:
        requests.post(f"{API}/setMyCommands", json={'commands': commands}, timeout=10)
    except:
        pass


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


def show_pending_for_action(chat_id, action):
    if action == 'confirm':
        bookings = sheets.get_bookings_by_status('Chờ')
        title = "✔️ <b>CHỌN ĐƠN XÁC NHẬN</b>"
        empty_msg = "✅ Không có đơn chờ!"
        prefix = 'confirm_'
        btn_icon = '✅'
    elif action == 'complete':
        bookings = sheets.get_bookings_by_status('Đã xác nhận')
        title = "✂️ <b>CHỌN ĐƠN HOÀN THÀNH</b>"
        empty_msg = "Không có đơn cần hoàn thành."
        prefix = 'complete_'
        btn_icon = '✂️'
    elif action == 'reject':
        bookings = sheets.get_bookings_by_status('Chờ')
        title = "❌ <b>CHỌN ĐƠN TỪ CHỐI</b>"
        empty_msg = "Không có đơn chờ xử lý."
        prefix = 'reject_'
        btn_icon = '❌'
    else:
        return

    if not bookings:
        send_message(chat_id, empty_msg)
        return

    msg = f"{title}\n━━━━━━━━━━━━━━━\n\n"
    buttons = []

    for b in bookings:
        bid = b[0] if len(b) > 0 else '?'
        name = b[1] if len(b) > 1 else '?'
        phone = b[2] if len(b) > 2 else ''
        service = b[4] if len(b) > 4 else ''
        date_val = b[5] if len(b) > 5 else ''
        time_val = b[6] if len(b) > 6 else ''

        msg += f"🆔 <b>{bid}</b> | {name} ({phone})\n📅 {date_val} 🕐 {time_val} | 💈 {service}\n\n"

        buttons.append([{
            'text': f'{btn_icon} {bid} — {name} | {date_val} {time_val}',
            'callback_data': f'{prefix}{bid}'
        }])

    keyboard = {'inline_keyboard': buttons}
    send_message_inline(chat_id, msg, keyboard)


def confirm_all_today(chat_id):
    """Xác nhận tất cả đơn đang chờ"""
    bookings = sheets.get_bookings_by_status('Chờ')
    if not bookings:
        send_message(chat_id, "✅ Không có đơn chờ xác nhận!")
        return

    confirmed = []
    for b in bookings:
        bid = b[0] if len(b) > 0 else ''
        name = b[1] if len(b) > 1 else ''
        if bid:
            result = sheets.update_status(bid, '✅ Đã xác nhận')
            if result:
                confirmed.append(f"{bid} — {name}")

    if confirmed:
        msg = f"✅ <b>ĐÃ XÁC NHẬN {len(confirmed)} ĐƠN</b>\n━━━━━━━━━━━━━━━\n\n"
        for c in confirmed:
            msg += f"• {c}\n"
        send_message(chat_id, msg)
    else:
        send_message(chat_id, "⚠️ Không xác nhận được đơn nào.")


def complete_all_today(chat_id):
    """Hoàn thành tất cả đơn đã xác nhận"""
    bookings = sheets.get_bookings_by_status('Đã xác nhận')
    if not bookings:
        send_message(chat_id, "Không có đơn đã xác nhận để hoàn thành.")
        return

    completed = []
    for b in bookings:
        bid = b[0] if len(b) > 0 else ''
        name = b[1] if len(b) > 1 else ''
        if bid:
            result = sheets.update_status(bid, '✅ Đã hoàn thành')
            if result:
                completed.append(f"{bid} — {name}")

    if completed:
        msg = f"🏁 <b>ĐÃ HOÀN THÀNH {len(completed)} ĐƠN</b>\n━━━━━━━━━━━━━━━\n\n"
        for c in completed:
            msg += f"• {c}\n"
        send_message(chat_id, msg)
    else:
        send_message(chat_id, "⚠️ Không hoàn thành được đơn nào.")


def handle_callback(callback):
    data = callback.get('data', '')
    chat_id = callback['message']['chat']['id']
    message_id = callback['message']['message_id']
    original_text = callback['message'].get('text', '')
    now_str = datetime.now().strftime('%H:%M %d/%m/%Y')

    if data.startswith('confirm_'):
        bid = data.replace('confirm_', '')
        row = sheets.update_status(bid, '✅ Đã xác nhận')
        if row is None:
            answer_callback(callback['id'], f'⚠️ {bid} không tìm thấy hoặc đã xử lý!')
            return
        answer_callback(callback['id'], f'✅ {bid} đã xác nhận!')
        new_text = original_text + f"\n\n✅ ĐÃ XÁC NHẬN — {now_str}"
        keyboard = {
            'inline_keyboard': [
                [{'text': '✂️ Hoàn thành', 'callback_data': f'complete_{bid}'}],
                [{'text': '📞 Gọi khách', 'url': f"tel:{row[2] if len(row) > 2 else ''}"}]
            ]
        }
        edit_message(chat_id, message_id, new_text, keyboard)
        send_message(chat_id, f"✅ Xác nhận <b>{bid}</b> — {row[1] if len(row) > 1 else ''}")

    elif data.startswith('reject_'):
        bid = data.replace('reject_', '')
        row = sheets.update_status(bid, '❌ Đã từ chối')
        if row is None:
            answer_callback(callback['id'], f'⚠️ {bid} không tìm thấy!')
            return
        answer_callback(callback['id'], f'❌ {bid} đã từ chối!')
        new_text = original_text + f"\n\n❌ ĐÃ TỪ CHỐI — {now_str}"
        edit_message(chat_id, message_id, new_text)
        send_message(chat_id, f"❌ Từ chối <b>{bid}</b> — {row[1] if len(row) > 1 else ''}")

    elif data.startswith('complete_'):
        bid = data.replace('complete_', '')
        row = sheets.update_status(bid, '✅ Đã hoàn thành')
        if row is None:
            answer_callback(callback['id'], f'⚠️ {bid} không tìm thấy!')
            return
        answer_callback(callback['id'], f'✅ {bid} hoàn thành!')
        new_text = original_text + f"\n\n✅ ĐÃ HOÀN THÀNH — {now_str}"
        edit_message(chat_id, message_id, new_text)
        send_message(chat_id, f"✂️ <b>{bid}</b> — {row[1] if len(row) > 1 else ''} hoàn thành!")

    elif data == 'confirm_all_yes':
        answer_callback(callback['id'], '✅ Đang xác nhận...')
        edit_message(chat_id, message_id, "⏳ Đang xác nhận tất cả...")
        confirm_all_today(chat_id)

    elif data == 'complete_all_yes':
        answer_callback(callback['id'], '✂️ Đang hoàn thành...')
        edit_message(chat_id, message_id, "⏳ Đang hoàn thành tất cả...")
        complete_all_today(chat_id)

    elif data == 'cancel_action':
        answer_callback(callback['id'], 'Đã hủy')
        edit_message(chat_id, message_id, "❌ Đã hủy thao tác.")


def handle_command(message):
    chat_id = message['chat']['id']
    text = message.get('text', '').strip()

    if text in ['/start', '/help', '❓ Trợ giúp']:
        set_bot_commands()
        send_message(chat_id,
            "🏠 <b>BarberShop Manager</b>\n\n"
            "📅 <b>Hôm nay / Ngày mai</b> — Xem lịch\n"
            "✔️ <b>Xác nhận đơn</b> — Chọn đơn duyệt\n"
            "✂️ <b>Hoàn thành đơn</b> — Chọn đơn xong\n"
            "❌ <b>Từ chối đơn</b> — Chọn đơn từ chối\n"
            "📊 <b>Thống kê</b> — Tổng quan\n\n"
            "✅ <b>Xác nhận tất cả</b> — Duyệt hết đơn chờ\n"
            "🏁 <b>Hoàn thành tất cả</b> — Xong hết đơn\n\n"
            "🔍 Tìm: /find [SĐT hoặc tên]"
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

    elif text == '✔️ Xác nhận đơn':
        show_pending_for_action(chat_id, 'confirm')

    elif text == '✂️ Hoàn thành đơn':
        show_pending_for_action(chat_id, 'complete')

    elif text == '❌ Từ chối đơn':
        show_pending_for_action(chat_id, 'reject')

    elif text == '✅ Xác nhận tất cả':
        # Hỏi xác nhận trước
        bookings = sheets.get_bookings_by_status('Chờ')
        if not bookings:
            send_message(chat_id, "✅ Không có đơn chờ!")
            return
        msg = f"⚠️ Xác nhận <b>tất cả {len(bookings)} đơn</b> đang chờ?\n\n"
        for b in bookings:
            msg += f"• {b[0]} — {b[1]} | {b[5]} {b[6]}\n"
        keyboard = {
            'inline_keyboard': [
                [
                    {'text': f'✅ Xác nhận {len(bookings)} đơn', 'callback_data': 'confirm_all_yes'},
                    {'text': '❌ Hủy', 'callback_data': 'cancel_action'}
                ]
            ]
        }
        send_message_inline(chat_id, msg, keyboard)

    elif text == '🏁 Hoàn thành tất cả':
        bookings = sheets.get_bookings_by_status('Đã xác nhận')
        if not bookings:
            send_message(chat_id, "Không có đơn đã xác nhận để hoàn thành.")
            return
        msg = f"⚠️ Hoàn thành <b>tất cả {len(bookings)} đơn</b> đã xác nhận?\n\n"
        for b in bookings:
            msg += f"• {b[0]} — {b[1]} | {b[5]} {b[6]}\n"
        keyboard = {
            'inline_keyboard': [
                [
                    {'text': f'🏁 Hoàn thành {len(bookings)} đơn', 'callback_data': 'complete_all_yes'},
                    {'text': '❌ Hủy', 'callback_data': 'cancel_action'}
                ]
            ]
        }
        send_message_inline(chat_id, msg, keyboard)

    else:
        send_message(chat_id, "Bấm nút bên dưới hoặc gõ /help")


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
