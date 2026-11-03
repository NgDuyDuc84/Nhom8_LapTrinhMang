
# BÁO CÁO CHẠY THỰC TẾ NETGUARD

## 1. Mục đích

Ghi nhận quá trình chạy và kiểm tra các chức năng
của hệ thống giám sát mạng NetGuard.

## 2. Môi trường thực hiện

- Hệ điều hành: Windows
- Python: 3.14.5
- Công cụ lập trình: Visual Studio Code
- Công cụ kiểm thử: pytest 9.2.0

## 3. Các chức năng đã kiểm tra

### 3.1. Kiểm thử chẩn đoán mạng

- Số bài kiểm thử: 12
- Kết quả: 12 PASS, 0 FAIL

### 3.2. Mô phỏng tình huống mạng

Đã kiểm thử bằng dữ liệu giả lập:
- Phát hiện trùng địa chỉ IP.
- Xác định trường hợp không trùng IP.
- Phát hiện thiết bị mới.
- Phát hiện thiết bị mất kết nối.

Kết quả: 4 PASS, 0 FAIL.

### 3.3. Cảnh báo Zalo

Đã kiểm thử:
- Định dạng nội dung cảnh báo.
- Cảnh báo mức warning.
- Chế độ chạy thử dry-run.
- Trường hợp chưa cấu hình API.

Kết quả: 4 PASS, 0 FAIL.

Lưu ý: Chưa thực hiện gửi tin nhắn Zalo thật.

### 3.4. Quét Wi-Fi

Đã chạy lệnh:

python -m extras.wifi_channels

Kết quả:
- Đọc được thông tin các mạng Wi-Fi xung quanh.
- Hiển thị SSID, BSSID, kênh và tín hiệu.
- Kênh 2.4 GHz được chương trình đề xuất: 1.

### 3.5. Xuất báo cáo PDF

Đã chạy thử chức năng tạo báo cáo PDF.

File kiểm tra:
exports/netguard_test.pdf

Đã xác nhận báo cáo có 7 mục.

Chưa xác nhận đầy đủ chất lượng hiển thị
của biểu đồ và phông chữ.

## 4. Kết quả kiểm thử tự động

Lệnh thực hiện:

python -m pytest tests/test_diagnosis.py tests/test_simulate_network.py tests/test_zalo_notify.py -v

Kết quả:

20 passed in 0.74s

## 5. Minh chứng

Cần bổ sung ảnh chụp:
- Terminal hiển thị 20 bài kiểm thử PASS.
- Terminal quét Wi-Fi và đề xuất kênh.
- Báo cáo PDF đã tạo.
- Giao diện chính NetGuard khi chạy thành công.

## 6. Hạn chế

- Chưa xác nhận kiểm thử tích hợp toàn bộ NetGuard.
- Chưa kiểm thử gửi cảnh báo Zalo thực tế.
- Mô phỏng xung đột IP sử dụng dữ liệu giả lập.
- Chưa có kết quả kiểm thử trên nhiều môi trường mạng.

## 7. Kết luận

Các chức năng đã kiểm tra có kết quả phù hợp
với những tình huống kiểm thử đã xây dựng.

Hệ thống cần tiếp tục được kiểm thử tích hợp
và chạy thực tế trước khi nghiệm thu.
