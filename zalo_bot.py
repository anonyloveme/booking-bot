import requests
import json
from datetime import datetime
import config
import sheets

ZALO_API = f"https://bot-api.zaloplatforms.com/bot{config.ZALO_BOT_TOKEN}"

def send_message(chat_id, text):
    payload = {
        'chat_id': chat_id,
        'text': text
    }
    resp = requests.post(f"{ZALO_API}/sendMessage", json=payload, timeout=10)
    print(f"Zalo sendMessage response: {resp.status_code} {resp.text}")
    return resp.json()

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

            print(f"Zalo message from {sender_name}: {text}")
            handle_zalo_message(chat_id, text, sender_name)
    except Exception as e:
        print(f"Zalo handle error: {e}")

def handle_zalo_message(chat_id, text, sender_name):
    text_lower = text.lower()

    if text_lower in ['/start', 'hi', 'hello', 'xin chào', 'chào', 'đặt lịch', 'book', 'start']:
        msg = (
            "✂️ BarberShop - Đặt Lịch Cắt Tóc\n"
            "━━━━━━━━━━━━━━━\n\n"
            "Chào bạn! Để đặt lịch, vui lòng gửi thông tin theo mẫu:\n\n"
            "DATLICH\n"
            "Họ tên: [tên của bạn]\n"
            "SĐT: [số điện thoại]\n"
            "Dịch vụ: [tên dịch vụ]\n"
            "Ngày: [dd/mm/yyyy]\n"
            "Giờ: [HH:MM]\n"
            "Ghi chú: [nếu có]\n\n"
            "━━━━━━━━━━━━━━━\n"
            "📋 Dịch vụ có sẵn:\n"
            "1. Cắt Tóc Nam - 100K\n"
            "2. Cạo Râu & Tạo Kiểu - 70K\n"
            "3. Nhuộm Tóc - 200K\n"
            "4. Gội Đầu & Massage - 80K\n"
            "5. Uốn / Duỗi - 250K\n"
            "6. Combo VIP - 350K\n\n"
            "Ví dụ:\n"
            "DATLICH\n"
            "Họ tên: Nguyễn Văn A\n"
            "SĐT: 0901234567\n"
            "Dịch vụ: Combo VIP\n"
            "Ngày: 20/02/2026\n"
            "Giờ: 14:00\n"
            "Ghi chú: Cắt kiểu Undercut"
        )
        send_message(chat_id, msg)

    elif text_lower.startswith('datlich'):
        booking_data = parse_zalo_booking(text, sender_name)

        if not booking_data.get('fullname') or not booking_data.get('phone'):
            send_message(chat_id, "⚠️ Thiếu thông tin! Vui lòng nhập đầy đủ Họ tên và SĐT.\n\nGõ 'đặt lịch' để xem hướng dẫn.")
            return

        booking_data['source'] = 'Zalo'

        # Chuyển ngày dd/mm/yyyy sang yyyy-mm-dd
        date_parts = booking_data.get('date', '').split('/')
        if len(date_parts) == 3:
            booking_data['date'] = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"

        booking_id, date_formatted = sheets.add_booking(booking_data)

        confirm_msg = (
            f"✅ Đặt lịch thành công!\n\n"
            f"🆔 Mã: {booking_id}\n"
            f"👤 Khách: {booking_data['fullname']}\n"
            f"📅 Ngày: {date_formatted}\n"
            f"🕐 Giờ: {booking_data.get('time', 'Chưa chọn')}\n"
            f"💈 Dịch vụ: {booking_data.get('service', 'Chưa chọn')}\n\n"
            f"Chúng tôi sẽ liên hệ xác nhận sớm nhất!"
        )
        send_message(chat_id, confirm_msg)

        # Thông báo admin qua Telegram
        from telegram_bot import notify_new_booking
        notify_new_booking(booking_id, booking_data, date_formatted)

    elif text_lower in ['menu', 'dịch vụ', 'bảng giá', 'giá', 'dich vu', 'bang gia', 'gia']:
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

    else:
        send_message(chat_id, "Xin chào! Gõ 'đặt lịch' để đặt lịch cắt tóc hoặc 'menu' để xem bảng giá.")

def parse_zalo_booking(text, sender_name):
    data = {
        'fullname': sender_name,
        'phone': '',
        'email': '',
        'service': '',
        'date': '',
        'time': '',
        'note': ''
    }

    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        lower = line.lower()

        if lower.startswith('họ tên:') or lower.startswith('ho ten:') or lower.startswith('tên:') or lower.startswith('ten:'):
            data['fullname'] = line.split(':', 1)[1].strip()
        elif lower.startswith('sđt:') or lower.startswith('sdt:') or lower.startswith('số:') or lower.startswith('phone:') or lower.startswith('so:'):
            data['phone'] = line.split(':', 1)[1].strip()
        elif lower.startswith('email:'):
            data['email'] = line.split(':', 1)[1].strip()
        elif lower.startswith('dịch vụ:') or lower.startswith('dich vu:') or lower.startswith('service:'):
            data['service'] = line.split(':', 1)[1].strip()
        elif lower.startswith('ngày:') or lower.startswith('ngay:') or lower.startswith('date:'):
            data['date'] = line.split(':', 1)[1].strip()
        elif lower.startswith('giờ:') or lower.startswith('gio:') or lower.startswith('time:'):
            data['time'] = line.split(':', 1)[1].strip()
        elif lower.startswith('ghi chú:') or lower.startswith('ghi chu:') or lower.startswith('note:'):
            data['note'] = line.split(':', 1)[1].strip()

    return data

def set_webhook(url):
    resp = requests.post(f"{ZALO_API}/setWebhook", json={
        'url': f"{url}/zalo",
        'secret_token': config.ZALO_SECRET_TOKEN
    }, timeout=10)
    print(f"Zalo setWebhook response: {resp.status_code} {resp.text}")
    return resp.json()
