# Kết quả sửa mã NetGuard - 12/11/2026

Đối chiếu 44 nhóm phát hiện trong báo cáo ngày 11/11/2026. Người dùng đã thay đổi yêu cầu từ dừng sau từng lỗi sang hoàn tất cả đợt và báo cáo một lần. Bản sửa giữ Windows/LAN IPv4 là phạm vi sản phẩm; các giới hạn của ARP, ICMP, RF và dịch vụ thông báo được công bố bên dưới.

## Kiểm chứng đã thực hiện

- Môi trường cài mới tại `tmp/fresh-env`, cài trực tiếp `requirements-dev.txt`, Python 3.14.7 trên Windows. Không dùng Matplotlib hoặc thư viện PDF ngoài runtime đã khai báo.
- Kết quả chốt: **232 test pass**, gồm 70 trường hợp bổ sung so với mốc 162 sau lỗi 01. Coverage dòng toàn bộ ứng dụng: **76%**. Ruff và `pip check` đạt. Không coi số này là độ phủ mọi trạng thái mạng.
- Các test tự động dùng SQLite riêng, socket/capture/HTTP giả; fixture chung ngăn test ghi vào CSDL người dùng và tắt gửi thông báo ra ngoài. Có test ở ranh giới AsyncSniffer/ICMP, worker thật, transaction và Qt.
- Đã kiểm tra metadata card và GUID hồ sơ Windows ngoài sandbox bằng API đọc; card đang dùng có hồ sơ NLM hợp lệ. Không gửi ARP/ping/traceroute thật trong lần kiểm chứng mã này.
- Đã tạo PDF giả lập có tiếng Việt, thiếu dữ liệu, timeout và traceroute; render đủ hai trang và kiểm tra hình, bảng, N/A, font. Đã kiểm tra bố cục bảng/biểu đồ Qt offscreen; tab Chẩn đoán có cuộn để dùng ở chiều cao cửa sổ nhỏ.
- Demo `python -m db.database` chạy thành công trong CSDL tạm riêng.
- Có GitHub Actions cho cài mới trên Windows/Python 3.12, Ruff, pytest/coverage. Workflow chưa được chạy trên GitHub tại thời điểm tạo commit local.

## Đối chiếu từng nhóm

