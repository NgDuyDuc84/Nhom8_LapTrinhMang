# Kịch bản thuyết trình NetGuard, bản 1 để duyệt

Đề tài đề xuất: **NetGuard – Ứng dụng giám sát thiết bị và hỗ trợ chẩn đoán mạng LAN**

Đối tượng giả định: giảng viên và sinh viên môn Lập trình mạng.

Thời lượng đề xuất: 12 phút, gồm khoảng 9 phút trình bày và 3 phút demo, chưa tính hỏi đáp. Tổng cộng 12 slide. Tên giảng viên, thành viên và phân công trình bày sẽ bổ sung sau khi duyệt nội dung.

Đây là kịch bản nội dung trước khi dựng PPTX. Lời dẫn có thể điều chỉnh theo cách nói của người trình bày. Những kết quả demo bên dưới là kết quả cần quan sát, chưa phải xác nhận đã thử trên mạng thật trong lần chuẩn bị này.

## Slide 1. Giới thiệu đề tài

**Thời lượng:** 20 giây.

**Trên slide:**
- NetGuard
- Ứng dụng giám sát thiết bị và hỗ trợ chẩn đoán mạng LAN
- Nhóm 8, môn Lập trình mạng
- Tên thành viên và giảng viên: bổ sung sau

**Lời thuyết trình:**

“Kính chào thầy/cô và các bạn. Nhóm 8 xin trình bày dự án NetGuard. Đây là ứng dụng desktop giúp người dùng theo dõi các thiết bị trong mạng LAN, nhận cảnh báo khi có thiết bị mới chưa tin cậy và hỗ trợ khoanh vùng khi kết nối mạng có dấu hiệu bất thường.”

**Minh họa dự kiến:** tên sản phẩm và một ảnh giao diện thật đã kiểm tra trước buổi báo cáo.

## Slide 2. Bài toán thực tế

**Thời lượng:** 40 giây.

**Trên slide:**
- Khó theo dõi thiết bị nào đang có mặt trong mạng
- Thiết bị mới có thể xuất hiện mà người dùng chưa nhận biết
- Khi mạng chậm, cần thêm dữ liệu để phân biệt vấn đề trong LAN và phía ngoài

**Lời thuyết trình:**

“Trong một mạng gia đình hoặc phòng học nhỏ, người dùng thường chỉ biết máy có kết nối Wi-Fi hay không. Khi xuất hiện thiết bị mới hoặc mạng chậm, chúng ta phải tự mở nhiều công cụ để kiểm tra. Từ tình huống đó, nhóm xây dựng một ứng dụng tập hợp thông tin thiết bị và các phép đo mạng vào cùng giao diện.”

## Slide 3. Mục tiêu và phạm vi

**Thời lượng:** 40 giây.

**Trên slide:**
- Liệt kê IP, MAC và trạng thái quan sát của thiết bị
- Lưu tên, ghi chú, mức tin cậy và lịch sử
- Cảnh báo thiết bị mới sau khi chốt danh sách ban đầu
- Đo RTT, mất gói và đưa ra nhận định hỗ trợ kiểm tra mạng
- Phạm vi chính: mạng LAN IPv4 trên Windows

**Lời thuyết trình:**

“NetGuard tập trung vào giám sát và cung cấp thông tin để người dùng kiểm tra mạng. Ứng dụng cho phép quản lý danh sách thiết bị và theo dõi chất lượng kết nối qua các phép đo ICMP. Cảnh báo giúp người dùng nhận biết thay đổi để kiểm tra tiếp. Chức năng hiện tại không chặn hoặc ngắt kết nối thiết bị.”

## Slide 4. Công nghệ và kiến trúc

**Thời lượng:** 60 giây.

**Trên slide:**
- Python, PySide6 và pyqtgraph cho ứng dụng desktop
- Scapy kết hợp Npcap để gửi và nghe ARP
- icmplib để đo ICMP, tracert.exe để dò đường trên Windows
- SQLite lưu thiết bị, lịch sử xuất hiện, ping và cảnh báo
- Các tầng: giao diện, backend, dịch vụ nền, xử lý mạng và dữ liệu

