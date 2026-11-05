# Sổ tay hiểu dự án NetGuard và trả lời Q&A

Ngày đối chiếu mã: 05/11/2026. Dành cho thành viên Nhóm 8 học để trình bày môn Lập trình mạng.

## 0. Đọc trạng thái phiên bản trước khi học

Trong lúc khảo sát, mã nguồn thay đổi do một thao tác merge từ bên ngoài phiên đọc này:

- Trước merge, đã chạy `.\.venv\Scripts\python.exe -m pytest -q --tb=short`, kết quả **65 passed in 7.52s**.
- Sau đó, `git status --short` báo xung đột tại README, giao diện, MAC, Wi-Fi và Zalo. `ui/main_window.py` chứa dấu xung đột và kiểm tra cú pháp báo `SyntaxError`.
- Các module OUI, CSV và PDF ban đầu là khung; mã triển khai mới xuất hiện trong lần merge. Vì vậy, câu “chưa có mã PDF/CSV/OUI” trong kịch bản cũ không còn mô tả đủ trạng thái mới. Cũng chưa thể dùng mã vừa nhập làm bằng chứng rằng tích hợp đã chạy thành công.
- Sổ tay giải thích lõi đã đối chiếu, đồng thời ghi riêng những phần mới cần xác minh sau merge. Không dùng kết quả 65 test trước merge để khẳng định bản sau merge chạy đạt.

Đây là trạng thái quan sát trong lần chuẩn bị tài liệu, không phải cam kết trạng thái repo trong những lần mở sau. Trước buổi báo cáo, kiểm tra lại mã, test và demo thực tế.

## 1. Câu giới thiệu phải nói được trong 30 giây

> NetGuard là ứng dụng desktop viết bằng Python, giúp theo dõi các thiết bị quan sát được trong mạng LAN IPv4. Ứng dụng dùng ARP để phát hiện IP và MAC, lưu danh sách cùng lịch sử vào SQLite, cảnh báo thiết bị mới sau khi thiết lập danh sách ban đầu. Đồng thời, chương trình đo ICMP tới gateway, một hop phía sau gateway và một đích ngoài để hỗ trợ khoanh vùng sự cố kết nối.

Ba việc chính: **quan sát thiết bị, cảnh báo thay đổi, hỗ trợ chẩn đoán**.

Phạm vi chính: Windows, LAN IPv4, mạng gia đình hoặc phòng học nhỏ. Không tự chặn thiết bị, không đo băng thông tải xuống, không chứng minh ai là hacker và không bảo đảm tìm ra nguyên nhân sự cố chính xác.

## 2. Bài toán, giá trị và kiến thức môn học

Bài toán thực tế: khó biết thiết bị nào xuất hiện trong LAN; khi mạng chậm thường phải mở nhiều công cụ để kiểm tra; cần giữ lịch sử thay vì chỉ nhìn kết quả một thời điểm.

Giá trị của NetGuard là ghép việc quan sát thiết bị, đo kết nối, lưu lịch sử và hiển thị vào một ứng dụng. Không nên tuyên bố nhóm phát minh ra ARP hay ping.

Kiến thức vận dụng:

- Địa chỉ IPv4, subnet mask, gateway và bảng định tuyến.
- Ethernet frame, broadcast, địa chỉ MAC và ARP Request/Reply.
- ICMP Echo, RTT, timeout, mất gói và TTL trong traceroute.
- Lập trình I/O mạng qua thư viện, xử lý lỗi và các tác vụ nền.
- Tách tầng, callback, Qt signals/slots, lưu trữ và đồng bộ truy cập dữ liệu.

Nếu hỏi “mô hình client/server ở đâu?”: đây là ứng dụng giám sát cục bộ. Chương trình chủ động gửi phép đo và xử lý phản hồi; không có server web riêng hay giao thức TCP client/server tự thiết kế trong các luồng chính hiện tại.

## 3. Từ vựng cần hiểu bằng ví dụ

| Khái niệm | Cách hiểu và liên hệ dự án |
|---|---|
| LAN | Mạng cục bộ; phạm vi ARP phụ thuộc miền liên kết/broadcast quan sát được |
| IPv4 | Địa chỉ logic như `192.168.1.10`; có thể đổi khi DHCP cấp lại |
| MAC | Địa chỉ liên kết như `ac:74:b1:41:a5:d2`; dùng làm khóa nhận diện trong CSDL |
| Subnet mask | Xác định phần mạng/phần host để tính dải quét |
| Gateway | Router mà máy thường gửi gói tới khi đi ra ngoài subnet |
| Broadcast | Gửi frame tới `ff:ff:ff:ff:ff:ff` trong miền mạng cục bộ |
| ARP | Hỏi địa chỉ MAC tương ứng một IPv4 trên liên kết cục bộ |
| ICMP | Giao thức thông báo/điều khiển đi cùng IP; ping dùng Echo Request/Reply |
| RTT | Thời gian từ gửi yêu cầu đến nhận phản hồi, tính bằng ms, gồm cả hai chiều |
| Packet loss | Trong chương trình: tỷ lệ phép ping không nhận phản hồi trong thời hạn |
| TTL | Giới hạn số chặng của gói IP; traceroute tăng TTL để quan sát đường đi |
| Hop | Một chặng có thể quan sát qua phản hồi traceroute |
| ISP | Nhà cung cấp Internet; nhãn `isp` trong mã chỉ là mốc ước lượng sau gateway |
| Baseline thiết bị | Cờ đánh dấu đã kết thúc giai đoạn thu thập thiết bị ban đầu |
| Baseline RTT | Mức RTT tham chiếu tính từ các phản hồi thành công trong cửa sổ đo |
| OUI | Trong module này: tiền tố 3 byte MAC dùng để tra tên hãng trong CSV |
| MAC cục bộ | MAC có bit quản lý cục bộ; có thể do riêng tư hoặc cấu hình thủ công |

Ví dụ subnet thông thường: IP `192.168.1.10`, mask `255.255.255.0` tương ứng `/24`, mạng `192.168.1.0/24`, host `.1` đến `.254`, broadcast `.255`. Đó là 254 địa chỉ có thể quét, không phải 254 thiết bị chắc chắn đang tồn tại.

Tránh nói MAC không bao giờ đổi: điện thoại có thể dùng MAC riêng tư và địa chỉ cũng có thể bị giả mạo. Tránh nói “MAC là danh tính người dùng”.

## 4. Công nghệ và lý do lựa chọn

