# Báo cáo kiểm thử hiện tại - 12/11/2026

Kết quả chốt: **249 test pass**, coverage dòng **77%**, Ruff đạt và pip check không báo dependency hỏng. Đã cài requirements-dev trong một venv mới trên Windows/Python 3.14.7; CI cấu hình Windows/Python 3.12 chưa chạy trên GitHub tại lúc tạo commit local.

Chi tiết từng lỗi/bằng chứng/giới hạn: [báo cáo sửa mã](remediation-report-2026-11-12.md). Các con số 20/65/145/162 trong tài liệu lịch sử là mốc cũ, không phải kết quả hiện tại.

Bộ hiện tại kiểm tra capture startup/runtime/cleanup, worker refresh/stop, network context/session, transaction/chống lặp, thiết bị/nhận diện, parser mDNS/NBNS, ICMP socket, chẩn đoán, CSV, PDF, UI và launcher. Các phép thử dùng DB tạm, I/O mạng/HTTP giả và tắt outbound notifications. Có kiểm tra metadata NLM/card thật theo chế độ chỉ đọc và render PDF/Qt offscreen.

Không có kết quả diễn tập driver/mạng thật, account Telegram/Zalo thật, đo RF hoặc bài tải nhiều ngày. Coverage không phải bằng chứng mọi đường đi/OS đều hoạt động đúng.

Bổ sung 17 trường hợp cho subnet lớn: `/18`, `/16`, `/8`, `/0` tính lười và biên `/31`, `/32`; phủ đủ 16 phần của `/18`; gửi tối đa 64 packet/lô, hủy giữa lô; thử lại phần lỗi mạng/CSDL; reset khi đổi mạng; chỉ tăng misses trong phần đã kiểm tra; lưu 16.382 hồ sơ; phân trang/sửa đúng MAC; tiến độ và signal cũ; CLI quét đến phần cuối và gộp router lặp. Đây là dữ liệu/I/O giả, chưa phải nghiệm thu Wi-Fi trường. Chi tiết: [large-subnet-support.md](large-subnet-support.md).

Chạy lại:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest --cov -q
```
