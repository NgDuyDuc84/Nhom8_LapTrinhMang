# Nhom8_LapTrinhMang

# Hướng dẫn cài đặt và chạy dự án

Ứng dụng desktop bằng **Python** để giám sát mạng LAN: quét thiết bị bằng ARP, cảnh báo thiết bị lạ, chẩn đoán mạng chậm bằng ICMP, xuất báo cáo PDF.

> Mở hằng ngày: nhấp đúp **`Mo_NetGuard.cmd`**, bấm **Yes** khi Windows hỏi cấp quyền.
> Không cần mở PowerShell bằng Administrator hoặc kích hoạt `.venv` mỗi lần.
> Ứng dụng tự xin quyền cần thiết; vẫn cần cài Npcap và các thư viện ở lần cài đặt đầu tiên.

## 1. Yêu cầu hệ thống

| Thành phần | Yêu cầu | Kiểm tra |
|---|---|---|
| Hệ điều hành | Windows 10 hoặc 11, 64-bit | `winver` |
| Python | 3.11 hoặc 3.12 khuyến nghị; môi trường phát triển hiện tại dùng 3.14.7 | `python --version` |
| Npcap | Bản mới nhất từ https://npcap.com | `sc query npcap` phải ra `STATE: 4 RUNNING` |
| Git | Bản mới nhất | `git --version` |
| Mạng | Wi-Fi hoặc Ethernet thật, **không bật client isolation** | Ping được điện thoại cùng mạng |

Cần cài thêm để test (không bắt buộc để chạy):

| Công cụ | Dùng để |
|---|---|
| Wireshark | Đối chiếu gói ARP/ICMP chương trình gửi ra |
| Clumsy | Giả lập mất gói và trễ để thử phần chẩn đoán |
| Điện thoại hoặc laptop thứ hai | Giả lập "thiết bị lạ" |

## 2. Cài Npcap

1. Tải bản cài từ npcap.com, chạy bằng "Run as administrator".
2. Cài với tùy chọn mặc định. Tick thêm "WinPcap API-compatible Mode" cũng được.
3. Mở CMD bằng quyền admin, gõ `sc query npcap`. Phải thấy `RUNNING`. (Gõ đúng, không có dấu chấm ở cuối.)
4. Nếu báo lỗi 1060 thì khởi động lại máy rồi thử lại.

## 3. Cài dự án

Mở **PowerShell**, chạy từng lệnh:

```powershell
git clone https://github.com/NgDuyDuc84/Nhom8_LapTrinhMang.git
cd Nhom8_LapTrinhMang

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
```

Nếu PowerShell báo lỗi "running scripts is disabled", chạy lệnh này rồi kích hoạt lại venv:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Thư viện sử dụng (`requirements.txt`)

```
scapy
icmplib
PySide6
pyqtgraph
reportlab
pytest
```

| Thư viện | Vai trò |
|---|---|
| scapy | ARP scan, dựng và đọc gói tin (dùng Npcap bên dưới) |
| icmplib | Ping ICMP và traceroute dự phòng trên nền tảng khác Windows |
| PySide6 | Giao diện desktop (Qt) |
| pyqtgraph | Biểu đồ độ trễ và mất gói theo thời gian |
| reportlab | Xuất báo cáo PDF |
| pytest | Chạy test |

Khi mọi thứ chạy ổn, chốt phiên bản bằng `pip freeze > requirements.txt` để cả nhóm dùng cùng bản.

## 4. Kiểm tra môi trường trước khi code

Chạy **trong terminal mở bằng quyền Administrator**, với venv đã kích hoạt.

**Kiểm tra Scapy thấy card mạng:**

```powershell
python -c "from scapy.all import conf; print(conf.ifaces)"
```

Phải thấy card Wi-Fi hoặc Ethernet đang dùng, kèm IP và MAC. Danh sách rỗng hoặc báo lỗi tức là Npcap chưa cài đúng hoặc chưa chạy bằng Admin.

**Kiểm tra ARP scan** (thay dải IP bằng mạng của bạn, ví dụ `192.168.102.0/24`):

```powershell
python -c "from scapy.all import ARP, Ether, srp; ans,_=srp(Ether(dst='ff:ff:ff:ff:ff:ff')/ARP(pdst='192.168.102.0/24'), timeout=2, verbose=0); [print(r.psrc, r.hwsrc) for _,r in ans]"
```

Phải thấy ít nhất router và các thiết bị đang bật. Đối chiếu với `arp -a` hoặc Wireshark (lọc `arp`).

**Kiểm tra ICMP:**