| Thành phần | Vai trò thực tế | Lý do phù hợp |
|---|---|---|
| Python | Ngôn ngữ của ứng dụng | Dễ tổ chức logic và ghép thư viện mạng/giao diện |
| Scapy | Dựng/gửi frame ARP và nghe phản hồi | Có khả năng thao tác gói tin mức thấp |
| Npcap | Hạ tầng bắt/gửi gói cho Scapy trên Windows | Cho phép làm việc với frame trên card mạng |
| icmplib | Gửi phép ping IPv4, trả RTT | Giảm việc tự viết xử lý raw ICMP |
| `tracert.exe` | Traceroute trên Windows | Dùng cơ chế và đường định tuyến của hệ điều hành |
| PySide6 | Giao diện Qt | Có bảng, hộp thoại, signals/slots và khay hệ thống |
| pyqtgraph | Đồ thị RTT ở UI | Phù hợp hiển thị dữ liệu đo theo thời gian |
| SQLite | Lưu cục bộ | Không cần dựng máy chủ CSDL riêng |
| pytest | Kiểm thử tự động | Dễ kiểm tra logic với dữ liệu kiểm soát và thay thế I/O mạng |
| ReportLab | Mã xuất PDF mới được đưa vào | Tạo văn bản, bảng và trang PDF |
| matplotlib | Mã PDF mới dùng để vẽ biểu đồ | Cần xác minh phụ thuộc sau merge; chưa thấy trong requirements khi khảo sát |

Không gọi PySide6 là PyQt6: hai gói khác nhau. Không nói toàn bộ ping đều đi qua Npcap: luồng ARP dùng Scapy/Npcap, còn luồng ICMP gọi icmplib. Kiểm tra khởi động của bản hiện tại vẫn yêu cầu Admin và Npcap cho chế độ giám sát tích hợp.

## 5. Kiến trúc và cách lần theo mã

```text
main.py: chọn CLI hoặc mở GUI
    |
    +-- GUI --> ui/main_window.py
    |               |
    |           backend.py: hợp đồng và Qt signals
    |               |
    +------------ services/ ---------------------+
                 |                              |
         ScanLoop / PingMonitor         baseline / alerts
                 |
               core/
         ARP / ICMP / traceroute / diagnosis / interfaces
                 |
         db/repository.py --> db/database.py --> SQLite

extras/: MAC, OUI, Wi-Fi, CSV, PDF, thông báo mở rộng
```

`models.py` chứa dataclass dùng chung: `Device`, `PingResult`, `Alert`, `Diagnosis`, `Hop`. `config.py` chứa chu kỳ, ngưỡng, đường dẫn.

Phân biệt vai trò:

- `core/`: thao tác mạng và quy tắc tính toán; không phụ thuộc Qt. `diagnose()` là hàm thuần xét thống kê.
- `services/`: điều phối quét/ping định kỳ, lưu dữ liệu, sinh sự kiện qua callback.
- `backend.py`: cầu nối cho GUI, chuyển callback nền thành Qt signals, cung cấp các hàm quản lý thiết bị và truy vấn.
- `ui/`: hiển thị dữ liệu và nhận thao tác của người dùng.
- `db/`: định nghĩa bảng, giao dịch, chuyển dòng dữ liệu thành dataclass.

Một luồng ví dụ: **ARP Reply → ScanEntry → ScanLoop → Device và SQLite → callback → Backend signal → bảng thiết bị**.

Luồng chẩn đoán: **ping → RTT hoặc timeout → lịch sử cửa sổ → TargetStats → diagnose → ổn định kết luận → Backend signal → UI**.

Điểm vào GUI tạo `QApplication`, kiểm tra môi trường, tạo Backend/MainWindow, chạy dịch vụ và vào vòng lặp Qt. Khi thoát, dừng dịch vụ trước khi đóng CSDL.

## 6. Quét thiết bị bằng ARP: phải kể lại được từng bước

Mã chính: `core/interfaces.py`, `core/arp_scanner.py`, `services/scan_loop.py`.

1. Đọc card mạng và cấu hình IPv4 từ Windows; ưu tiên card thật có kết nối và gateway, tham khảo card Windows dùng để đi tới `1.1.1.1`.
2. Tính subnet từ IP/mask; từ chối subnet trên 1.024 host trước khi liệt kê toàn bộ.
3. Tìm card Scapy có cùng IfIndex để gửi/nhận đúng card.
4. Mở `AsyncSniffer` lọc ARP; đợi khoảng 0,8 giây cho capture handle sẵn sàng.
5. Dựng frame `Ether(src=MAC_máy, dst=broadcast) / ARP(hwsrc=MAC_máy, psrc=IP_máy, pdst=IP_đích)` cho các host.
6. Gửi bằng `sendp`, giãn cách khoảng 1 ms/gói; mặc định hai vòng, chờ phản hồi 2 giây mỗi vòng.
7. Nhận ARP Reply (`op == 2`), lấy `psrc` và `hwsrc`; chỉ nhận IP trong dải và bỏ MAC rỗng/toàn 0.
8. Gộp kết quả theo IP, thêm chính máy đang chạy và sắp xếp IP theo giá trị số.
9. Dịch vụ tìm thiết bị theo MAC, cập nhật IP/thông tin quan sát, giữ tên/ghi chú/tin cậy đã lưu.
10. Sau một lượt quét hoàn tất, xét thiết bị vắng mặt và làm mới giao diện.

Câu giải thích ARP: “Máy hỏi: ai đang giữ IP này? Thiết bị có IP đó phản hồi MAC của mình. Chương trình thu các cặp IP–MAC để lập danh sách.”

Vì sao không dùng `srp()` trong bản này: ghi chú mã cho biết môi trường Windows của nhóm có phản hồi trong capture nhưng Scapy ghép request/reply không thành công. Bản triển khai tách nghe và gửi. Đây là cách xử lý cho môi trường đã gặp, không có nghĩa `srp()` luôn bị lỗi.

Vì sao thêm máy mình: máy không tự trả lời yêu cầu ARP của chính nó theo cách quét này, nên chương trình thêm IP/MAC của card đã chọn. Do đó tổng kết quả không hoàn toàn là số thiết bị khác trả lời ARP.

Giới hạn: router thường không chuyển tiếp broadcast ARP sang subnet khác; client isolation, VLAN, thiết bị ngủ hoặc không phản hồi có thể làm thiếu dữ liệu. Cùng tên Wi-Fi chưa chắc cùng miền có thể quan sát nhau.

## 7. Online, offline và dữ liệu cũ

