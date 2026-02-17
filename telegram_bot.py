import requests, json
from datetime import datetime, timezone, timedelta
import config, sheets

API = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}"
VN_TZ = timezone(timedelta(hours=7))

def vn_now():
    return datetime.now(VN_TZ)

# ===== BÀN PHÍM CỐ ĐỊNH =====
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

# ===== GỬI TIN NHẮN =====
def send_message(chat_id, text, reply_markup=None, parse_mode='HTML'):
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
        'reply_markup': json.dumps(reply_markup or ADMIN_KEYBOARD)
    }
    try:
        r = requests.post(f"{API}/sendMessage", json=payload, timeout=10)
        result = r.json()
        if not result.get('ok'):
            print(f"TG send error: {result}")
        return result
    except Exception as e:
        print(f"TG send exception: {e}")
        return {}

def send_message_inline(chat_id, text, reply_markup=None):
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        r = requests.post(f"{API}/sendMessage", json=payload, timeout=10)
        result = r.json()
        if not result.get('ok'):
            print(f"TG inline send error: {result}")
        return result
    except Exception as e:
        print(f"TG inline exception: {e}")
        return {}

def edit_message(chat_id, message_id, text, reply_markup=None):
    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    try:
        r = requests.post(f"{API}/editMessageText", json=payload, timeout=10)
        return r.json()
    except Exception as e:
        print(f"TG edit exception: {e}")
        return {}

def answer_callback(callback_id, text=''):
    try:
        requests.post(f"{API}/answerCallbackQuery", json={
            'callback_query_id': callback_id,
            'text': text
        }, timeout=10)
    except:
        pass

def set_bot_commands():
    cmds = [
        {'command': 'start', 'description': '🏠 Bắt đầu'},
        {'command': 'today', 'description': '📅 Lịch hôm nay'},
        {'command': 'tomorrow', 'description': '📅 Lịch ngày mai'},
        {'command': 'find', 'description': '🔍 Tìm đơn'},
        {'command': 'stats', 'description': '📊 Thống kê'},
        {'command': 'help', 'description': '❓ Trợ giúp'}
    ]
    try:
        requests.post(f"{API}/setMyCommands", json={'commands': cmds}, timeout=10)
    except:
        pass

# ===== THÔNG BÁO ĐƠN MỚI =====
def notify_new_booking(booking_id, data, date_formatted):
    now_str = vn_now().strftime('%H:%M %d/%m/%Y')
    msg = (
        f"✂️ <b>LỊCH HẸN MỚI</b> ✂️\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"🆔 <b>Mã:</b> {booking_id}\n"
        f"👤 <b>Khách:</b> {data.get('fullname', '')}\n"
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
        f"⏰ <i>{now_str} (VN)</i>\n"
        f"📱 <i>Nguồn: {data.get('source', 'Website')}</i>"
    )

    # Không dùng tel: vì Telegram không hỗ trợ
    keyboard = {
        'inline_keyboard': [
            [
                {'text': '✅ Xác nhận', 'callback_data': f'confirm_{booking_id}'},
                {'text': '❌ Từ chối', 'callback_data': f'reject_{booking_id}'}
            ]
        ]
    }
    return send_message_inline(config.TELEGRAM_CHAT_ID, msg, keyboard)

# ===== HIỂN THỊ DANH SÁCH ĐƠN ĐỂ CHỌN =====
def show_pending_for_action(chat_id, action):
    if action == 'confirm':
        bookings = sheets.get_bookings_by_status('Chờ')
        title = "✔️ <b>CHỌN ĐƠN XÁC NHẬN</b>"
        empty_msg = "✅ Không có đơn chờ xác nhận!"
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
        empty_msg = "Không có đơn chờ để từ chối."
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