```powershell
python -c "from icmplib import ping; r=ping('1.1.1.1', count=4); print(r.avg_rtt, r.packet_loss)"
```

## 5. Chạy ứng dụng

Để mở giao diện, nhấp đúp **`Mo_NetGuard.cmd`** trong thư mục dự án, rồi bấm **Yes**
ở hộp thoại cấp quyền Windows. Launcher tự chọn Python trong `.venv`; không phải gõ lệnh.
Chọn **No** sẽ hủy mở ứng dụng, không hỏi quyền lặp lại.

Nếu dùng terminal thường, `python main.py` cũng tự chọn môi trường `.venv` của dự án
và xin quyền khi cần. Không cần mở lại terminal bằng Administrator cho chế độ GUI.

Các lệnh **CLI** bên dưới vẫn cần terminal Administrator khi gửi/nhận gói mạng thô.
Kích hoạt venv:

```powershell
.venv\Scripts\Activate.ps1
```

Các chế độ CLI hiện có:

~~~powershell
python main.py --cli scan
python main.py --cli monitor
python main.py --cli baseline
python main.py --cli trace 1.1.1.1
python main.py --cli diagnose
~~~

monitor chạy liên tục đến Ctrl+C. Lần đầu, để chương trình nhận diện thiết bị hiện có,
sau đó mở terminal thứ hai và chạy `python main.py --cli baseline`. Sau khi chốt baseline,
thiết bị mới chưa tin cậy sẽ bị cảnh báo.

Giao diện đã có trong `ui/main_window.py` và `ui/tray.py`
của HuyTien trên nhánh `feature/gui-monitor`. Xem cách mở ở mục 5.4.

Windows `tracert.exe` gửi ba probe cho mỗi TTL; thời gian chờ có thể dài khi nhiều hop không
trả lời. Tắt VPN như CloudflareWARP trước khi đối chiếu traceroute.

**Chạy test:**

```powershell
python -m pytest -q
```

### 5.1. Kiểm tra khi tắt và bật lại mạng

Mở PowerShell bằng quyền Administrator, kích hoạt `.venv`, sau đó chạy:

```powershell
python main.py --cli diagnose
```

Tắt Wi-Fi hoặc rút cáp mạng trong khi lệnh đang chạy. Chương trình báo máy mất
kết nối LAN và tiếp tục chờ. Bật Wi-Fi/cắm cáp lại: chương trình tự đọc lại IP,
mặt nạ và gateway mỗi chu kỳ ping (khoảng 2 giây), rồi thu thập mẫu mới để chẩn đoán.
Nếu card có IP nhưng thiếu gateway, chương trình báo rõ `không có gateway`.
Lỗi tạo/gửi socket được hiển thị là `lỗi đo`, không được ghi thành mất gói 100%.
Các kết luận dựa trên ping cần ít nhất 10 mẫu và giữ ổn định 3 chu kỳ.

Với lệnh theo dõi thiết bị:

```powershell
python main.py --cli monitor
```

Chương trình đọc lại cấu hình card ở mỗi chu kỳ quét (30 giây), mở lại bộ nghe ARP
khi cấu hình thay đổi và tự quét tiếp khi kết nối trở lại. Một lần quét lỗi không
được dùng để kết luận tất cả thiết bị đã offline. Các lệnh `monitor` và `diagnose`
có thể khởi động khi chưa kết nối LAN; quyền Administrator và Npcap vẫn cần thiết.
Sau khi chọn được card, các lệnh CLI tiếp tục theo dõi card đó. Muốn đổi sang card
khác trong CLI, dừng bằng Ctrl+C và chạy lại lệnh. Trên GUI, dùng nút **Làm mới mạng**
để chọn lại kết nối đang hoạt động mà không phải đóng ứng dụng.

Các lệnh chạy một lần như `scan` hoặc `trace` báo lỗi rõ khi chưa kết nối; cần chạy
lại sau khi có mạng. Traceroute ra Internet cần gateway. Nếu chỉ ngắt đường Internet
của router trong khi máy vẫn nối Wi-Fi, router vẫn có thể ping được; đây là tình
huống khác với tắt card Wi-Fi của máy.

### 5.2. Chạy các tính năng phụ

Chạy từ thư mục gốc dự án trong PowerShell:

```powershell
cd D:\Nhom8_LapTrinhMang
.\.venv\Scripts\Activate.ps1
```

**Quét Wi-Fi xung quanh và gợi ý kênh 2.4 GHz:**

```powershell
python -m extras.wifi_channels
```

