# Nhom8_LapTrinhMang

# Hướng dẫn cài đặt và chạy dự án

Ứng dụng desktop bằng **Python** để giám sát mạng LAN: quét thiết bị bằng ARP, cảnh báo thiết bị lạ, chẩn đoán mạng chậm bằng ICMP, xuất báo cáo PDF.

> Lưu ý: ứng dụng gửi và nhận gói tin thô nên **bắt buộc có Npcap và phải chạy bằng quyền Administrator**.

## 1. Yêu cầu hệ thống

| Thành phần | Yêu cầu | Kiểm tra |
|---|---|---|
| Hệ điều hành | Windows 10 hoặc 11, 64-bit | `winver` |
| Python | 3.11 hoặc 3.12 (nhớ tick "Add Python to PATH" khi cài) | `python --version` |
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
git clone <địa-chỉ-repo>
cd <thư-mục-repo>

python -m venv .venv
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
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
| icmplib | Ping và traceroute bằng ICMP |
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

> Phần này dùng được sau khi có `main.py`.

1. Mở PowerShell hoặc VS Code **bằng quyền Administrator** (chuột phải, Run as administrator).
2. Kích hoạt venv rồi chạy:

```powershell
.venv\Scripts\Activate.ps1
python main.py
```

3. Lần đầu chạy: chọn đúng card mạng (Wi-Fi hoặc Ethernet), quét, rồi bấm **Tin cậy** cho các thiết bị của mình. Từ đó thiết bị nào mới xuất hiện sẽ bị cảnh báo.

**Chạy test:**

```powershell
pytest
```

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