# ===== XỬ LÝ CALLBACK =====
def handle_callback(callback):
    data = callback.get('data', '')
    chat_id = callback['message']['chat']['id']
    message_id = callback['message']['message_id']
    original_text = callback['message'].get('text', '')
    now_str = vn_now().strftime('%H:%M %d/%m/%Y')

    print(f"Callback: {data} at {now_str} VN")

    # === XÁC NHẬN 1 ĐƠN ===
    if data.startswith('confirm_') and data != 'confirm_all_yes':
        bid = data.replace('confirm_', '')
        row = sheets.update_status(bid, '✅ Đã xác nhận')
        if not row:
            answer_callback(callback['id'], f'⚠️ Không tìm thấy {bid} đang chờ!')
            return
        answer_callback(callback['id'], f'✅ {bid} đã xác nhận!')
        new_text = original_text + f"\n\n✅ ĐÃ XÁC NHẬN — {now_str}"
        keyboard = {'inline_keyboard': [[
            {'text': '✂️ Hoàn thành', 'callback_data': f'complete_{bid}'}
        ]]}
        edit_message(chat_id, message_id, new_text, keyboard)
        send_message(chat_id, f"✅ Đã xác nhận <b>{bid}</b> — {row[1] if len(row) > 1 else ''}")

    # === TỪ CHỐI 1 ĐƠN ===
    elif data.startswith('reject_') and data != 'reject_all':
        bid = data.replace('reject_', '')
        row = sheets.update_status(bid, '❌ Đã từ chối')
        if not row:
            answer_callback(callback['id'], f'⚠️ Không tìm thấy {bid}!')
            return
        answer_callback(callback['id'], f'❌ {bid} đã từ chối!')
        new_text = original_text + f"\n\n❌ ĐÃ TỪ CHỐI — {now_str}"
        edit_message(chat_id, message_id, new_text)
        send_message(chat_id, f"❌ Đã từ chối <b>{bid}</b> — {row[1] if len(row) > 1 else ''}")

    # === HOÀN THÀNH 1 ĐƠN ===
    elif data.startswith('complete_') and data != 'complete_all_yes':
        bid = data.replace('complete_', '')
        row = sheets.update_status(bid, '✅ Đã hoàn thành')
        if not row:
            answer_callback(callback['id'], f'⚠️ Không tìm thấy {bid}!')
            return
        answer_callback(callback['id'], f'✂️ {bid} hoàn thành!')
        new_text = original_text + f"\n\n✅ ĐÃ HOÀN THÀNH — {now_str}"
        edit_message(chat_id, message_id, new_text)
        send_message(chat_id, f"✂️ <b>{bid}</b> — {row[1] if len(row) > 1 else ''} hoàn thành!")

    # === XÁC NHẬN TẤT CẢ — ĐỒNG Ý ===
    elif data == 'confirm_all_yes':
        answer_callback(callback['id'], '⏳ Đang xác nhận tất cả...')
        bookings = sheets.get_bookings_by_status('Chờ')
        if not bookings:
            edit_message(chat_id, message_id, "✅ Không có đơn chờ xác nhận!")
            return
        count = 0
        for b in bookings:
            bid = b[0] if len(b) > 0 else ''
            if bid:
                result = sheets.update_status(bid, '✅ Đã xác nhận')
                if result:
                    count += 1
        msg = f"✅ <b>ĐÃ XÁC NHẬN TẤT CẢ</b>\n\nSố đơn: <b>{count}</b>\n⏰ {now_str}"
        edit_message(chat_id, message_id, msg)
        send_message(chat_id, f"✅ Đã xác nhận tất cả <b>{count}</b> đơn!")

    # === HOÀN THÀNH TẤT CẢ — ĐỒNG Ý ===
    elif data == 'complete_all_yes':
        answer_callback(callback['id'], '⏳ Đang hoàn thành tất cả...')
        bookings = sheets.get_bookings_by_status('Đã xác nhận')
        if not bookings:
            edit_message(chat_id, message_id, "Không có đơn cần hoàn thành!")
            return
        count = 0
        for b in bookings:
            bid = b[0] if len(b) > 0 else ''
            if bid:
                result = sheets.update_status(bid, '✅ Đã hoàn thành')
                if result:
                    count += 1
        msg = f"🏁 <b>ĐÃ HOÀN THÀNH TẤT CẢ</b>\n\nSố đơn: <b>{count}</b>\n⏰ {now_str}"
        edit_message(chat_id, message_id, msg)
        send_message(chat_id, f"🏁 Đã hoàn thành tất cả <b>{count}</b> đơn!")

    # === HỦY THAO TÁC ===
    elif data == 'cancel_action':
        answer_callback(callback['id'], 'Đã hủy')
        edit_message(chat_id, message_id, "❎ Đã hủy thao tác.")

    else:
        answer_callback(callback['id'], '⚠️ Không nhận diện được lệnh')