**Lời thuyết trình:**

“Nhóm chia chương trình thành các tầng để dễ kiểm tra và phát triển. Phần lõi thực hiện quét ARP, đo ICMP và xử lý quy tắc chẩn đoán. Các dịch vụ nền điều phối những tác vụ này và lưu dữ liệu vào SQLite. Backend chuyển kết quả sang giao diện qua Qt signals, giúp các thao tác đo mạng chạy ở luồng nền.”

**Minh họa dự kiến:** sơ đồ kiến trúc dựa trên mã hiện tại. Khi dựng deck, giữ sơ đồ có thể chỉnh sửa.

## Slide 5. Phát hiện thiết bị bằng ARP

**Thời lượng:** 60 giây.

**Trên slide:**
- Gửi ARP Request trong subnet của card mạng đã chọn
- Thu ARP Reply để lấy IP và MAC
- Cấu hình quét định kỳ: 30 giây
- Xác nhận offline sau 3 lần quét hợp lệ liên tiếp không thấy thiết bị

**Lời thuyết trình:**

“Để phát hiện thiết bị trong cùng mạng LAN IPv4, ứng dụng gửi ARP Request và thu phản hồi chứa địa chỉ IP cùng MAC. Chương trình lặp lại việc quét theo cấu hình 30 giây. Một lần không nhận phản hồi chưa đủ để coi thiết bị đã rời mạng, nên hệ thống chờ ba lần quét hợp lệ liên tiếp. Khi quét lỗi hoặc máy mất LAN, chương trình không dùng tình huống đó để kết luận toàn bộ thiết bị offline.”

**Điểm kỹ thuật có thể nói thêm khi được hỏi:** bản hiện tại mở AsyncSniffer trước rồi gửi bằng sendp, thu phản hồi riêng để xử lý vấn đề ghép request/reply của Scapy trên môi trường Windows của nhóm.

**Giới hạn cần hiểu:** ARP không bảo đảm tìm đủ mọi thiết bị. Thiết bị ngủ hoặc mạng bật client isolation có thể làm thiếu phản hồi. Không hứa xác nhận offline chính xác sau 90 giây vì mỗi lượt quét còn có thời gian thực thi.

## Slide 6. Cảnh báo thiết bị mới

**Thời lượng:** 55 giây.

**Trên slide:**
- Thu thập danh sách thiết bị ban đầu
- Chốt baseline để bắt đầu nhận diện thiết bị mới
- Cảnh báo khi thiết bị mới chưa tin cậy xuất hiện
- Hạn chế cảnh báo lặp trong khoảng 30 phút

**Lời thuyết trình:**

“Nếu cảnh báo ngay lần quét đầu, tất cả thiết bị đang dùng đều có thể bị coi là mới. Vì vậy, ứng dụng có bước thu thập danh sách ban đầu rồi chốt baseline. Sau thời điểm đó, thiết bị mới xuất hiện và chưa được đánh dấu tin cậy sẽ tạo cảnh báo. Người dùng có thể kiểm tra IP, MAC, đặt tên và cập nhật mức tin cậy.”

**Lưu ý cho người demo:** baseline hiện chốt qua `python main.py --cli baseline`. Nút “Tin cậy tất cả” chỉ đổi cờ tin cậy, không chốt baseline. Thiết bị đã có trong cơ sở dữ liệu quay lại mạng không tự động được xem là thiết bị mới. Địa chỉ MAC cục bộ có thể do cơ chế riêng tư, không đủ căn cứ kết luận thiết bị nguy hiểm.

## Slide 7. Hỗ trợ chẩn đoán mạng bằng ICMP

**Thời lượng:** 80 giây.

**Trên slide:**
- Các mốc đo: gateway, hop phản hồi sau gateway và đích ngoài 1.1.1.1
- Chỉ số: RTT và tỷ lệ mất gói
- Tối thiểu 10 mẫu, cửa sổ tối đa 30 mẫu
- Nhận định thông thường cần ổn định 3 chu kỳ đánh giá

