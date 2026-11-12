# Rà soát mã nguồn NetGuard — 11/11/2026

Đánh giá bản mã đang có trong working tree, gồm thay đổi chưa commit. Không sửa mã ứng dụng và không chạy quét, ping, traceroute hoặc thay đổi mạng thật trong lần rà soát này.

Đã đọc 31 file Python của ứng dụng, tổng cộng 5.101 dòng; đọc thêm 8 file kiểm thử/mô phỏng, launcher, requirements, tài liệu kiến trúc, lỗi đã biết và các cấu hình liên quan. Có kiểm tra cách lưu các công cụ dựng slide trong Git; không kiểm toán toàn bộ mã thư viện trong `node_modules`, Npcap hay các dependency Python.

Mức ưu tiên: **P1** cần xử lý trước khi dựa vào kết quả/cảnh báo hoặc nghiệm thu chức năng liên quan; **P2** gây sai kết quả, mất thông tin hoặc lỗi vận hành trong tình huống cụ thể; **P3** là giới hạn phạm vi, trải nghiệm hoặc bảo trì. Đây là 44 **nhóm vấn đề**, gồm cả lỗi và giới hạn thiết kế, không phải 44 lỗi đều xảy ra trong mọi lần chạy. Một lần đọc mã và kiểm thử offline không chứng minh đã tìm được mọi lỗi có thể tồn tại.

> **Trạng thái hiện tại:** đây là ảnh chụp các phát hiện trước bản sửa. Kết quả xử lý từng nhóm, kiểm chứng và giới hạn còn giữ nằm trong [báo cáo sửa mã 12/11/2026](remediation-report-2026-11-12.md). Không dùng các con số/lỗi ở dưới như mô tả của bản mã mới.

## Bằng chứng kiểm tra

- Chạy `.\.venv\Scripts\python.exe -m pytest -q`: **65 passed in 8.60s**.
- Parse toàn bộ 39 file Python ứng dụng và kiểm thử bằng `ast.parse`: không có lỗi cú pháp.
- `pip check`: không báo dependency đã khai báo bị hỏng. Tuy nhiên, import `extras.pdf_report` thất bại với `ModuleNotFoundError: No module named 'matplotlib'`.
- Các phép thử bổ sung dùng tiến trình riêng, CSDL tạm và mock I/O. Không gọi `Backend.start()` để chạy dịch vụ mạng thật.
- Đã tái hiện: cảnh báo `danger` bị chặn sau `warning`; hai luồng ghi hai cảnh báo trùng; offline ghi đè `last_seen`; thiết bị chưa tin cậy quay lại không báo; cờ tin cậy đi theo MAC sang mạng khác; kết quả quét cũ được đánh dấu Online ở mạng mới; cùng MAC có hai IP chỉ còn một IP.
- Đã tái hiện: lỗi khởi tạo capture bị coi như scan thành công; listener trả về từ `start()` dù capture đã lỗi; lỗi gửi của `icmplib` thành kết quả `None`; RTT router 120 ms ổn định cho kết luận `ok`; đổi hop ISP giữ nguyên 30 mẫu của hop cũ; DHCP đổi IP hợp lệ gây cảnh báo đổi MAC.
- Đã tái hiện: `stop(timeout=0.01)` báo không chạy dù worker còn sống và còn ghi CSDL; lỗi callback khiến cảnh báo thiết bị mới không được thử lại; cảnh báo chỉ phát signal không có trong danh sách UI; refresh làm mất lựa chọn và lỗi refresh để cờ `_refreshing=True`.
- Đã tái hiện: báo cáo không có mẫu vẫn gán mất gói 0%; demo CSDL xóa cả mẫu ping khác; trường tên CSV `=1+1` được ghi nguyên dạng. Icon theme `network-workgroup` trả icon rỗng trong phép thử Qt offscreen; chưa xác nhận hành vi khay trên mọi máy Windows.

## Quét thiết bị và cảnh báo

### 01. [P1 — đã tái hiện] Lỗi bắt gói có thể trở thành một lượt quét “thành công”

**Vị trí:** [core/arp_scanner.py:106](D:/Nhom8_LapTrinhMang/core/arp_scanner.py:106), [core/arp_scanner.py:118](D:/Nhom8_LapTrinhMang/core/arp_scanner.py:118).

`AsyncSniffer.start()` tạo luồng nền; lỗi mở capture có thể xảy ra trong luồng đó. Scanner chỉ ngủ 0,8 giây rồi gửi, không xác nhận capture đã sẵn sàng. Ngoại lệ từ `sniffer.stop()` lại bị bỏ qua. Khi giả lập capture khởi tạo lỗi nhưng phần gửi không lỗi, hàm vẫn trả danh sách gồm chính máy đang chạy. Sau ba lượt như vậy, `ScanLoop` có thể đánh dấu các thiết bị khác Offline dù thực tế chương trình không nghe được phản hồi.

**Hướng sửa:** dùng tín hiệu capture sẵn sàng, kiểm tra lỗi/kết thúc bất thường của sniffer; chỉ dùng scan đã xác thực thành công để cập nhật hiện diện. Không dùng thời gian ngủ cố định làm xác nhận khởi tạo.

**Cập nhật 11/11/2026:** đã triển khai bản sửa và 17 test hồi quy; toàn bộ 162 test pass. Người dùng sau đó yêu cầu sửa tiếp toàn bộ; xem báo cáo sửa mã hiện tại. Xem [tiến độ triển khai](implementation-progress.md) để biết thay đổi và giới hạn kiểm chứng. Mô tả và vị trí ở trên ghi lại mã tại thời điểm rà soát ban đầu.

### 02. [P1 — đã tái hiện] Bộ nghe ARP có thể hỏng mà dịch vụ không biết

**Vị trí:** [core/arp_listener.py:67](D:/Nhom8_LapTrinhMang/core/arp_listener.py:67), [services/scan_loop.py:183](D:/Nhom8_LapTrinhMang/services/scan_loop.py:183), [backend.py:187](D:/Nhom8_LapTrinhMang/backend.py:187).

`ArpListener.start()` chỉ bắt lỗi đồng bộ từ `start()`, chưa bắt lỗi khởi tạo trong luồng Scapy. Không có theo dõi sức khỏe hoặc cơ chế mở lại khi listener chết; backend chỉ tạo lại listener lúc cấu hình card thay đổi. Vì vậy có thể mất phát hiện tranh chấp IP/gateway cho đến khi kết nối đổi hoặc ứng dụng khởi động lại. Một lần ngắt/bật ngắn giữa hai chu kỳ quét cũng có thể không làm đổi khóa mạng mà scan loop quan sát được.

**Hướng sửa:** xác nhận listener sẵn sàng, phát trạng thái hoạt động/lỗi lên UI, kiểm tra và khởi động lại có giới hạn thời gian chờ.

### 03. [P1 — đã tái hiện] Chống lặp chặn cả cảnh báo nguy hiểm khác loại

**Vị trí:** [services/alerts.py:46](D:/Nhom8_LapTrinhMang/services/alerts.py:46), [services/alerts.py:63](D:/Nhom8_LapTrinhMang/services/alerts.py:63), [db/repository.py:199](D:/Nhom8_LapTrinhMang/db/repository.py:199).

Khóa chống lặp chỉ là `device_mac`, không có loại sự kiện hay mức độ. Một `warning` thiết bị lạ vừa được ghi có thể chặn `danger` đổi MAC gateway của cùng MAC trong 30 phút. Điều này trái với mô tả “cùng loại cảnh báo” ở đầu module. Các cảnh báo dùng MAC `None` cũng chia sẻ một nhóm duy nhất.

**Hướng sửa:** lưu mã loại cảnh báo, chống lặp theo loại và đối tượng; cho phép nâng mức nghiêm trọng đi qua ngay.

### 04. [P2 — đã tái hiện] Kiểm tra chống lặp và ghi cảnh báo không nguyên tử

**Vị trí:** [services/alerts.py:54](D:/Nhom8_LapTrinhMang/services/alerts.py:54), [services/alerts.py:63](D:/Nhom8_LapTrinhMang/services/alerts.py:63).