Tính năng dùng `netsh wlan show networks mode=bssid` trên Windows. Cần bật card
Wi-Fi; không bắt buộc có Internet. Nếu Windows chặn quét, kiểm tra dịch vụ WLAN
AutoConfig và quyền truy cập vị trí trong Settings. Khi không quét được hoặc không
có dữ liệu 2.4 GHz, chương trình báo chưa đủ dữ liệu và không đề xuất mặc định kênh 1.
Khi có dữ liệu, gợi ý chọn trong các kênh 1, 6, 11 dựa trên tín hiệu và độ chồng lấn;
đây là ước lượng, không tự đổi kênh trên router.

**Mô phỏng trùng IP, thiết bị mới và thiết bị mất kết nối:**

```powershell
python tests/simulate/simulate_network.py
```

Lệnh dùng dữ liệu giả, chạy được khi offline và không gửi gói tin mạng.

**Demo nội dung cảnh báo Zalo:**

```powershell
python -m extras.zalo_notify
```

Lệnh chỉ in cảnh báo mẫu ra terminal, chạy được khi offline. Chưa tích hợp Zalo
Official Account API nên **chưa gửi tin nhắn Zalo thật** và chưa tự nối vào luồng
cảnh báo của `monitor`. Hàm `send_zalo_alert(..., dry_run=False)` trả trạng thái
`not_configured`, không báo gửi thành công.

### 5.3. Chạy kiểm thử

Các bài test dưới đây dùng dữ liệu giả/mô phỏng, không cần Internet hay quyền Admin.

```powershell
# Quy tắc chẩn đoán mạng (12 test)
python -m pytest tests/test_diagnosis.py -v

# Mô phỏng mạng (4 test)
python -m pytest tests/test_simulate_network.py -v

# Demo cảnh báo Zalo (4 test)
python -m pytest tests/test_zalo_notify.py -v

# Chạy chung 20 test trong tài liệu DTG1
python -m pytest tests/test_diagnosis.py tests/test_simulate_network.py tests/test_zalo_notify.py -v

# Hồi quy mất/kết nối lại mạng và quét kênh Wi-Fi
python -m pytest tests/test_network_recovery.py tests/test_wifi_channels.py -v

# Toàn bộ test, gồm cả các tình huống hồi quy mới
python -m pytest -q
```

Các bài test tự động không thay thế bước kiểm tra tắt/bật card thật ở mục 5.1.

### 5.4. Mở giao diện NetGuard

Nhấp đúp **`Mo_NetGuard.cmd`** rồi chọn **Yes** ở hộp thoại cấp quyền của Windows.
Không cần chuột phải “Run as administrator”, mở PowerShell hay kích hoạt môi trường.
Ứng dụng tự xin quyền một lần cho mỗi lần mở; nếu đã có quyền thì mở thẳng giao diện.
File chạy được cả khi thư mục dự án có dấu cách hoặc chữ tiếng Việt.

Hoặc dùng PowerShell/terminal **thường** và chạy:

```powershell
cd D:\Nhom8_LapTrinhMang

.\.venv\Scripts\python.exe main.py
```

Khi mở GUI từ một thư mục khác, ứng dụng vẫn dùng dữ liệu của thư mục dự án.
Nếu khởi động lỗi trước khi nạp được giao diện, chương trình hiện hộp thoại và lưu
chi tiết vào `logs/startup.log` để dễ kiểm tra. Nếu báo thiếu `.venv`, xem lại bước
cài đặt ở mục 3. Windows vẫn cần bạn chấp thuận UAC vì chức năng mạng sử dụng quyền cao.

UI hiển thị card mạng, IPv4/mặt nạ và gateway. Thiết bị lấy
từ quét ARP; các mẫu RTT/mất gói và kết luận lấy từ dịch vụ ICMP. Không tự sinh
thiết bị, cảnh báo hoặc kết luận bình thường khi chưa đo được. Thiếu dữ liệu sẽ
hiện trạng thái chờ hoặc lỗi đo. Vẫn cần Npcap và quyền Administrator; nếu chưa nối
LAN, cửa sổ mở để chờ mạng và tự đo khi kết nối lại.

`python -m ui.main_window` và `python ui/main_window.py` cũng mở giao diện qua cùng
đường khởi động. UI không còn chế độ demo hoặc tham số `--fake`.

Các thiết bị từ CSDL cũ hiện **Chưa xác minh trong phiên** cho đến khi được quan
sát trong phiên hiện tại. Khi mất LAN, trạng thái hiển thị là chưa xác minh thay
vì coi các trạng thái Online đã lưu là dữ liệu đang đo. Cột **Thấy gần nhất** và
đồ thị **lịch sử 30 phút** cho biết thời điểm của dữ liệu. Dừng ứng dụng cũ rồi mở
lại để nạp mã mới.