| Dữ liệu quan sát | Nhận định của ứng dụng |
|---|---|
| Gateway có chỉ số xấu | Nghi vấn mạng nội bộ hoặc router |
| Gateway ổn, mốc phía nhà mạng xấu | Nghi vấn đường truyền hoặc phía nhà mạng |
| Các mốc trước ổn, đích ngoài xấu | Nghi vấn phía Internet hoặc đích đo |
| Đủ dữ liệu và cả ba mốc ổn | Mạng bình thường theo các phép đo |
| Thiếu dữ liệu cần thiết | Chưa đủ cơ sở kết luận |

**Lời thuyết trình:**

“Để hỗ trợ khoanh vùng vấn đề, ứng dụng so sánh kết quả ping tại các vị trí trên đường đi. Ví dụ, nếu gateway đã có mất gói hoặc độ trễ bất thường, người dùng nên kiểm tra mạng nội bộ trước. Nếu gateway ổn nhưng các mốc phía sau có vấn đề, ứng dụng đưa ra nhận định tương ứng. Đây là gợi ý dựa trên ICMP. Một thiết bị có thể hạn chế trả lời ping, nên kết quả cần được đối chiếu với các dấu hiệu khác.”

**Chi tiết dành cho hỏi đáp:** mất gói trên 5% hoặc RTT trung vị vượt `max(3 × RTT nền, 20 ms)` được xem là xấu khi đủ mẫu. RTT nền lấy theo phân vị 25 của các mẫu thành công trong cửa sổ. Mốc “nhà mạng” là hop phản hồi đầu tiên sau gateway trong kết quả dò đường, chưa xác minh chủ sở hữu. Khi không xác định được mốc này, chương trình vẫn có thể báo vấn đề phía ngoài nếu đích ngoài xấu, kèm thông tin thiếu mốc nhà mạng. Khi đích ngoài ổn nhưng thiếu mốc nhà mạng, chương trình chưa kết luận đầy đủ là bình thường.

## Slide 8. Giao diện và dữ liệu theo thời gian

**Thời lượng:** 45 giây.

**Trên slide:**
- Thiết bị: IP, MAC, tên, ghi chú, tin cậy và lần thấy gần nhất
- Cảnh báo: danh sách sự kiện và thông báo ở khay hệ thống
- Chẩn đoán: số đo, lỗi đo và đồ thị RTT lịch sử
- Dữ liệu cũ hiện “Chưa xác minh trong phiên” khi chưa quan sát lại

**Lời thuyết trình:**

“Giao diện tập hợp thông tin thiết bị, cảnh báo và kết quả chẩn đoán để người dùng theo dõi. Một điểm nhóm chú ý là thời điểm của dữ liệu. Thiết bị từng được lưu trong cơ sở dữ liệu chưa có nghĩa là đang online ở lần mở hiện tại. Vì vậy, ứng dụng có trạng thái chưa xác minh và thời điểm thấy gần nhất để tránh gây hiểu nhầm.”

**Minh họa dự kiến:** ảnh thật của tab Thiết bị và Chẩn đoán. Giao diện có tab Báo cáo nhưng chức năng tạo PDF chưa hoàn thiện, cần nói rõ nếu ảnh có hiển thị tab này.

## Slide 9. Demo ứng dụng

**Thời lượng:** 180 giây.

**Trên slide:**
- Quan sát thiết bị đang có trong LAN
- Cho một thiết bị mới vào mạng sau baseline
- Xem cảnh báo và cập nhật mức tin cậy
- Theo dõi số đo, ngắt rồi nối lại Wi-Fi trên máy chạy ứng dụng

**Lời mở demo:**

“Sau đây nhóm minh họa hai luồng chính. Đầu tiên là phát hiện thay đổi về thiết bị. Tiếp theo là quan sát ứng dụng khi máy mất và khôi phục kết nối LAN.”

