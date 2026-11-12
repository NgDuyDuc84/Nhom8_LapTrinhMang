# Tiến độ thực hiện theo từng bước

Yêu cầu ban đầu: dừng sau từng mục. Yêu cầu cập nhật: sửa tiếp toàn bộ các nhóm trong báo cáo rồi báo cáo tổng hợp một lần; không còn mốc chờ duyệt từng lỗi.

| Mục | Công việc | Trạng thái |
|---|---|---|
| 1 | Mở ứng dụng dễ hơn, không phải tự mở PowerShell Administrator | Người dùng đã xác nhận và cho tiếp tục mục 2 |
| 2 | Nút làm mới mạng/dữ liệu theo yêu cầu | Người dùng đã cho tiếp tục mục 3 |
| 3 | Nhận diện thiết bị dễ hiểu từ MAC, hãng và các nguồn thông tin bổ sung | Người dùng đã đồng ý bắt đầu sửa từng lỗi |
| 4 | Xử lý từng nhóm vấn đề trong báo cáo rà soát | Đã triển khai đợt sửa tổng thể; xem docs/remediation-report-2026-11-12.md |

## Mục 1 — Cách chạy

1. Nếu có bản NetGuard cũ đang chạy, chọn **Thoát** trong menu khay hệ thống trước.
2. Nhấp đúp `Mo_NetGuard.cmd` trong thư mục dự án.
3. Chọn **Yes** khi Windows hỏi quyền để mở ứng dụng. Chọn **No** sẽ hủy, không hỏi lại liên tục.

Không cần tự mở terminal Administrator hoặc kích hoạt `.venv`. GUI mở bằng `python main.py` từ terminal thường cũng tự xử lý môi trường và yêu cầu quyền. CLI giữ cách dùng cũ.

Thay đổi: launcher không còn phụ thuộc PowerShell; GUI tự dùng Python của dự án, tự xin quyền khi cần và cố định thư mục dữ liệu theo dự án. Có chặn lặp khởi động lại và hộp thoại/log cho lỗi trước khi nạp được GUI tại `logs/startup.log`.

## Kiểm chứng mục 1

- Toàn bộ test: **74 passed**; gồm 9 test mới về luồng xin quyền, hủy UAC, chọn Python, báo lỗi và giữ hành vi CLI/help.
- Chạy launcher CMD thật với `pythonw.exe` trong thư mục tạm có chữ tiếng Việt, dấu cách và `&`, từ thư mục làm việc khác: **PASS**; đúng Python `.venv` và đúng thư mục dữ liệu.
- Các test xin quyền dùng mock, không mở hộp thoại UAC hoặc dịch vụ mạng thật. Người dùng cần xác nhận lần mở thực tế bằng nút Yes và kiểm tra cửa sổ hiện lên.
- Tại mốc hoàn tất mục 1, chưa làm refresh mạng, nhận diện loại thiết bị hoặc sửa tiếp các lỗi trong báo cáo.

## Mục 2 — Làm mới mạng

Thoát bản NetGuard cũ, mở lại bằng `Mo_NetGuard.cmd`, rồi bấm **Làm mới mạng** trên thanh công cụ, cạnh **Tin cậy**.

- Nút chuyển thành **Đang làm mới…**, tạm khóa và báo tiến độ dưới thông tin kết nối.
- Đọc lại card đang hoạt động, cấu hình IPv4/gateway; quét và đo lại bằng các worker đang có. Yêu cầu chờ lượt hiện tại nếu worker đang bận, không tạo lượt quét chồng nhau.
- Khi hoàn tất, hiện thời điểm làm mới; mất LAN, thiếu gateway, lỗi đo/quét hoặc subnet quá lớn đều có thông báo. Có thể bấm lại sau khi xử lý kết nối.
- Chọn lại được card đang hoạt động sau khi đổi Wi-Fi/Ethernet. Kết quả của lượt làm mới được so với kết nối khi hoàn tất; nếu không khớp thì yêu cầu thử lại.
- Giữ tên, ghi chú, tin cậy và lịch sử CSDL. Chỉ các mẫu thống kê trong bộ nhớ được thu thập lại; chẩn đoán chờ đủ dữ liệu mới.

Kiểm chứng: **90 test pass**, gồm 16 test mới cho làm mới mạng. Có test dùng worker thật với I/O mạng giả để kiểm tra đánh thức chu kỳ dài, gộp yêu cầu lặp, tuần tự hóa scan/ping, đổi card, lỗi và thử lại. Có kiểm tra luồng khởi động thật `Backend.start()` kết nối đủ các callback làm mới, thứ tự kết quả giữa hai dịch vụ và signal trễ của lượt trước. Đã render và kiểm tra bố cục trạng thái đang làm mới, thành công và lỗi bằng Qt offscreen.

Chưa thử thao tác với mạng thật trong lượt triển khai này. Người dùng cần kiểm tra nút trên ứng dụng thực tế trước khi chuyển mục 3. Giới hạn subnet lớn và việc danh sách thiết bị còn chứa lịch sử nhiều mạng vẫn thuộc các nhóm sửa tiếp theo trong báo cáo.

## Mục 3 — Nhận diện thiết bị

