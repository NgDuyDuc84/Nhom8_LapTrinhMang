# Tiến độ thực hiện theo từng bước

Theo yêu cầu của người dùng: hoàn tất từng mục, dừng để người dùng kiểm tra, chỉ chuyển sang mục tiếp theo sau khi người dùng đồng ý.

| Mục | Công việc | Trạng thái |
|---|---|---|
| 1 | Mở ứng dụng dễ hơn, không phải tự mở PowerShell Administrator | Người dùng đã xác nhận và cho tiếp tục mục 2 |
| 2 | Nút làm mới mạng/dữ liệu theo yêu cầu | Đã triển khai, kiểm thử tự động và kiểm tra bố cục; chờ người dùng kiểm tra thực tế |
| 3 | Nhận diện thiết bị dễ hiểu từ MAC, hãng và các nguồn thông tin bổ sung | Chưa thực hiện |
| 4 | Xử lý từng nhóm vấn đề trong báo cáo rà soát | Chưa thực hiện; mỗi nhóm là một lượt kiểm tra riêng |

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
