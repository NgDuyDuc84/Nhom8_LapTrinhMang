# Tiến độ thực hiện theo từng bước

Theo yêu cầu của người dùng: hoàn tất từng mục, dừng để người dùng kiểm tra, chỉ chuyển sang mục tiếp theo sau khi người dùng đồng ý.

| Mục | Công việc | Trạng thái |
|---|---|---|
| 1 | Mở ứng dụng dễ hơn, không phải tự mở PowerShell Administrator | Đã triển khai và kiểm thử tự động; chờ người dùng kiểm tra thực tế |
| 2 | Nút làm mới mạng/dữ liệu theo yêu cầu | Chưa thực hiện |
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
- Chưa làm refresh mạng, nhận diện loại thiết bị hoặc sửa tiếp các lỗi trong báo cáo.