Không thêm `--cli` khi muốn mở cửa sổ. Đóng bằng nút **X** sẽ ẩn cửa sổ xuống khay
hệ thống. Nhấp phải biểu tượng NetGuard cạnh đồng hồ, chọn **Mở NetGuard** để hiện
lại hoặc **Thoát** để kết thúc ứng dụng. Có thể cần bấm dấu mũi tên ở khay để thấy
biểu tượng; bản UI này dùng biểu tượng theo theme nên trên một số máy biểu tượng
có thể không hiển thị rõ.

| Phần giao diện | Chức năng đã nối | Giới hạn hiện tại |
|---|---|---|
| Thiết bị | Tên dễ đọc, loại gợi ý, hãng/card mạng, Online/Offline hoặc chưa xác minh, tin cậy, ghi chú; xem MAC/IP và nguồn nhận diện trong Chi tiết | Loại gợi ý chưa phải xác minh phần cứng; có thể xác nhận loại thủ công |
| Cảnh báo | Danh sách 20 cảnh báo gần nhất, màu mức độ và thông báo qua khay hệ thống | Chưa có bộ lọc, tìm kiếm hoặc gửi Zalo trên UI |
| Chẩn đoán | Nhận đúng kết luận từ backend; bảng địa chỉ đích, RTT mới nhất, mất gói của 30 mẫu lịch sử và lỗi đo; đồ thị RTT lịch sử 30 phút | Không tự kết luận `ok` từ bản ghi cũ hoặc khi chưa đủ mẫu; chưa có biểu đồ mất gói riêng |
| Báo cáo | Chọn khoảng thời gian và đường dẫn lưu PDF, gọi `extras/pdf_report.py` | Cần cài đủ thư viện xuất báo cáo, gồm ReportLab và Matplotlib |
| Khay hệ thống | Ẩn, mở lại, thoát và hiện thông báo | Không phải gửi thông báo Zalo |

Các chức năng lõi chưa có nút riêng trên UI: traceroute, chốt baseline, lịch sử
online/offline từng thiết bị, xuất CSV, quét kênh Wi-Fi và demo Zalo. Đánh dấu
**Tin cậy tất cả** chỉ thay đổi cờ tin cậy, không gọi `finish_baseline()`.
Để chốt baseline cho chế độ mạng thật sau khi đã quét đủ thiết bị, mở PowerShell khác:

```powershell
.\.venv\Scripts\python.exe main.py --cli baseline
```

Hãng card mạng được tra ngoại tuyến bằng dữ liệu đóng gói trong Scapy cùng các mục
bổ sung ở `data/oui.csv`. MAC riêng tư/cục bộ không được gán hãng từ tiền tố.
Tên/ghi chú do người dùng đặt và lịch sử đã lưu vẫn được giữ nguyên.

### 5.5. Làm mới mạng ngay trên giao diện

Bấm **Làm mới mạng** trên thanh công cụ, cạnh nút **Tin cậy**. Ứng dụng sẽ đọc lại
card đang hoạt động, IP/mặt nạ/gateway, quét thiết bị và lấy các mẫu đo kết nối mới.
Có thể dùng sau khi đổi Wi-Fi, chuyển Wi-Fi/Ethernet hoặc khi muốn kiểm tra lại ngay.

- Trong lúc thực hiện, nút chuyển thành **Đang làm mới…** và tạm khóa. Nếu đang có
  lượt quét/đo, yêu cầu chờ lượt đó kết thúc rồi thực hiện trên cùng dịch vụ nền.
- Dòng bên dưới thông tin kết nối báo thời điểm hoàn tất hoặc lỗi cụ thể. Có thể
  thử lại sau khi kết nối trở lại. Quét lỗi không được tính là một lượt thiết bị vắng mặt.
- Tên, ghi chú, cờ tin cậy và lịch sử trong CSDL được giữ lại. Thiết bị cũ vẫn có
  trong danh sách đã biết; những thiết bị thấy trong lượt mới được xác minh lại.
- Các mẫu thống kê chẩn đoán trong bộ nhớ được thu thập lại; lịch sử đã lưu không bị xóa.
  Tab Chẩn đoán chờ đủ mẫu trước khi đưa ra kết luận mới. Việc tìm hop ISP tiếp tục ở nền.
- Nếu kết nối thay đổi trong lúc làm mới, ứng dụng yêu cầu thử lại để tránh xác nhận
  kết quả quét của kết nối khác. Nút này không tự kết nối hoặc đổi Wi-Fi trong Windows.