`should_alert()` đọc CSDL rồi `add_alert()` ghi bằng giao dịch khác. Hai luồng cùng kiểm tra trước khi luồng nào ghi sẽ cùng phát cảnh báo. Đã tái hiện hai bản ghi cho cùng sự kiện bằng hai luồng; khóa SQLite của từng thao tác không bảo vệ toàn bộ chuỗi kiểm tra–ghi, và cũng không giải quyết nhiều tiến trình.

**Hướng sửa:** gom quyết định và ghi vào một giao dịch có bảo vệ phù hợp; thiết kế khóa chống lặp dùng được giữa các tiến trình.

### 05. [P2 — đã tái hiện] UI chưa hoàn tất quy trình bật cảnh báo thiết bị lạ

**Vị trí:** [ui/main_window.py:114](D:/Nhom8_LapTrinhMang/ui/main_window.py:114), [ui/main_window.py:525](D:/Nhom8_LapTrinhMang/ui/main_window.py:525), [services/baseline.py:22](D:/Nhom8_LapTrinhMang/services/baseline.py:22), [services/scan_loop.py:173](D:/Nhom8_LapTrinhMang/services/scan_loop.py:173).

GUI không hiển thị trạng thái baseline và không gọi `finish_baseline()`. “Tin cậy tất cả” chỉ đổi cờ `trusted`. Với CSDL mới, người chỉ dùng GUI có thể theo dõi mãi mà cảnh báo thiết bị lạ vẫn chưa được bật; phải biết chạy lệnh CLI riêng theo README. Baseline hiện chỉ là cờ toàn cục, không có bản chụp thành viên để xem lại hoặc rà soát.

**Hướng sửa:** thêm quy trình kiểm tra danh sách ban đầu, chốt baseline và hiển thị rõ trạng thái bảo vệ; tách “tin cậy” khỏi “hoàn tất thiết lập” trong cách giải thích cho người dùng.

### 06. [P2 — đã tái hiện] Thiết bị chưa tin cậy chỉ được cảnh báo ở lần thêm CSDL đầu tiên

**Vị trí:** [services/scan_loop.py:144](D:/Nhom8_LapTrinhMang/services/scan_loop.py:144), [services/scan_loop.py:168](D:/Nhom8_LapTrinhMang/services/scan_loop.py:168).

Điều kiện là `is_new`, không phải “chưa tin cậy vừa xuất hiện lại”. Thiết bị đã được thấy trước baseline, hoặc đã được cảnh báo rồi rời mạng, quay lại sẽ không được cảnh báo nữa, kể cả sau 30 phút chống lặp. Bỏ cờ tin cậy cũng không làm lần xuất hiện tiếp theo được báo. Đây là phạm vi hiện tại đã được tài liệu mô tả, nhưng làm khả năng giám sát thiết bị chưa được chấp nhận khá yếu.

Ngoài ra, nếu lỗi xảy ra sau khi thêm thiết bị nhưng trước khi ghi cảnh báo, lần sau `is_new=False` nên cảnh báo bị mất vĩnh viễn. Đã tái hiện bằng callback `on_device` ném lỗi.

**Hướng sửa:** định nghĩa sự kiện xuất hiện theo phiên/hiện diện; tách ghi nhận thiết bị, trạng thái cần cảnh báo và việc gửi cảnh báo để có thể thử lại.

### 07. [P2 — đã tái hiện] Thiết bị, tin cậy và baseline chưa tách theo từng mạng

**Vị trí:** [db/database.py:21](D:/Nhom8_LapTrinhMang/db/database.py:21), [db/repository.py:107](D:/Nhom8_LapTrinhMang/db/repository.py:107), [services/scan_loop.py:192](D:/Nhom8_LapTrinhMang/services/scan_loop.py:192), [services/baseline.py:16](D:/Nhom8_LapTrinhMang/services/baseline.py:16), [backend.py:198](D:/Nhom8_LapTrinhMang/backend.py:198).

Thiết bị có khóa chính chỉ là MAC; danh sách và việc đánh dấu Offline lấy toàn bộ CSDL. Chuyển Wi-Fi vẫn trộn thiết bị cũ; cùng MAC mang theo tin cậy/tên sang mạng khác; ba lần quét ở mạng mới có thể ghi Offline cho thiết bị thuộc mạng cũ. Bộ phát hiện ARP cũng được khởi tạo từ toàn bộ thiết bị cũ, nên hai mạng dùng cùng IP gateway có thể tạo so sánh sai. Baseline cũng áp dụng chung cho mọi mạng.

Vấn đề hiển thị dữ liệu mạng cũ đã được ghi nhận trong [docs/known-issues.md:18](D:/Nhom8_LapTrinhMang/docs/known-issues.md:18).

**Hướng sửa:** có định danh mạng và phạm vi dữ liệu nhất quán cho thiết bị, baseline, hiện diện, tin cậy và bộ phát hiện ARP; tách màn hình mạng hiện tại khỏi lịch sử.

### 08. [P2 — đã tái hiện] Kết quả quét cũ vẫn được chấp nhận sau khi đổi mạng

**Vị trí:** [services/scan_loop.py:128](D:/Nhom8_LapTrinhMang/services/scan_loop.py:128), [backend.py:206](D:/Nhom8_LapTrinhMang/backend.py:206), [backend.py:237](D:/Nhom8_LapTrinhMang/backend.py:237), [backend.py:262](D:/Nhom8_LapTrinhMang/backend.py:262).

Quét lấy interface một lần trước khi gửi; callback thiết bị/kết quả không mang mã phiên kết nối. Trong lúc quét, ping monitor có thể đã phát mạng mới và xóa `_session_macs`; kết quả quét mạng cũ về sau lại thêm MAC vào tập đã xác minh. Đã tái hiện thiết bị `192.168.1.20` hiển thị Online khi kết nối hiện tại là `10.0.0.9`. Traceroute có kiểm tra generation, scan chưa có cơ chế tương tự.

**Hướng sửa:** gắn định danh/generation kết nối với cả scan và các sự kiện của nó; bỏ kết quả đã hết hiệu lực trước khi ghi/hiển thị.

### 09. [P2 — đã tái hiện] `last_seen` bị đổi thành thời điểm đánh dấu Offline

**Vị trí:** [db/repository.py:129](D:/Nhom8_LapTrinhMang/db/repository.py:129), [services/scan_loop.py:201](D:/Nhom8_LapTrinhMang/services/scan_loop.py:201), [ui/main_window.py:346](D:/Nhom8_LapTrinhMang/ui/main_window.py:346).

`set_online(False)` vẫn cập nhật `last_seen=moment`. Thiết bị được thấy lúc T, vắng ba lượt, sẽ có “thấy gần nhất” thành T+90 giây hoặc hơn dù không có quan sát mới. Cột UI, dữ liệu xuất và điều kiện kiểm tra thiết bị cũ của bộ phát hiện ARP bị ảnh hưởng.

**Hướng sửa:** chỉ cập nhật `last_seen` khi có quan sát thật; dùng trường khác cho thời điểm chuyển trạng thái.

### 10. [P2 — đã tái hiện một phần] Mô hình làm mất các quan hệ IP–MAC nhiều chiều

**Vị trí:** [core/arp_scanner.py:92](D:/Nhom8_LapTrinhMang/core/arp_scanner.py:92), [core/arp_scanner.py:104](D:/Nhom8_LapTrinhMang/core/arp_scanner.py:104), [db/database.py:22](D:/Nhom8_LapTrinhMang/db/database.py:22), [services/scan_loop.py:148](D:/Nhom8_LapTrinhMang/services/scan_loop.py:148).

Scanner giữ MAC đầu tiên cho mỗi IP bằng `setdefault`; hai MAC cùng nhận một IP không còn đầy đủ trong kết quả scan. Ngược lại, khi một MAC có hai IP, việc upsert theo MAC khiến IP sau ghi đè IP trước; đã tái hiện hai kết quả scan chỉ còn một thiết bị với IP cuối. Cảnh báo thụ động có thể bù một phần, nhưng phụ thuộc listener hoạt động và không có lịch sử quan sát đầy đủ để tra lại.

**Hướng sửa:** lưu quan sát IP–MAC theo mạng/thời gian riêng khỏi hồ sơ thiết bị; bảo toàn các claim xung đột.

