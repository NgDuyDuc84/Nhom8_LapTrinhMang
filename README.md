# NetGuard

Ứng dụng giám sát mạng LAN IPv4 trên Windows 10/11, có giao diện và chế độ dòng lệnh.

## Cài đặt và chạy

Cài Python 3.11 trở lên, sau đó mở PowerShell tại thư mục dự án.
Ứng dụng dùng API mạng có sẵn của Windows, **không cần cài Npcap**:

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

## Xuất file EXE trên Windows

Có hai phiên bản để chọn:

| File | Cách sử dụng |
| --- | --- |
| `output/NetGuard.exe` | Chạy trực tiếp, không cần Npcap; giám sát IP/MAC định kỳ qua Windows. |
| `output/NetGuardSetup.exe` | Cài bản Full và tạo lối tắt. Nếu thiếu Npcap, tự tải từ trang chính thức và mở trình cài để người dùng xác nhận. |
| `output/NetGuardFull.exe` | Bản Full chạy trực tiếp trên máy đã có Npcap; khôi phục quét và nghe gói ARP thụ động. |

Hai bản dùng cùng giao diện, nhưng lưu dữ liệu cạnh EXE tương ứng. Chế độ
`--history` của cả hai bản không bật dịch vụ giám sát.

Chạy tại thư mục dự án sau khi đã tạo `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

Để tạo cả hai bản và bộ cài:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1 -Edition All
```

`-Edition Full` chỉ build bản Full; `-Edition Setup` build lại bộ cài sau khi đã
có `output/NetGuardFull.exe`. Bộ cài xác minh SHA256 của chương trình được nhúng,
chép vào thư mục do người dùng chọn, giữ dữ liệu cũ và tạo lối tắt Desktop/Start Menu.

Npcap 1.90 được **tải trực tiếp từ npcap.com khi người dùng bấm Cài đặt**, không
được nhúng trong gói. Bộ cài kiểm tra SHA256 và chữ ký Authenticode của Nmap trước
khi mở wizard chính thức; không dùng `/S` hoặc tự chấp nhận giấy phép. Nếu máy đã
nạp được Npcap thì không tải/cài lại. Cần Internet khi phải tải Npcap. Nếu Windows
yêu cầu khởi động lại, ứng dụng chỉ nên mở sau khi khởi động lại.
Xem `output/HAI_PHIEN_BAN.txt` để sử dụng bản Full và bộ cài.

Kết quả là **`output/NetGuard.exe`**, bản giao diện Windows 64-bit một file,
không cần cài Python trên máy đích. Font PDF tiếng Việt và biểu tượng được nhúng
sẵn; lịch sử mạng và cấu hình cá nhân không được đóng gói.

Đặt EXE trong thư mục có quyền ghi. Nhấp đúp để giám sát và chấp nhận UAC.
Máy đích **không cần Python hay Npcap**. Quét ARP, danh sách card mạng và
kiểm tra gateway dùng API có sẵn của Windows. Quyền Administrator vẫn được
yêu cầu để các phép đo ICMP hoạt động.
`output/Mo_LichSu.cmd` mở chế độ chỉ xem lịch sử/báo cáo, không xin quyền
Administrator. Các lệnh CLI tiếp tục chạy từ mã nguồn như hướng dẫn trên.

`data/` và `logs/` được tạo cạnh EXE, giữ nguyên sau khi đóng ứng dụng.
Muốn mang lịch sử cũ theo, thoát ứng dụng rồi sao chép thêm `data/` vào cạnh EXE.
Xem `output/HUONG_DAN.txt` để sử dụng bản đóng gói.

## Chức năng hiện có

- **Quét LAN bằng ARP Windows:** chủ động phân giải lại IP/MAC, theo dõi Online/Offline và quét subnet lớn theo từng phần 128 host có tiến độ. Không dùng cache ARP cũ để xác nhận Online.
- **Nhận diện thiết bị:** tra hãng ngoại tuyến, gợi ý tên/loại từ thông tin LAN; cho sửa tên, ghi chú và loại thiết bị.
- **Thiết bị tin cậy:** lưu danh sách đã xác nhận và cảnh báo thiết bị chưa tin cậy sau khi hoàn tất thiết lập.
- **Giám sát IP/MAC định kỳ:** chủ động kiểm tra MAC gateway và đọc thay đổi bảng ARP Windows; hỗ trợ cảnh báo thay đổi MAC router và xác nhận mốc MAC. Không bắt gói ARP thụ động; có thể bỏ sót thay đổi giữa các lần kiểm tra. Cache ARP chỉ dùng để quan sát IP/MAC, không xác nhận thiết bị đang Online.
- **Đo và chẩn đoán kết nối:** RTT, mất gói, biểu đồ và nhận định suy giảm tại router, hop sau gateway hoặc đích ngoài. Lỗi đo/thiếu dữ liệu được phân biệt với mất gói.
- **Traceroute:** xem các hop trên đường đi và lưu kết quả để tra cứu.
- **Cảnh báo trong ứng dụng:** tìm kiếm, phân trang, đánh dấu đã xử lý; mặc định chỉ hiển thị hồ sơ của mạng đang kết nối.
- **Lịch sử và hồ sơ mạng:** lưu SQLite riêng theo mạng, xem hồ sơ cũ, sao lưu/khôi phục và cấu hình thời gian giữ dữ liệu. Dữ liệu nằm trong `data/`; dùng Công cụ để mở lịch sử mạng khác.
- **Quét Wi-Fi:** xem AP, băng tần, kênh, tín hiệu và gợi ý kênh 2.4 GHz theo các AP quan sát được.
- **Xuất báo cáo:** PDF tiếng Việt theo khoảng thời gian tối đa 31 ngày và CSV danh sách thiết bị. Font PDF và giấy phép được kèm trong `assets/fonts/`.

ARP chỉ quan sát được IPv4 trong cùng miền broadcast. MAC/tên thiết bị không xác thực danh tính; chẩn đoán ICMP và gợi ý kênh Wi-Fi là các nhận định từ dữ liệu đo, không chứng minh toàn bộ Internet hay chất lượng phổ vô tuyến.
