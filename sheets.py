import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone, timedelta
import config, json, os

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
VN_TZ = timezone(timedelta(hours=7))  # UTC+7

def vn_now():
    """Trả về thời gian hiện tại theo giờ Việt Nam"""
    return datetime.now(VN_TZ)

def get_sheet():
    if os.path.exists('credentials.json'):
        creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    else:
        creds_json = json.loads(os.environ.get('GOOGLE_CREDENTIALS', '{}'))
        creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(config.SHEET_ID).sheet1

def get_today_str():
    return vn_now().strftime('%d/%m/%Y')

def generate_booking_id(sheet):
    data = sheet.get_all_values()
    today = get_today_str()
    max_num = 0
    for row in data[1:]:
        if len(row) >= 10 and today in row[9] and row[0].startswith('DUC'):
            try:
                num = int(row[0].replace('DUC', ''))
                max_num = max(max_num, num)
            except:
                pass
    return f"DUC{max_num + 1:02d}"

def add_booking(data):
    sheet = get_sheet()
    booking_id = generate_booking_id(sheet)
    now = vn_now().strftime('%H:%M %d/%m/%Y')

    date_raw = data.get('date', '')
    parts = date_raw.split('-')
    date_formatted = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else date_raw

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

    next_row = len(sheet.get_all_values()) + 1
    cell_range = f'A{next_row}:J{next_row}'
    sheet.update(cell_range, [row])
    print(f"Sheet: {booking_id} -> row {next_row} ({cell_range}) at {now} VN time")
    return booking_id, date_formatted

def update_status(booking_id, new_status):
    sheet = get_sheet()
    data = sheet.get_all_values()
    target_row = -1

    for i, row in enumerate(data):
        if row and row[0] == booking_id:
            if 'xác nhận' in new_status.lower() and 'Chờ' not in new_status and 'Chờ' in row[8]:
                target_row = i
                break
            if 'hoàn thành' in new_status.lower() and 'Đã xác nhận' in row[8]:
                target_row = i
                break
            if 'từ chối' in new_status.lower() and 'Chờ' in row[8]:
                target_row = i
                break

    # Fallback: tìm theo ID
    if target_row < 0:
        for i, row in enumerate(data):
            if row and row[0] == booking_id:
                target_row = i
                break

    if target_row >= 0:
        sheet.update_cell(target_row + 1, 9, new_status)
        print(f"Status: {booking_id} -> {new_status} (row {target_row + 1}) at {vn_now().strftime('%H:%M %d/%m/%Y')} VN")
        return data[target_row]
    print(f"Status: {booking_id} NOT FOUND")
    return None

def get_bookings_by_date(target_date):
    sheet = get_sheet()
    results = [row for row in sheet.get_all_values()[1:] if len(row) >= 7 and row[5] == target_date]
    return sorted(results, key=lambda x: x[6] if len(x) > 6 else '')

def get_bookings_by_status(status_keyword):
    sheet = get_sheet()
    results = [row for row in sheet.get_all_values()[1:] if len(row) >= 9 and status_keyword in row[8]]
    return results[-20:]

def find_booking(keyword):
    sheet = get_sheet()
    kw = keyword.lower()
    results = [row for row in sheet.get_all_values()[1:] if any(kw in str(c).lower() for c in row[:4])]
    return results[-10:]

def get_stats():
    sheet = get_sheet()
    rows = sheet.get_all_values()[1:]
    today = get_today_str()
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
        print(f"Cleared {count} rows at {vn_now().strftime('%H:%M %d/%m/%Y')} VN")
        return {'cleared': count}
    except Exception as e:
        print(f"Clear error: {e}")
        return {'cleared': 0, 'error': str(e)}

def get_daily_summary():
    sheet = get_sheet()
    rows = sheet.get_all_values()[1:]
    if not rows:
        return None
    customers = [{
        'id': r[0] if len(r) > 0 else '',
        'name': r[1] if len(r) > 1 else '',
        'phone': r[2] if len(r) > 2 else '',
        'service': r[4] if len(r) > 4 else '',
        'time': r[6] if len(r) > 6 else '',
        'status': r[8] if len(r) > 8 else ''
    } for r in rows]
    return {
        'date': get_today_str(),
        'total': len(rows),
        'completed': sum(1 for r in rows if len(r) > 8 and 'hoàn thành' in r[8].lower()),
        'confirmed': sum(1 for r in rows if len(r) > 8 and 'Đã xác nhận' in r[8]),
        'rejected': sum(1 for r in rows if len(r) > 8 and 'từ chối' in r[8].lower()),
        'pending': sum(1 for r in rows if len(r) > 8 and 'Chờ' in r[8]),
        'customers': customers
    }