Thông số quét định kỳ: 30 giây; một lần quét mặc định gửi hai vòng. Nếu tác vụ kéo dài, chu kỳ thực tế có thể dài hơn cấu hình.

- Thấy MAC trong lần quét hợp lệ: đặt online, đặt lại bộ đếm vắng mặt.
- Không thấy trong ba lần quét hợp lệ liên tiếp: đánh dấu offline.
- Quét ném lỗi hoặc card mất kết nối: không dùng lỗi đó để tăng vắng mặt như một lần quét thành công.
- Kết nối thay đổi: đọc lại IP/mask/gateway, xóa bộ đếm liên quan và mở lại listener phù hợp.
- Sau khi đã chọn card, dịch vụ tiếp tục theo dõi card đó; không âm thầm chuyển sang Ethernet khác nếu Wi-Fi đã chọn bị tắt.

Không hứa “đúng 90 giây sẽ offline”: còn phụ thuộc thời điểm thiết bị rời đi so với lượt quét và thời gian chạy từng lượt.

Trên UI bản trước merge, dữ liệu từ lần chạy cũ chưa được quan sát trong phiên hiện tại hiện “Chưa xác minh trong phiên”; khi mất LAN hiện trạng thái chưa xác minh do mất LAN. `device.online` đã lưu không đủ chứng minh thiết bị đang có mặt ngay lúc mở app.

Một chi tiết cần cải thiện nếu hỏi sâu: `repository.set_online()` cập nhật `last_seen` cả khi chuyển offline. Vì thế không nên mô tả cột này là bằng chứng chính xác tuyệt đối của thời điểm ARP Reply cuối cùng. Nên tách thời điểm quan sát cuối và thời điểm thay đổi trạng thái.

## 8. Baseline, trusted và cảnh báo thiết bị mới

Mã: `services/baseline.py`, `services/scan_loop.py`, `services/alerts.py`.

Trước baseline: thiết bị mới được lưu với `trusted=False`; nhánh cảnh báo **thiết bị mới** chưa hoạt động. Bộ cảnh báo bất thường ARP là luồng riêng, không nên khẳng định mọi loại cảnh báo đều bị tắt trước baseline.

Sau baseline, điều kiện cảnh báo thiết bị mới là:

```text
MAC chưa có trong Devices
AND baseline đã được chốt
AND thiết bị chưa tin cậy
AND không bị hạn chế bởi thời gian chống lặp
```

Chốt bằng `python main.py --cli baseline` sau khi monitor/GUI đã quét và lưu đủ thiết bị. Lệnh `scan` chỉ in kết quả, không tự thực hiện luồng lưu thiết bị của `ScanLoop`; không dùng `scan` một mình để thay bước thu thập baseline.

`finish_baseline()` lưu cờ `baseline_done` và mốc `baseline_at` vào `Meta`. Không tự đổi toàn bộ thiết bị sang trusted và không chụp một bảng snapshot riêng. “Tin cậy tất cả” chỉ đổi cờ trusted, không gọi hàm chốt baseline.

Thiết bị đã có trong CSDL, kể cả chưa tin cậy, quay lại mạng không thỏa điều kiện `is_new`. Vì vậy không hứa mọi lần thiết bị lạ quay lại đều phát cảnh báo mới.

Thời gian chống lặp mặc định 30 phút. **Mã hiện tại truy vấn cảnh báo gần nhất theo MAC, chưa phân biệt loại cảnh báo**. Một cảnh báo có thể hạn chế một cảnh báo khác cho cùng MAC trong cửa sổ này. Không lặp lại mô tả “theo MAC và loại” trong chú thích như thể đã được cài đặt đúng.

Không coi trusted là xác thực bảo mật: đó là ghi chú tin cậy do người dùng đặt cho địa chỉ quan sát được. MAC vẫn có thể bị đổi hoặc giả mạo.

## 9. Nghe ARP thụ động và phát hiện bất thường

`ArpListener` nghe ARP Reply và các thông báo ARP phù hợp; chuyển quan sát thành `ArpObservation`. Khác với quét chủ động, listener không tự phát yêu cầu. Nó cũng không thể nhìn thấy mọi unicast giữa các máy khác trong mạng chuyển mạch.

`ArpAnomalyDetector` có các quy tắc:

- Nhiều MAC cùng nhận một IP trong cửa sổ 30 giây → cảnh báo tranh chấp IP.
- MAC của gateway khác MAC được biết → kiểm tra có chủ cũ vừa hoạt động hoặc có ít nhất hai claim trong cửa sổ xác nhận 5 giây, rồi cảnh báo mức nguy hiểm.
- IP đổi MAC khi thiết bị cũ vẫn online và gần đây còn hoạt động → cần xác nhận lặp để giảm cảnh báo do DHCP.
- Một MAC quảng bá ít nhất ba IP trong cửa sổ 60 giây → cảnh báo.

Các quy tắc cung cấp dấu hiệu để kiểm tra; DHCP, cấu hình nhiều IP, thiết bị mạng đặc biệt hoặc thay router có thể tạo thay đổi hợp lệ. Không dùng một cảnh báo để kết luận có tấn công ARP spoofing.

Giới hạn quan trọng: kết quả scanner gộp theo IP nên có thể chỉ giữ một MAC cho IP trùng. Luồng listener và bộ phát hiện bất thường bổ sung việc quan sát nhiều claim; đây không phải bằng chứng đã phát hiện được mọi xung đột thực tế.

## 10. ICMP, số đo và quy tắc chẩn đoán

`core/icmp.py` gọi `icmplib.ping()` với `count=1`, IPv4, IP nguồn lấy từ card đang theo dõi. Phản hồi trả RTT; không có phản hồi trả `None`; lỗi socket/quyền/IP nguồn thành ngoại lệ có thông báo.

Ba mốc:

| Tên trong mã | Địa chỉ | Ý nghĩa |
|---|---|---|
| `router` | Gateway của card | Quan sát đường từ máy tới router cục bộ |
| `isp` | Hop phản hồi đầu tiên sau gateway | Mốc ước lượng phía sau router; không xác minh chủ sở hữu |
| `external` | `1.1.1.1` | Một điểm tham chiếu bên ngoài bằng IP |

Vì dùng IP số, phép đo ngoài không kiểm tra riêng quá trình phân giải DNS. Ping được địa chỉ này cũng không chứng minh website, DNS, TCP hay HTTPS của người dùng hoạt động bình thường.

Chu kỳ cấu hình là 2 giây, timeout mỗi ping là 1 giây. Ba mốc được ping tuần tự trong một luồng; nếu nhiều mốc timeout, một lượt có thể vượt 2 giây. Đây không phải ba phép đo hoàn toàn đồng thời.

