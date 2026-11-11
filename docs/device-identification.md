# Nhận diện thiết bị — mục 3

## Cách kiểm tra

1. Thoát bản NetGuard cũ, mở lại bằng `Mo_NetGuard.cmd`, bấm **Làm mới mạng**.
2. Bảng thiết bị ưu tiên **Tên thiết bị**, **Loại thiết bị** và **Nhà sản xuất**. Máy đang chạy ứng dụng hiện **Máy tính này**; gateway được nhận diện theo cấu hình kết nối.
3. Tên/dịch vụ có thể cập nhật thêm sau khi lượt quét hoàn tất. Chọn một thiết bị rồi bấm **Chi tiết / Sửa tên** để xem MAC, IP, model, nguồn gợi ý và thời điểm thông tin LAN được cập nhật.
4. Đặt tên gợi nhớ hoặc chọn **Xác nhận loại thiết bị**, bấm **Lưu**. Lựa chọn của người dùng được giữ khi quét/nhận diện lại. Chọn **Tự nhận diện** để bỏ lựa chọn loại thủ công.
5. Bật **Hiện MAC / IP** nếu cần xem các địa chỉ ngay trong bảng. Khi sửa ghi chú, tên tự phát hiện không bị ghi thành tên thủ công.

## Các nguồn thông tin

| Nguồn | Thông tin sử dụng | Giới hạn |
|---|---|---|
| Tiền tố MAC | Hãng đăng ký giao diện/card mạng; ưu tiên prefix dài MA-S, MA-M rồi MA-L | Hãng card có thể khác hãng laptop/điện thoại; không chỉ dựa vào hãng để kết luận loại máy |
| Máy đang chạy NetGuard | Tên máy cục bộ và cờ `is_self` từ kết quả quét | Xác định máy này, không tự suy ra chính xác hãng/model phần cứng |
| Gateway của card được quét | Vai trò router/gateway | Đây là vai trò trong mạng, không phải xác minh model router |
| mDNS/DNS-SD | Tên `.local`, tên dễ đọc, dịch vụ in/Cast/AirPlay/chia sẻ tệp, model/hãng nếu thiết bị công bố | Có thể không phản hồi, bị chặn hoặc chỉ công bố một phần dữ liệu; thông tin tự khai báo không có tính xác thực |
| NetBIOS Node Status | Tên máy và dịch vụ chia sẻ tệp | Không đồng nghĩa chắc chắn là Windows hoặc là laptop; NAS cũng có thể trả lời |
| Người dùng | Tên gợi nhớ, ghi chú và loại đã xác nhận | Được lưu theo MAC hiện tại; thiết bị đổi MAC riêng tư sẽ được xem là định danh khác |

Dữ liệu tra hãng dùng bảng đóng gói của Scapy, tổng hợp từ Wireshark/IEEE; môi trường Scapy 2.8.0 của dự án có **50.825 prefix** được nạp. `data/oui.csv` là các mục bổ sung/ghi đè cục bộ, được nạp một lần vào cache. Không cần truy vấn website bằng MAC hay tải thêm dữ liệu khi chạy. Bảng không tự cập nhật theo thời gian; phiên bản dữ liệu đi cùng bản Scapy được cài.

MAC có bit quản lý cục bộ được ghi rõ là **riêng tư/cục bộ**, không gán hãng từ OUI. Không coi bit này là bằng chứng chắc chắn thiết bị là điện thoại hoặc đang dùng địa chỉ ngẫu nhiên. Nếu các nguồn LAN khác có thông tin, ứng dụng vẫn có thể đưa ra gợi ý loại/tên cho thiết bị đó.

## Cách hiểu kết quả

