# Báo cáo kiểm thử hiện tại - 12/11/2026

Kết quả chốt: **232 test pass**, coverage dòng **76%**, Ruff đạt và pip check không báo dependency hỏng. Đã cài requirements-dev trong một venv mới trên Windows/Python 3.14.7; CI cấu hình Windows/Python 3.12 chưa chạy trên GitHub tại lúc tạo commit local.

Chi tiết từng lỗi/bằng chứng/giới hạn: [báo cáo sửa mã](remediation-report-2026-11-12.md). Các con số 20/65/145/162 trong tài liệu lịch sử là mốc cũ, không phải kết quả hiện tại.

Bộ hiện tại kiểm tra capture startup/runtime/cleanup, worker refresh/stop, network context/session, transaction/chống lặp, thiết bị/nhận diện, parser mDNS/NBNS, ICMP socket, chẩn đoán, CSV, PDF, UI và launcher. Các phép thử dùng DB tạm, I/O mạng/HTTP giả và tắt outbound notifications. Có kiểm tra metadata NLM/card thật theo chế độ chỉ đọc và render PDF/Qt offscreen.

Không có kết quả diễn tập driver/mạng thật, account Telegram/Zalo thật, đo RF hoặc bài tải nhiều ngày. Coverage không phải bằng chứng mọi đường đi/OS đều hoạt động đúng.

Chạy lại:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest --cov -q
```
