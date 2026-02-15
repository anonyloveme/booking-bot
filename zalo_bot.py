import requests
import json
from datetime import datetime, timedelta
import config
import sheets

ZALO_API = f"https://bot-api.zaloplatforms.com/bot{config.ZALO_BOT_TOKEN}"

# Lưu trạng thái hội thoại của từng user (in-memory)
user_sessions = {}

SERVICES = {
    '1': 'Cắt Tóc Nam - 100K',
    '2': 'Cạo Râu & Tạo Kiểu - 70K',
    '3': 'Nhuộm Tóc - 200K',
    '4': 'Gội Đầu & Massage - 80K',
    '5': 'Uốn / Duỗi - 250K',
    '6': 'Combo VIP - 350K'
}

# Các bước hội thoại
STEP_CHOOSE_SERVICE = 'choose_service'
STEP_ENTER_NAME = 'enter_name'
STEP_ENTER_PHONE = 'enter_phone'
STEP_ENTER_DATE = 'enter_date'
STEP_ENTER_TIME = 'enter_time'
STEP_ENTER_NOTE = 'enter_note'
STEP_CONFIRM = 'confirm'


def send_message(chat_id, text):
    payload = {
        'chat_id': chat_id,
        'text': text
    }
    try:
        resp = requests.post(f"{ZALO_API}/sendMessage", json=payload, timeout=10)
        print(f"Zalo sendMessage: {resp.status_code} {resp.text}")
        return resp.json()
    except Exception as e:
        print(f"Zalo send error: {e}")
        return {}


def handle_zalo_update(data):
    try:
        result = data.get('result', {})
        event = result.get('event_name', '')
        print(f"Zalo event: {event}")

        if event == 'message.text.received':
            message = result.get('message', {})
            chat_id = message.get('chat', {}).get('id', '')
            text = message.get('text', '').strip()
            sender_name = message.get('from', {}).get('display_name', 'Khách')

            print(f"Zalo msg from {sender_name} ({chat_id}): {text}")
            handle_zalo_message(chat_id, text, sender_name)
    except Exception as e:
        print(f"Zalo handle error: {e}")


def handle_zalo_message(chat_id, text, sender_name):
    text_lower = text.lower().strip()

    # ===== LỆNH ĐẶC BIỆT (luôn ưu tiên) =====
    if text_lower in ['huy', 'hủy', 'cancel', 'thoat', 'thoát', 'exit']:
        if chat_id in user_sessions:
            del user_sessions[chat_id]
        send_message(chat_id, "❌ Đã hủy đặt lịch.\n\nGõ 'đặt lịch' để bắt đầu lại.")
        return

    if text_lower in ['/start', 'hi', 'hello', 'xin chào', 'chào', 'start']:
        if chat_id in user_sessions:
            del user_sessions[chat_id]
        show_welcome(chat_id, sender_name)
        return

    if text_lower in ['menu', 'dịch vụ', 'dich vu', 'bảng giá', 'bang gia', 'giá', 'gia']:
        show_menu(chat_id)
        return

    if text_lower in ['đặt lịch', 'dat lich', 'book', 'đặt', 'dat']:
        start_booking(chat_id, sender_name)
        return

    # ===== XỬ LÝ THEO TRẠNG THÁI HỘI THOẠI =====
    if chat_id in user_sessions:
        session = user_sessions[chat_id]
        step = session.get('step', '')

        if step == STEP_CHOOSE_SERVICE:
            handle_choose_service(chat_id, text)
        elif step == STEP_ENTER_NAME:
            handle_enter_name(chat_id, text)
        elif step == STEP_ENTER_PHONE:
            handle_enter_phone(chat_id, text)
        elif step == STEP_ENTER_DATE:
            handle_enter_date(chat_id, text)
        elif step == STEP_ENTER_TIME:
            handle_enter_time(chat_id, text)
        elif step == STEP_ENTER_NOTE:
            handle_enter_note(chat_id, text)
        elif step == STEP_CONFIRM:
            handle_confirm(chat_id, text)
        return

    # ===== MẶC ĐỊNH =====
    send_message(chat_id,
        "Xin chào! Tôi là Bot đặt lịch cắt tóc ✂️\n\n"
        "Gõ 'đặt lịch' — Đặt lịch cắt tóc\n"
        "Gõ 'menu' — Xem bảng giá\n"
        "Gõ 'hủy' — Hủy đặt lịch đang nhập"
    )


# ===== CÁC MÀN HÌNH =====

def show_welcome(chat_id, sender_name):
    msg = (
        f"Xin chào {sender_name}! ✂️\n"
        f"Chào mừng bạn đến với BarberShop!\n\n"
        f"Gõ 'đặt lịch' — Đặt lịch cắt tóc\n"
        f"Gõ 'menu' — Xem bảng giá dịch vụ\n"
        f"Gõ 'hủy' — Hủy thao tác đang làm"
    )
    send_message(chat_id, msg)