### 11. [P2 — đã tái hiện] DHCP đổi IP hợp lệ có thể bị báo đổi MAC bất thường

**Vị trí:** [services/alerts.py:90](D:/Nhom8_LapTrinhMang/services/alerts.py:90), [services/alerts.py:152](D:/Nhom8_LapTrinhMang/services/alerts.py:152), [services/alerts.py:189](D:/Nhom8_LapTrinhMang/services/alerts.py:189).

`_known_owner` giữ ánh xạ IP cũ. Khi kiểm tra `old_still_active`, mã chỉ xét thiết bị cũ online và thời gian, không xét `old_device.ip == ip` đang tranh chấp. Thiết bị A đã chuyển từ `.20` sang `.30`, thiết bị B hợp lệ nhận `.20` và phát hai claim vẫn có thể bị báo trong khi A “vẫn online”.

**Hướng sửa:** cập nhật/hết hạn ánh xạ khi IP đổi và kiểm tra đúng IP mà thiết bị cũ còn sử dụng; kết hợp các quan sát thực sự đồng thời.

### 12. [P3 — giới hạn thiết kế] MAC/ARP chưa đủ để xác thực thiết bị hoặc gateway

**Vị trí:** [core/arp_scanner.py:94](D:/Nhom8_LapTrinhMang/core/arp_scanner.py:94), [core/arp_listener.py:94](D:/Nhom8_LapTrinhMang/core/arp_listener.py:94), [services/alerts.py:82](D:/Nhom8_LapTrinhMang/services/alerts.py:82), [services/alerts.py:124](D:/Nhom8_LapTrinhMang/services/alerts.py:124).

- Tin cậy gắn với MAC tự khai báo qua ARP; không có xác thực thiết bị. Thiết bị dùng lại MAC đã tin cậy có thể vượt qua quy tắc “MAC mới”. MAC cục bộ cũng chỉ là một bit, không chứng minh được địa chỉ thật sự ngẫu nhiên.
- Gateway lấy MAC từ CSDL hoặc claim đầu tiên khi chưa biết; chưa có bước xác minh nguồn tin hay quy trình chấp nhận router thay thế hợp lệ.
- Scanner/listener chưa kiểm tra đầy đủ MAC unicast hợp lệ, sự nhất quán giữa Ethernet source và ARP source, hoặc ngữ cảnh request/reply. Listener cũng không lọc nguồn IP theo subnet đang theo dõi.

**Hướng sửa:** coi đây là cảnh báo từ quan sát, không phải xác thực; chuẩn hóa/kiểm tra đầu vào, xác lập và cập nhật gateway có kiểm soát, bổ sung nhiều nguồn bằng chứng nếu cần mức tin cậy cao hơn.

### 13. [P2 — đọc mã] Bộ phát hiện ARP chưa có giới hạn tài nguyên tổng thể

**Vị trí:** [services/alerts.py:84](D:/Nhom8_LapTrinhMang/services/alerts.py:84), [services/alerts.py:100](D:/Nhom8_LapTrinhMang/services/alerts.py:100), [services/alerts.py:127](D:/Nhom8_LapTrinhMang/services/alerts.py:127).

Chỉ lọc hết hạn bên trong IP/MAC đang được truy cập; các khóa IP/MAC cũ ở dict bên ngoài, `_known_owner` và các dict candidate không được dọn định kỳ. Nhiều địa chỉ mới làm bộ nhớ tăng theo số định danh đã gặp. Chống lặp theo từng MAC cũng không giới hạn tổng số cảnh báo từ nhiều MAC, nên lưu lượng bất thường có thể làm tăng ghi CSDL và tải UI.

**Hướng sửa:** giới hạn phạm vi nguồn, số mục, thời gian tồn tại; dọn toàn cục và áp dụng giới hạn tốc độ tổng thể cho cảnh báo.

## Chẩn đoán và dữ liệu báo cáo

### 14. [P1 — đã tái hiện] Lỗi gửi ICMP thật vẫn có thể được ghi thành mất gói

**Vị trí:** [core/icmp.py:45](D:/Nhom8_LapTrinhMang/core/icmp.py:45), [services/ping_monitor.py:173](D:/Nhom8_LapTrinhMang/services/ping_monitor.py:173).

Wrapper mong `icmplib.ping()` ném lỗi gửi socket để phân biệt “lỗi đo” với timeout. Trong bản `icmplib 3.0.4` đang cài, hàm ping bắt `ICMPLibError` ở vòng send/receive rồi trả `Host`; `ping_once()` chỉ xét `packets_received`, nên lỗi gửi cũng trả `None`. Đã mock lỗi ở socket của chính thư viện, giữ nguyên `icmplib.ping()`: kết quả là `None`, không có ngoại lệ. Ping monitor sẽ lưu nó thành mất gói 100%.

Các test hiện tại mock pinger cấp cao ném lỗi nên chưa kiểm tra đúng hành vi này. Lỗi tạo/bind socket bên ngoài vòng send của thư viện vẫn có thể được wrapper bắt; không phải mọi lỗi socket đều bị nuốt.

**Hướng sửa:** đo bằng API socket có phân biệt trạng thái gửi/nhận, hoặc bổ sung lớp trả trạng thái đo đủ chi tiết; ít nhất kiểm tra trường hợp không gửi được probe và thêm test tại ranh giới thư viện thật.

### 15. [P2 — đã tái hiện] RTT chậm kéo dài tự trở thành đường cơ sở “bình thường”

**Vị trí:** [services/ping_monitor.py:210](D:/Nhom8_LapTrinhMang/services/ping_monitor.py:210), [core/diagnosis.py:29](D:/Nhom8_LapTrinhMang/core/diagnosis.py:29).

RTT nền là phân vị 25 trong chính 30 mẫu đang đánh giá. Khi cả cửa sổ đều chậm, nền cũng tăng và ngưỡng `3 × nền` tăng theo. Đã thử 30 mẫu router đều 120 ms: nền = 120 ms, ngưỡng = 360 ms, không mất gói thì ba mốc có thể cho `ok`. Việc suy giảm kéo dài hoặc chậm ngay từ lúc mở ứng dụng không được nhận diện tốt; spike ngắn cũng dễ bị median che đi.

**Hướng sửa:** học đường cơ sở từ giai đoạn đã xác nhận khỏe, hạn chế tốc độ thích nghi, bổ sung ngưỡng theo loại đích và các chỉ số jitter/percentile nếu mục tiêu cần chúng.

### 16. [P2 — đã tái hiện quy tắc] Kết luận vị trí lỗi quá chắc so với bằng chứng

**Vị trí:** [core/diagnosis.py:47](D:/Nhom8_LapTrinhMang/core/diagnosis.py:47), [core/diagnosis.py:56](D:/Nhom8_LapTrinhMang/core/diagnosis.py:56), [tests/test_diagnosis.py:32](D:/Nhom8_LapTrinhMang/tests/test_diagnosis.py:32).

Router hoặc hop trung gian xấu được ưu tiên kết luận lỗi mạng nhà/ISP trước khi đối chiếu đích cuối. Đã thử router và external khỏe, riêng ISP mất phản hồi: kết quả vẫn `isp_issue`. Dữ liệu này chưa đủ chứng minh đường chuyển tiếp có lỗi; chương trình chưa phân biệt được đích trung gian không đáp ứng phép đo với lỗi truyền tải thật. Test hiện còn khẳng định tình huống tương tự là ISP lỗi.

Ngoài ra, chỉ ping một IP cố định không xác nhận được DNS, HTTP, băng thông, đăng nhập captive portal hay toàn bộ Internet. `ok` chỉ có nghĩa các phép đo ICMP được chọn đạt quy tắc hiện tại.

**Hướng sửa:** đối chiếu ảnh hưởng có tiếp tục đến đích cuối không, dùng ngôn ngữ “nghi ngờ”, có mức tin cậy và kiểm tra nhiều đích/giao thức phù hợp.

### 17. [P2 — đọc mã] “Hop ISP” chưa chắc thuộc ISP và có thể trùng đích ngoài

**Vị trí:** [core/traceroute.py:199](D:/Nhom8_LapTrinhMang/core/traceroute.py:199).

