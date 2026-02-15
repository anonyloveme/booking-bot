import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import config
import json
import os

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_sheet():
    """Kết nối Google Sheets"""
    # Hỗ trợ cả file và environment variable
    if os.path.exists('credentials.json'):
        creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    else:
        # Đọc từ env (dùng cho Render)
        creds_json = json.loads(os.environ.get('GOOGLE_CREDENTIALS', '{}'))
        creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
    
    client = gspread.authorize(creds)
    sheet = client.open_by_key(config.SHEET_ID).sheet1
    return sheet

def add_booking(data):
    """Thêm booking mới vào Sheet"""
    sheet = get_sheet()
    booking_id = 'BK' + datetime.now().strftime('%Y%m%d%H%M%S')
    now = datetime.now().strftime('%H:%M %d/%m/%Y')
    
    # Chuyển ngày từ yyyy-mm-dd sang dd/mm/yyyy
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
    """Cập nhật trạng thái booking"""
    sheet = get_sheet()
    data = sheet.get_all_values()
    for i, row in enumerate(data):
        if row[0] == booking_id:
            sheet.update_cell(i + 1, 9, new_status)
            return row
    return None

def get_bookings_by_date(target_date):
    """Lấy booking theo ngày (dd/mm/yyyy)"""
    sheet = get_sheet()
    data = sheet.get_all_values()
    results = []
    for row in data[1:]:  # Bỏ header
        if len(row) >= 9 and row[5] == target_date:
            results.append(row)
    return sorted(results, key=lambda x: x[6])  # Sắp xếp theo giờ

def get_bookings_by_status(status_keyword):
    """Lấy booking theo trạng thái"""
    sheet = get_sheet()
    data = sheet.get_all_values()
    results = []
    for row in data[1:]:
        if len(row) >= 9 and status_keyword in row[8]:
            results.append(row)
    return results[-20:]  # Lấy 20 gần nhất

def find_booking(keyword):
    """Tìm kiếm booking"""
    sheet = get_sheet()
    data = sheet.get_all_values()
    keyword_lower = keyword.lower()
    results = []
    for row in data[1:]:
        if any(keyword_lower in str(cell).lower() for cell in row[:4]):
            results.append(row)
    return results[-10:]

def get_stats():
    """Thống kê tổng quan"""
    sheet = get_sheet()
    data = sheet.get_all_values()
    today = datetime.now().strftime('%d/%m/%Y')
    
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