def show_menu(chat_id):
    msg = (
        "💈 BẢNG GIÁ DỊCH VỤ\n"
        "━━━━━━━━━━━━━━━\n\n"
        "1. Cắt Tóc Nam — 100.000đ\n"
        "2. Cạo Râu & Tạo Kiểu — 70.000đ\n"
        "3. Nhuộm Tóc — 200.000đ\n"
        "4. Gội Đầu & Massage — 80.000đ\n"
        "5. Uốn / Duỗi — 250.000đ\n"
        "6. Combo VIP — 350.000đ\n\n"
        "Gõ 'đặt lịch' để bắt đầu đặt lịch!"
    )
    send_message(chat_id, msg)


# ===== QUY TRÌNH ĐẶT LỊCH =====

def start_booking(chat_id, sender_name):
    user_sessions[chat_id] = {
        'step': STEP_CHOOSE_SERVICE,
        'sender_name': sender_name,
        'fullname': '',
        'phone': '',
        'service': '',
        'date': '',
        'time': '',
        'note': ''
    }

    msg = (
        "✂️ ĐẶT LỊCH CẮT TÓC\n"
        "━━━━━━━━━━━━━━━\n\n"
        "Bước 1/6 — Chọn dịch vụ:\n\n"
        "1 — Cắt Tóc Nam (100K)\n"
        "2 — Cạo Râu & Tạo Kiểu (70K)\n"
        "3 — Nhuộm Tóc (200K)\n"
        "4 — Gội Đầu & Massage (80K)\n"
        "5 — Uốn / Duỗi (250K)\n"
        "6 — Combo VIP (350K)\n\n"
        "👉 Gõ số (1-6) để chọn\n"
        "Gõ 'hủy' để thoát"
    )
    send_message(chat_id, msg)


def handle_choose_service(chat_id, text):
    text = text.strip()
    if text not in SERVICES:
        send_message(chat_id, "⚠️ Vui lòng gõ số từ 1 đến 6 để chọn dịch vụ.\n\nGõ 'hủy' để thoát.")
        return

    session = user_sessions[chat_id]
    session['service'] = SERVICES[text]
    session['step'] = STEP_ENTER_NAME

    msg = (
        f"✅ Dịch vụ: {SERVICES[text]}\n\n"
        f"Bước 2/6 — Nhập họ tên của bạn:\n\n"
        f"👉 Ví dụ: Nguyễn Văn A"
    )
    send_message(chat_id, msg)


def handle_enter_name(chat_id, text):
    if len(text) < 2:
        send_message(chat_id, "⚠️ Họ tên quá ngắn. Vui lòng nhập lại:")
        return

    session = user_sessions[chat_id]
    session['fullname'] = text
    session['step'] = STEP_ENTER_PHONE

    msg = (
        f"✅ Họ tên: {text}\n\n"
        f"Bước 3/6 — Nhập số điện thoại:\n\n"
        f"👉 Ví dụ: 0901234567"
    )
    send_message(chat_id, msg)


def handle_enter_phone(chat_id, text):
    import re
    phone = text.replace(' ', '').replace('.', '').replace('-', '')
    if not re.match(r'^(0|\+84)[0-9]{9,10}$', phone):
        send_message(chat_id, "⚠️ Số điện thoại không hợp lệ.\nVui lòng nhập lại (VD: 0901234567):")
        return

    session = user_sessions[chat_id]
    session['phone'] = phone
    session['step'] = STEP_ENTER_DATE

    today = datetime.now().strftime('%d/%m/%Y')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%d/%m/%Y')

    msg = (
        f"✅ SĐT: {phone}\n\n"
        f"Bước 4/6 — Chọn ngày hẹn:\n\n"
        f"1 — Hôm nay ({today})\n"
        f"2 — Ngày mai ({tomorrow})\n"
        f"Hoặc gõ ngày: dd/mm/yyyy\n\n"
        f"👉 Ví dụ: 20/02/2026"
    )
    send_message(chat_id, msg)


def handle_enter_date(chat_id, text):
    text = text.strip()
    today = datetime.now()
    tomorrow = today + timedelta(days=1)

    if text == '1':
        date_str = today.strftime('%d/%m/%Y')
    elif text == '2':
        date_str = tomorrow.strftime('%d/%m/%Y')
    else:
        # Kiểm tra định dạng dd/mm/yyyy
        try:
            parsed = datetime.strptime(text, '%d/%m/%Y')
            if parsed.date() < today.date():
                send_message(chat_id, "⚠️ Ngày đã qua. Vui lòng chọn ngày hôm nay hoặc sau:")
                return
            date_str = text
        except ValueError:
            send_message(chat_id, "⚠️ Sai định dạng. Gõ 1, 2 hoặc ngày dd/mm/yyyy\nVí dụ: 20/02/2026")
            return

    session = user_sessions[chat_id]
    session['date'] = date_str
    session['step'] = STEP_ENTER_TIME

    msg = (
        f"✅ Ngày: {date_str}\n\n"
        f"Bước 5/6 — Chọn giờ hẹn:\n\n"
        f"1 — 08:00    5 — 12:00\n"
        f"2 — 09:00    6 — 14:00\n"
        f"3 — 10:00    7 — 15:00\n"
        f"4 — 11:00    8 — 16:00\n\n"
        f"Hoặc gõ giờ: HH:MM\n"
        f"👉 Ví dụ: 14:30"
    )
    send_message(chat_id, msg)