| Bước | Thao tác | Kết quả cần quan sát |
|---|---|---|
| Chuẩn bị trước giờ báo cáo | Cài Npcap, mở ứng dụng bằng quyền Admin, chọn mạng không cô lập client | Thấy đúng card mạng, IP và gateway |
| Chuẩn bị trước giờ báo cáo | Dùng dữ liệu demo tách riêng, giữ thiết bị thứ hai chưa từng được ghi nhận và chưa kết nối | Có điều kiện minh họa đúng thiết bị mới mà không xóa dữ liệu sử dụng thật |
| 1 | Quan sát danh sách sau khi quét đủ, chốt baseline bằng CLI | Danh sách ban đầu đã được ghi nhận |
| 2 | Cho thiết bị thứ hai vào cùng mạng | Thiết bị được ghi nhận ở một lượt quét sau và tạo cảnh báo nếu đủ điều kiện |
| 3 | Đặt tên hoặc đánh dấu tin cậy | Giao diện cập nhật thông tin của thiết bị |
| 4 | Mở Chẩn đoán và xem mẫu đã thu trước đó | Phân biệt số đo đang có, trạng thái chờ và lỗi đo |
| 5 | Tắt rồi bật Wi-Fi trên máy chạy NetGuard | Thông báo mất LAN, sau đó đọc lại cấu hình và đo tiếp |

**Lời chốt demo:**

“Qua phần minh họa, chúng ta quan sát được cách NetGuard ghi nhận thiết bị và phản ứng khi kết nối của máy thay đổi. Phần nhận định chất lượng mạng cần đủ mẫu nên có thể vẫn ở trạng thái chờ sau khi kết nối lại.”

**Dự phòng:** chuẩn bị ảnh hoặc video từ buổi chạy thử, ghi rõ là bản ghi trước. Có thể dùng `python tests/simulate/simulate_network.py` để minh họa dữ liệu mô phỏng nhưng phải nói rõ đây là mô phỏng. Không thử tấn công ARP trực tiếp trên mạng lớp. Không đưa xuất PDF hoặc gửi Zalo thật vào demo hiện tại.

## Slide 10. Kiểm thử và kết quả hiện tại

**Thời lượng:** 55 giây.

**Trên slide:**
- Bộ kiểm thử tự động hiện tại: 65/65 bài đạt
- Nội dung gồm quy tắc chẩn đoán, mô phỏng mạng và khôi phục kết nối
- Kiểm tra giao diện với dữ liệu được kiểm soát, phân biệt dữ liệu cũ và số đo hiện tại
- Tiếp tục đối chiếu hoạt động trên mạng thật trước buổi báo cáo

**Lời thuyết trình:**

“Trong lần chạy kiểm tra phục vụ chuẩn bị nội dung, bộ kiểm thử hiện tại có 65 bài đạt. Các bài kiểm tra bao phủ nhiều tình huống như thiếu mẫu ping, mất kết nối, thiết bị mới và cách giao diện hiển thị dữ liệu đã lưu. Kết quả này xác nhận các tình huống tự động đã kiểm tra. Nhóm vẫn cần chạy thử trên mạng thật để đối chiếu ARP, ICMP và diễn tập demo.”

**Ghi chú bằng chứng:** chạy ngày 05/11/2026, lệnh `.\.venv\Scripts\python.exe -m pytest -q --tb=short`, kết quả `65 passed in 1.54s`. Không dùng thời gian chạy test làm chỉ số tốc độ quét mạng. Không tuyên bố độ chính xác 100% hoặc đã kiểm chứng đầy đủ mạng thật.

## Slide 11. Hạn chế và hướng phát triển

**Thời lượng:** 60 giây.

**Trên slide:**
- ARP phụ thuộc phản hồi thiết bị và cấu hình mạng
- Nhận định ICMP cần đối chiếu, đặc biệt khi hop không trả lời
- Hoàn thiện PDF, CSV và tra hãng từ MAC
- Tích hợp thông báo bên ngoài và bổ sung thao tác baseline trên UI

**Lời thuyết trình:**

“Phiên bản hiện tại đã có phần lõi giám sát và giao diện kết nối dữ liệu mạng, nhưng còn những phần cần hoàn thiện. Xuất PDF, CSV và tra hãng từ MAC vẫn mới có khung. Zalo hiện chỉ mô phỏng nội dung thông báo. Hướng phát triển tiếp theo là hoàn thiện các chức năng này, bổ sung thao tác baseline trên giao diện và đánh giá nhận định chẩn đoán trong nhiều điều kiện mạng hơn.”

