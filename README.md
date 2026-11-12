# NetGuard - giám sát LAN trên Windows

NetGuard quét ARP, nhận diện thiết bị từ MAC/OUI và thông tin LAN, đo ICMP, ghi lịch sử SQLite và xuất PDF/CSV. Phạm vi hỗ trợ là Windows 10/11, IPv4 trong LAN cùng miền broadcast; không xác thực danh tính thiết bị hoặc chứng minh toàn bộ Internet hoạt động tốt.

## Cài đặt

Cài Python 3.11 trở lên (CI dùng 3.12; môi trường kiểm tra hiện tại là 3.14.7) và Npcap từ [trang chính thức](https://npcap.com/). Tạo môi trường tại thư mục dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Không cần kích hoạt `.venv`. Không cần Matplotlib: biểu đồ PDF dùng ReportLab và font Noto Sans có giấy phép trong `assets/fonts/`.

## Mở ứng dụng

- Nhấp đúp **Mo_NetGuard.cmd**. Windows hỏi quyền bắt gói một lần; chọn Yes để giám sát. Không phải tự mở PowerShell Administrator.
- Nhấp đúp **Mo_LichSu.cmd** để mở dữ liệu/lịch sử và xuất báo cáo mà không bật dịch vụ mạng hoặc yêu cầu quyền bắt gói.
- Thoát bản đang chạy qua menu khay hệ thống trước khi mở lại sau một lần cập nhật mã. Nếu khay không khả dụng, đóng cửa sổ sẽ thoát ứng dụng.
- Chỉ một tiến trình giám sát dùng cùng thư mục dữ liệu được phép chạy. Chế độ xem lịch sử có thể dùng riêng.

Lỗi khởi động nằm ở `logs/startup.log`; lỗi dịch vụ và traceback nằm ở `logs/netguard.log` có giới hạn dung lượng.

## Dùng giao diện

Bấm **Làm mới mạng** để đọc lại card, quét và đo lại. Các yêu cầu được thực hiện trên worker có sẵn; các chu kỳ không chồng nhau. Capture hỏng hoặc kết nối đổi trong lúc quét sẽ làm lượt quét thất bại; không tăng bộ đếm vắng mặt hay ghi kết quả cũ sang mạng mới.

Bảng ưu tiên tên, loại thiết bị, hãng. **Hiện MAC / IP** hoặc **Chi tiết / Sửa tên** cho xem địa chỉ, bằng chứng và lựa chọn loại thủ công. OUI tra ngoại tuyến; MAC riêng tư/cục bộ có thể không xác định hãng. Tên, model và dịch vụ tự công bố chỉ là gợi ý.

Trong **Công cụ**:

1. Kiểm tra danh sách, đánh dấu thiết bị quen thuộc **Tin cậy**, rồi chọn **Hoàn tất thiết lập / Bật cảnh báo**. Hai thao tác này có ý nghĩa riêng. Thiết bị chưa tin cậy đã tồn tại, xuất hiện lại hoặc vừa bị bỏ tin cậy đều có thể được cảnh báo; không báo định kỳ chỉ vì hết cooldown.
2. Chọn đúng router rồi dùng **Xác nhận MAC router đã chọn** sau khi đối chiếu thiết bị thực tế. MAC này là mốc so sánh được người dùng chấp nhận, không phải xác thực mật mã.
3. Xem lịch sử thiết bị, chạy traceroute nền, xuất CSV, quét Wi-Fi hoặc mở cài đặt.
4. Sao lưu/khôi phục hồ sơ mạng bằng API backup của SQLite. Khôi phục dừng worker và tạo bản sao trước khi ghi dữ liệu.
5. Chọn **Xem hồ sơ mạng / lịch sử cũ** để xem mạng khác hoặc dữ liệu trước khi ứng dụng có định danh mạng. Quay lại theo dõi bằng lựa chọn kết nối hiện tại; chế độ bắt gói vẫn cần quyền thích hợp.

Tab Cảnh báo có tìm kiếm, trang trước/sau và đánh dấu đã xử lý. Tab Chẩn đoán có biểu đồ RTT/loss; mốc giữa được gọi là **hop sau gateway**, chưa xác minh thuộc ISP. Một hop trung gian phản hồi kém trong khi đích cuối tốt không đủ để kết luận ISP lỗi.

## Dữ liệu, nâng cấp và hồ sơ mạng

- Đường dẫn được tính từ vị trí dự án, không phụ thuộc thư mục làm việc.
- `data/netguard.db` giữ dữ liệu cũ chưa có định danh mạng; **không tự chuyển tin cậy cũ sang mọi mạng mới**.
- Các hồ sơ mới nằm ở `data/networks/<id>.db`, tách theo Network List Manager của Windows, card, subnet/gateway và nhãn bổ sung. Tên, ghi chú, tin cậy, baseline, cảnh báo và lịch sử đều ở đúng hồ sơ.
- Nếu Windows không cung cấp hồ sơ, ứng dụng yêu cầu đặt nhãn riêng qua cài đặt thay vì âm thầm dùng chung mạng. Nhãn dự phòng cần được người dùng đổi khi đổi sang mạng khác mà Windows vẫn không định danh được.
- Nâng cấp schema có version, giữ dữ liệu cũ và tạo bản sao `.pre-v3.bak` trước khi nâng cấp CSDL có dữ liệu. Bản sao và file đang dùng không đưa vào Git.
- Lưu riêng quan sát IP-MAC, kể cả nhiều MAC cùng nhận IP hoặc một MAC có nhiều IP. Không áp UNIQUE IP toàn cục.
- Ping lưu address, session và trạng thái `ok`, `timeout`, `measurement_error`, `offline`, `unavailable`. Lỗi đo/không có dữ liệu không được tính thành mất gói 0% hoặc 100%.
- Mặc định giữ lịch sử chi tiết 30 ngày; bảo trì khi mở hồ sơ và theo giờ lúc theo dõi. Giữ metadata người dùng và trạng thái biên cần thiết. Hồ sơ không theo dõi không bị tự mở để xóa dữ liệu.
- Ngân sách hồ sơ tự tăng theo subnet: tối thiểu 10.000 hoặc 4 lần số địa chỉ của subnet, lấy số lớn hơn (`/18`: 65.536 hồ sơ MAC). Mỗi phần quét tối đa 4.096 claim; detector có TTL/số mục và cảnh báo có ngân sách tổng thể. Các ngân sách chống claim/MAC bất thường không phải giới hạn số host của subnet.
- Thời gian hiển thị/lưu trữ là GMT+7. API nhận datetime có timezone sẽ chuyển về GMT+7; giữ microsecond.

Nút làm mới giữ metadata của **cùng hồ sơ**. Dữ liệu cũ không bị xóa nếu danh sách của hồ sơ mới ban đầu trống: chọn hồ sơ lịch sử cũ trong Công cụ để xem lại.

## Báo cáo

Xuất PDF chạy nền, có hủy và ghi file hoàn tất bằng thay thế nguyên tử; lỗi không ghi đè bản báo cáo trước. Chọn khoảng tối đa 31 ngày. SQL có cả hai cận thời gian; thống kê đọc qua snapshot riêng, không giữ khóa UI/writer trong suốt lúc dựng báo cáo.

PDF dùng metadata của phiên đã đo, không lấy card đang kết nối tại lúc xuất. Liệt kê phiên, trạng thái đo và số mẫu; thiếu dữ liệu hiện N/A/dấu gạch. Timeout được tổng hợp theo giờ, tối đa 500 nhóm mỗi mốc. Diagnosis/traceroute được lưu SQLite. Các khoảng ứng dụng không chạy hoặc không đo được không chứng minh có kết nối tốt.

CSV bảo vệ các trường text bắt đầu bằng dấu có thể được phần mềm bảng tính hiểu thành công thức. Kết quả Wi-Fi chỉ ước lượng từ AP/tín hiệu, chưa đo channel width, tải thực hay nhiễu phổ; khi thiếu Band thì giữ Unknown, không suy ra băng tần chỉ từ số kênh.

## Cài đặt và phạm vi quét

Mở **Công cụ → Cài đặt** để chọn tên card, CIDR, đích ngoài, chu kỳ, ngưỡng RTT/loss, retention và nhãn hồ sơ. Cấu hình được validate tại `data/settings.json`, áp dụng khi mở lại. File cấu hình hỏng được báo rõ và dùng mặc định để vẫn mở được giao diện sửa lại.

Để trống **Dải quét tùy chọn** để phủ toàn subnet của card, kể cả `/18` hoặc lớn hơn. Có thể nhập CIDR nhỏ hơn nếu muốn; CIDR vẫn phải nằm trong subnet thực. Dải IP được tính lười, không tạo danh sách hàng triệu địa chỉ trong RAM.

Mỗi phần kiểm tra tối đa 1.024 địa chỉ, dựng/gửi từng lô 64 packet và kiểm tra hủy giữa các lô. Router được kiểm tra mỗi phần nếu thuộc dải đã chọn. Với mạng lớn, worker nghỉ 1 giây rồi tiếp tục phần kế tiếp; sau phần cuối mới nghỉ theo chu kỳ quét. Kết quả và tiến độ được cập nhật sau từng phần thành công. Nút **Làm mới mạng** quét phần kế tiếp, không đặt lại về đầu khi vẫn ở cùng mạng.

Ví dụ `/18` có 16.382 địa chỉ host, được phủ bằng 16 phần; đây là số địa chỉ có thể kiểm tra, không phải số thiết bị chắc chắn đang hoạt động. Thời gian phủ phụ thuộc Npcap, phản hồi và tốc độ gửi; mạng lớn không được cập nhật tức thì. Chỉ IP nằm trong phần đã quét thành công mới tăng số lần vắng mặt; Offline cần ba lần thực sự kiểm tra mà không thấy. Bảng thiết bị phân trang 250 dòng, các ô tổng vẫn tính trên toàn hồ sơ. CLI `scan` chạy các phần đến hết một vòng rồi in kết quả gộp.

Các probe ping độc lập chạy đồng thời nhưng chu kỳ vẫn tuần tự. Cửa sổ là số mẫu có thời gian thực, không mặc định 30 mẫu luôn tương đương 60 giây.

ARP không bao phủ IPv6, VLAN/thiết bị sau router hoặc client isolation. Thiết bị ngủ/im lặng có thể vắng ARP. Online/Offline là kết quả quan sát. MAC có thể bị giả mạo; ICMP không kiểm tra DNS, HTTP, captive portal hay băng thông. Quyền bắt gói hiện áp dụng cho tiến trình giám sát; chế độ lịch sử không bật các dịch vụ đó.

## Thông báo Telegram/Zalo tùy chọn

Mặc định tắt. Không lưu token vào mã hoặc JSON cấu hình. Chỉ bật khi chủ hệ thống muốn gửi cảnh báo ra dịch vụ đã cấu hình:

- `NETGUARD_NOTIFICATIONS_ENABLED=1`.
- Telegram: `NETGUARD_TELEGRAM_TOKEN`, `NETGUARD_TELEGRAM_CHAT_ID`.
- Zalo OA: `NETGUARD_ZALO_ACCESS_TOKEN`, `NETGUARD_ZALO_USER_ID`; tài khoản/quyền/tương tác người nhận phải đáp ứng điều kiện của OA API.

Có hàng đợi RAM tối đa 100 thông báo và tối đa 3 lần thử khi lỗi có thể thử lại. Lỗi kênh hiển thị trên UI; cảnh báo gốc còn trong CSDL. Hàng đợi chưa gửi không được bảo đảm tồn tại sau khi tắt app. Không tự refresh token OA. Zalo `dry_run=True` vẫn chỉ mô phỏng.

Các adapter dựa trên [Telegram Bot API](https://core.telegram.org/bots/api#sendmessage) và [Zalo OA message API](https://stc-developers.zdn.vn/docs/v2/official-account/tin-nhan/tin-tu-van/gui-tin-tu-van-trich-dan?lang=vi). Chưa kiểm chứng gửi thật bằng tài khoản người dùng trong đợt sửa này.

## CLI

```powershell
.\.venv\Scripts\python.exe main.py --cli scan
.\.venv\Scripts\python.exe main.py --cli monitor
.\.venv\Scripts\python.exe main.py --cli baseline
.\.venv\Scripts\python.exe main.py --cli diagnose
.\.venv\Scripts\python.exe main.py --cli trace 1.1.1.1
.\.venv\Scripts\python.exe -m db.database
```

CLI bắt gói cần quyền thích hợp. Lệnh demo CSDL cuối cùng chỉ dùng CSDL tạm riêng, không dọn dữ liệu đang dùng theo mốc thời gian.

## Kiểm thử và Git

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest --cov -q
```

Mọi test có CSDL riêng và tắt thông báo ra ngoài. Các bài mạng dùng I/O giả; không mặc nhiên chứng minh tương thích mọi Windows/Npcap hoặc tải dài hạn. GitHub Actions kiểm tra cài mới trên Windows/Python 3.12.

Cache `.presentation-build`, `node_modules`, DB, WAL/SHM, backup, token và log không đưa vào commit mới. Mã công cụ slide cũ được tách ở `tools/presentations/` với manifest/lock; không cần nó để chạy NetGuard. Việc bỏ track không xóa file trên máy hoặc xóa các file đã có trong **lịch sử Git**.

`git push` chỉ đẩy commit. Nếu mã còn `M`/`??` trong `git status` và HEAD chưa có commit mới thì push vẫn báo Everything up-to-date. Báo cáo rà soát gốc: `docs/code-review-2026-11-11.md`; kết quả sửa hiện tại: `docs/remediation-report-2026-11-12.md`.
