from lunardate import LunarDate
from datetime import timedelta

WEEKDAYS_VI = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ Nhật']

LUNAR_MONTHS_VI = {
    1: 'Giêng', 2: 'Hai', 3: 'Ba', 4: 'Tư', 5: 'Năm', 6: 'Sáu',
    7: 'Bảy', 8: 'Tám', 9: 'Chín', 10: 'Mười', 11: 'Mười Một', 12: 'Chạp'
}

CAN = ['Giáp', 'Ất', 'Bính', 'Đinh', 'Mậu', 'Kỷ', 'Canh', 'Tân', 'Nhâm', 'Quý']
CHI = ['Tý', 'Sửu', 'Dần', 'Mão', 'Thìn', 'Tỵ', 'Ngọ', 'Mùi', 'Thân', 'Dậu', 'Tuất', 'Hợi']

def get_can_chi(lunar_year):
    can = CAN[(lunar_year - 4) % 10]
    chi = CHI[(lunar_year - 4) % 12]
    return f"{can} {chi}"

def lunar_to_solar(lunar_year, lunar_month, lunar_day, leap=False):
    try:
        ld = LunarDate(lunar_year, lunar_month, lunar_day, leap)
        return ld.toSolarDate()
    except Exception:
        return None

def generate_solar_dates(lunar_month, lunar_day, start_year, end_year, leap=False, reminder_days=7):
    results = []
    for year in range(start_year, end_year + 1):
        solar = lunar_to_solar(year, lunar_month, lunar_day, leap)
        if solar:
            reminder = solar - timedelta(days=reminder_days)
            month_name = LUNAR_MONTHS_VI.get(lunar_month, str(lunar_month))
            leap_str = ' (nhuận)' if leap else ''
            results.append({
                'lunar_year': year,
                'can_chi': get_can_chi(year),
                'lunar_str': f"Ngày {lunar_day} tháng {month_name}{leap_str}",
                'solar_date': solar.isoformat(),
                'solar_str': solar.strftime('%d/%m/%Y'),
                'reminder_date': reminder.strftime('%d/%m/%Y'),
                'reminder_iso': reminder.isoformat(),
                'day_of_week': WEEKDAYS_VI[solar.weekday()],
                'is_past': solar.isoformat() < __import__('datetime').date.today().isoformat(),
            })
    return results