# ===== XỬ LÝ LỆNH / NÚT BẤM =====
def handle_command(message):
    chat_id = message['chat']['id']
    text = message.get('text', '').strip()
    now_str = vn_now().strftime('%H:%M %d/%m/%Y')

    print(f"Command: '{text}' from {chat_id} at {now_str} VN")

    # --- START / HELP ---
    if text in ['/start', '/help', '❓ Trợ giúp']:
        set_bot_commands()
        send_message(chat_id,
            "🏠 <b>BarberShop Manager</b>\n\n"
            "📅 <b>Hôm nay / Ngày mai</b> — Xem lịch\n"
            "✔️ <b>Xác nhận đơn</b> — Duyệt từng đơn\n"
            "✂️ <b>Hoàn thành đơn</b> — Đánh dấu xong\n"
            "❌ <b>Từ chối đơn</b> — Từ chối từng đơn\n"
            "✅ <b>Xác nhận tất cả</b> — Duyệt hết đơn chờ\n"
            "🏁 <b>Hoàn thành tất cả</b> — Xong hết đơn đã duyệt\n"
            "📊 <b>Thống kê</b> — Tổng quan\n\n"
            "🔍 Tìm: /find [SĐT hoặc tên]"
        )

    # --- HÔM NAY ---
    elif text in ['/today', '📅 Hôm nay']:
        today = sheets.get_today_str()
        bookings = sheets.get_bookings_by_date(today)
        if not bookings:
            send_message(chat_id, f"📅 <b>Hôm nay ({today})</b>\n\nKhông có lịch hẹn.")
            return
        msg = f"📅 <b>Hôm nay ({today})</b>\n━━━━━━━━━━━━━━━\n\n"
        for b in bookings:
            status = b[8] if len(b) > 8 else ''
            msg += f"🆔 {b[0]} | 🕐 {b[6]} | {b[1]} ({b[2]})\n💈 {b[4]} | {status}\n\n"
        msg += f"📊 Tổng: <b>{len(bookings)}</b>"
        send_message(chat_id, msg)

    # --- NGÀY MAI ---
    elif text in ['/tomorrow', '📅 Ngày mai']:
        tmr = (vn_now() + timedelta(days=1)).strftime('%d/%m/%Y')
        bookings = sheets.get_bookings_by_date(tmr)
        if not bookings:
            send_message(chat_id, f"📅 <b>Ngày mai ({tmr})</b>\n\nKhông có lịch hẹn.")
            return
        msg = f"📅 <b>Ngày mai ({tmr})</b>\n━━━━━━━━━━━━━━━\n\n"
        for b in bookings:
            status = b[8] if len(b) > 8 else ''
            msg += f"🆔 {b[0]} | 🕐 {b[6]} | {b[1]} ({b[2]})\n💈 {b[4]} | {status}\n\n"
        msg += f"📊 Tổng: <b>{len(bookings)}</b>"
        send_message(chat_id, msg)

    # --- TÌM KIẾM ---
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

    # --- THỐNG KÊ ---
    elif text in ['/stats', '📊 Thống kê']:
        s = sheets.get_stats()
        send_message(chat_id,
            f"📊 <b>THỐNG KÊ</b>\n━━━━━━━━━━━━━━━\n\n"
            f"📋 Tổng: <b>{s['total']}</b>\n"
            f"📅 Hôm nay: <b>{s['today']}</b>\n\n"
            f"⏳ Chờ: <b>{s['pending']}</b>\n"
            f"✅ Xác nhận: <b>{s['confirmed']}</b>\n"
            f"✂️ Hoàn thành: <b>{s['completed']}</b>\n"
            f"❌ Từ chối: <b>{s['rejected']}</b>\n\n"
            f"⏰ {now_str}"
        )

    # --- XÁC NHẬN TỪNG ĐƠN ---
    elif text == '✔️ Xác nhận đơn':
        show_pending_for_action(chat_id, 'confirm')

    # --- HOÀN THÀNH TỪNG ĐƠN ---
    elif text == '✂️ Hoàn thành đơn':
        show_pending_for_action(chat_id, 'complete')

    # --- TỪ CHỐI TỪNG ĐƠN ---
    elif text == '❌ Từ chối đơn':
        show_pending_for_action(chat_id, 'reject')

    # --- XÁC NHẬN TẤT CẢ ---
    elif text == '✅ Xác nhận tất cả':
        bookings = sheets.get_bookings_by_status('Chờ')
        if not bookings:
            send_message(chat_id, "✅ Không có đơn chờ xác nhận!")
            return
        msg = f"⚠️ <b>XÁC NHẬN TẤT CẢ?</b>\n\nSẽ xác nhận <b>{len(bookings)}</b> đơn đang chờ:\n\n"
        for b in bookings:
            bid = b[0] if len(b) > 0 else '?'
            name = b[1] if len(b) > 1 else '?'
            date_val = b[5] if len(b) > 5 else ''
            time_val = b[6] if len(b) > 6 else ''
            msg += f"• {bid} — {name} | {date_val} {time_val}\n"
        keyboard = {
            'inline_keyboard': [
                [
                    {'text': '✅ Đồng ý xác nhận tất cả', 'callback_data': 'confirm_all_yes'},
                    {'text': '❎ Hủy', 'callback_data': 'cancel_action'}
                ]
            ]
        }
        send_message_inline(chat_id, msg, keyboard)

    # --- HOÀN THÀNH TẤT CẢ ---
    elif text == '🏁 Hoàn thành tất cả':
        bookings = sheets.get_bookings_by_status('Đã xác nhận')
        if not bookings:
            send_message(chat_id, "Không có đơn đã xác nhận để hoàn thành!")
            return
        msg = f"⚠️ <b>HOÀN THÀNH TẤT CẢ?</b>\n\nSẽ hoàn thành <b>{len(bookings)}</b> đơn đã xác nhận:\n\n"
        for b in bookings:
            bid = b[0] if len(b) > 0 else '?'
            name = b[1] if len(b) > 1 else '?'
            date_val = b[5] if len(b) > 5 else ''
            time_val = b[6] if len(b) > 6 else ''
            msg += f"• {bid} — {name} | {date_val} {time_val}\n"
        keyboard = {
            'inline_keyboard': [
                [
                    {'text': '🏁 Đồng ý hoàn thành tất cả', 'callback_data': 'complete_all_yes'},
                    {'text': '❎ Hủy', 'callback_data': 'cancel_action'}
                ]
            ]
        }
        send_message_inline(chat_id, msg, keyboard)

    # --- MẶC ĐỊNH ---
    else:
        send_message(chat_id, "Bấm nút bên dưới hoặc gõ /help")

# ===== WEBHOOK =====
def set_webhook(url):
    try:
        resp = requests.post(f"{API}/setWebhook", json={
            'url': f"{url}/telegram",
            'drop_pending_updates': True
        }, timeout=10)
        set_bot_commands()
        return resp.json()
    except Exception as e:
        return {'error': str(e)}

def delete_webhook():
    try:
        resp = requests.post(f"{API}/deleteWebhook", json={
            'drop_pending_updates': True
        }, timeout=10)
        return resp.json()
    except Exception as e:
        return {'error': str(e)}