| Nhóm | Kết quả trong mã hiện tại |
|---|---|
| 01 | Scanner chờ ready callback, kiểm tra lỗi/luồng tự chết và lỗi đóng; capture không hợp lệ không tạo lượt hiện diện thành công. Có hủy giữa các lô gửi/đợi. |
| 02 | Listener xác nhận ready, theo dõi sức khỏe, báo lỗi lên backend/UI và tự thử lại với backoff có giới hạn. Không mở thêm capture khi capture cũ còn treo. |
| 03 | Chống lặp theo loại sự kiện và đối tượng; cho nâng mức nghiêm trọng đi qua. Gateway change, conflict, stranger và multi-IP có khóa riêng. |
| 04 | Quyết định chống lặp và INSERT ở cùng BEGIN IMMEDIATE, có khóa/nested transaction; tránh hai luồng/quá trình cùng ghi một sự kiện. |
| 05 | Giao diện có trạng thái chưa/đã bật cảnh báo và quy trình Hoàn tất thiết lập; lưu snapshot BaselineMembers trong cùng transaction. Tin cậy và chốt thiết lập có ý nghĩa riêng. |
| 06 | Lưu trạng thái cảnh báo chờ; xử lý thiết bị cũ chưa tin cậy, quay lại và bị bỏ tin cậy. Alert được lưu trước callback; lỗi callback không làm mất sự kiện. Thiết bị online liên tục không bị báo lại chỉ vì cooldown hết. |
| 07 | Hồ sơ lưu trữ tách theo GUID NLM/card/subnet/gateway/nhãn; mỗi worker giữ phạm vi của lượt làm việc. Card dùng adapter GUID ổn định; MAC riêng tư của máy đổi không làm trộn/mất hồ sơ mạng. Thiết bị, tin cậy, baseline, hiện diện, metadata và cảnh báo không tự đi theo MAC sang mọi mạng. Dữ liệu cũ giữ trong legacy. |
| 08 | Đọc lại kết nối sau scan, kiểm tra generation và khóa commit chung; bỏ kết quả cũ trước khi ghi/callback. UI bỏ các signal chẩn đoán/phép đo/kết nối đã hết hiệu lực. |
| 09 | Chuyển Offline không ghi đè last_seen. Thời điểm đổi trạng thái có PresenceLog riêng. |
| 10 | Scanner giữ tập IP-MAC; Observations giữ các claim và session. Hồ sơ chọn IP chính ổn định, không làm mất các quan hệ xung đột/nhiều IP đã quan sát. |
| 11 | Đối chiếu đúng IP hiện tại của chủ cũ, hết hạn map/candidate; DHCP chuyển thiết bị sang IP khác không tự biến thành bất thường đổi MAC ở IP cũ. |
| 12 | Lọc MAC unicast, nguồn IP/subnet, Ethernet source/ARP source và ngữ cảnh reply. Có bước người dùng xác nhận mốc MAC router. **Giữ giới hạn:** ARP/MAC không xác thực danh tính và không chống được mọi giả mạo. |
| 13 | TTL, giới hạn map/candidate và số owner/IP; giới hạn claim/lượt, hồ sơ/mạng, quan sát thụ động và cảnh báo tổng thể. Vượt ngân sách scan báo lỗi, không trả phần thiếu rồi suy ra Offline. |
| 14 | Dùng socket ICMP trực tiếp; lỗi send/receive socket được báo lỗi đo. Chỉ timeout/phản hồi ICMP âm được xem là probe không nhận echo; có test send lỗi, timeout và RTT thành công. |
| 15 | Nền không tự trôi lên theo cửa sổ chậm; thêm ngưỡng tuyệt đối router/đích ngoài, có cấu hình. Router chậm kéo dài từ lúc mở ứng dụng vẫn bị nhận diện. |
| 16 | Đối chiếu suy giảm tới đích cuối; một hop trung gian phản hồi kém khi external tốt không cho isp_issue. Ngôn ngữ kết luận là nghi ngờ/quan sát; ok chỉ nói về ICMP. |
| 17 | Bỏ gateway/đích cuối khi chọn mốc trung gian; UI gọi hop sau gateway và nêu chưa xác minh chủ sở hữu. Không biết hop không làm đích cuối đang tốt thành lỗi ISP. |
| 18 | Traceroute nhận card đã chọn; Windows kiểm tra tuyến trước/sau, từ chối kết quả nếu không tương ứng. Nhánh socket khác bind source. Kết quả cũ bị kiểm tra generation. |
| 19 | Cửa sổ có timestamp/địa chỉ, hết hạn từng mẫu và reset khi đích/card/hop đổi. Không đưa reply của hop cũ vào cửa sổ mới. |
| 20 | PingLog lưu address, session_id và trạng thái; lịch sử UI theo phiên, đổi địa chỉ/phiên làm đứt đường biểu đồ. |
| 21 | Lưu offline/unavailable/measurement_error riêng. Loss chỉ tính probe hợp lệ; không có mẫu là N/A. RTT/loss có khoảng trống khi lỗi đo/gián đoạn, không đổi RTT None thành 0. |
| 22 | Lưu diagnosis, traceroute, thời điểm/metadata phiên và kết thúc quan sát trong SQLite. Truy vấn trạng thái đầu kỳ chỉ khi còn trong phiên có quan sát; lịch sử hiện diện hiển thị cả mốc chưa/ngừng giám sát. |
| 23 | PDF lấy metadata phiên được lưu cùng phép đo; nhiều phiên được liệt kê. Không lấy card đang hoạt động lúc xuất cho dữ liệu quá khứ. |
| 24 | Xuất PDF bằng worker, có hủy, giới hạn 31 ngày, SQL đủ hai cận và tổng hợp timeout theo giờ. Connection snapshot riêng không giữ khóa UI/writer suốt truy vấn; ghi đích nguyên tử sau thành công. |
| 25 | Bỏ Matplotlib khỏi đường xuất; dùng ReportLab vector. Đóng gói Noto Sans + OFL, font fallback có thông báo rõ; có test tạo PDF thật và kiểm tra render. |
| 26 | Lỗi scan/listener/traceroute có trạng thái và cảnh báo được lưu thống nhất. Có log xoay vòng và traceback; UI cho biết dữ liệu có thể cũ. |
| 27 | Giữ handle worker đến khi join xác nhận dừng; timeout ném lỗi, không đóng DB hay tạo worker chồng. Có hủy scan và khóa một tiến trình giám sát cho cùng thư mục dữ liệu. Native call treo vĩnh viễn vẫn cần xử lý ở mức tiến trình/driver. |
| 28 | Gộp cập nhật thiết bị, giữ item/row theo MAC, giảm truy vấn ping còn theo chu kỳ và cập nhật curve sẵn có. Không dựng lại cả bảng cho từng device signal. |
| 29 | Giữ lựa chọn/scroll/item; trì hoãn cập nhật khi editor đang mở. Chỉnh sửa ở generation cũ không được lưu sang hồ sơ kết nối mới. |
| 30 | Tải dữ liệu trước khi đổi bảng, try/finally khôi phục trạng thái; lỗi tải giữ bảng cũ. Lỗi lưu checkbox/tên/ghi chú/bulk có phản hồi và cho thử lại. |
| 31 | Có SVG dự phòng khi icon theme rỗng; kiểm tra system tray và icon trước khi ẩn cửa sổ. Double-click mở lại, notification dùng icon theo mức. |
| 32 | Retention cấu hình, bảo trì theo hồ sơ/giờ, query bounded, limit âm bị từ chối. Có sao lưu/khôi phục qua SQLite backup và giữ metadata người dùng. |
| 33 | Demo luôn tạo CSDL tạm riêng; bỏ hẳn thao tác dọn PingLog theo timestamp chung trên dữ liệu thật. |
| 34 | Resolve đường dẫn theo dự án, chuẩn hóa GMT+7 và microsecond, thêm launcher lịch sử không bật quyền bắt gói. **Giữ phạm vi:** giám sát Windows; quyền cao vẫn áp dụng cho tiến trình giám sát. |
| 35 | Schema version/migration + backup trước nâng cấp; validation API cho MAC/IP/target/RTT/loss/thời gian và transaction nghiệp vụ có rollback. Hồ sơ IP-MAC nhiều chiều vẫn được biểu diễn; không áp UNIQUE IP. |
| 36 | Đã xử lý từ mục nhận diện: bảng OUI Scapy ngoại tuyến có cache/longest prefix và override; MAC cục bộ giữ Unknown khi thiếu bằng chứng. |
| 37 | Wi-Fi trả trạng thái/lỗi có cấu trúc, loại trùng BSSID, giữ Unknown khi Band thiếu. **Giữ giới hạn:** gợi ý kênh là ước lượng; chưa đo phổ, channel width/tải hay loại AP của chính mình. |
| 38 | Thêm luồng UI cho baseline, lịch sử, CSV, traceroute, Wi-Fi, cài đặt, backup và phân trang/tìm/ack cảnh báo. Có legend RTT/loss. Telegram/Zalo có adapter opt-in, queue bounded/retry; token/quyền OA cần cấu hình, chưa thử gửi thật. |
| 39 | Cấu hình có validation/UI; kết quả ping/diagnosis/hop bất biến, snapshot được copy và có generation. Dọn comment/logic dư, cập nhật tài liệu theo bản hiện tại. Chưa áp dụng type checker toàn dự án. |
| 40 | Chọn card/CIDR giới hạn, không đánh dấu Offline cho địa chỉ ngoài dải được quét; ping độc lập đồng thời, timestamp thực và phạm vi/độ trễ được giải thích. **Giữ phạm vi:** một card, IPv4 cùng broadcast, tối đa 1.024 địa chỉ/lượt; không mở rộng thành IPv6/VLAN hoặc phép đo băng thông. |
| 41 | Bỏ theo dõi 8.607 file cache/sidecar, thêm ignore và tách source công cụ sang tools/presentations với manifest/lock/env thay đường dẫn tài khoản máy. File trên máy giữ nguyên. Lịch sử Git đã tồn tại không bị viết lại. |
| 42 | Thêm hồi quy ở ranh giới dependency/DB/worker/UI/PDF, CSDL tạm chung, tắt outbound trong test, kiểm tra cài mới, Ruff/coverage và workflow CI. Mạng/driver thật và bài tải nhiều ngày vẫn cần nghiệm thu riêng. |
| 43 | Text CSV nguy hiểm được ép literal trước khi ghi; có test cho =, +, -, @, tab và whitespace đầu ô. |
| 44 | Reset trạng thái phiên khi đổi kết nối/stop/start; snapshot getter không lộ trạng thái mutable. Signal Qt trễ không đưa chẩn đoán cũ về sau reset; timeout worker không giả vờ đã dừng. |