Hàm chọn hop đầu tiên có IP sau gateway, hoặc TTL > 1 nếu không thấy gateway. Hop đó có thể là router nội bộ thứ hai hoặc chính `1.1.1.1` nếu các hop giữa im lặng. Không có xác minh chủ sở hữu/vai trò; hai mốc `isp` và `external` thậm chí có thể đo cùng IP. Nếu không tìm được hop, dù router/external tốt, hệ thống chỉ trả `unknown` lâu dài.

**Hướng sửa:** lưu rõ đây là “hop sau gateway được quan sát”, tránh trùng đích và đưa giới hạn nhận diện vào kết luận; không dùng nhãn ISP như bằng chứng sở hữu chắc chắn.

### 18. [P2 — đọc mã] Traceroute không bị ràng buộc vào card mà monitor đang theo dõi

**Vị trí:** [services/ping_monitor.py:65](D:/Nhom8_LapTrinhMang/services/ping_monitor.py:65), [services/ping_monitor.py:262](D:/Nhom8_LapTrinhMang/services/ping_monitor.py:262), [core/traceroute.py:24](D:/Nhom8_LapTrinhMang/core/traceroute.py:24), [core/traceroute.py:53](D:/Nhom8_LapTrinhMang/core/traceroute.py:53).

Monitor giữ card ưu tiên và bind IP nguồn khi ping. Traceroute lại gọi `get_active_interface()` không truyền card đó, rồi dùng `tracert.exe` theo routing table hệ điều hành. Khi có Wi-Fi/Ethernet cùng hoạt động hoặc route/VPN thay đổi, đường dò và đường ping có thể khác nhau, làm mốc ISP không còn tương ứng với mạng đang giám sát. Generation theo cấu hình card chưa phát hiện hết thay đổi routing table.

**Hướng sửa:** thống nhất ngữ cảnh tuyến đường/interface cho mọi phép đo hoặc phát hiện và từ chối kết luận khi chúng không tương ứng.

### 19. [P2 — đã tái hiện một phần] Cửa sổ thống kê chưa hết hiệu lực khi dữ liệu đổi ngữ cảnh hoặc quá cũ

**Vị trí:** [services/ping_monitor.py:175](D:/Nhom8_LapTrinhMang/services/ping_monitor.py:175), [services/ping_monitor.py:210](D:/Nhom8_LapTrinhMang/services/ping_monitor.py:210), [services/ping_monitor.py:269](D:/Nhom8_LapTrinhMang/services/ping_monitor.py:269).

Khi tìm được IP hop ISP mới trên cùng interface, `_isp_ip` đổi nhưng `_history['isp']` giữ nguyên; đã tái hiện giữ 30 mẫu của IP cũ. Lỗi đo chỉ bỏ qua, lịch sử trong deque không chứa timestamp và không hết hạn theo thời gian. Sau khoảng lỗi đo dài, một mẫu mới có thể lại được đánh giá chung với các mẫu rất cũ.

**Hướng sửa:** gắn mẫu với địa chỉ đích, kết nối và thời gian; reset cửa sổ khi đích đổi, hết hạn mẫu và yêu cầu đủ dữ liệu mới sau khoảng gián đoạn.

### 20. [P2 — đọc mã] Lịch sử ping mất địa chỉ đích và định danh mạng/phiên

**Vị trí:** [models.py:42](D:/Nhom8_LapTrinhMang/models.py:42), [db/database.py:43](D:/Nhom8_LapTrinhMang/db/database.py:43), [db/repository.py:170](D:/Nhom8_LapTrinhMang/db/repository.py:170), [ui/main_window.py:391](D:/Nhom8_LapTrinhMang/ui/main_window.py:391).

Chỉ lưu vai trò `router/isp/external`, RTT, loss và thời gian. Không thể biết mẫu thuộc gateway/IP ISP/interface nào sau khi đổi mạng. UI tính mất gói từ 30 mẫu lịch sử CSDL và đồ thị 30 phút, nên có thể trộn hai mạng hoặc hai hop ISP trong cùng thống kê, dù cửa sổ chẩn đoán trong RAM đã reset.

**Hướng sửa:** lưu address, network/session và trạng thái phép đo; truy vấn lịch sử theo đúng phạm vi, hiển thị ranh giới khi thay đổi.

### 21. [P2 — đã tái hiện một phần] Không có dữ liệu có thể xuất thành mất gói 0%

**Vị trí:** [services/ping_monitor.py:135](D:/Nhom8_LapTrinhMang/services/ping_monitor.py:135), [backend.py:374](D:/Nhom8_LapTrinhMang/backend.py:374), [extras/pdf_report.py:149](D:/Nhom8_LapTrinhMang/extras/pdf_report.py:149), [extras/pdf_report.py:417](D:/Nhom8_LapTrinhMang/extras/pdf_report.py:417), [ui/main_window.py:442](D:/Nhom8_LapTrinhMang/ui/main_window.py:442).

Mất LAN/lỗi đo không được lưu thành bản ghi trạng thái đo; báo cáo chỉ biết các mẫu ping đã có. Khi không có mẫu, backend gán `loss_pct=0.0`; biểu đồ PDF còn đổi RTT `None` thành 0. Đã xác nhận cả ba mốc không có mẫu vẫn nhận loss 0%. “Không ghi nhận mất gói” không chứng minh khoảng thời gian đó có kết nối tốt.

Đồ thị UI cũng chỉ chèn `nan` khi đã có mẫu không phản hồi. Khoảng mất LAN/lỗi đo không có hàng trong CSDL sẽ bị nối đường giữa các mẫu hữu hạn trước và sau, không tự tạo khoảng trống tương ứng.

**Hướng sửa:** lưu các khoảng offline/measurement_error/không giám sát; tách coverage khỏi loss, hiển thị N/A khi thiếu mẫu và vẽ khoảng trống thật. Giữ sự phân biệt lỗi đo với timeout thay vì biến mọi lỗi thành mất gói.

### 22. [P2 — đọc mã] Báo cáo lịch sử phụ thuộc dữ liệu trong RAM và mốc chuyển trạng thái

**Vị trí:** [backend.py:120](D:/Nhom8_LapTrinhMang/backend.py:120), [backend.py:272](D:/Nhom8_LapTrinhMang/backend.py:272), [backend.py:393](D:/Nhom8_LapTrinhMang/backend.py:393), [services/ping_monitor.py:235](D:/Nhom8_LapTrinhMang/services/ping_monitor.py:235), [db/repository.py:236](D:/Nhom8_LapTrinhMang/db/repository.py:236).

- Diagnosis chỉ giữ 500 sự kiện trong RAM và traceroute chỉ giữ kết quả gần nhất; khởi động lại mất các dữ liệu này dù ping cũ vẫn còn.
- Traceroute tự tìm ISP trong `PingMonitor` không được chuyển thành `_last_traceroute` của backend. GUI chưa có nút gọi `Backend.run_traceroute()`, nên phần traceroute PDF thường trống trong luồng dùng GUI thông thường.
- Diagnosis chỉ phát khi kết luận thay đổi. Một tình trạng bắt đầu trước khoảng báo cáo và kéo dài suốt khoảng đó không được lấy kèm trạng thái trước `start`, khiến báo cáo thiếu kết luận đang có hiệu lực.
- `get_presence()` cũng chỉ lấy thay đổi kể từ `since`, không lấy trạng thái gần nhất trước ranh giới để dựng lịch sử đầy đủ. Dừng ứng dụng không tạo mốc “ngừng quan sát”, nên không được suy diễn trạng thái xuyên qua thời gian app không chạy.

**Hướng sửa:** lưu sự kiện/trạng thái giám sát và traceroute có ngữ cảnh vào CSDL; truy vấn cả trạng thái đầu kỳ, không chỉ các lần đổi trong kỳ.

### 23. [P2 — đọc mã] Thông tin card trong PDF là card lúc xuất, không phải lúc đo

**Vị trí:** [backend.py:389](D:/Nhom8_LapTrinhMang/backend.py:389).

Xuất báo cáo tuần trước vẫn gọi `get_active_interface()` hiện tại. Nếu đã chuyển Wi-Fi hoặc card ưu tiên khác, thông tin đầu báo cáo có thể thuộc mạng B trong khi số liệu thuộc mạng A hoặc nhiều mạng. Khi offline thì phần card trống mặc dù phép đo trước đó có card hợp lệ.