Một `PingResult.loss_pct` là 0% hoặc 100% do một mẫu chỉ gửi một ping. Còn tỷ lệ của cửa sổ:

```text
loss_pct = số mẫu không phản hồi / tổng mẫu hợp lệ trong cửa sổ × 100
```

Ví dụ 2/30 không phản hồi → khoảng 6,67%, vượt ngưỡng 5%; 1/30 → khoảng 3,33%, chưa vượt ngưỡng mất gói. 1/10 → 10%. Đúng 5% chưa bị đánh dấu xấu bằng điều kiện `>`.

Thống kê dùng tối đa 30 mẫu gần nhất cho từng mốc, ít nhất 10 mẫu mới đủ điều kiện xét. RTT trung vị chỉ lấy mẫu phản hồi thành công. RTT nền lấy phần tử ở chỉ số `int((n - 1) * 0.25)` của danh sách RTT thành công đã sắp xếp; đó là cách ước lượng phân vị 25 trong mã.

Một mốc bị coi là xấu nếu đủ mẫu, phép đo khả dụng và thỏa ít nhất một điều kiện:

```text
loss_pct > 5
OR
rtt_median > max(3 × rtt_baseline, 20 ms)
```

Ví dụ minh họa trực tiếp cho hàm quy tắc: nếu baseline là 8 ms thì ngưỡng là 24 ms; median 30 ms vượt ngưỡng, median đúng 24 ms chưa vượt. Trong hoạt động thật, median và baseline được tính cùng cửa sổ; nếu toàn bộ mẫu chậm đều, baseline có thể cũng tăng và làm giảm khả năng phát hiện. Baseline RTT hiện không phải một giá trị khỏe mạnh cố định đã hiệu chuẩn từ trước.

Thứ tự trong `diagnose()`:

1. Router đủ mẫu và xấu → `home_issue`.
2. Không đo được router hoặc thiếu mẫu → `unknown`.
3. Router đủ mẫu và không xấu; mốc ISP đủ mẫu và xấu → `isp_issue`.
4. Thiếu phép đo ngoài cần thiết → `unknown`.
5. Thiếu ISP nhưng đích ngoài xấu → `internet_issue`, có giải thích thiếu hop nhà mạng.
6. Thiếu ISP, đích ngoài không xấu → `unknown`, chưa kết luận đủ ba mốc.
7. Có đủ mốc: đích ngoài xấu → `internet_issue`; các mốc đều không xấu → `ok`.

Các mã verdict là nhãn kết quả thuật toán. Khi nói trước lớp, dùng “nghi vấn” hoặc “hỗ trợ khoanh vùng”, dù câu chữ trong phần mềm có thể ghi “lỗi”.

`PingMonitor` thường chỉ phát kết luận khi cùng verdict tồn tại ba lần đánh giá liên tiếp; các cửa sổ trượt chồng lấn dữ liệu, không phải ba bộ 30 mẫu độc lập. Mất LAN hoặc không có gateway được phản ánh ngay. Không cần chờ đủ 30 mẫu mới xét; 30 là độ dài tối đa, 10 là tối thiểu.

Khi cấu hình kết nối thay đổi, monitor xóa lịch sử thống kê trong RAM, xóa mốc ISP và thu thập lại. Kết quả traceroute cũ bị loại bằng số thế hệ kết nối. Lịch sử SQLite vẫn còn để xem quá khứ.

Phân biệt quan trọng: **timeout sau phép ping** có thể được ghi là không phản hồi; **lỗi tạo/gửi socket** không phải bằng chứng mất gói và không được thêm như mẫu mất 100%.

## 11. Traceroute: cách giải thích và giới hạn

Nguyên lý: gửi gói với TTL tăng dần. Router làm hết TTL có thể gửi ICMP Time Exceeded; đích trả Echo Reply. Chương trình dùng các phản hồi để dựng danh sách hop. Dấu `*` là không nhận phản hồi tương ứng, chưa chứng minh router đó làm rơi lưu lượng chuyển tiếp của người dùng.

Windows dùng `tracert.exe` với `-d` bỏ tra tên, `-4` dùng IPv4, `-h` giới hạn hop và `-w` timeout. Bản cấu hình giới hạn 15 hop; Windows gửi ba probe mỗi TTL dù tham số `count` của wrapper mặc định là 1. Không nên nói mọi nền tảng đều gửi một gói cho mỗi TTL.

`find_isp_hop()` tìm hop có IP đầu tiên sau gateway; nếu gateway không hiện, tìm phản hồi có TTL > 1. Có thể gặp double NAT, router trung gian, hop im lặng hoặc mốc được chọn không thật sự thuộc ISP. Đây là ước lượng vị trí, không tra ASN hay xác minh nhà mạng.

`mark_latency_jump()` đánh dấu điểm tăng RTT rõ có phản hồi kế tiếp còn cao; không coi một hop trả lời ICMP chậm đơn lẻ là bằng chứng tắc nghẽn. RTT hop là số đo đi-về tới hop, không phải thời gian riêng của đoạn nối giữa hai router; không tùy tiện trừ để coi là độ trễ chính xác một liên kết.

PingMonitor thử tìm lại route sau khoảng 60 giây khi chưa có mốc và làm mới khoảng 300 giây khi đã có. Việc dò đường chạy ở luồng riêng để không chặn vòng ping.

## 12. Cơ sở dữ liệu và đa luồng

Đường dẫn mặc định: `data/netguard.db`, tính theo thư mục làm việc. Nên chạy từ gốc dự án.

| Bảng | Nội dung | Điểm cần nhớ |
|---|---|---|
| `Devices` | MAC, IP, tên, ghi chú, vendor, trusted, online, các mốc thời gian | MAC là khóa chính; một dòng mỗi MAC |
| `PresenceLog` | MAC, online/offline, thời điểm | Ghi khi đổi trạng thái hoặc chưa có lịch sử |
| `PingLog` | target, RTT có thể NULL, loss_pct, thời điểm | target lưu nhãn router/isp/external |
| `Alerts` | mức độ, nội dung, MAC liên quan, thời điểm | MAC có thể NULL |
| `Meta` | key/value | Lưu cờ và thời điểm baseline |

Có index theo MAC/thời gian hoặc target/thời gian để hỗ trợ truy vấn. Câu SQL truyền tham số bằng `?`; không nối trực tiếp dữ liệu người dùng vào câu SQL.

