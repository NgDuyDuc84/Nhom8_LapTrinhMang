# Nhom8_LapTrinhMang

Chương trình giám sát máy trạm trong mạng LAN (bài tập nhóm môn Lập trình mạng).

Gồm 2 chương trình Windows Forms:

| Chương trình | Thư mục | Vai trò |
|---|---|---|
| `LanMonitor.Server` | `src/Server` | Lắng nghe kết nối, quản lý danh sách máy trạm, gửi thông báo |
| `LanMonitor.Client` | `src/Client` | Máy trạm: đăng ký với Server, gửi nhịp tim, hiện thông báo |

## Cách chạy

```bash
dotnet build src/LanMonitor.sln
```

Mở 2 cửa sổ (hoặc 2 máy trong cùng mạng LAN):

```bash
# Cua so 1: Server
dotnet src/Server/bin/Debug/net8.0-windows/LanMonitor.Server.dll

# Cua so 2, 3, ...: cac may tram
dotnet src/Client/bin/Debug/net8.0-windows/LanMonitor.Client.dll
```

Trong VS Code: mở thư mục gốc dự án rồi bấm `F5`, chọn cấu hình
`Server + Client` (xem `.vscode/launch.json`).

Thao tác trên Server: bấm **Bắt đầu lắng nghe** → trên mỗi máy trạm điền IP của
Server rồi bấm **Kết nối Server** → nhập nội dung thông báo, chọn một dòng trong
bảng rồi bấm **Gửi máy đã chọn** (hoặc **Gửi tất cả**) → muốn lấy thông tin của
một máy trạm thì chọn dòng đó rồi bấm **Yêu cầu thông tin máy**; kết quả hiện ở
ô *Kết quả trả lời từ máy trạm* bên dưới.

## Giao thức tầng ứng dụng

- Truyền qua **TCP**, cổng mặc định **5000**.
- Mỗi thông điệp là **một dòng JSON** kết thúc bằng ký tự `\n`.
  Nhờ ký tự này bên nhận biết được ranh giới giữa các thông điệp, vì TCP chỉ là
  luồng byte và không giữ ranh giới thông điệp.
- Không mã hoá, để có thể bắt gói bằng Wireshark và **đọc nội dung bằng mắt**.

Một dòng trên đường truyền:

```json
{"type":"HEARTBEAT","id":"4f3c...","from":"PC01","payload":"","timestamp":"2026-10-12 09:30:00"}
```

| Trường | Ý nghĩa |
|---|---|
| `type` | Loại thông điệp (xem bảng dưới) |
| `id` | Mã thông điệp, dùng để đối chiếu thông điệp trả lời với thông điệp gốc |
| `from` | Tên máy gửi (`SERVER` là của Server) |
| `payload` | Nội dung kèm theo (IP, nội dung thông báo, ...) |
| `timestamp` | Thời điểm tạo thông điệp |

### Các loại thông điệp

| Loại | Chiều | Giai đoạn | Ý nghĩa |
|---|---|---|---|
| `REGISTER` | Client → Server | 1 | Máy trạm đăng ký với Server, `payload` là IP của máy trạm |
| `ACK` | cả hai chiều | 1, 3 | Xác nhận đã nhận được thông điệp, `id` giữ nguyên của thông điệp gốc |
| `HEARTBEAT` | Client → Server | 2 | "Tôi còn sống", gửi định kỳ mỗi 5 giây |
| `NOTIFY` | Server → Client | 3 | Thông báo của Server gửi cho một máy trạm (hoặc tất cả) |
| `REQUEST` | Server → Client | 4 | Server yêu cầu máy trạm làm gì đó, `payload` là mã yêu cầu |
| `RESPONSE` | Client → Server | 4 | Máy trạm trả lời yêu cầu, `id` giữ nguyên của `REQUEST` |
| `ERROR` | Client → Server | 4 | Máy trạm báo không xử lý được yêu cầu, kèm lý do |

## Ghi chú kỹ thuật

- **Khoá khi ghi:** mỗi kết nối TCP có thể bị ghi từ nhiều luồng (luồng giao
  diện bấm nút gửi, luồng đọc dữ liệu trả ACK, luồng gửi nhịp tim). Nếu hai
  luồng cùng gọi `WriteLine` thì hai dòng JSON sẽ xen vào nhau và bên nhận
  không tách được thông điệp, nên mọi chỗ ghi đều đi qua một hàm có khoá
  (`MonitorServer.SendToStation` và `MonitorClient.Send`).
- **Mọi thao tác với control đều qua `Invoke`/`BeginInvoke`** vì sự kiện mạng
  đến từ luồng khác, không phải luồng giao diện.
- **Chỉ thực thể đang là hiện tại mới được đổi trạng thái:** mỗi lần Client kết nối
  mang một số hiệu (`MonitorClient._connectionId`), mỗi lần Server chạy mang một số
  hiệu (`MonitorServer._runId`). Luồng của kết nối cũ / lần chạy cũ phải so số hiệu
  của mình với số hiệu hiện tại trước khi báo mất kết nối, đánh Offline máy trạm hay
  bỏ yêu cầu đang chờ. Nhờ vậy việc ngắt rồi kết nối lại (hoặc Dừng rồi Bật lại)
  không phá hỏng trạng thái của kết nối mới — đây là cách chữa gốc cho lỗi 1, 2, 4
  ở giai đoạn 5.

## Kiểm thử bằng Wireshark

Lọc `tcp.port == 5000`, chuột phải một gói → *Follow → TCP Stream*. Sẽ thấy:

- mỗi kết nối: một dòng `REGISTER` rồi `ACK` trả về;
- cứ 5 giây một dòng `HEARTBEAT`;
- khi bấm gửi: một dòng `NOTIFY` từ Server và một dòng `ACK` từ máy trạm;
- khi bấm yêu cầu thông tin: một dòng `REQUEST` từ Server và một dòng `RESPONSE`
  từ máy trạm (hoặc `ERROR` nếu máy trạm không xử lý được), cả hai cùng `id`.

### File bắt gói mẫu và tài liệu thuyết trình

Trong `docs/` có sẵn một phiên làm việc thật đã bắt gói (59 gói, 20,88 giây,
3 kết nối TCP, không có gói truyền lại) kèm nhật ký của chương trình trong đúng
phiên đó, để mở lên xem hoặc dùng khi thuyết trình mà không cần chạy lại:

- `docs/wireshark/phien-demo.pcapng` — mở bằng Wireshark
- `docs/wireshark/nhat-ky-phien-demo.txt` — mốc thời gian để đối chiếu gói với dòng log
- `docs/Wireshark-ThuyetTrinh-TCP.md` — hướng dẫn thuyết trình về TCP qua chính
  đồ án này: kịch bản nói từng bước, bộ lọc dùng dần, bảng đối chiếu **gói ↔ dòng
  mã nguồn**, cách bắt gói live và các câu hỏi thường gặp

## Xử lý sự cố

- **`dotnet not found`**: khởi động lại VS Code (hoặc mở terminal mới) để nạp
  PATH mới.
- **Không kết nối được giữa 2 máy**: mở cổng 5000 trong Windows Firewall cho
  cả hai máy.
- **Smart App Control của Windows chặn file `.dll` vừa build** (`An Application
  Control policy has blocked this file`): lỗi này nằm ở cơ chế bảo vệ của
  Windows theo từng hash file, không phải lỗi chương trình. Cách chạy được ngay
  là dùng bản Release (`-c Release`), hoặc tắt Smart App Control trong
  *Windows Security → App & browser control* (lưu ý: sau khi tắt thì không bật
  lại được nếu không cài lại Windows).