**Hướng sửa:** lấy metadata đã lưu cùng từng phiên đo, chia báo cáo theo mạng/interface khi khoảng chọn chứa nhiều ngữ cảnh.

### 24. [P2 — đọc mã] Xuất PDF có thể khóa giao diện và dùng quá nhiều tài nguyên

**Vị trí:** [ui/main_window.py:552](D:/Nhom8_LapTrinhMang/ui/main_window.py:552), [backend.py:364](D:/Nhom8_LapTrinhMang/backend.py:364), [db/repository.py:170](D:/Nhom8_LapTrinhMang/db/repository.py:170), [extras/pdf_report.py:406](D:/Nhom8_LapTrinhMang/extras/pdf_report.py:406).

Toàn bộ đọc CSDL, tổng hợp, import/vẽ Matplotlib và dựng PDF chạy trên luồng UI. Không có tiến độ, hủy hoặc giới hạn khoảng thời gian. SQL chỉ có cận dưới `since`; cận trên `end` được lọc sau trong Python, nên chọn một khoảng cũ ngắn vẫn có thể đọc mọi mẫu từ đó tới hiện tại. PDF còn tạo một dòng cho mỗi mẫu mất gói, có thể thành báo cáo rất dài.

**Hướng sửa:** truy vấn đủ hai cận trong SQL, tổng hợp theo khoảng/sự kiện, đặt giới hạn phù hợp và chuyển việc xuất sang worker có tiến độ/hủy.

### 25. [P1 — đã tái hiện] Cài đúng requirements hiện chưa đủ để xuất PDF

**Vị trí:** [requirements.txt:1](D:/Nhom8_LapTrinhMang/requirements.txt:1), [extras/pdf_report.py:11](D:/Nhom8_LapTrinhMang/extras/pdf_report.py:11), [extras/pdf_report.py:37](D:/Nhom8_LapTrinhMang/extras/pdf_report.py:37).

Module PDF import `matplotlib`, nhưng requirements không khai báo. Trong `.venv` hiện tại, import module thất bại ngay. Bộ 65 test vẫn qua vì chưa import/kiểm tra luồng xuất PDF thật. Module còn đòi font tại `C:/Windows/Fonts/arial.ttf` ngay khi import, không có font đóng gói hay phương án dự phòng.

**Hướng sửa:** khai báo dependency runtime, kiểm thử xuất PDF trong môi trường dựng mới và quản lý font có dự phòng. Kiểm tra trực quan PDF sau khi tính năng chạy được; lần rà soát này chưa xác nhận layout PDF tạo bởi ứng dụng vì dependency đang thiếu.

## Giao diện và vận hành

### 26. [P2 — đã tái hiện một phần] Một số lỗi/cảnh báo không xuất hiện trong danh sách UI

**Vị trí:** [services/scan_loop.py:119](D:/Nhom8_LapTrinhMang/services/scan_loop.py:119), [backend.py:204](D:/Nhom8_LapTrinhMang/backend.py:204), [backend.py:342](D:/Nhom8_LapTrinhMang/backend.py:342), [ui/main_window.py:472](D:/Nhom8_LapTrinhMang/ui/main_window.py:472), [Mo_NetGuard.cmd:9](D:/Nhom8_LapTrinhMang/Mo_NetGuard.cmd:9).

Lỗi scan, kể cả vượt giới hạn subnet, chỉ ghi stderr/`last_error`; UI chưa nhận trạng thái lỗi scan. Lỗi listener/traceroute do backend tạo chỉ phát signal, không lưu Alerts. `on_alert_raised()` lại đọc lại danh sách từ CSDL thay vì thêm alert nhận được, nên những cảnh báo này không vào tab Cảnh báo; đã tái hiện danh sách vẫn rỗng. Chạy qua `pythonw.exe` không có terminal thuận tiện để đọc log; chưa có log file và traceback phục vụ điều tra.

**Hướng sửa:** có trạng thái dịch vụ và kênh lỗi riêng, lưu/phân phối cảnh báo nhất quán, ghi log có thời gian và traceback; UI cho biết dữ liệu đang cũ do scan lỗi.

### 27. [P2 — đã tái hiện một phần] `stop()` chưa bảo đảm worker đã dừng trước khi đóng CSDL

**Vị trí:** [services/scan_loop.py:100](D:/Nhom8_LapTrinhMang/services/scan_loop.py:100), [services/ping_monitor.py:103](D:/Nhom8_LapTrinhMang/services/ping_monitor.py:103), [backend.py:168](D:/Nhom8_LapTrinhMang/backend.py:168), [db/database.py:93](D:/Nhom8_LapTrinhMang/db/database.py:93).

Scan loop bỏ tham chiếu `_thread` trước khi biết `join(timeout)` có thành công không. Ping monitor cũng xóa tham chiếu sau thời hạn chờ mà không xác nhận worker đã chết. Scan không có hủy giữa các bước gửi/đợi/cập nhật. Đã tái hiện `is_running=False` trong khi worker còn sống và vẫn ghi thiết bị sau `stop()`.

Backend sau đó đóng CSDL; worker còn chạy có thể mở lại kết nối hoặc gặp lỗi trong quá trình đóng. `transaction()` lấy connection trước khi vào khối khóa dùng nó cũng tạo cửa sổ tranh chấp với `close()`. Gọi start lại sau timeout có thể tạo worker chồng nhau. Trên UI, quá trình dừng còn chờ đồng bộ nhiều worker nên có thể mất đáng kể thời gian. Chưa có cơ chế ngăn hai tiến trình giám sát độc lập cùng ghi cùng DB.

**Hướng sửa:** hủy I/O có giới hạn, giữ handle đến khi xác nhận kết thúc, báo thất bại khi không dừng được và chỉ đóng tài nguyên sau khi tất cả người dùng chúng đã thoát; quản lý rõ nhiều instance.

### 28. [P2 — đọc mã] UI đọc và dựng lại quá nhiều dữ liệu

**Vị trí:** [ui/main_window.py:318](D:/Nhom8_LapTrinhMang/ui/main_window.py:318), [ui/main_window.py:391](D:/Nhom8_LapTrinhMang/ui/main_window.py:391), [ui/main_window.py:468](D:/Nhom8_LapTrinhMang/ui/main_window.py:468), [ui/main_window.py:483](D:/Nhom8_LapTrinhMang/ui/main_window.py:483), [ui/main_window.py:525](D:/Nhom8_LapTrinhMang/ui/main_window.py:525), [db/database.py:67](D:/Nhom8_LapTrinhMang/db/database.py:67).

Mỗi thiết bị mới/đổi trạng thái làm đọc và dựng lại toàn bộ bảng, resize tất cả cột. Một lượt phát nhiều thiết bị, hoặc “Tin cậy tất cả”, dẫn đến nhiều lần dựng N hàng, có thể đạt chi phí gần O(N²). `_device_rows` chưa được dùng để cập nhật từng hàng; handler checkbox còn có một vòng tìm kiếm không có tác dụng.

Mỗi signal ping lại đọc lịch sử 30 phút của cả ba mốc và xóa/vẽ lại toàn bộ đồ thị, sau đó signal kết thúc chu kỳ lại làm việc đó. Khi có ba mốc, riêng các lần refresh này có thể tạo 12 truy vấn lịch sử mỗi chu kỳ. Mọi truy vấn còn chia sẻ một connection/khóa với writer nên có thể chặn luồng UI.

**Hướng sửa:** cập nhật theo lô/từng hàng, gộp signal theo chu kỳ, cache cửa sổ dữ liệu và cập nhật curve hiện có; cân nhắc mô hình dữ liệu Qt phù hợp thay vì dựng lại widget toàn bảng.

### 29. [P2 — đã tái hiện] Refresh thiết bị làm mất lựa chọn và có thể ngắt việc sửa

**Vị trí:** [ui/main_window.py:321](D:/Nhom8_LapTrinhMang/ui/main_window.py:321), [ui/main_window.py:504](D:/Nhom8_LapTrinhMang/ui/main_window.py:504).