Một kết nối SQLite dùng chung, `check_same_thread=False`, được bảo vệ bằng `threading.RLock`. Giao dịch commit khi xong, rollback nếu lỗi. WAL hỗ trợ phối hợp đọc/ghi ở mức SQLite, nhưng các đoạn dùng cùng khóa của tiến trình vẫn lần lượt chạy; không nói chương trình cho nhiều luồng ghi đồng thời vào một kết nối mà không cần khóa.

Thời gian lõi dùng giờ Việt Nam GMT+7, lưu chuỗi ISO 8601 không offset, bỏ microsecond. Muốn mở rộng đa múi giờ cần quy ước thời gian rõ hơn.

Các tác vụ nền: ScanLoop, PingMonitor, ARP capture và dò route khi cần. Thread phù hợp vì chủ yếu chờ I/O. Python GIL không khiến việc chờ I/O của mô hình này vô ích, nhưng cũng không có nghĩa tất cả tính toán Python chạy song song trên nhiều lõi.

Core/services dùng callback để không phụ thuộc Qt; backend chuyển sang Qt signals để UI xử lý trong cơ chế sự kiện. Tác vụ nền không trực tiếp sửa widget.

Hạn chế lưu trữ: chưa thấy cơ chế tự dọn PingLog theo thời hạn; nếu đủ ba mốc và đo khoảng hai giây/lượt liên tục thì ước tính cỡ 129.600 bản ghi/ngày. Đây là phép ước lượng, không phải số benchmark đã đo.

Không phải mọi thứ đều lưu lâu dài: kết luận chẩn đoán của Backend và traceroute thủ công gần nhất giữ trong bộ nhớ phiên; Backend giới hạn danh sách kết luận gần đây ở 500 phần tử. Không có bảng Diagnosis hay Traceroute trong schema hiện tại.

Chưa tách dữ liệu theo định danh mạng/router. Chuyển sang mạng khác có thể dùng chung Devices, baseline và lịch sử nhãn đích. Đây là hướng cải thiện quan trọng nếu phát triển sản phẩm.

## 13. Giao diện và các tính năng bổ sung

Hợp đồng GUI đã đọc trước merge có bốn tab: Thiết bị, Cảnh báo, Chẩn đoán, Báo cáo. Thiết bị có sửa tên/ghi chú/tin cậy. Cảnh báo hiển thị các sự kiện gần đây và thông báo khay. Chẩn đoán có phép đo hiện tại và đồ thị lịch sử RTT 30 phút. Dữ liệu lịch sử và dữ liệu đang đo phải được phân biệt.

Đồ thị 30 phút khác cửa sổ 30 mẫu: một bên là khoảng lịch sử hiển thị, một bên là đầu vào ngắn hạn cho thuật toán. Không nói chương trình cần đo 30 phút mới chẩn đoán.

Đóng bằng X đưa cửa sổ xuống tray; muốn dừng chọn Thoát. Kiểm tra icon tray trước buổi demo vì icon theo theme có thể không rõ trên một số máy.

Trạng thái tính năng phụ khi đang nhập nhánh:

| Tính năng | Điều đã thấy trong mã | Cách trình bày đúng |
|---|---|---|
| MAC cục bộ | Đọc bit `0x02` của byte đầu; file đang xung đột | Chỉ là dấu hiệu địa chỉ được quản lý cục bộ, không chứng minh ngẫu nhiên/hacker |
| OUI | Đã xuất hiện mã đọc `data/oui.csv`, chuẩn hóa prefix và tra hãng | Phụ thuộc dữ liệu; CSV quan sát hiện chỉ có hai prefix ZTE/Intel, không phải danh bạ đầy đủ |
| CSV | Đã xuất hiện hàm ghi Device/PingResult bằng UTF-8 BOM | Có mã module, cần thử sau merge; chưa có nút CSV trong UI đã đọc |
| PDF | Đã xuất hiện mã ReportLab, matplotlib, Arial Windows, bảy nhóm nội dung | Cần kiểm tra phụ thuộc, tạo file và xem chất lượng xuất thực tế sau merge |
| Wi-Fi | `netsh wlan show networks mode=bssid`, gợi ý kênh 1/6/11 | Ước lượng 2.4 GHz, không tự đổi router; file đang xung đột |
| Zalo | Tạo nội dung và dry-run; khi gửi thật trả not_configured | Chưa tích hợp gửi Zalo thật; file đang xung đột |
| Telegram | Hàm khung `NotImplementedError` đã đọc | Chưa triển khai |

Wi-Fi chọn kênh theo điểm cộng của tín hiệu và độ chồng lấn; ít điểm hơn được ưu tiên. Không có dữ liệu 2.4 GHz thì trả `None` ở bản đã đọc trước merge. Điểm số không đo đầy đủ nhiễu radio, tải sử dụng kênh, độ rộng kênh hay chất lượng Internet.

PDF mới nhận dữ liệu backend tổng hợp: thông tin card, khoảng thời gian, thống kê ping, sự kiện mất phản hồi, kết luận trong phiên và traceroute thủ công nếu có. Không gọi báo cáo là bằng chứng pháp lý hay chứng minh nhà mạng có lỗi; đó là bản tổng hợp quan sát.

## 14. Kiểm thử: báo cáo kết quả thế nào

Lần chạy trước merge: **65 passed in 7.52s**. Số test gồm tham số hóa, không chỉ số hàm bắt đầu bằng `test_`.

Các nhóm được thấy:

- `test_diagnosis.py`: các verdict, thiếu mẫu, ngưỡng mất gói/RTT.
- `test_network_recovery.py`: IP/card không hợp lệ, mất/kết nối lại LAN, thay IP, kết quả route cũ, socket error khác timeout, parsing traceroute.
- `test_ui_smoke.py`: UI offscreen với dữ liệu kiểm soát, dữ liệu cũ không thành phép đo sống, truyền kết quả/lỗi từ backend, thao tác trusted.
- `test_cli_offline.py`: monitor/diagnose bắt đầu khi offline và dừng sạch.
- `test_wifi_channels.py`: thiếu dữ liệu, chọn kênh và đọc dữ liệu netsh được thay thế trong test.
- `test_simulate_network.py`: các hàm mô phỏng phát hiện trùng IP/thiết bị mới/thiết bị rời đi.
- `test_zalo_notify.py`: định dạng, dry-run và not_configured.

Các hàm mô phỏng trong `tests/simulate/simulate_network.py` khác luồng đo mạng thật. Test mô phỏng trùng IP không tự chứng minh `ArpAnomalyDetector` đã được kiểm chứng đầy đủ trên mạng thật.