- Bảng ưu tiên tên dễ hiểu, loại thiết bị và hãng. MAC/IP có trong Chi tiết hoặc bật bằng **Hiện MAC / IP**.
- Tra hãng ngoại tuyến bằng bảng Scapy, hiện có 50.825 prefix; hỗ trợ longest prefix MA-L/M/S và mục bổ sung cục bộ. Không tra hãng theo tiền tố MAC quản lý cục bộ/riêng tư.
- Kết hợp vai trò máy này/gateway, mDNS/DNS-SD, tên và dịch vụ NetBIOS để gợi ý loại. Không suy ra điện thoại/laptop từ hãng Apple/Samsung/Intel riêng lẻ.
- Hộp thoại **Chi tiết / Sửa tên** cho xem bằng chứng, thời điểm metadata cập nhật và chọn loại thủ công. Loại thủ công, tên gợi nhớ, ghi chú và tin cậy không bị nhận diện tự động ghi đè.
- Bổ sung `DeviceIdentity` vào CSDL cũ bằng cách tạo bảng mới. Tên/dịch vụ chạy ở worker có timeout, cache và gộp cập nhật UI theo lô; kết quả cũ không ghi đè IP đã đổi hoặc metadata mới hơn.
- Cảnh báo thiết bị chưa tin cậy dùng tên dễ hiểu và MAC thay vì bắt người dùng xác định qua IP.

Kiểm chứng: **145 test pass**, gồm 55 test mới của mục 3. Đã kiểm tra dữ liệu OUI thật được đóng gói, parser/socket giả, dữ liệu CSDL cũ, worker/cache/hủy, lựa chọn thủ công, UI và luồng `Backend.start()` thực tế với I/O giả. Đã render bảng và hộp thoại chi tiết bằng Qt offscreen. Chưa gửi gói khám phá lên mạng thật trong lần triển khai này.

Chi tiết: `docs/device-identification.md`. Nhóm 36 trong báo cáo (bảng OUI chỉ có hai prefix) được xử lý trong phạm vi mục này. Người dùng đã đồng ý bắt đầu mục 4; sau đó người dùng yêu cầu hoàn tất toàn bộ và báo cáo một lần.

## Mục 4 — Lỗi 01: không coi capture hỏng là quét thành công

Trước bản sửa, lỗi mở bộ bắt gói trong luồng `AsyncSniffer` có thể bị bỏ qua; scanner vẫn trả về chính máy này và khiến các thiết bị khác bị tính là vắng mặt. Đã tái hiện bằng một test thất bại trên mã cũ trước khi sửa.

- Chờ `started_callback` xác nhận bộ bắt gói sẵn sàng trước khi gửi ARP, thay khoảng ngủ cố định 0,8 giây. Thời hạn khởi tạo tối đa 3 giây.
- Kiểm tra lỗi của luồng nền và trường hợp capture tự dừng không có ngoại lệ; ngừng lượt quét khi bắt gói hỏng. Chờ phản hồi bằng `join(timeout)` để nhận lỗi ngay khi luồng kết thúc.
- Dừng và chờ đóng capture có thời hạn 1 giây; lỗi đóng hoặc chưa dừng xong đều làm lượt quét thất bại. Giữ lỗi gốc nếu đồng thời có lỗi dọn dẹp. Capture mở xong sau thời hạn khởi tạo sẽ tự nhận yêu cầu dừng qua callback; không thể cưỡng bức kết thúc một lời gọi driver bị treo vĩnh viễn trong Python.
- Chỉ trả dữ liệu sau khi hoàn tất kiểm tra và dừng. Lượt lỗi không thêm thiết bị, không cập nhật `last_seen`/lịch sử hiện diện và không tăng bộ đếm vắng mặt. Capture khỏe nhưng không có thiết bị nào trả lời vẫn là lượt quét hợp lệ.
- Thông báo thiếu quyền hướng dẫn mở `Mo_NetGuard.cmd` theo cách chạy mới.

Kiểm chứng: **162 test pass**, gồm **17 test mới** trong `tests/test_arp_scanner.py`. Dùng luồng/bao ngoại lệ thật của Scapy với I/O giả, kiểm tra lỗi khởi tạo, readiness trễ/thiếu, lỗi đọc, tự dừng, lỗi gửi/đóng, timeout và tình huống capture chết đúng lúc chuẩn bị dừng. Bốn kịch bản tích hợp với `ScanLoop` và SQLite tạm chứng minh nhiều lượt lỗi liên tiếp vẫn giữ dữ liệu/bộ đếm, rồi quét lại thành công khi capture phục hồi. Không gửi gói mạng thật hoặc ghi dữ liệu thử vào CSDL đang sử dụng.

Để kiểm tra thực tế: chọn **Thoát** ở khay hệ thống của bản cũ, mở lại bằng `Mo_NetGuard.cmd`, bấm **Làm mới mạng** và kiểm tra danh sách thiết bị. Các tình huống lỗi driver đã được kiểm thử giả lập, chưa xác nhận trên Npcap thật trong lượt sửa này.

**Cập nhật 12/11/2026:** mốc dừng sau lỗi 01 đã được người dùng thay đổi. Listener, phạm vi dữ liệu, cảnh báo, chẩn đoán, báo cáo và giao diện đã được sửa tiếp trong đợt tổng thể. Xem báo cáo sửa mã hiện tại để biết kết quả và giới hạn kiểm chứng.
