# Báo cáo kiểm thử hiện tại - 16/11/2026

Kết quả chốt sau sửa phạm vi cảnh báo trên UI: **263 test pass**, coverage dòng **78%**, Ruff và `git diff --check` đạt. Có thêm 10 trường hợp cho tab Cảnh báo; mốc trước đó sau sửa nhận diện khi đổi kết nối là 253 test. Môi trường kiểm tra là Windows/Python 3.14.7; chưa xác nhận kết quả CI trên GitHub cho thay đổi này.

Chi tiết từng lỗi/bằng chứng/giới hạn của đợt trước: [báo cáo sửa mã](remediation-report-2026-11-12.md). Các con số 20/65/145/162/243/249/253/265/283 trong tài liệu lịch sử là mốc cũ, không phải kết quả hiện tại. Cảnh báo được lưu SQLite và hiển thị trong tab Cảnh báo/thanh trạng thái; đóng cửa sổ sẽ thoát và dừng worker.

`tests/test_alert_network_scope.py` tái hiện lỗi UI đọc cảnh báo legacy lúc chưa xác định mạng bằng một test thất bại trước sửa. Bộ mới kiểm tra khởi động live không đọc legacy; đổi sang mạng không có cảnh báo; hai mạng cùng IP được tách và đặt lại tìm kiếm/trang; ngắt kết nối bỏ signal đến muộn; lựa chọn cũ không đánh dấu nhầm ID trùng ở mạng mới; lịch sử legacy được mở rõ ràng; xem lịch sử rồi quay lại live có/không có LAN; lỗi tải mạng mới không giữ dòng mạng cũ; sự kiện từ mạng cũ không thay danh sách/thanh trạng thái. Các test dùng SQLite tạm và Qt thật, không phát gói mạng. Kiểm tra đóng GUI trong tiến trình riêng vẫn xác nhận đúng chế độ live/history.

Bộ hiện tại kiểm tra capture startup/runtime/cleanup, worker refresh/stop, network context/session, transaction/chống lặp, thiết bị/nhận diện, parser mDNS/NBNS, ICMP socket, chẩn đoán, CSV, PDF, UI và launcher. Các phép thử dùng DB tạm và I/O mạng giả. Có kiểm tra metadata NLM/card thật theo chế độ chỉ đọc và render PDF/Qt offscreen.

Kiểm tra thật ngày 16/11/2026: đọc card/NLM ngoài sandbox, rồi quét ARP giới hạn gateway `/32` trên Wi-Fi (1 vòng, timeout 1 giây). Gateway phản hồi; OUI nhận diện gateway ZTE và card máy Intel. mDNS/NetBIOS không trả gợi ý tên trong lượt thử này. Không thay đổi kết nối và không ghi CSDL người dùng. Chi tiết nhận diện và bằng chứng hồi quy: [nhận diện thiết bị](device-identification.md).

Chưa diễn tập lỗi driver, ngắt/chuyển Wi-Fi/Ethernet vật lý, thiết bị thật vào/rời LAN, đo RF hoặc bài tải nhiều ngày. Coverage không phải bằng chứng mọi đường đi/OS đều hoạt động đúng.

Bổ sung 17 trường hợp cho subnet lớn: `/18`, `/16`, `/8`, `/0` tính lười và biên `/31`, `/32`; phủ đủ 16 phần của `/18`; gửi tối đa 64 packet/lô, hủy giữa lô; thử lại phần lỗi mạng/CSDL; reset khi đổi mạng; chỉ tăng misses trong phần đã kiểm tra; lưu 16.382 hồ sơ; phân trang/sửa đúng MAC; tiến độ và signal cũ; CLI quét đến phần cuối và gộp router lặp. Đây là dữ liệu/I/O giả, chưa phải nghiệm thu Wi-Fi trường. Chi tiết: [large-subnet-support.md](large-subnet-support.md).

Chạy lại:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest --cov -q
```