Không nói “đạt 100% độ chính xác”, “đã phủ 100% mã” hoặc “không còn lỗi” từ 65 bài đạt. Không dùng thời gian chạy test để nói tốc độ quét LAN. Cũng không gọi mọi test đều là unit test thuần: có kiểm tra nhiều thành phần ghép nhau với I/O được thay thế.

Tài liệu mới `docs/real-run.md` ghi một số lần chạy của nhánh được nhập, nhưng cũng ghi chưa kiểm tra tích hợp đầy đủ. Đó là kết quả được tác giả tài liệu ghi lại, không phải mọi thao tác đều đã được chạy lại trong phiên chuẩn bị sổ tay này.

## 15. Kịch bản demo thực tế

Trước tiên cần hoàn tất merge, không còn dấu conflict trong mã Python, chạy lại test và diễn tập đúng phiên bản sẽ trình bày.

Chuẩn bị:

1. Windows, Python/venv đầy đủ, Npcap và quyền Admin cho phần giám sát tích hợp.
2. Mạng được phép quét, không bật client isolation; hạn chế VPN gây sai khác đường đi.
3. Máy/điện thoại thứ hai với MAC chưa có trong CSDL demo nếu muốn minh họa cảnh báo mới.
4. Giữ dữ liệu demo riêng đã chuẩn bị; không xóa CSDL sử dụng thật để làm thiết bị “mới”. Bản này chưa có sẵn tham số `--db` để tự chọn file.
5. Chạy từ gốc dự án, mở đủ sớm để có mẫu ping; chuẩn bị ảnh/video chạy thử.

Lệnh:

```powershell
# Chạy từng lệnh phù hợp; monitor/diagnose chạy liên tục tới Ctrl+C.
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe main.py --cli scan
.\.venv\Scripts\python.exe main.py --cli monitor
.\.venv\Scripts\python.exe main.py --cli baseline
.\.venv\Scripts\python.exe main.py --cli diagnose
.\.venv\Scripts\python.exe main.py --cli trace 1.1.1.1
.\.venv\Scripts\python.exe -m extras.wifi_channels
.\.venv\Scripts\python.exe tests/simulate/simulate_network.py
.\.venv\Scripts\python.exe -m pytest -q --tb=short
```

Trình tự demo 3–5 phút:

- Mở UI, chỉ rõ card/IP/gateway và một vài thiết bị đã quan sát.
- Sau khi GUI hoặc monitor đã lưu thiết bị ban đầu, chốt baseline từ terminal khác.
- Cho thiết bị mới vào cùng mạng; chờ một lượt quét hợp lệ và chỉ cảnh báo nếu xuất hiện đúng điều kiện.
- Đặt tên/đánh dấu tin cậy, giải thích đó là dữ liệu quản lý của người dùng.
- Mở chẩn đoán, giải thích RTT, mất phản hồi, thiếu mốc nếu có.
- Tắt Wi-Fi của máy chạy NetGuard rồi bật lại, chỉ trạng thái mất LAN và quá trình đo lại.
- Chỉ demo PDF sau khi bản mới đã tạo và kiểm tra file thành công.

Nếu cần minh họa thiết bị offline theo scanner, phải chờ đủ ba lần quét hợp lệ vắng mặt, khó vừa một demo ngắn. Đừng hứa vừa ngắt là mọi dòng đổi offline ngay.

Tắt Wi-Fi máy chạy app khác với rút đường Internet của router: trường hợp sau LAN/router vẫn có thể hoạt động. Nếu chỉ thấy `unknown` vì thiếu hop hoặc chưa đủ mẫu, giải thích chính xác thay vì coi demo đã hỏng.

Mô phỏng chỉ in dữ liệu tạo sẵn, không gửi gói và không phải tấn công thật. Khi dùng cần nói rõ đang minh họa mô phỏng.

## 16. Ngân hàng Q&A: 50 câu thường gặp

### A. Mục tiêu và kiến thức mạng

**1. Dự án giải quyết việc gì?** Giúp người dùng theo dõi thiết bị quan sát được trong LAN, nhận biết thay đổi và xem số đo hỗ trợ kiểm tra kết nối.

**2. Tại sao không chỉ dùng ping?** Ping cho biết phản hồi IP; ARP bổ sung cặp IP–MAC trong LAN. Ứng dụng còn ghép lịch sử, mức tin cậy, cảnh báo và giao diện.

**3. Tại sao dùng ARP?** Mục tiêu là phát hiện thiết bị IPv4 cùng liên kết và lấy MAC; đó là thông tin ARP hỗ trợ trực tiếp.

**4. ARP có quét được Internet không?** Không theo cách này. Phạm vi là miền liên kết cục bộ; muốn quan sát mạng khác cần phương pháp/quyền truy cập phù hợp.

**5. Ping dùng TCP hay UDP, cổng bao nhiêu?** Luồng ping dùng ICMP trên IPv4, không dùng cổng TCP/UDP. Traceroute Windows của bản này cũng dùng ICMP.

**6. ARP thuộc tầng nào?** ARP dùng frame Ethernet và phục vụ ánh xạ IPv4 sang địa chỉ liên kết. Khi nói theo OSI có thể nêu nó phục vụ liên hệ lớp mạng và lớp liên kết; tránh nói ARP chạy trên TCP.

**7. RTT là tốc độ mạng phải không?** RTT là thời gian khứ hồi tính bằng ms. Mbps là băng thông/thông lượng; dự án chưa đo tốc độ tải xuống/tải lên.

**8. Vì sao dùng 1.1.1.1?** Là IP tham chiếu bên ngoài đã cấu hình để đo đường ra, không phụ thuộc tra tên cho chính đích này. Một IP không đại diện mọi dịch vụ Internet.

**9. Ping ổn nhưng không vào web thì sao?** Cần kiểm tra DNS, TCP/TLS, proxy, trình duyệt, server hoặc băng thông; phép đo ICMP chưa bao phủ các thành phần đó.

**10. Có cần Internet để quét LAN?** Không nhất thiết. LAN còn hoạt động và các máy nhìn thấy nhau thì vẫn có thể quét; chẩn đoán đường ra ngoài mới cần điều kiện tương ứng.

### B. Thiết bị và cảnh báo

**11. Sao không thấy hết thiết bị?** Có thể do client isolation, VLAN, chọn card sai, thiết bị ngủ hoặc không phản hồi; danh sách là những gì quan sát được.

