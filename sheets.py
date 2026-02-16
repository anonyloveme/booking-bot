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

def generate_booking_id():
    """Tạo mã đơn dạng DUC01, DUC02... reset mỗi ngày"""
    sheet = get_sheet()
    data = sheet.get_all_values()
    today = get_today_str()

    # Đếm số đơn hôm nay
    count = 0
    for row in data[1:]:  # Bỏ header
        if len(row) >= 10 and today in row[9]:  # Cột J = Thời gian tạo
            count += 1

    next_num = count + 1
    return f"DUC{next_num:02d}"  # DUC01, DUC02... DUC99

def add_booking(data):
    sheet = get_sheet()
    booking_id = generate_booking_id()
    now = datetime.now().strftime('%H:%M %d/%m/%Y')

    date_parts = data.get('date', '').split('-')
    if len(date_parts) == 3:
        date_formatted = f"{date_parts[2]}/{date_parts[1]}/{date_parts[0]}"
    else:
        date_formatted = data.get('date', '')

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
    sheet.append_row(row)
    return booking_id, date_formatted

def update_status(booking_id, new_status):
    sheet = get_sheet()
    data = sheet.get_all_values()
    for i, row in enumerate(data):
        if row[0] == booking_id:
            sheet.update_cell(i + 1, 9, new_status)
            return row
    return None

def get_bookings_by_date(target_date):
    sheet = get_sheet()
    data = sheet.get_all_values()
    results = []
    for row in data[1:]:
        if len(row) >= 9 and row[5] == target_date:
            results.append(row)
    return sorted(results, key=lambda x: x[6])

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
    keyword_lower = keyword.lower()
    results = []
    for row in data[1:]:
        if any(keyword_lower in str(cell).lower() for cell in row[:4]):
            results.append(row)
    return results[-10:]

def get_stats():
    sheet = get_sheet()
    data = sheet.get_all_values()
    today = get_today_str()

    total = len(data) - 1
    pending = sum(1 for r in data[1:] if 'Chờ' in r[8])
    confirmed = sum(1 for r in data[1:] if 'xác nhận' in r[8] and 'Chờ' not in r[8])
    completed = sum(1 for r in data[1:] if 'hoàn thành' in r[8].lower())
    rejected = sum(1 for r in data[1:] if 'từ chối' in r[8].lower())
    today_count = sum(1 for r in data[1:] if len(r) > 5 and r[5] == today)

    return {
        'total': total,
        'pending': pending,
        'confirmed': confirmed,
        'completed': completed,
        'rejected': rejected,
        'today': today_count
    }

def clear_old_data():
    """Xóa tất cả dữ liệu cũ (giữ lại header)"""
    try:
        sheet = get_sheet()
        data = sheet.get_all_values()

        if len(data) <= 1:
            return {'cleared': 0, 'message': 'Không có dữ liệu để xóa'}

        # Đếm số dòng cần xóa
        rows_to_clear = len(data) - 1

        # Xóa tất cả trừ header (dòng 1)
        if rows_to_clear > 0:
            sheet.delete_rows(2, len(data))

        return {'cleared': rows_to_clear, 'message': f'Đã xóa {rows_to_clear} dòng'}

    except Exception as e:
        print(f"Clear data error: {e}")
        return {'cleared': 0, 'error': str(e)}

def get_daily_summary():
    """Tổng kết cuối ngày trước khi xóa"""
    sheet = get_sheet()
    data = sheet.get_all_values()

    if len(data) <= 1:
        return None

    total = len(data) - 1
    completed = sum(1 for r in data[1:] if 'hoàn thành' in r[8].lower())
    confirmed = sum(1 for r in data[1:] if 'xác nhận' in r[8] and 'Chờ' not in r[8])
    rejected = sum(1 for r in data[1:] if 'từ chối' in r[8].lower())
    pending = sum(1 for r in data[1:] if 'Chờ' in r[8])

    # Danh sách khách
    customers = []
    for row in data[1:]:
        customers.append({
            'id': row[0],
            'name': row[1],
            'phone': row[2],
            'service': row[4] if len(row) > 4 else '',
            'time': row[6] if len(row) > 6 else '',
            'status': row[8] if len(row) > 8 else ''
        })

    return {
        'date': get_today_str(),
        'total': total,
        'completed': completed,
        'confirmed': confirmed,
        'rejected': rejected,
        'pending': pending,
        'customers': customers
    }
