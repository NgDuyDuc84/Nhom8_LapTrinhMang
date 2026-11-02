
# BÁO CÁO KIỂM THỬ NETGUARD

## 1. Mục đích

Kiểm tra tính chính xác của các chức năng:
- Chẩn đoán tình trạng kết nối mạng.
- Phát hiện xung đột địa chỉ IP.
- Phát hiện thiết bị mới và thiết bị mất kết nối.
- Tạo nội dung cảnh báo Zalo.

## 2. Môi trường kiểm thử

- Hệ điều hành: Windows
- Python: 3.14.5
- Pytest: 9.2.0
- Công cụ: Visual Studio Code

## 3. Phương pháp kiểm thử

Sử dụng pytest để kiểm thử tự động các hàm Python.

Các tình huống mạng và cảnh báo được kiểm thử
bằng dữ liệu giả lập, không tác động đến mạng thật.

## 4. Kết quả kiểm thử

| Nhóm kiểm thử | Tổng số | PASS | FAIL |
|---|---:|---:|---:|
| Chẩn đoán mạng | 12 | 12 | 0 |
| Mô phỏng mạng | 4 | 4 | 0 |
| Cảnh báo Zalo | 4 | 4 | 0 |
| **Tổng cộng** | **20** | **20** | **0** |

Thời gian thực thi: 0.74 giây.

Tỷ lệ kiểm thử thành công: 100%.

## 5. Lệnh kiểm thử

```powershell
python -m pytest tests/test_diagnosis.py tests/test_simulate_network.py tests/test_zalo_notify.py -v
```

## 6. Đánh giá

- Các hàm chẩn đoán vượt qua 12 bài kiểm thử.
- Chức năng mô phỏng phát hiện đúng các tình huống được kiểm thử.
- Chức năng tạo cảnh báo Zalo vượt qua 4 bài kiểm thử.
- Chưa kiểm thử gửi thông báo Zalo thực tế.
- Chưa thực hiện kiểm thử tích hợp toàn bộ hệ thống.

## 7. Kết luận

Toàn bộ 20 bài kiểm thử tự động đã PASS.

Các chức năng được kiểm thử đáp ứng những tình huống
đã xây dựng. Cần tiếp tục kiểm thử tích hợp và
chạy thực tế trước khi nghiệm thu toàn hệ thống.
```