`setRowCount(0)` xóa toàn bộ item, lựa chọn và editor. Đã xác nhận chọn một hàng xong, nhận một lần refresh scan thì số item được chọn về 0. Quét định kỳ hoặc một cập nhật nền có thể làm người dùng mất vị trí/việc nhập tên hoặc ghi chú ngay trên bảng.

**Hướng sửa:** giữ lựa chọn, vị trí cuộn và trạng thái sửa theo MAC; cập nhật từng mục hoặc trì hoãn mục đang được sửa.

### 30. [P2 — đã tái hiện] Một lần lỗi refresh có thể vô hiệu hóa lưu chỉnh sửa

**Vị trí:** [ui/main_window.py:318](D:/Nhom8_LapTrinhMang/ui/main_window.py:318), [ui/main_window.py:486](D:/Nhom8_LapTrinhMang/ui/main_window.py:486), [ui/main_window.py:504](D:/Nhom8_LapTrinhMang/ui/main_window.py:504).

Cờ `_refreshing=True` không được trả lại bằng `finally`. Nếu đọc CSDL hoặc dựng bảng lỗi, các handler checkbox/tên/ghi chú tiếp tục bỏ qua thao tác cho tới khi có một refresh thành công khác. Đã tái hiện cờ bị giữ lại sau lỗi tạm thời. Các thao tác đổi tin cậy/đổi tên cũng thiếu phản hồi UI rõ khi ghi CSDL lỗi.

**Hướng sửa:** bảo đảm khôi phục cờ/trạng thái bằng `try/finally`, giữ bảng hợp lệ nếu tải thất bại và phản hồi lỗi lưu trực tiếp cho người dùng.

### 31. [P2 — đã xác nhận điều kiện icon rỗng] Ẩn xuống khay có thể khiến cửa sổ khó mở lại

**Vị trí:** [ui/tray.py:14](D:/Nhom8_LapTrinhMang/ui/tray.py:14), [ui/main_window.py:572](D:/Nhom8_LapTrinhMang/ui/main_window.py:572).

`QIcon.fromTheme()` có thể trả icon rỗng mà không ném ngoại lệ; mã không kiểm tra `isNull()` và cũng không có icon tài nguyên dự phòng. `closeEvent` chỉ dựa vào `tray.isVisible()` để ẩn cửa sổ, chưa kiểm tra khay hệ thống có khả dụng hoặc icon có thực sự dùng được. Điều kiện icon rỗng đã xuất hiện trong phép thử offscreen; README cũng ghi nhận icon có thể không rõ trên một số máy. Cần kiểm thử khay thật trên máy đích để xác nhận trải nghiệm đầy đủ.

**Hướng sửa:** đóng gói icon, kiểm tra khả năng dùng system tray và chỉ ẩn khi có đường mở lại chắc chắn. Mức độ thông báo hiện cũng chưa được thể hiện bằng icon tương ứng (`color` được tính nhưng không sử dụng).

### 32. [P2 — đọc mã] Không có chính sách lưu trữ và giới hạn dữ liệu lâu dài

**Vị trí:** [db/repository.py:161](D:/Nhom8_LapTrinhMang/db/repository.py:161), [db/repository.py:170](D:/Nhom8_LapTrinhMang/db/repository.py:170), [db/repository.py:217](D:/Nhom8_LapTrinhMang/db/repository.py:217), [config.py:16](D:/Nhom8_LapTrinhMang/config.py:16).

PingLog, Alerts, PresenceLog và thiết bị đã biết không có purge/archive hoặc cấu hình giữ dữ liệu. Nếu cả ba mốc đều đo mỗi hai giây thì khoảng **129.600 mẫu/ngày**; đây là ước tính theo cấu hình, không phải số đo tải thực tế. Truy vấn dùng `fetchall()`, không có phân trang cho lịch sử. `list_alerts()` cũng không chặn limit âm; SQLite có thể trả không giới hạn nếu API bị gọi như vậy.

**Hướng sửa:** quy định retention, tổng hợp dữ liệu cũ, giới hạn truy vấn/xuất và có quy trình sao lưu/khôi phục CSDL phù hợp với WAL.

### 33. [P2 — đã tái hiện] Demo CSDL có thể xóa dữ liệu thật

**Vị trí:** [db/database.py:115](D:/Nhom8_LapTrinhMang/db/database.py:115), [db/database.py:150](D:/Nhom8_LapTrinhMang/db/database.py:150).

`python -m db.database` dùng CSDL thật. Lệnh dọn `DELETE FROM PingLog WHERE ts >= started` xóa mọi ping từ thời điểm bắt đầu demo, không chỉ mẫu demo. Đã tái hiện một mẫu external không thuộc demo bị xóa cùng. Việc xóa theo MAC cố định/Meta key cố định cũng không khôi phục dữ liệu đã tồn tại nếu trùng định danh demo. Thao tác demo chưa được bảo vệ bằng CSDL tạm và cleanup toàn bộ trong `finally`.

**Hướng sửa:** dùng CSDL tạm riêng cho demo; tuyệt đối không dọn dữ liệu thực bằng một mốc thời gian chung.

## Phạm vi hỗ trợ, bảo trì và chất lượng dự án

### 34. [P3 — đọc mã] Đường dẫn, thời gian và môi trường chạy còn phụ thuộc máy

**Vị trí:** [config.py:34](D:/Nhom8_LapTrinhMang/config.py:34), [db/database.py:76](D:/Nhom8_LapTrinhMang/db/database.py:76), [models.py:19](D:/Nhom8_LapTrinhMang/models.py:19), [ui/main_window.py:297](D:/Nhom8_LapTrinhMang/ui/main_window.py:297), [extras/pdf_report.py:529](D:/Nhom8_LapTrinhMang/extras/pdf_report.py:529), [core/interfaces.py:353](D:/Nhom8_LapTrinhMang/core/interfaces.py:353).

- DB_PATH tương đối với thư mục làm việc; chạy script bằng đường dẫn tuyệt đối từ thư mục khác có thể tạo một DB khác, làm tưởng mất baseline/lịch sử. OUI lại được resolve theo thư mục mã nguồn, nên hai loại dữ liệu không cùng quy ước.
- Thời gian DB cố định GMT+7 dạng naive; QDateTime và thời điểm tạo PDF dùng giờ hệ thống. Khi máy khác múi giờ, chọn khoảng báo cáo và dữ liệu lưu có thể lệch. Timestamp còn bị bỏ microsecond và chưa có một ràng buộc thống nhất với datetime có timezone truyền từ API.
- Phần interface dựa trên API Windows; nhánh ICMP/traceroute cho nền tảng khác chưa đủ làm ứng dụng đa nền tảng. GUI/diagnose hiện yêu cầu cả Admin và Npcap; quyền cao áp dụng cho toàn bộ tiến trình UI, CSDL và xuất file. Chưa có cách chạy phần xem lịch sử/báo cáo độc lập với quyền bắt gói.

**Hướng sửa:** resolve dữ liệu theo vị trí ứng dụng hoặc thư mục dữ liệu người dùng, chuẩn hóa thời gian có timezone và kiểm tra môi trường theo từng năng lực cần dùng. Phạm vi Windows hiện là lựa chọn của dự án, cần ghi rõ khi phân phối.

### 35. [P3 — đọc mã] Schema và hợp đồng dữ liệu chưa đủ chặt để nâng cấp an toàn

**Vị trí:** [db/database.py:20](D:/Nhom8_LapTrinhMang/db/database.py:20), [models.py:24](D:/Nhom8_LapTrinhMang/models.py:24), [db/repository.py:63](D:/Nhom8_LapTrinhMang/db/repository.py:63), [db/repository.py:107](D:/Nhom8_LapTrinhMang/db/repository.py:107), [services/baseline.py:27](D:/Nhom8_LapTrinhMang/services/baseline.py:27).

Chỉ có `CREATE TABLE IF NOT EXISTS`, chưa có version/migration cho CSDL cũ. Schema không ràng buộc enum, boolean, RTT/loss hợp lệ hoặc quan hệ lịch sử với thiết bị. Dataclass/API repository cũng chưa xác thực MAC/IP/target; một IP hoặc timestamp không hợp lệ trong DB có thể làm cả `list_devices()`/refresh lỗi. Các thao tác logic như upsert + hiện diện + cảnh báo, hoặc hai khóa baseline, được commit riêng nên có thể để trạng thái dở dang khi lỗi.

