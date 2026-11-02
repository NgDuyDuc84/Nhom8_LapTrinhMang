# Kiến trúc NetGuard

## Sơ đồ khối

~~~text
ui.main_window.MainWindow (B)
              │ Qt signals / BackendBase
              ▼
          backend.py (A)
        ┌─────┼───────────────┐
        ▼     ▼               ▼
 services/  core/          extras/ (C)
  scan loop  ARP / ICMP     OUI / MAC / PDF
  ping monitor traceroute   CSV / Wi-Fi / notify
        └─────┼───────────────┘
              ▼
         db/repository.py
              ▼
         db/database.py
              ▼
       data/netguard.db
~~~

## Luồng dữ liệu

- core/ thực hiện I/O mạng và không import Qt. arp_scanner quét LAN; arp_listener chỉ nghe
  thụ động; icmp đo RTT; traceroute tìm đường đi; diagnosis nhận thống kê và trả kết luận
  bằng hàm thuần.
- services/ chạy trong các luồng nền, ghép core/ với repository. Callback báo thiết bị,
  cảnh báo, mẫu ping và kết luận; tầng này không import Qt.
- db/repository.py chuyển dataclass sang SQLite và ngược lại. db/database.py giữ một kết nối
  WAL, dùng khóa luồng và lưu thời gian ISO 8601 theo GMT+7.
- backend.py là cầu nối duy nhất của UI với lõi: khởi động/dừng dịch vụ, cung cấp truy vấn,
  đổi callback nền thành Qt signals, và gom dữ liệu để yêu cầu xuất PDF.
- ui/fake_data.py cung cấp FakeBackend cho B. UI chọn Backend hoặc FakeBackend nhưng dùng
  cùng các signal/hàm trong BackendBase.
- extras/ do C sở hữu. Phần A chỉ gọi các module này qua chữ ký đã thống nhất; riêng PDF
  sẽ báo lỗi tiếng Việt nếu build_report còn là stub.

## Luồng khởi động

1. main.py kiểm tra môi trường rồi tạo QApplication.
2. Chế độ thật tạo Backend; chế độ --fake tạo FakeBackend.
3. Backend.start() mở SQLite, chọn card mạng, rồi chạy quét ARP, nghe ARP và ping nền.
4. UI nhận Device, Alert, PingResult, Diagnosis và list[Hop] qua signals.
5. Khi thoát, aboutToQuit gọi Backend.stop() để dừng listener và các luồng nền trước khi
   đóng SQLite.

## Chế độ CLI

main.py --cli gọi trực tiếp dịch vụ/core, không khởi tạo Qt. monitor hiển thị thiết bị và
cảnh báo; diagnose hiển thị ba mốc ping và kết luận; trace hiển thị các hop; scan quét ARP
một lần. Trên Windows, traceroute dùng tracert.exe để theo routing table của hệ điều hành;
các hop không có phản hồi vẫn được điền thành *.