Giới hạn subnet lớn hiện vẫn áp dụng: mạng vượt 1.024 host sẽ báo lỗi quét trên dòng
làm mới. Việc mở rộng phạm vi quét và tách lịch sử theo mạng là các phần sửa tiếp theo.

### 5.6. Nhận diện thiết bị bằng hãng, tên và dịch vụ

Bảng thiết bị hiển thị tên dễ hiểu và loại thiết bị thay cho việc lấy IP làm tên.
**Máy tính này** là máy đang chạy NetGuard; router/gateway được nhận diện theo kết nối.

- Tra hãng/card mạng ngoại tuyến từ hơn 50.000 prefix MAC trong môi trường hiện tại.
  Hãng linh kiện như Intel có thể khác hãng sản xuất cả chiếc máy.
- Thu thập bổ sung tên/model/dịch vụ công bố trong LAN qua mDNS/DNS-SD và NetBIOS ở nền.
  Tên/loại có thể cập nhật thêm sau khi lượt quét hoàn tất.
- Các loại suy luận có chữ **gợi ý**. MAC riêng tư/cục bộ hoặc thiếu phản hồi có thể
  vẫn hiện **Chưa xác định**; không tự kết luận điện thoại/laptop chỉ dựa vào tên hãng.
- Chọn thiết bị, bấm **Chi tiết / Sửa tên** để xem nguồn nhận diện, model, MAC/IP,
  đặt tên gợi nhớ và **Xác nhận loại thiết bị**. Chọn **Tự nhận diện** để bỏ loại thủ công.
- Bật **Hiện MAC / IP** khi cần hiện địa chỉ trong bảng. Tên, ghi chú, tin cậy và
  loại đã xác nhận được giữ sau khi làm mới hoặc mở lại ứng dụng.

Ứng dụng chỉ hỏi trong LAN, không gửi MAC tới dịch vụ tra cứu trên Internet.
Xem [phương pháp, giới hạn và cách kiểm tra nhận diện](docs/device-identification.md).

## 6. Lỗi thường gặp


| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Danh sách card rỗng, hoặc báo thiếu `wpcap.dll` | Chưa cài Npcap, hoặc cài lỗi | Cài lại Npcap, restart máy |
| Quét không ra thiết bị nào | Chưa chạy Admin, chọn nhầm card, hoặc Wi-Fi bật client isolation | Mở terminal bằng Admin; chọn card Wi-Fi/Ethernet thật; thử mạng khác |
| Chỉ thấy router | Client isolation hoặc mạng khách | Dùng mạng nhà, không dùng Wi-Fi công cộng |
| Chọn nhầm card | Máy có VPN, VMware, VirtualBox sinh card ảo (`Local Area Connection*`, `CloudflareWARP`...) | Chọn card có IP cùng dải với router; tắt VPN khi test |
| Ping và traceroute cho kết quả lạ | VPN (CloudflareWARP) đang bật | Tắt VPN |
| `Activate.ps1` bị chặn | Chính sách thực thi của PowerShell | Lệnh `Set-ExecutionPolicy` ở mục 3 |
| `ModuleNotFoundError` | Chưa kích hoạt venv hoặc chưa `pip install` | Kích hoạt venv rồi cài lại |

## 7. Cấu trúc thư mục dự kiến

```
├─ main.py            # điểm vào
├─ models.py          # Device, PingResult, Alert, Diagnosis
├─ config.py          # ngưỡng cảnh báo, chu kỳ quét
├─ core/              # ARP scan, ICMP, traceroute, kết luận chẩn đoán
├─ services/          # quét định kỳ, ping liên tục, baseline, cảnh báo
├─ db/                # SQLite
├─ ui/                # giao diện PySide6
├─ extras/            # OUI, nhận diện MAC ngẫu nhiên, kênh Wi-Fi, CSV, PDF
├─ data/              # oui.csv
├─ tests/
└─ docs/
```

## 8. Quy ước làm việc với Git

- Mỗi người chỉ sửa trong thư mục được giao. `models.py` chỉ nhóm trưởng sửa.
- Trước khi làm: `git pull` trên `main`, rồi tạo nhánh mới (`git checkout -b ten-nhanh`).
- Xong việc: `git push` nhánh của mình rồi báo nhóm trưởng merge. Không ghi thẳng vào `main`.
- Không commit file `.venv/`, `__pycache__/`, `*.db`.

## 9. Lưu ý

- Chỉ quét mạng của mình hoặc mạng được cho phép.
- Chương trình chỉ **cảnh báo**, không chặn hay đuổi thiết bị.
- Thử ARP spoofing hoặc trùng IP chỉ làm trong máy ảo của nhóm.