**12. Vì sao dùng MAC làm khóa?** Để theo dõi một địa chỉ liên kết khi IP do DHCP thay đổi. Đổi/giả MAC vẫn là giới hạn nhận diện.

**13. Baseline là gì?** Là giai đoạn thu thập thiết bị ban đầu và cờ xác nhận đã kết thúc; giúp không cảnh báo tất cả thiết bị ngay khi mới dùng.

**14. Chốt baseline có tự trusted tất cả không?** Không. Cờ baseline và cờ trusted là hai dữ liệu riêng.

**15. Bấm “Tin cậy tất cả” đã bật cảnh báo thiết bị mới chưa?** Chưa chốt baseline bằng thao tác đó. Cần gọi finish_baseline, hiện thực hiện qua CLI.

**16. Thiết bị chưa trusted quay lại có báo không?** Nhánh cảnh báo thiết bị mới chỉ chạy khi MAC chưa có trong CSDL; quay lại không tự thỏa điều kiện mới.

**17. Có đuổi được thiết bị lạ không?** Hiện chương trình cảnh báo để người dùng kiểm tra; không chặn hoặc ngắt thiết bị.

**18. MAC cục bộ chắc chắn là hacker?** Không. Bit cục bộ có thể do quyền riêng tư, cấu hình thủ công hoặc máy ảo. Nó không xác minh hành vi nguy hiểm.

**19. MAC trusted có thể bị giả không?** Có. Trusted là quyết định quản lý, không phải cơ chế xác thực mật mã.

**20. Chống lặp theo cái gì?** Bản mã đã kiểm tra dùng cảnh báo gần nhất theo MAC, thời hạn 30 phút; cần thêm loại cảnh báo nếu muốn chống lặp độc lập từng loại.

**21. Vì sao ba lần mới offline?** Để giảm báo nhầm khi bỏ sót một lượt. Đổi lại phải chấp nhận phát hiện chậm hơn.

**22. Tắt Wi-Fi máy giám sát có làm mọi máy thành offline?** Không nên suy ra như vậy; máy quan sát mất khả năng đo. Bản UI đã đọc hiển thị chưa xác minh khi mất LAN.

**23. Có phát hiện ARP spoofing không?** Có quy tắc cảnh báo một số dấu hiệu như gateway đổi MAC hoặc tranh chấp IP; cần đối chiếu thực tế, chưa thể kết luận mọi cảnh báo là tấn công.

**24. Ai đảm bảo dữ liệu ARP đúng?** ARP quan sát được không có cơ chế xác thực danh tính mạnh trong luồng hiện tại; dữ liệu có thể bị giả hoặc thiếu, nên là thông tin hỗ trợ.

### C. Chẩn đoán và traceroute

**25. Dùng AI để chẩn đoán à?** Không. Dùng thống kê cửa sổ và quy tắc ngưỡng trong core/diagnosis.py.

**26. Tại sao ping ba mốc?** Để so sánh từ phần gần máy tới phần xa hơn, hỗ trợ khoanh vùng thay vì chỉ nhìn một đích.

**27. Mốc ISP chắc chắn thuộc nhà mạng không?** Không. Đó là hop phản hồi đầu tiên sau gateway; double NAT và thiết bị trung gian có thể làm nhãn này không chính xác.

**28. Thiếu hop ISP nhưng ping ngoài ổn thì có báo bình thường không?** Theo quy tắc hiện tại là unknown vì chưa đủ ba mốc; nếu đích ngoài xấu có thể báo internet_issue kèm thiếu mốc.

**29. Một gói không trả lời có kết luận ngay không?** Không từ nhánh thống kê thông thường: cần đủ mẫu và kết luận ổn định qua ba lần đánh giá; mất LAN có luồng phản ánh ngay.

**30. Vì sao chọn 5%, gấp ba, 20 ms?** Đó là ngưỡng mặc định/heuristic của phiên bản, cần hiệu chỉnh bằng thử nghiệm; không phải tiêu chuẩn bảo đảm cho mọi mạng.

**31. Vì sao dùng median thay mean?** Median ít chịu ảnh hưởng bởi một vài phản hồi rất cao. Các giá trị không phản hồi được xét riêng qua tỷ lệ mất gói.

**32. Ba cửa sổ có phải 90 mẫu mới hoàn toàn không?** Không. Đây là ba lần đánh giá liên tiếp trên cửa sổ trượt chồng lấn.

**33. Router hạn chế ICMP có gây báo sai không?** Có thể. Router xử lý phản hồi ICMP khác lưu lượng chuyển tiếp, nên cần đối chiếu nhiều dấu hiệu và thử ứng dụng thực tế.

**34. Dấu sao traceroute là đường truyền đứt?** Chưa đủ cơ sở. Nó thể hiện không có phản hồi tương ứng trước timeout; các hop sau vẫn có thể trả lời.

**35. Có xác định đúng từng đoạn bị chậm không?** Chương trình đánh dấu biến đổi RTT để hỗ trợ kiểm tra; RTT khứ hồi, lọc ICMP và đường về khác nhau hạn chế suy luận chính xác một đoạn.

**36. Mạng chậm đều từ đầu có phát hiện không?** Không bảo đảm: baseline RTT hiện tính từ chính cửa sổ đang đo, có thể tăng cùng độ trễ. Có thể cải thiện bằng baseline khỏe mạnh dài hạn và thêm phép đo.

**37. Lỗi socket khác mất gói thế nào?** Socket lỗi nghĩa là phép đo không thực hiện được đúng cách; timeout nghĩa là không nhận phản hồi sau phép ping. Chương trình phân biệt hai trường hợp.

**38. Đổi IP xong có dùng thống kê cũ không?** Monitor phát hiện cấu hình thay đổi, xóa cửa sổ RAM và mốc ISP rồi đo lại; lịch sử CSDL vẫn giữ.

### D. Thiết kế, dữ liệu và triển khai

**39. Vì sao ứng dụng không bị treo khi chờ mạng?** Các phép đo định kỳ và dò route chạy nền; backend gửi sự kiện về UI. Cần đánh giá riêng những thao tác đồng bộ khác khi mở rộng.

**40. Có nhiều luồng thì CSDL bị ghi chồng không?** Các giao dịch của kết nối chung dùng RLock; WAL hỗ trợ phối hợp truy cập SQLite. Không dựa riêng vào check_same_thread=False để bảo đảm an toàn.

**41. Dữ liệu mất khi tắt app không?** Devices, PresenceLog, PingLog, Alerts và Meta lưu SQLite. Kết luận và traceroute được backend giữ trong phiên có giới hạn, chưa lưu thành bảng riêng.

