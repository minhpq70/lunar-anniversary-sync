# Sự kiện Lịch Âm (giỗ chạp)

Web app chạy local trên Ubuntu, giúp tạo và đồng bộ các sự kiện lịch âm (ngày giỗ chạp, lễ tết) lên Google Calendar. Mỗi năm, ngày âm lịch được tính toán tự động ra ngày dương lịch tương ứng và tạo sự kiện riêng kèm nhắc nhở.

## Tính năng

- Nhập ngày sự kiện theo âm lịch (hỗ trợ tháng nhuận)
- Xem trước danh sách ngày dương lịch tương ứng cho từng năm, kèm Can Chi
- Nhắc nhở tự cấu hình (mặc định 7 ngày trước, tối đa 28 ngày)
- Đồng bộ lên Google Calendar: tạo all-day event cho từng năm với 3 lớp nhắc nhở
- Email thông báo bổ sung: thêm CC email (được thêm làm attendee, nhận invitation và reminder)
- Cảnh báo khi thêm sự kiện trùng ngày âm lịch
- Xóa sự kiện đồng thời xóa luôn trên Google Calendar (theo event ID hoặc tìm theo tên)
- Lưu trữ sự kiện local bằng SQLite

## Yêu cầu

- Python 3.10+
- Tài khoản Google (để dùng Google Calendar API)

## Cài đặt

```bash
git clone https://github.com/minhpq70/lunar-anniversary-sync
cd lunar-anniversary-sync
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

## Chạy app

```bash
./start.sh
# Mở trình duyệt: http://localhost:5001
```

## Cấu hình Google Calendar

1. Vào [Google Cloud Console](https://console.cloud.google.com)
2. Tạo project → bật **Google Calendar API** (APIs & Services → Library)
3. Cấu hình **OAuth consent screen**:
   - Chọn **External** → điền App name, email
   - Mục **Audience** → **Test users** → thêm email Google của bạn
4. Tạo **OAuth 2.0 credentials**: Credentials → Create → **Desktop app**
5. Tải file JSON về, đổi tên thành `credentials.json`, đặt vào thư mục gốc project
6. Mở app → nhấn **Kết nối Google Calendar** → đăng nhập → cho phép quyền truy cập

> Nếu thấy màn hình "Google hasn't verified this app": nhấn **Advanced** → **Go to app (unsafe)** — bình thường với app chế độ Testing.

Token được lưu vào `token.json` sau lần đăng nhập đầu tiên — các lần sau không cần đăng nhập lại.

## Cấu trúc thư mục

```
lunar-anniversary-sync/
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
Google Calendar's RRULE không hỗ trợ lặp theo lịch âm. Mỗi năm cùng một ngày âm lịch rơi vào ngày dương khác nhau (ví dụ: 15/3 âm = 12/04/2025, nhưng = 01/05/2026). App tạo sự kiện riêng cho từng năm thay vì dùng recurrence rule.

**All-day event:** Sự kiện được tạo dạng all-day (trường `date` thay vì `dateTime`) để phù hợp với tính chất ngày giỗ/lễ không gắn giờ cụ thể.

**Reminder — 3 lớp nhắc nhở:**

| Loại | Thời điểm kích hoạt | Ghi chú |
|------|---------------------|---------|
| Popup | 0:00 ngày D-N (N ngày trước) | N mặc định = 7, cấu hình được |
| Popup | 0:00 ngày sự kiện | iOS giữ notification đến lần mở màn hình đầu tiên buổi sáng |
| Email | 0:00 ngày D-N | Hoạt động tốt trên Google Workspace; Gmail cá nhân tùy cài đặt |

> **Tại sao không phải 7h sáng?** Google Calendar API chỉ nhận `minutes` từ 0–40320 (tính ngược từ nửa đêm). All-day event bắt đầu lúc 00:00 nên không thể đặt reminder sau nửa đêm cùng ngày (cần offset dương — API không hỗ trợ). Trên iOS, notification 0:00 thường hiển thị khi mở màn hình lần đầu buổi sáng.

**Email CC (attendees):** Google Calendar API không hỗ trợ CC trực tiếp trên reminder email. Giải pháp: thêm email bổ sung làm attendee — họ nhận invitation email ngay khi event được tạo. Nếu accept, event vào calendar của họ kèm reminder riêng.

**PKCE (OAuth2):** `google-auth-oauthlib` >= 1.0 tự động dùng PKCE (`autogenerate_code_verifier=True`). `code_verifier` được lưu vào Flask session trong bước redirect và khôi phục lại trong callback để tránh lỗi `invalid_grant: Missing code verifier`.