**Tính năng phụ có thể nhắc nếu còn thời gian:** đã có công cụ CLI quét Wi-Fi và gợi ý kênh 2.4 GHz dựa trên dữ liệu quan sát. Đây là ước lượng, chưa tích hợp vào UI và không tự đổi kênh router. Bộ phát hiện bất thường ARP đã có mã, cần đánh giá thêm trong môi trường thử phù hợp trước khi khẳng định hiệu quả thực tế.

## Slide 12. Kết luận và hỏi đáp

**Thời lượng:** 25 giây.

**Trên slide:**
- Vận dụng ARP và ICMP vào một ứng dụng giám sát LAN
- Kết hợp xử lý mạng nền, giao diện desktop và lưu trữ lịch sử
- Cảm ơn thầy/cô và các bạn

**Lời thuyết trình:**

“Qua dự án NetGuard, nhóm đã vận dụng các kiến thức lập trình mạng để phát hiện thiết bị và thu thập số đo hỗ trợ kiểm tra kết nối. Nhóm cũng thực hiện việc lưu lịch sử, xử lý tác vụ nền và đưa kết quả lên giao diện desktop. Nhóm xin cảm ơn thầy/cô và các bạn đã lắng nghe, và mong nhận được góp ý.”

## Những chỗ cần thống nhất trước khi dựng PPTX

1. Thời lượng 12 phút và 12 slide có phù hợp yêu cầu của giảng viên không.
2. Tên đề tài, giảng viên, danh sách thành viên và người phụ trách từng đoạn.
3. Chọn demo trực tiếp hay bản ghi từ buổi diễn tập. Phải thử trước việc thiết bị mới chưa có trong dữ liệu và thời gian chờ lượt quét.
4. Nếu PDF, CSV, OUI hoặc Zalo được hoàn thiện trước ngày báo cáo, cập nhật trạng thái sau khi kiểm tra lại.

## Các cách diễn đạt cần giữ chính xác

| Tránh khẳng định | Cách nói đề xuất |
|---|---|
| Phát hiện hacker hoặc chống xâm nhập hoàn chỉnh | Cảnh báo thiết bị mới và một số bất thường ARP |
| Tìm đủ tất cả thiết bị trong mạng | Ghi nhận thiết bị quan sát được qua ARP |
| Xác định chính xác nguyên nhân mạng chậm | Hỗ trợ khoanh vùng dựa trên RTT và mất gói ICMP |
| Ping ổn nghĩa là mọi ứng dụng dùng Internet đều ổn | Các phép đo ICMP hiện không ghi nhận bất thường |
| MAC cục bộ nghĩa là thiết bị lạ hoặc nguy hiểm | MAC cục bộ có thể liên quan cơ chế riêng tư |
| Đã xuất PDF, gửi Zalo hoặc tra hãng thành công | Các phần này đang hoàn thiện theo trạng thái mã hiện tại |
| 65 test đạt nghĩa là hệ thống không còn lỗi | 65 tình huống tự động hiện tại chạy đạt |

## Căn cứ nội dung trong dự án

- `README.md`: cách chạy và giới hạn hiện tại.
- `docs/architecture.md`: kiến trúc và luồng dữ liệu.
- `config.py`: chu kỳ và các ngưỡng mặc định.
- `core/arp_scanner.py`, `services/scan_loop.py`: phát hiện thiết bị và xử lý vắng mặt.
- `services/baseline.py`, `services/alerts.py`: baseline và cảnh báo.
- `core/diagnosis.py`, `services/ping_monitor.py`: quy tắc và thống kê chẩn đoán.
- `backend.py`, `ui/main_window.py`: kết nối dịch vụ với giao diện.
- `extras/`: trạng thái triển khai tính năng phụ.
- `tests/` và kết quả chạy pytest ngày 05/11/2026: bằng chứng kiểm thử tự động.