**42. Có cần máy chủ CSDL không?** Không, SQLite là file cục bộ; phù hợp ứng dụng một máy. Nếu quản lý nhiều điểm cần thiết kế đồng bộ/server riêng.

**43. Cài đặt cần gì?** Python/venv và thư viện, Npcap, quyền Admin theo kiểm tra hiện tại; mạng cho phép quan sát các client. Mã PDF mới còn cần kiểm tra matplotlib và font.

**44. Linux/macOS có chạy đầy đủ không?** Có nhánh traceroute dự phòng nhưng đọc card, GUI khởi động và Wi-Fi phụ thuộc Windows. Không tuyên bố toàn ứng dụng đã đa nền tảng.

**45. Có hỗ trợ IPv6 không?** Lõi hiện tập trung IPv4/ARP; hỗ trợ IPv6 cần thiết kế khám phá bằng NDP và phép đo tương ứng.

**46. 65 bài đạt nghĩa là phủ 100% à?** Không. Nó chỉ xác nhận 65 trường hợp chạy đạt ở lần chạy trước merge; chưa đo coverage và chưa đại diện mọi điều kiện mạng.

**47. Đã gửi Zalo thật chưa?** Chưa. Dry-run tạo nội dung, `sent=False`; gửi thật chưa có tích hợp, trả trạng thái chưa cấu hình.

**48. PDF/CSV/OUI đã xong chưa?** Trong lúc khảo sát đã xuất hiện mã triển khai từ nhánh mới. Cần hoàn tất merge và kiểm tra tương ứng trước khi khẳng định bản tích hợp chạy thành công; không dùng kịch bản cũ để kết luận mã vẫn là stub.

**49. Điểm khác công cụ có sẵn là gì?** Với phạm vi đồ án, nhóm tập trung tích hợp các kiến thức mạng, lưu trữ và UI thành luồng quản lý thiết bị/chẩn đoán dễ theo dõi. Không khẳng định ưu thế tốc độ/độ chính xác nếu chưa benchmark.

**50. Hạn chế và hướng phát triển ưu tiên?** Hoàn tất tích hợp và demo ổn định; thử trên nhiều mạng; tách dữ liệu theo mạng; phân biệt loại khi chống lặp; quản lý lịch sử dài hạn; bổ sung baseline UI, phép đo DNS/TCP/HTTP, đa đích và IPv6 theo phạm vi tiếp theo.

## 17. Cách trả lời khi bị hỏi khó

Cấu trúc ba bước: **cơ chế đang làm → dữ liệu/điều kiện → giới hạn và bước kiểm tra tiếp**.

Ví dụ: “Nhóm dùng ARP Reply để thu IP và MAC trong subnet. Thiết bị sẽ được ghi nhận khi chương trình quan sát được phản hồi hợp lệ. Nếu mạng bật client isolation hoặc thiết bị ngủ thì có thể không thấy, nên nhóm không cam kết danh sách luôn đầy đủ.”

Khi chưa biết: “Phần đó hiện nhóm chưa kiểm chứng. Với phiên bản đang trình bày, cơ chế đang dùng là …; để khẳng định thêm cần thử …”. Trả lời dựa trên cái đang có, không biến dự định thành tính năng đã hoàn thành.

Khi bị hỏi “100% không?”: nêu mẫu đo và phạm vi đã thử. Tỷ lệ bài test chạy đạt không bằng độ chính xác phát hiện trên mạng thật.

## 18. Mạch trình bày 10–12 phút

1. 45 giây: bài toán, tên sản phẩm và hai luồng chính.
2. 60 giây: công nghệ/kiến trúc, chỉ vị trí xử lý mạng nền.
3. 90 giây: ARP, dữ liệu thiết bị, baseline và điều kiện cảnh báo.
4. 120 giây: ba mốc ICMP, số đo, quy tắc và giới hạn.
5. 3–4 phút: demo đã diễn tập.
6. 60 giây: test, giới hạn thực tế và hướng phát triển.
7. 20 giây: cảm ơn, chuyển hỏi đáp.

Kịch bản slide chi tiết có sẵn tại `docs/kich_ban_thuyet_trinh.md`; cần cập nhật trạng thái các module mới và số liệu test sau merge trước khi dùng.

## 19. Tờ nhớ nhanh trước khi lên trình bày

- ARP lấy IP–MAC trong LAN; ICMP đo phản hồi; TTL hỗ trợ dò đường.
- Quét 30 giây; hai vòng ARP; chờ 2 giây/vòng; ba lần quét hợp lệ vắng mặt mới offline.
- Baseline thiết bị khác trusted, cũng khác baseline RTT.
- Cảnh báo thiết bị mới dựa trên MAC chưa có trong CSDL, sau baseline.
- Ping chu kỳ cấu hình 2 giây, timeout 1 giây; ít nhất 10 mẫu, tối đa 30 mẫu.
- Xấu khi loss > 5% hoặc median RTT > max(3 × nền, 20 ms).
- Thông thường cùng verdict ba lần đánh giá mới phát; mất LAN/thiếu gateway phản ánh ngay.
- `unknown` thể hiện thiếu cơ sở; không phải “mạng chắc chắn tốt” hoặc “app chắc chắn hỏng”.
- UI lịch sử 30 phút khác cửa sổ thuật toán 30 mẫu.
- MAC cục bộ không đồng nghĩa thiết bị nguy hiểm; trusted không ngăn giả mạo.
- ICMP không đo Mbps, không kiểm tra toàn bộ DNS/web và không xác định thủ phạm chắc chắn.
- 65 test đạt là mốc trước merge; test lại sau khi hoàn tất tích hợp.
- Zalo thật chưa triển khai; OUI/CSV/PDF mới cần kiểm tra sau merge.

## 20. Nguồn đối chiếu

Mã nguồn cục bộ: `main.py`, `config.py`, `models.py`, `backend.py`, `core/`, `services/`, `db/`, `ui/`, `extras/`, `tests/`. Các nhận định về trạng thái triển khai dựa trên file đã đọc trong phiên này, không chỉ dựa vào README.

Nguồn nguyên lý giao thức:

- [RFC 826 — ARP](https://www.rfc-editor.org/rfc/rfc826): ánh xạ địa chỉ giao thức sang địa chỉ Ethernet.
- [RFC 792 — ICMP](https://www.rfc-editor.org/rfc/rfc792): thông điệp ICMP, Echo và Time Exceeded.
- [Microsoft Learn — tracert](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/tracert): TTL tăng dần, tham số và hop không trả lời.