- **Gợi ý**: suy luận từ tên/model/dịch vụ công bố; chưa phải xác minh phần cứng. Ví dụ dịch vụ in có thể thuộc máy in hoặc máy chủ in; SMB có thể thuộc máy tính hoặc NAS.
- **Đã chọn**: loại do người dùng chọn trong hộp thoại. Nhận diện tự động tiếp tục được lưu riêng và không ghi đè lựa chọn này.
- **Chưa xác định**: không đủ bằng chứng. Apple/Samsung/Intel riêng lẻ không đủ để kết luận điện thoại hay laptop.
- **(theo MAC)**: tổ chức/hãng đăng ký tiền tố MAC; có thể là hãng linh kiện mạng. Không phải phép xác minh chính xác nhà sản xuất chip/card hoặc toàn bộ chiếc máy.
- Tên quan sát được lưu riêng với tên do người dùng đặt. Thông tin LAN cũ được giữ khi thiết bị tạm không trả lời; thời điểm cập nhật xem trong Chi tiết. Khi MAC chuyển sang IP khác, dữ liệu nhận diện gắn với IP cũ không được dùng lại cho IP mới.

## Phạm vi kỹ thuật

- Bổ sung bảng `DeviceIdentity` bằng `CREATE TABLE IF NOT EXISTS`, giữ bảng thiết bị/lịch sử hiện tại. Các trường tự động không ghi đè tên, ghi chú, cờ tin cậy hoặc loại thủ công.
- Nhận diện cơ bản chạy trong lượt quét; thu thập tên/dịch vụ chạy ở worker riêng. Worker chỉ giữ yêu cầu mới nhất, gộp cập nhật bảng theo lô, bỏ kết quả công việc đã bị thay thế và kiểm tra MAC còn ở đúng IP trước khi ghi.
- Cache phát hiện bổ sung trong 5 phút khi cấu hình và danh sách thiết bị không đổi. Bấm **Làm mới mạng** bỏ qua cache này.
- Chỉ hỏi/nhận từ các IPv4 đã thấy trong subnet hiện tại; tối đa 128 đích mỗi lượt nhận diện bổ sung. mDNS dùng UDP 5353 và multicast nội bộ `224.0.0.251`; NetBIOS dùng Node Status UDP 137. Có timeout, kiểm tra nguồn/transaction ID và giới hạn kích thước/số gói. Không quét cổng, truy vấn DNS ngoài mạng hay tải URL do thiết bị cung cấp.
- Ghép PTR/SRV/TXT/A qua nhiều gói; hỏi thêm khi thiếu record. Không gán dịch vụ cho máy gửi proxy nếu record A trỏ sang địa chỉ khác. Phản hồi không hợp lệ hoặc cổng UDP đóng không làm hỏng việc nhận diện các máy khác.
- Không phát hiện xuyên VLAN/client isolation hoặc bảo đảm mọi điện thoại/TV đều công bố tên. Không suy ra được RAM, CPU, hệ điều hành chính xác hoặc danh tính chủ sở hữu chỉ từ MAC.
- Việc tách toàn bộ hồ sơ thiết bị theo từng mạng và các lỗi khác trong báo cáo vẫn thuộc mục 4.

## Kiểm chứng

**145 test pass**, gồm 55 bài mới cho mục 3: lookup ngoại tuyến/longest prefix, MAC cục bộ, suy luận có bằng chứng, bảo toàn CSDL cũ và dữ liệu thủ công, chống ghi nhận diện cũ, worker/cache/hủy, giao diện và luồng `Backend.start()` thực tế. Kiểm tra parser/transport bằng gói tổng hợp và socket giả, không gửi gói mạng thật trong lần kiểm thử này. Đã render và kiểm tra bảng thiết bị cùng hộp thoại chi tiết bằng Qt offscreen.

Nguồn kỹ thuật: [IEEE Registration Authority](https://standards.ieee.org/products-programs/regauth/), [Scapy data API](https://scapy.readthedocs.io/en/latest/api/scapy.data.html), [RFC 6762 — mDNS](https://www.rfc-editor.org/rfc/rfc6762), [RFC 6763 — DNS-SD](https://www.rfc-editor.org/rfc/rfc6763), [RFC 1002 — NetBIOS](https://www.rfc-editor.org/rfc/rfc1002).
