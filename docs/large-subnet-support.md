# Hỗ trợ subnet lớn - 12/11/2026

Lỗi cũ xuất phát từ ba giới hạn độc lập: từ chối subnet trên 1.024 host, chỉ giữ tối đa 4.096 claim trong một lần quét toàn mạng và chỉ lưu 10.000 hồ sơ MAC. Chỉ tăng một hằng số không giải quyết được bộ nhớ, thời gian dừng và hai giới hạn còn lại.

## Hành vi mới

- Chấp nhận IPv4 subnet lớn và CIDR hợp lệ nằm trong subnet của card. Dải được tính lười, không tạo sẵn toàn bộ chuỗi địa chỉ hay packet.
- Mỗi phần quét tối đa 1.024 địa chỉ và thêm gateway nếu gateway thuộc dải nhưng nằm ngoài phần đó. Dựng/gửi tối đa 64 packet/lô; giữ giãn cách 1 ms/gói, hai vòng mặc định và kiểm tra hủy giữa các lô.
- `/18` có 16.382 host được phủ bằng 16 phần. Kết quả được ghi/cập nhật UI từng phần. Worker nghỉ 1 giây giữa các phần; sau phần cuối mới nghỉ theo chu kỳ thông thường. Không mở nhiều lượt quét đồng thời.
- Chỉ tiến vị trí khi phần quét đã ghi CSDL thành công. Lỗi capture, đổi generation, hủy hoặc rollback không làm bỏ qua phần đó. Đổi kết nối đặt lại tiến độ; Làm mới cùng mạng tiếp tục phần kế tiếp.
- Chỉ IP thực sự được gửi trong phần thành công mới tích lũy lần vắng mặt. Thiết bị ở phần khác giữ trạng thái cũ/chưa xác minh; ba lần không thấy tính theo ba lần kiểm tra IP đó, không theo ba phần bất kỳ.
- Ngân sách hồ sơ là `max(10000, 4 * subnet.num_addresses)`: `/18` cho phép 65.536 hồ sơ MAC, đủ địa chỉ và biến động MAC thông thường. Trần 4.096 claim áp dụng cho một phần tối đa 1.025 IP, không cho toàn bộ 16.382 host. Ngân sách chống lưu lượng/MAC bất thường vẫn được giữ.
- UI hiển thị số địa chỉ đã kiểm tra trong vòng hiện tại, tổng host và bảng 250 thiết bị/trang. Tổng thiết bị/Online/chưa tin cậy vẫn tính trên toàn hồ sơ. CLI scan đi qua mọi phần và gộp quan sát lặp.

## Sử dụng và kiểm chứng

Thoát bản đang chạy và mở lại `Mo_NetGuard.cmd`. Để trống **Công cụ → Cài đặt → Dải quét tùy chọn** nếu muốn phủ toàn subnet; CIDR nhỏ đã tự đặt trước đó vẫn được giữ. Cấu hình thay đổi có hiệu lực sau khi mở lại.

249 test đạt, coverage 77%, Ruff và pip check đạt. Có kiểm tra đầy đủ 16 phần `/18`, lưu/hiển thị 16.382 hồ sơ, chống Offline sai, hủy/thử lại và dải `/0` chỉ ở mức tính địa chỉ. Đã render/kiểm tra giao diện 1.280 × 840 ở trang đầu và trang cuối của danh sách giả lập. Không gửi ARP thật trong bộ kiểm thử. Không thay schema hoặc xóa dữ liệu hiện có.

Số host trong subnet là số địa chỉ có thể kiểm tra, không chứng minh có từng đó thiết bị Online. Wi-Fi trường có client isolation/VLAN hoặc thiết bị không trả ARP vẫn có thể chỉ thấy một phần thiết bị. Mạng càng lớn thì thời gian phủ và thời gian xác nhận Offline càng dài; thời gian thực tế phụ thuộc driver và mạng, chưa nghiệm thu trực tiếp trên Wi-Fi trường.
