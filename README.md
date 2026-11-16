# NetGuard

Ứng dụng giám sát mạng LAN IPv4 trên Windows 10/11, có giao diện và chế độ dòng lệnh.

## Cài đặt và chạy

Cài Python 3.11 trở lên và [Npcap](https://npcap.com/), sau đó mở PowerShell tại thư mục dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

- Mở **Mo_NetGuard.cmd** và chọn **Yes** khi Windows hỏi quyền để bắt đầu giám sát.
- Mở **Mo_LichSu.cmd** để xem lịch sử, sao lưu và xuất báo cáo mà không bật dịch vụ giám sát.
- Đóng cửa sổ bằng **X** hoặc **Alt+F4** để thoát và dừng các dịch vụ.
- Nếu không mở được, xem `logs/startup.log`; lỗi khi chạy nằm ở `logs/netguard.log`.

Trong giao diện, bấm **Làm mới mạng** để quét/đo lại. Đánh dấu các thiết bị quen thuộc là **Tin cậy**, rồi chọn **Công cụ → Hoàn tất thiết lập / Bật cảnh báo**. Mở **Công cụ → Cài đặt** để chọn card, dải quét và ngưỡng đo; thay đổi cấu hình có hiệu lực sau khi mở lại.

Có thể chạy bằng dòng lệnh trong terminal có quyền thích hợp:

```powershell
.\.venv\Scripts\python.exe main.py --cli scan
.\.venv\Scripts\python.exe main.py --cli monitor
.\.venv\Scripts\python.exe main.py --cli baseline
.\.venv\Scripts\python.exe main.py --cli diagnose
.\.venv\Scripts\python.exe main.py --cli trace 1.1.1.1
```

## Chức năng hiện có

- **Quét LAN bằng ARP:** tìm IP/MAC, theo dõi Online/Offline và quét subnet lớn theo từng phần có tiến độ.
- **Nhận diện thiết bị:** tra hãng ngoại tuyến, gợi ý tên/loại từ thông tin LAN; cho sửa tên, ghi chú và loại thiết bị.
- **Thiết bị tin cậy:** lưu danh sách đã xác nhận và cảnh báo thiết bị chưa tin cậy sau khi hoàn tất thiết lập.
- **Bất thường ARP:** phát hiện nhiều MAC cùng quảng bá IP, thay đổi MAC gateway và một MAC quảng bá nhiều IP; hỗ trợ xác nhận mốc MAC router.
- **Đo và chẩn đoán kết nối:** RTT, mất gói, biểu đồ và nhận định suy giảm tại router, hop sau gateway hoặc đích ngoài. Lỗi đo/thiếu dữ liệu được phân biệt với mất gói.
- **Traceroute:** xem các hop trên đường đi và lưu kết quả để tra cứu.
- **Cảnh báo trong ứng dụng:** tìm kiếm, phân trang, đánh dấu đã xử lý; mặc định chỉ hiển thị hồ sơ của mạng đang kết nối.
- **Lịch sử và hồ sơ mạng:** lưu SQLite riêng theo mạng, xem hồ sơ cũ, sao lưu/khôi phục và cấu hình thời gian giữ dữ liệu. Dữ liệu nằm trong `data/`; dùng Công cụ để mở lịch sử mạng khác.
- **Quét Wi-Fi:** xem AP, băng tần, kênh, tín hiệu và gợi ý kênh 2.4 GHz theo các AP quan sát được.
- **Xuất báo cáo:** PDF tiếng Việt theo khoảng thời gian tối đa 31 ngày và CSV danh sách thiết bị. Font PDF và giấy phép được kèm trong `assets/fonts/`.

ARP chỉ quan sát được IPv4 trong cùng miền broadcast. MAC/tên thiết bị không xác thực danh tính; chẩn đoán ICMP và gợi ý kênh Wi-Fi là các nhận định từ dữ liệu đo, không chứng minh toàn bộ Internet hay chất lượng phổ vô tuyến.