## Thay đổi dữ liệu cần biết

Dữ liệu cũ không bị tự chuyển tin cậy sang hồ sơ mới vì bản cũ không lưu bằng chứng mạng nào sở hữu metadata đó. Chọn **Công cụ → Xem hồ sơ mạng / lịch sử cũ** để xem lại legacy. Tên/ghi chú/tin cậy mới và làm mới định kỳ giữ đúng trong từng hồ sơ.

Khi mở lại phiên, SQLite có migration và bản sao trước nâng cấp. Restore yêu cầu worker dừng và khóa tiến trình; bản trước restore được giữ. Bản sao được migration và kiểm tra đủ bảng/cột trong file tạm trước khi thay dữ liệu đang dùng; bản thiếu schema hoặc thuộc phiên bản tương lai bị từ chối mà không ghi đè dữ liệu. Giám sát được khởi động lại sau lần restore bị từ chối nếu trước đó đang chạy. Report đọc snapshot riêng, không thay card metadata bằng card lúc xuất.

## Phần chưa được chứng minh bằng kiểm thử thực tế

Chưa gửi ARP/ICMP/traceroute thật để so sánh với Wireshark/Npcap trên các máy khác; chưa thử lỗi driver vật lý, khay thật trên mọi Windows, tải bão ARP/many-day retention hay tài khoản Telegram/Zalo thật. 76% coverage dòng không chứng minh 100% hành vi. Các giới hạn chuẩn ARP/ICMP/RF và phạm vi Windows/IPv4 vẫn được giữ, thể hiện trong README và known-issues.