**Hướng sửa:** bổ sung validation ở biên, schema version/migration, ràng buộc phù hợp và transaction theo thao tác nghiệp vụ. Cần giữ khả năng biểu diễn tranh chấp IP, không giải quyết bằng cách áp UNIQUE IP toàn cục.

### 36. [P3 — giới hạn hiện có] Tra hãng gần như chỉ đủ cho hai mẫu đã biết

**Vị trí:** [data/oui.csv:1](D:/Nhom8_LapTrinhMang/data/oui.csv:1), [extras/oui.py:34](D:/Nhom8_LapTrinhMang/extras/oui.py:34), [services/scan_loop.py:151](D:/Nhom8_LapTrinhMang/services/scan_loop.py:151).

Danh sách OUI chỉ có hai prefix ZTE và Intel. Hầu hết MAC khác sẽ Unknown; chưa có nguồn cập nhật hoặc hỗ trợ các độ dài assignment khác. Mỗi lookup mở và duyệt CSV lại; thiết bị Unknown tiếp tục lookup ở mỗi scan. Khi mở rộng danh sách, chi phí I/O/tìm tuyến tính tăng. MAC cục bộ cũng không cho phép suy ra hãng chắc chắn từ prefix.

**Hướng sửa:** dùng bộ dữ liệu có nguồn/phiên bản, nạp cache một lần, xử lý riêng MAC cục bộ và giữ trạng thái không xác định khi không đủ bằng chứng.

### 37. [P3 — giới hạn thiết kế] Gợi ý kênh Wi-Fi chỉ là ước lượng và thiếu thông tin lỗi

**Vị trí:** [extras/wifi_channels.py:10](D:/Nhom8_LapTrinhMang/extras/wifi_channels.py:10), [extras/wifi_channels.py:24](D:/Nhom8_LapTrinhMang/extras/wifi_channels.py:24), [extras/wifi_channels.py:117](D:/Nhom8_LapTrinhMang/extras/wifi_channels.py:117), [extras/wifi_channels.py:145](D:/Nhom8_LapTrinhMang/extras/wifi_channels.py:145).

Parser chỉ nhận một số nhãn tiếng Anh/Việt và bảng mã được thử lại theo heuristic. Nếu không đọc được Band, suy ra băng tần chỉ bằng số kênh có thể nhầm với Wi-Fi 6 GHz. Lỗi lệnh, timeout, thiếu quyền/vị trí, WLAN tắt và không có AP đều bị gộp thành `[]`, khó hướng dẫn xử lý đúng.

Điểm kênh chưa xét channel width, mức sử dụng thực, nhiễu ngoài Wi-Fi, trùng BSSID giữa các interface hoặc phân biệt AP của chính mình. RSSI là suy ra từ phần trăm tín hiệu, không phải phép đo phổ. Chưa thể dùng kết quả như một kết luận chắc chắn về kênh tối ưu.

**Hướng sửa:** trả lỗi/trạng thái có cấu trúc, kiểm tra băng tần rõ ràng, loại trùng và trình bày giả định/độ tin cậy của gợi ý.

### 38. [P3 — phạm vi chức năng] Một số chức năng chưa được hoàn thiện hoặc chưa có luồng dùng trực tiếp

**Vị trí:** [extras/telegram_notify.py:6](D:/Nhom8_LapTrinhMang/extras/telegram_notify.py:6), [extras/zalo_notify.py:39](D:/Nhom8_LapTrinhMang/extras/zalo_notify.py:39), [ui/main_window.py:217](D:/Nhom8_LapTrinhMang/ui/main_window.py:217), [README.md:270](D:/Nhom8_LapTrinhMang/README.md:270).

Telegram còn `NotImplementedError`; Zalo chỉ format/demo và trả `not_configured` khi yêu cầu gửi thật. Hai module chưa nối vào pipeline cảnh báo; chưa có gửi, thử lại hay hàng đợi thông báo. UI chưa có các luồng riêng cho traceroute, baseline, lịch sử hiện diện, CSV, Wi-Fi và cài đặt ngưỡng/card. Cảnh báo chỉ hiển thị 20 mục gần nhất, không có xem cũ, lọc/tìm hoặc xác nhận đã xử lý. Biểu đồ RTT chưa tạo legend để giải thích ba đường màu và chưa có biểu đồ loss riêng.

**Hướng sửa:** thống nhất danh sách chức năng được hỗ trợ, hoàn thiện luồng dùng theo ưu tiên; giữ việc demo và gửi thật được mô tả minh bạch như README hiện tại.

### 39. [P3 — đọc mã] Cấu hình và hợp đồng giữa các tầng còn khó thay đổi, dễ lệch

**Vị trí:** [config.py:1](D:/Nhom8_LapTrinhMang/config.py:1), [models.py:42](D:/Nhom8_LapTrinhMang/models.py:42), [backend.py:223](D:/Nhom8_LapTrinhMang/backend.py:223), [services/ping_monitor.py:160](D:/Nhom8_LapTrinhMang/services/ping_monitor.py:160), [ui/main_window.py:391](D:/Nhom8_LapTrinhMang/ui/main_window.py:391).

Đích ngoài, ngưỡng, chu kỳ, giới hạn và đường dẫn chủ yếu viết cứng; chưa có cấu hình người dùng hoặc kiểm chứng ngưỡng trên nhiều điều kiện mạng. Ba vai trò đích và chuỗi verdict/status lặp ở nhiều file. Signal `object`/dict tự do không có schema rõ, UI suy luận trạng thái bằng chuỗi như “Online”, “Chưa xác minh”. Backend lấy trạng thái mutable của monitor qua callback, chưa có một snapshot bất biến và hợp đồng kiểu thống nhất.

Các mô tả “phần của A/B/C”, “chưa làm xong”, “giai đoạn” còn lẫn trong mã đã triển khai; có code dư như vòng tìm thiết bị đầu tiên trong handler checkbox. Các vấn đề này tăng công sửa và nguy cơ các tầng hiểu khác nhau khi thêm tính năng.

**Hướng sửa:** tập trung enum/typed result/snapshot, cấu hình đã validate và tài liệu phản ánh bản hiện tại; dọn code/comment dư theo từng thay đổi có kiểm chứng.

### 40. [P3 — giới hạn phạm vi] Phạm vi mạng được hỗ trợ còn hẹp và thời gian phát hiện không cố định

**Vị trí:** [config.py:10](D:/Nhom8_LapTrinhMang/config.py:10), [config.py:33](D:/Nhom8_LapTrinhMang/config.py:33), [core/interfaces.py:296](D:/Nhom8_LapTrinhMang/core/interfaces.py:296), [core/interfaces.py:329](D:/Nhom8_LapTrinhMang/core/interfaces.py:329), [services/ping_monitor.py:167](D:/Nhom8_LapTrinhMang/services/ping_monitor.py:167).

- Subnet trên 1.024 host bị từ chối hoàn toàn, chưa có chọn phạm vi nhỏ/chia lô/tiến độ. `/18` ở lỗi đã biết không được scan; tăng hằng số đơn thuần chưa giải quyết thời gian/tải.
- ARP chỉ quan sát LAN IPv4 cùng miền broadcast có thể tiếp cận; không tìm được đầy đủ thiết bị IPv6, phía sau router/VLAN hoặc bị client isolation. Thiết bị ngủ/im lặng có thể bị đánh dấu Offline theo tiêu chí vắng ARP; Online/Offline là kết quả quan sát, không phải trạng thái xác thực của toàn thiết bị.
- Chỉ theo dõi một card đã chọn; không có UI chọn card hoặc chuyển dự phòng. Đây là hành vi có chủ đích theo README, vẫn là giới hạn khi dùng máy nhiều card. Bảng IPv4 chỉ giữ một địa chỉ trên mỗi interface.
- Ba đích được ping tuần tự, mỗi đích có timeout một giây. Khi cả ba timeout, một vòng có thể mất khoảng ba giây cộng overhead, vượt cấu hình hai giây; các mốc cũng không được đo cùng thời điểm. Cửa sổ 30 mẫu không luôn tương ứng 60 giây. Đánh dấu Offline cần ba lượt scan hợp lệ nên thường trễ khoảng 60–90 giây hoặc lâu hơn tùy pha/lỗi/thời gian scan.

