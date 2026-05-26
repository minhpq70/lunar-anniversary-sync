# Sự kiện Lịch Âm (giỗ chạp)

Web app chạy local trên Ubuntu, giúp tạo và đồng bộ các sự kiện lịch âm (ngày giỗ chạp, lễ tết) lên Google Calendar. Mỗi năm, ngày âm lịch sẽ được tính toán tự động ra ngày dương lịch tương ứng và tạo sự kiện riêng kèm nhắc nhở.

## Tính năng

- Nhập ngày sự kiện theo âm lịch (hỗ trợ tháng nhuận)
- Xem trước danh sách ngày dương lịch tương ứng cho từng năm, kèm Can Chi
- Nhắc nhở tự cấu hình (mặc định 7 ngày trước, tối đa 28 ngày)
- Đồng bộ lên Google Calendar: tạo all-day event cho từng năm với 3 lớp nhắc nhở (xem bên dưới)
- Lưu trữ sự kiện local bằng SQLite

## Yêu cầu

- Python 3.10+
- Tài khoản Google (để dùng Google Calendar API)

## Cài đặt

```bash
git clone <repo>
cd lunar-calendar
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

## Chạy app

```bash
./start.sh
# Mở trình duyệt: http://localhost:5000
```

## Cấu hình Google Calendar

1. Vào [Google Cloud Console](https://console.cloud.google.com)
2. Tạo project → bật **Google Calendar API** (APIs & Services → Library)
3. Tạo **OAuth 2.0 credentials** (APIs & Services → Credentials → Create → Desktop app)
4. Tải file JSON về, đổi tên thành `credentials.json`, đặt vào thư mục gốc project
5. Thêm email của bạn vào **Test users** (OAuth consent screen → Test users) nếu app đang ở chế độ Testing
6. Mở app → nhấn **Kết nối Google Calendar** → đăng nhập Google → cho phép quyền truy cập

Token được lưu vào `token.json` sau lần đăng nhập đầu tiên — các lần sau không cần đăng nhập lại.

## Cấu trúc thư mục

```
lunar-calendar/
├── app.py              # Flask backend, routes, Google Calendar API
├── lunar_utils.py      # Chuyển đổi âm lịch ↔ dương lịch
├── requirements.txt
├── start.sh            # Script khởi động
├── credentials.json    # OAuth credentials (tự thêm, không commit)
├── token.json          # Token Google (tự sinh, không commit)
├── events.db           # SQLite database (tự sinh)
└── templates/
    └── index.html      # Giao diện web
```

## Lưu ý kỹ thuật

**Tại sao không dùng RRULE (recurring event)?**
Google Calendar's RRULE không hỗ trợ lặp theo lịch âm. Mỗi năm cùng một ngày âm lịch rơi vào ngày dương khác nhau (ví dụ: 15/3 âm = 12/04/2025, nhưng = 01/05/2026). Do đó app tạo sự kiện riêng cho từng năm thay vì dùng recurrence rule.

**All-day event:** Sự kiện được tạo dạng all-day (dùng trường `date` thay vì `dateTime`) để phù hợp với tính chất ngày giỗ/lễ không gắn với giờ cụ thể.

**Reminder — 3 lớp nhắc nhở:**

| Loại | Thời điểm kích hoạt | Ghi chú |
|------|---------------------|---------|
| Popup | 0:00 ngày D-N (N ngày trước) | N mặc định = 7, cấu hình được |
| Popup | 0:00 ngày sự kiện | iOS giữ notification đến lần mở màn hình đầu tiên buổi sáng |
| Email | 0:00 ngày D-N | Hoạt động tốt trên Google Workspace; Gmail cá nhân tùy cài đặt |

> **Tại sao không phải 7h sáng?** Google Calendar API chỉ nhận giá trị `minutes` từ 0 đến 40320 (tính *ngược về trước* từ nửa đêm). All-day event bắt đầu lúc 00:00, nên không thể đặt reminder vào 7h sáng *cùng ngày* (cần offset dương — API không hỗ trợ). Trên iOS, notification lúc 0:00 thường hiển thị vào buổi sáng khi mở khóa màn hình lần đầu.
