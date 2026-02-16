import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import config
import json
import os

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def get_sheet():
    if os.path.exists('credentials.json'):
        creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    else:
        creds_json = json.loads(os.environ.get('GOOGLE_CREDENTIALS', '{}'))
        creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(config.SHEET_ID).sheet1
    return sheet


def get_today_str():
    return datetime.now().strftime('%d/%m/%Y')


def generate_booking_id(sheet):
    """Tạo mã DUC01, DUC02... không bao giờ trùng trong ngày"""
    data = sheet.get_all_values()
    today = get_today_str()

    # Tìm số lớn nhất hiện có trong ngày
    max_num = 0
    for row in data[1:]:
        if len(row) >= 10 and today in row[9]:
            bid = row[0]
            if bid.startswith('DUC'):
                try:
                    num = int(bid.replace('DUC', ''))
                    if num > max_num:
                        max_num = num
                except:
                    pass

    return f"DUC{max_num + 1:02d}"


def add_booking(data):
    sheet = get_sheet()
    booking_id = generate_booking_id(sheet)
    now = datetime.now().strftime('%H:%M %d/%m/%Y')

    date_raw = data.get('date', '')
    date_parts = date_raw.split('-')
    if len(date_parts) == 3:
        date_formatted = f"{date_parts[2]}/{date_parts[1]}/{date_parts[0]}"
    else:
        date_formatted = date_raw

    row = [
        booking_id,
        data.get('fullname', ''),
        data.get('phone', ''),
        data.get('email', ''),
        data.get('service', ''),
        date_formatted,
        data.get('time', ''),
        data.get('note', ''),
        '⏳ Chờ xác nhận',
        now
    ]

    all_data = sheet.get_all_values()
    next_row = len(all_data) + 1
    sheet.update(f'A{next_row}:J{next_row}', [row])

    print(f"Sheet: {booking_id} -> row {next_row}")
    return booking_id, date_formatted


def update_status(booking_id, new_status):
    """Cập nhật trạng thái — tìm đúng dòng có mã đơn khớp"""
    sheet = get_sheet()
    data = sheet.get_all_values()

    # Tìm dòng có booking_id khớp (ưu tiên đơn chưa xử lý)
    target_row = -1
    target_data = None

    for i, row in enumerate(data):
        if len(row) > 0 and row[0] == booking_id:
            # Nếu là confirm → tìm đơn đang "Chờ"
            if 'xác nhận' in new_status.lower() and 'Chờ' not in new_status:
                if len(row) > 8 and 'Chờ' in row[8]:
                    target_row = i
                    target_data = row
            # Nếu là complete → tìm đơn đang "Đã xác nhận"
            elif 'hoàn thành' in new_status.lower():
                if len(row) > 8 and 'Đã xác nhận' in row[8]:
                    target_row = i
                    target_data = row
            # Nếu là reject → tìm đơn đang "Chờ"
            elif 'từ chối' in new_status.lower():
                if len(row) > 8 and 'Chờ' in row[8]:
                    target_row = i
                    target_data = row
            else:
                # Fallback: lấy dòng đầu tiên khớp mã
                if target_row == -1:
                    target_row = i
                    target_data = row

    if target_row >= 0:
        sheet.update_cell(target_row + 1, 9, new_status)
        print(f"Sheet: {booking_id} row {target_row + 1} -> {new_status}")
        return target_data

    print(f"Sheet: {booking_id} NOT FOUND")
    return None


def get_bookings_by_date(target_date):
    sheet = get_sheet()
    data = sheet.get_all_values()
    results = []
    for row in data[1:]:
        if len(row) >= 7 and row[5] == target_date:
            results.append(row)
    return sorted(results, key=lambda x: x[6] if len(x) > 6 else '')


def get_bookings_by_status(status_keyword):
    sheet = get_sheet()
    data = sheet.get_all_values()
    results = []
    for row in data[1:]:
        if len(row) >= 9 and status_keyword in row[8]:
            results.append(row)
    return results[-20:]


def find_booking(keyword):
    sheet = get_sheet()
    data = sheet.get_all_values()
    kw = keyword.lower()
    results = []
    for row in data[1:]:
        if any(kw in str(c).lower() for c in row[:4]):
            results.append(row)
    return results[-10:]


def get_stats():
    sheet = get_sheet()
    data = sheet.get_all_values()
    today = get_today_str()
    rows = data[1:]

    return {
        'total': len(rows),
        'pending': sum(1 for r in rows if len(r) > 8 and 'Chờ' in r[8]),
        'confirmed': sum(1 for r in rows if len(r) > 8 and 'Đã xác nhận' in r[8]),
        'completed': sum(1 for r in rows if len(r) > 8 and 'hoàn thành' in r[8].lower()),
        'rejected': sum(1 for r in rows if len(r) > 8 and 'từ chối' in r[8].lower()),
        'today': sum(1 for r in rows if len(r) > 5 and r[5] == today)
    }


def clear_old_data():
    try:
        sheet = get_sheet()
        data = sheet.get_all_values()
        if len(data) <= 1:
            return {'cleared': 0}
        count = len(data) - 1
        sheet.delete_rows(2, len(data))
        return {'cleared': count}
    except Exception as e:
        print(f"Clear error: {e}")
        return {'cleared': 0, 'error': str(e)}


def get_daily_summary():
    sheet = get_sheet()
    data = sheet.get_all_values()
    if len(data) <= 1:
        return None
    rows = data[1:]
    customers = []
    for r in rows:
        customers.append({
            'id': r[0] if len(r) > 0 else '',
            'name': r[1] if len(r) > 1 else '',
            'phone': r[2] if len(r) > 2 else '',
            'service': r[4] if len(r) > 4 else '',
            'time': r[6] if len(r) > 6 else '',
            'status': r[8] if len(r) > 8 else ''
        })
    return {
        'date': get_today_str(),
        'total': len(rows),
        'completed': sum(1 for r in rows if len(r) > 8 and 'hoàn thành' in r[8].lower()),
        'confirmed': sum(1 for r in rows if len(r) > 8 and 'Đã xác nhận' in r[8]),
        'rejected': sum(1 for r in rows if len(r) > 8 and 'từ chối' in r[8].lower()),
        'pending': sum(1 for r in rows if len(r) > 8 and 'Chờ' in r[8]),
        'customers': customers
    }