def handle_enter_time(chat_id, text):
    text = text.strip()

    time_options = {
        '1': '08:00', '2': '09:00', '3': '10:00', '4': '11:00',
        '5': '12:00', '6': '14:00', '7': '15:00', '8': '16:00'
    }

    if text in time_options:
        time_str = time_options[text]
    else:
        # Kiểm tra định dạng HH:MM
        import re
        if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', text):
            send_message(chat_id, "⚠️ Sai định dạng. Gõ số 1-8 hoặc giờ HH:MM\nVí dụ: 14:30")
            return
        time_str = text

    session = user_sessions[chat_id]
    session['time'] = time_str
    session['step'] = STEP_ENTER_NOTE

    msg = (
        f"✅ Giờ: {time_str}\n\n"
        f"Bước 6/6 — Ghi chú (nếu có):\n\n"
        f"👉 VD: Cắt kiểu Undercut\n"
        f"Gõ '0' nếu không có ghi chú"
    )
    send_message(chat_id, msg)


def handle_enter_note(chat_id, text):
    session = user_sessions[chat_id]

    if text.strip() == '0':
        session['note'] = ''
    else:
        session['note'] = text

    session['step'] = STEP_CONFIRM

    # Hiện tổng kết
    msg = (
        "📋 XÁC NHẬN THÔNG TIN\n"
        "━━━━━━━━━━━━━━━\n\n"
        f"💈 Dịch vụ: {session['service']}\n"
        f"👤 Họ tên: {session['fullname']}\n"
        f"📞 SĐT: {session['phone']}\n"
        f"📅 Ngày: {session['date']}\n"
        f"🕐 Giờ: {session['time']}\n"
    )
    if session['note']:
        msg += f"📝 Ghi chú: {session['note']}\n"
    msg += (
        "\n━━━━━━━━━━━━━━━\n"
        "1 — ✅ Xác nhận đặt lịch\n"
        "2 — ❌ Hủy\n"
        "3 — 🔄 Đặt lại từ đầu"
    )
    send_message(chat_id, msg)


def handle_confirm(chat_id, text):
    text = text.strip()

    if text == '2':
        del user_sessions[chat_id]
        send_message(chat_id, "❌ Đã hủy đặt lịch.\nGõ 'đặt lịch' để bắt đầu lại.")
        return

    if text == '3':
        sender_name = user_sessions[chat_id].get('sender_name', 'Khách')
        del user_sessions[chat_id]
        start_booking(chat_id, sender_name)
        return

    if text != '1':
        send_message(chat_id, "👉 Gõ 1 để xác nhận, 2 để hủy, 3 để đặt lại.")
        return

    # ===== XÁC NHẬN - LƯU BOOKING =====
    session = user_sessions[chat_id]

    # Chuyển ngày dd/mm/yyyy sang yyyy-mm-dd để lưu vào sheets
    date_parts = session['date'].split('/')
    if len(date_parts) == 3:
        date_for_sheet = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"
    else:
        date_for_sheet = session['date']

    booking_data = {
        'fullname': session['fullname'],
        'phone': session['phone'],
        'email': '',
        'service': session['service'],
        'date': date_for_sheet,
        'time': session['time'],
        'note': session['note'],
        'source': 'Zalo'
    }

    try:
        booking_id, date_formatted = sheets.add_booking(booking_data)

        # Gửi xác nhận cho khách
        confirm_msg = (
            "🎉 ĐẶT LỊCH THÀNH CÔNG!\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"🆔 Mã: {booking_id}\n"
            f"💈 Dịch vụ: {session['service']}\n"
            f"👤 Khách: {session['fullname']}\n"
            f"📞 SĐT: {session['phone']}\n"
            f"📅 Ngày: {date_formatted}\n"
            f"🕐 Giờ: {session['time']}\n"
        )
        if session['note']:
            confirm_msg += f"📝 Ghi chú: {session['note']}\n"
        confirm_msg += (
            "\n━━━━━━━━━━━━━━━\n"
            "Chúng tôi sẽ liên hệ xác nhận sớm!\n\n"
            "Gõ 'đặt lịch' để đặt thêm lịch mới."
        )
        send_message(chat_id, confirm_msg)

        # Thông báo admin qua Telegram
        from telegram_bot import notify_new_booking
        notify_new_booking(booking_id, booking_data, date_formatted)

    except Exception as e:
        print(f"Booking save error: {e}")
        send_message(chat_id, "⚠️ Có lỗi xảy ra, vui lòng thử lại sau hoặc gọi 0901 234 567.")

    # Xóa session
    if chat_id in user_sessions:
        del user_sessions[chat_id]


def set_webhook(url):
    resp = requests.post(f"{ZALO_API}/setWebhook", json={
        'url': f"{url}/zalo",
        'secret_token': config.ZALO_SECRET_TOKEN
    }, timeout=10)
    print(f"Zalo setWebhook: {resp.status_code} {resp.text}")
    return resp.json()