Lịch sử Git còn chứa những file cache/WAL đã từng commit. Bản sửa chỉ bỏ theo dõi từ commit mới, không xóa file trên máy và không viết lại lịch sử hoặc force-push.

## Git và thông báo Everything up-to-date

Tại lúc người dùng hỏi kiểm tra, `main` và `origin/main` cùng ở `410b4ac84f16fa41fb2357d0315b8677cc24c26c`. Mã mới còn trong working tree (`M`/`??`), chưa có commit mới nên `git push` không có gì để đẩy. Đã đối chiếu bằng `git ls-remote`.

Đợt sửa được đóng gói thành commit local sau khi kiểm thử; phần dọn cache và phần sửa ứng dụng được tách để dễ xem. Chưa tự push remote. Kiểm tra `git status -sb` rồi dùng `git push origin main` để đưa commit local lên GitHub. Không dùng `git add .` để gom dữ liệu chạy tùy ý.

## Nguồn kỹ thuật được đối chiếu

- Hành vi AsyncSniffer/icmplib đối chiếu mã thư viện đang cài theo requirements.
- Định danh mạng dùng [Windows Network List Manager](https://learn.microsoft.com/en-us/windows/win32/api/netlistmgr/nn-netlistmgr-inetworklistmanager) và [Windows SDK netlistmgr.h](https://github.com/microsoft/win32metadata/blob/main/generation/WinSDK/RecompiledIdlHeaders/um/netlistmgr.h). Không dùng GUID mạng mặc định NDIS làm hồ sơ NLM.
- Adapter tùy chọn theo [Telegram sendMessage](https://core.telegram.org/bots/api#sendmessage) và [Zalo OA API](https://stc-developers.zdn.vn/docs/v2/official-account/tin-nhan/tin-tu-van/gui-tin-tu-van-trich-dan?lang=vi); Noto Sans giữ giấy phép OFL trong assets/fonts.