**Hướng sửa:** công bố rõ phạm vi và độ trễ phát hiện; cho chọn dải/card, có ngân sách scan, cân nhắc đo đồng thời và gắn timestamp chính xác khi so sánh các mốc.

### 41. [P2/P3 — xác nhận từ Git] Repository đang chứa dữ liệu chạy và bộ công cụ dựng artifact rất lớn

**Vị trí:** [.gitignore:1](D:/Nhom8_LapTrinhMang/.gitignore:1), [data/netguard.db-wal](D:/Nhom8_LapTrinhMang/data/netguard.db-wal), [.presentation-build/export.mjs:5](D:/Nhom8_LapTrinhMang/.presentation-build/export.mjs:5).

Git theo dõi 8.672 file, trong đó `.presentation-build` có 8.607 file, khoảng **391 MB** dung lượng nội dung ở HEAD; riêng đường dẫn `node_modules` có 8.530 file. Đây là tổng kích thước file trong cây Git, không phải dung lượng clone đã nén. Có các native binary phụ thuộc nền tảng, file cache và artifact trung gian làm diff/status nhiễu, tăng chi phí tải/lưu và khó xác định dependency cần thiết để dựng lại.

DB chính bị ignore bằng `*.db`, nhưng `.db-wal` khoảng 4,14 MB và `.db-shm` vẫn được track. WAL chứa các trang dữ liệu SQLite, cần được coi là dữ liệu chạy có thể chứa lịch sử mạng; commit nó không phải cách sao lưu nhất quán và có nguy cơ đưa dữ liệu quan sát vào Git. Chỉ thêm ignore không loại file đã track.

Các script dựng slide còn viết cứng ổ D, tài khoản Windows và đường dẫn cache Codex của máy tác giả, nên việc dựng lại artifact trên máy thành viên khác chưa tái lập được.

**Hướng sửa:** tách source/tooling/output, khai báo dependency bằng manifest/lock phù hợp, bỏ track cache/node_modules và sidecar DB trong một thay đổi được kiểm tra; xem xét dữ liệu đã vào lịch sử trước khi chia sẻ repo. Không tự ý xóa lịch sử Git hoặc dữ liệu hiện tại.

### 42. [P2/P3 — đọc mã và chạy test] Test hiện chưa bảo vệ các rủi ro quan trọng của luồng thật

**Vị trí:** [tests/test_simulate_network.py:2](D:/Nhom8_LapTrinhMang/tests/test_simulate_network.py:2), [tests/simulate/simulate_network.py:18](D:/Nhom8_LapTrinhMang/tests/simulate/simulate_network.py:18), [tests/test_network_recovery.py:101](D:/Nhom8_LapTrinhMang/tests/test_network_recovery.py:101), [tests/test_ui_smoke.py:27](D:/Nhom8_LapTrinhMang/tests/test_ui_smoke.py:27), [docs/test-report.md:29](D:/Nhom8_LapTrinhMang/docs/test-report.md:29).

65 test hiện tại là kết quả tốt cho các tình huống đã viết, không chứng minh các chức năng thật không có lỗi. Bốn test mô phỏng gọi các hàm phát hiện riêng trong `tests/simulate`, không gọi `ArpAnomalyDetector` hoặc scan loop thật. Test lỗi socket mock pinger cấp cao nên không phát hiện việc thư viện thật nuốt lỗi gửi. Test UI mock toàn bộ tray; chưa bảo vệ điều kiện icon rỗng/ẩn cửa sổ.

Chưa có bài kiểm tra trực tiếp cho xuất PDF, phần lớn quy tắc anomaly/chống lặp, lỗi AsyncSniffer, persistence/repository, đổi mạng giữa một scan, hết timeout khi dừng, khôi phục dữ liệu và tải kéo dài. Chưa có cấu hình CI, lint/type check hoặc đo coverage trong phần source dự án được kiểm tra. Không có kết quả mạng thật trong lần rà soát này; tài liệu test-report vẫn tổng kết bộ cũ 20 test và chưa được đồng bộ với 65 test hiện có.

**Hướng sửa:** bổ sung hồi quy theo các lỗi tái hiện được, kiểm tra đúng ranh giới dependency và có môi trường cài mới; sau đó chạy kiểm chứng mạng thật có kiểm soát, kiểm tra trực quan PDF/tray và đo tải dài hạn. Không cần thêm test chỉ để lặp lại implementation.

### 43. [P3 — đã tái hiện điều kiện] CSV chưa bảo vệ trường văn bản có thể được hiểu là công thức

**Vị trí:** [extras/csv_export.py:35](D:/Nhom8_LapTrinhMang/extras/csv_export.py:35).

Tên/ghi chú được ghi nguyên dạng. `csv.writer` xử lý dấu phân cách, không vô hiệu hóa công thức khi file được mở bằng phần mềm bảng tính; đã xác nhận tên `=1+1` còn nguyên trong ô CSV. Trong luồng hiện tại, tên/ghi chú do người dùng đặt, không tự lấy từ dữ liệu LAN, nên đây là rủi ro có điều kiện khi xuất/chia sẻ nội dung không tin cậy, không phải chứng cứ một thiết bị mạng có thể tự thực thi mã trên máy.

**Hướng sửa:** có chính sách xuất text an toàn cho phần mềm bảng tính, áp dụng cho các trường văn bản và kiểm thử cách phần mềm đích diễn giải file.

### 44. [P3 — đọc mã] Trạng thái phiên backend chưa được reset và công bố nhất quán

**Vị trí:** [backend.py:168](D:/Nhom8_LapTrinhMang/backend.py:168), [backend.py:206](D:/Nhom8_LapTrinhMang/backend.py:206), [backend.py:250](D:/Nhom8_LapTrinhMang/backend.py:250), [services/ping_monitor.py:194](D:/Nhom8_LapTrinhMang/services/ping_monitor.py:194), [services/ping_monitor.py:235](D:/Nhom8_LapTrinhMang/services/ping_monitor.py:235).

Đổi kết nối xóa measurements và MAC phiên, nhưng không xóa/đánh dấu hết hiệu lực diagnosis của backend; `get_latest_diagnosis()` vẫn có thể trả kết luận mạng cũ. UI hiện tự xóa bản sao riêng khi nhận connection signal, nên hai nơi giữ trạng thái có thể khác nhau. `stop()` cũng không reset các tập/metadata phiên; khi tái sử dụng cùng đối tượng backend, dữ liệu phiên trước có thể còn. Ping monitor reset cửa sổ khi đổi mạng nhưng giữ `_last_emitted_verdict/text`, có thể bỏ qua thông báo cần phát lại nếu lần chuyển trạng thái ngắn chưa đủ để có verdict khác.

**Hướng sửa:** định nghĩa state machine theo phiên kết nối, đánh dấu tính hợp lệ và phát snapshot thống nhất; reset đầy đủ khi stop/start hoặc đổi ngữ cảnh. Cần thêm test vòng đời này trước khi cung cấp chức năng khởi động lại dịch vụ trong cùng cửa sổ.

## Thứ tự xử lý đề nghị

1. **Làm kết quả quan sát đáng tin:** 01, 02, 03, 14; xử lý 25 để tính năng PDF thực sự chạy được.
2. **Ngăn dữ liệu sai khi đổi mạng và sai lịch sử:** 07, 08, 09, 19, 20, 21, 22, 23.
3. **Hoàn thiện cảnh báo và chẩn đoán:** 04, 05, 06, 10, 11, 15, 16, 17, 18.
4. **Ổn định vận hành:** 13, 24, 26–33, 41; bổ sung các bài hồi quy ở 42 cùng từng lần sửa.
5. **Mở rộng phạm vi và giảm công bảo trì:** các giới hạn P3 còn lại theo mục tiêu sử dụng thực tế.

Các kết quả trong báo cáo đủ để lập danh sách sửa cụ thể. Chưa có đánh giá độ bao phủ toàn bộ trạng thái mạng, hiệu năng đo thực tế trên subnet lớn, tương thích nhiều bản Windows/Npcap hay kiểm toán bảo mật dependency.
