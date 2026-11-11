# Các lỗi đã ghi nhận

## Quét thiết bị khi chuyển sang Wi-Fi trường có subnet lớn

- Ngày ghi nhận: 05/11/2026.
- Trạng thái: đã xác định nguyên nhân, chưa khắc phục theo yêu cầu của người dùng.
- IP quan sát được: `10.40.2.170`, mặt nạ `255.255.192.0`, gateway `10.40.0.1`.
- Mạng tương ứng: `10.40.0.0/18`, có 16.382 địa chỉ host dùng được. Đây là số địa chỉ có thể cấp, không phải số thiết bị thực tế đang kết nối.

### Nguyên nhân và biểu hiện

`config.py` đặt `MAX_SCAN_HOSTS = 1024`. Hàm `get_subnet_hosts()` trong
`core/interfaces.py` từ chối quét khi subnet có số địa chỉ host lớn hơn giới hạn
này. Đây là giới hạn phạm vi quét ARP, không phải giới hạn lưu trữ của SQLite hay
khả năng tiếp nhận kết nối của ứng dụng. Với subnet /18 trên, lượt quét bị từ chối
trước khi gửi yêu cầu ARP chủ động.

Thông tin card mạng trên UI đã cập nhật đúng sang Wi-Fi mới. Tuy nhiên, bảng thiết
bị vẫn lấy toàn bộ bản ghi trong bảng `Devices` của SQLite, chưa lọc theo mạng hiện
tại. Vì không có lượt quét mới thành công, các địa chỉ `192.168.102.x` của Wi-Fi cũ
vẫn xuất hiện. Ứng dụng đang hiển thị lịch sử đã lưu, không phải kết quả quét mới;
đây không phải một cơ chế dự phòng được thiết kế riêng. Lỗi quét hiện được ghi ra
terminal, chưa được báo rõ trên giao diện.

Giới hạn này thuộc chức năng quét thiết bị ARP. Ping gateway/Internet là luồng riêng,
không cần liệt kê toàn bộ địa chỉ trong subnet. Mạng trường còn có thể chia VLAN
hoặc cách ly thiết bị; chưa kiểm chứng các yếu tố này trong tình huống trên.

### Lời giải thích khi thuyết trình

“Hiện tại, chức năng quét thiết bị của ứng dụng được giới hạn ở các dải mạng có
tối đa 1.024 địa chỉ host. Wi-Fi trường đang sử dụng subnet /18, có khoảng 16.382
địa chỉ host nên vượt giới hạn này, khiến ứng dụng chưa thực hiện được lượt quét
mới. Trong khi đó, bảng thiết bị trên giao diện vẫn đọc lịch sử quét đã lưu trong
SQLite và chưa tách theo từng mạng, nên còn hiển thị thiết bị của Wi-Fi cũ. Đây là
hạn chế hiện tại của phần quét và hiển thị dữ liệu khi chuyển mạng.”

### Hướng xử lý đã ghi nhận, chưa triển khai

- Tách dữ liệu thiết bị theo mạng và phân biệt danh sách hiện tại với lịch sử.
- Đưa thông báo quét vượt giới hạn lên UI.
- Thiết kế quét có giới hạn phạm vi, thời gian và tiến độ cho subnet lớn.
- Kiểm tra lại tình huống đổi Wi-Fi giữa các subnet khác nhau.
