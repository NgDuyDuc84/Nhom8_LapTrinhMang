# Nhật ký tiến độ – Phần của A (NetGuard)

File này ghi lại kết quả từng giai đoạn để nhóm trưởng (A) đối chiếu.
Quy tắc: mỗi giai đoạn chỉ được coi là xong khi mục "Cách kiểm tra" đã chạy thật và có kết quả dán lại.

---

## Giai đoạn 0: Đọc và xác nhận (chưa viết code)

**Thời điểm khảo sát:** 2026-11-02

### 1. Trạng thái repo

- Nhánh hiện tại: `main`, working tree sạch, log chỉ có 1 commit `33ef0b7 Du An Lap Trinh Mang`.
- Nội dung repo: chỉ có `README.md` và `.gitignore`. **Chưa có file/thư mục nào khác.**
- `.gitignore` hiện tại: `.venv/`, `__pycache__/`, `*.pyc`, `*.db`, `.pytest_cache/`, `.vscode/`, `*.pcapng` → **đã có `*.db`**, không cần thêm.
- Không có `SETUP.md`, không có `PhanCongNhom.md` (README có mục "Hướng dẫn cài đặt và chạy dự án" tương đương SETUP).

### 2. Môi trường máy hiện tại

| Hạng mục | Kết quả khảo sát |
|---|---|
| Python | **3.14.7** (`C:\Users\84ndd\AppData\Local\Python\pythoncore-3.14-64\python.exe`) – **không khớp yêu cầu 3.11/3.12** |
| `py -0p` | Chỉ có 3.14 (64-bit), không có bản 3.11/3.12 nào khác |
| `.venv` | **Chưa có** |
| Thư viện (scapy, icmplib, PySide6, pyqtgraph, reportlab, pytest) | **Chưa cài bản nào** |
| Npcap | `sc query npcap` → `STATE: 4 RUNNING` → **đã cài và đang chạy** |
| Quyền terminal hiện tại | **Không phải Administrator** (`net session` thất bại) |
| Card Wi-Fi | `Killer(R) Wi-Fi 6 AX1650x 160MHz Wireless Network Adapter (200NGW)`, MAC `ac:74:b1:41:a5:d2`, IP `192.168.102.7/24`, gateway `192.168.102.1` |
| Card ảo | `CloudflareWARP` (172.16.0.2, đang bật, default route metric 261), `Local Area Connection* 1`, `Local Area Connection* 10`, 2× `Microsoft Wi-Fi Direct Virtual Adapter` (một cái MAC `ae:74:b1:41:a5:d2` – chỉ khác 1 bit so với Wi-Fi thật) |
| Card Ethernet | `Realtek Gaming 2.5GbE Family Controller` – đang disconnected |
| Route mặc định | `0.0.0.0/0 → 192.168.102.1` qua `192.168.102.7` metric 35 (thắng route WARP metric 261) |

### 3. Tóm tắt dự án và phần của A

NetGuard là app desktop Python (Windows) giám mạng LAN bằng ARP + ICMP: quét thiết bị, lưu SQLite, đánh dấu tin cậy/lạ, cảnh báo thiết bị lạ, ghi lịch sử online/offline; ping 3 mốc (router / hop nhà mạng / server ngoài) để kết luận lỗi ở nhà – nhà mạng – Internet, kèm traceroute; xuất PDF. Chỉ cảnh báo, không chặn, không đọc nội dung traffic.

Phần của A: `main.py`, `models.py`, `config.py`, `backend.py`, `requirements.txt`, `core/` (trừ arp_listener thuộc giai đoạn 9 tùy chọn), `services/`, `db/`, `ui/__init__.py` + `ui/fake_data.py`, file khung `extras/`, `docs/architecture.md`. Tuyệt đối không import Qt trong `core/` và `services/`.

### 4. Thứ tự giai đoạn

0 khảo sát → 1 khung repo → 2 card mạng/môi trường → 3 ARP scan → 4 SQLite → 5 quét định kỳ + baseline + cảnh báo (Mốc 1) → 6 ICMP + traceroute → 7 ping 3 mốc + kết luận (Mốc 2) → 8 ghép nối + PDF + GUI → 9 lớp bảo vệ phụ (tùy chọn, phải hỏi trước) → 10 rà soát, 30 phút ổn định, tổng kết.

### 5. Còn thiếu so với kiến trúc

Toàn bộ cây thư mục, `requirements.txt`, `.venv`, và mọi file Python đều còn thiếu. Riêng môi trường: Python sai phiên bản và chưa cài thư viện.

### 6. Chặn hiện tại (cần A quyết trước Giai đoạn 1)

1. Python 3.14.7 không nằm trong khoảng yêu cầu 3.11/3.12; PySide6 chưa chắc có wheel cho 3.14 → cần cài Python 3.12 rồi tạo `.venv` bằng 3.12.
2. Terminal hiện tại không phải Admin (Giai đoạn 2 trở đi bắt buộc Admin để Scapy/ICMP chạy).
3. CloudflareWARP đang bật → sẽ làm sai traceroute/ping ở Giai đoạn 6–7, cần tắt khi test.

### 7. Trạng thái

Giai đoạn 0: **đã xong** (A đã trả lời: giữ Python 3.14.7, agent tự cài môi trường, không cần `.gitkeep`, `README.md` đóng vai SETUP).

---

## Giai đoạn 1: Dựng khung repo (A1) – HOÀN THÀNH

### Quyết định môi trường (theo chỉ đạo của A)

- Giữ **Python 3.14.7** (không cài thêm 3.12). Đã tạo `.venv` bằng 3.14.7.
- Cài thành công toàn bộ `requirements.txt` trên 3.14: **PySide6 6.12.0** (wheel `cp310-abi3` nên chạy được trên 3.14), **scapy 2.8.0**, **icmplib 3.0.4**, **pyqtgraph 0.14.0**, **reportlab 5.1.0**, **pytest 9.2.0**.
- Không tạo `data/.gitkeep` (theo A). Thư mục `data/` sẽ do `db/database.py` tự tạo khi mở CSDL.

### File đã tạo

```
main.py, models.py, config.py, backend.py, requirements.txt
core/__init__.py, services/__init__.py, db/__init__.py, ui/__init__.py
extras/{oui,mac_random,csv_export,pdf_report,wifi_channels,telegram_notify}.py
ui/fake_data.py
docs/progress.md
```

Thư mục rỗng đã tạo: `data/`, `tests/`, `docs/` (không đặt file nào trong `tests/` và `data/`).

### Khác biệt so với bảng hợp đồng (cần báo B và C)

1. `models.py`: `first_seen` / `last_seen` có `default_factory=now` thay vì bắt buộc truyền. Lý do: dataclass không cho phép trường không có giá trị mặc định đứng sau trường có mặc định. Hệ quả: `Device(ip=..., mac=...)` vẫn hợp lệ, B/C không phải sửa gì.
2. Thêm hàm `models.now()` (trả `datetime.now()`) để cả dự án dùng chung một cách lấy thời gian.
3. `main.setup_console_encoding()`: đặt codepage console Windows về UTF-8 trước khi in, vì mặc định cp1252 gây `UnicodeEncodeError` với tiếng Việt. Đây là lỗi thật đã gặp và đã sửa.
4. `main.py` nhận thêm tham số vị trí `command` (`scan|monitor|trace|diagnose`) và `target` để dùng cho các giai đoạn sau; hiện in thông báo "chưa cài".

Không đổi tên signal/hàm nào so với hợp đồng: 5 signal (`device_updated`, `alert_raised`, `ping_result`, `diagnosis_changed`, `traceroute_done`) và 12 hàm của `BackendBase` giữ nguyên chữ ký.

### Kết quả kiểm tra (đã chạy thật, Python 3.14.7, không cần Admin)

| Lệnh | Kết quả |
|---|---|
| `python -c "import models, config, backend"` | OK |
| `from ui.fake_data import FakeBackend` | OK |
| import 6 module `extras/` | OK |
| `python main.py --help` | In trợ giúp tiếng Việt đúng |
| `python main.py --cli scan / trace 1.1.1.1 / --fake` | In thông báo "chưa cài", exit code 1 |
| Smoke `FakeBackend` (QCoreApplication 2,6 s) | 8 thiết bị, 6 `ping_result`, 1 `diagnosis_changed`, 1 cảnh báo `warning`, traceroute 8 hop (3 hop `flagged`, 1 hop `ip=None`) |
| `get_ping_history`, `get_device_history`, `set_trusted`, `finish_baseline`, `stop()` | Trả dữ liệu đúng, `is_first_run` đổi True→False |

Chưa kiểm tra (để giai đoạn sau): Scapy có thấy card mạng không, ICMP có chạy không — cần terminal Admin.

### Trạng thái

Giai đoạn 1: **XONG**. Chờ A commit/push rồi gõ "tiếp tục" để sang giai đoạn 2 (card mạng + môi trường, cần Admin để test).

**Phiên bản thư viện đã ghim** (theo yêu cầu của A): `scapy==2.8.0`, `icmplib==3.0.4`, `PySide6==6.12.0`, `pyqtgraph==0.14.0`, `reportlab==5.1.0`, `pytest==9.2.0` — đây là bộ đã cài và chạy thật trên Python 3.14.7.

---

# HỢP ĐỒNG CHUNG CHO B VÀ C (chốt sau giai đoạn 1)

Phần này để A copy sang nhóm; mọi thay đổi so với bản trong prompt đều ghi rõ.

## `models.py`

| Class | Trường (theo thứ tự) |
|---|---|
| `Device` | `ip`, `mac`, `vendor=""`, `name=""`, `note=""`, `trusted=False`, `online=False`, `randomized_mac=False`, `is_self=False`, `first_seen=<bây giờ>`, `last_seen=<bây giờ>` |
| `PingResult` | `target` (`"router"`/`"isp"`/`"external"`), `rtt_ms` (`float \| None`), `loss_pct`, `ts=<bây giờ>` |
| `Alert` | `level` (`"info"`/`"warning"`/`"danger"`), `message`, `device_mac=None`, `ts=<bây giờ>` |
| `Diagnosis` | `verdict` (`"ok"`/`"home_issue"`/`"isp_issue"`/`"internet_issue"`/`"unknown"`), `text`, `ts=<bây giờ>` |
| `Hop` | `ttl`, `ip=None`, `rtt_ms=None`, `flagged=False` |

Thay đổi so với prompt: `first_seen`/`last_seen` và các trường `ts` có giá trị mặc định (dataclass không cho trường không mặc định đứng sau trường có mặc định). Thêm hàm tiện ích `models.now()`.

## `backend.py` — `BackendBase`

Signal: `device_updated(object)`, `alert_raised(object)`, `ping_result(object)`,
`diagnosis_changed(object)`, `traceroute_done(object)`.

Hàm: `start()`, `stop()`, `list_devices()`, `set_trusted(mac, trusted)`, `rename(mac, name, note)`,
`is_first_run()`, `finish_baseline()`, `get_alerts(limit=100)`, `get_ping_history(target, minutes)`,
`get_device_history(mac, hours)`, `run_traceroute(target="1.1.1.1")`, `export_report(start, end, path)`.

Không đổi tên nào so với prompt. `FakeBackend` trong `ui/fake_data.py` đã cài đủ 12 hàm để B dựng UI ngay.

## `extras/` — chữ ký C phải giữ đúng

`oui.lookup(mac) -> str`; `mac_random.is_randomized(mac) -> bool`;
`csv_export.export_devices(devices, path)`, `csv_export.export_pings(pings, path)`;
`pdf_report.build_report(data: dict, path)`;
`wifi_channels.scan_wifi() -> list[dict]`, `wifi_channels.recommend_channel(networks) -> int`;
`telegram_notify.send_alert(text)`.

---

## Giai đoạn 2: Card mạng và kiểm tra môi trường (A2) – HOÀN THÀNH

### Cách lấy dữ liệu (quyết định kỹ thuật)

- Danh sách card: Scapy `conf.ifaces` (cho tên thân thiện, mô tả, MAC, `index` = IfIndex Windows).
- Mặt nạ mạng: `GetIpAddrTable` (ctypes `iphlpapi`) → chính xác, không phụ thuộc ngôn ngữ Windows.
- Cổng mặc định: `GetIpForwardTable` (các dòng `0.0.0.0/0`, chọn metric nhỏ nhất cho mỗi card).
- Card đang dùng để ra Internet: `GetBestInterface("1.1.1.1")` — **hỏi thẳng Windows**.
  Lý do: `conf.route.route("1.1.1.1")` của Scapy trả về **CloudflareWARP** (172.16.0.2) trong khi
  Windows thật chọn Wi-Fi (metric 35 so với 261) → nếu dùng route của Scapy sẽ chọn sai card.
- **Không dùng `psutil`**, không thêm thư viện ngoài.

### File tạo/sửa

- `core/interfaces.py` (mới): `NetInterface`, `list_interfaces`, `get_active_interface`,
  `get_subnet_hosts`, `check_environment`, thêm `is_admin`, `has_npcap`, khối `__main__`.
- `core/console.py` (mới): `setup_console_encoding()` dùng chung cho `main.py` và các `__main__`.
- `main.py`: dùng `core.console.setup_console_encoding` (bỏ bản trùng).
- `requirements.txt`: ghim phiên bản.

`NetInterface` có thêm trường `index: int` (IfIndex Windows) so với prompt — cần cho giai đoạn 3 để Scapy gửi đúng card.

### Kết quả chạy thật (máy A, 2026-11-02)

`python -m core.interfaces` (terminal **không** phải Admin):

```
* Wi-Fi                       192.168.102.7    255.255.255.0    192.168.102.1    ac:74:b1:41:a5:d2 thật   có
  Ethernet                    169.254.230.170  -                -                b4:45:06:96:39:41 thật   không
  CloudflareWARP              172.16.0.2       255.255.255.255  -                -                 ảo     có
  Local Area Connection* 1    169.254.40.238   -                -                ac:74:b1:41:a5:d3 ảo     không
  Local Area Connection* 10   169.254.154.27   -                -                ae:74:b1:41:a5:d2 ảo     không
  Local Area Connection* 7/8/9  -               -                -                -                 ảo     không
  Loopback Pseudo-Interface 1 127.0.0.1        255.0.0.0        -                00:00:00:00:00:00 ảo     không

Card được chọn: Wi-Fi | 192.168.102.7/255.255.255.0 | gateway 192.168.102.1 | MAC ac:74:b1:41:a5:d2 | IfIndex 19
Sẽ quét 254 host: 192.168.102.1 ... 192.168.102.254

Kiểm tra môi trường:
  - Chưa chạy bằng quyền Administrator: ...
  - Đang bật VPN (CloudflareWARP): ...
```

Các nhánh khác đã kiểm tra bằng script tạm:

| Trường hợp | Kết quả |
|---|---|
| `/24` | 254 host, không có địa chỉ mạng `.0` và broadcast `.255` |
| `10.0.0.5/8` | `ValueError`: vượt `MAX_SCAN_HOSTS = 1024` |
| `/30` | 2 host |
| `/32` | 1 host |
| Card thiếu IP/mặt nạ | `ValueError` tiếng Việt |
| `has_npcap()` | `True` (Npcap 1.x đang chạy) |
| `is_admin()` | `False` trong terminal hiện tại |

### Chưa kiểm chứng được

- Nhánh "Chưa cài Npcap" (máy đã cài Npcap).
- `check_environment()` trả danh sách rỗng khi chạy **Admin** → cần A chạy lại bằng quyền Admin.

### Trạng thái

Giai đoạn 2: **XONG**. Theo yêu cầu của A, cảnh báo VPN đã được **tách riêng** khỏi
`check_environment()` sang `get_warnings()` để app vẫn khởi động được khi bật WARP.
A xác nhận IP/MAC hiển thị trùng khớp với máy thật.

---

## Giai đoạn 3: ARP scan (A3) – HOÀN THÀNH (chờ A đối chiếu khi chạy Admin)

### Phát hiện quan trọng khi test

`srp()` / `srp1()` của Scapy **không dùng được trên máy này**: request gửi ra đúng
(chụp lại được trên dây), router **có** trả lời ARP (`28:77:77:db:b5:6c`), nhưng Scapy
luôn trả về 0 câu trả lời dù `timeout` tăng lên 5 giây. Nguyên nhân là phần khớp
request/reply của `srp` với Npcap trên Windows, không phải mạng.

Cách đã kiểm chứng và đang dùng: mở `AsyncSniffer(filter="arp")` trước, đợi
`SNIFFER_WARMUP_SEC = 0.8` giây cho Npcap mở handle, rồi `sendp` các ARP request và
tự thu mọi gói `op == 2` nằm trong subnet. Ghi chú này nằm ngay trong docstring của
`core/arp_scanner.py` để người sau không thử lại `srp` và tưởng code sai.

### File tạo/sửa

- `core/arp_scanner.py` (mới): `ScanEntry(ip, mac, is_self=False)`, `scan_subnet(iface, timeout, rounds)`,
  `_scapy_iface()` (khớp card theo IfIndex), `_translate_error()` (đổi lỗi Scapy sang tiếng Việt),
  khối `__main__` quét thử.
- `main.py`: thêm `run_scan()` cho `python main.py --cli scan`.
- `core/interfaces.py`: tách `get_warnings()` (VPN) khỏi `check_environment()`.

### Kết quả chạy thật (máy A, terminal **không** Admin, Npcap cho phép chụp)

`python main.py --cli scan`:

```
Đang quét Wi-Fi (192.168.102.7/255.255.255.0), chờ chút...
Xong sau 5.3 giây: 4 thiết bị trả lời ARP.
IP               MAC
192.168.102.1    28:77:77:db:b5:6c   <- router, khớp MAC trong đề bài
192.168.102.3    d4:e8:53:2c:8a:26
192.168.102.7    ac:74:b1:41:a5:d2   máy này
192.168.102.13   ea:f0:cc:11:24:dd   <- MAC ngẫu nhiên (bit locally-administered)
```

- Thời gian quét: **5,3–6,2 giây** cho /24 với 2 vòng (`ARP_ROUNDS = 2`), có giãn cách 1 ms/gói.
- `arp -a` **không** có các máy .3/.13 vì ARP thô không ghi vào cache của Windows → muốn đối chiếu
  phải ping cả dải trước rồi mới xem `arp -a`.
- Chạy 3 lần liên tiếp: 4 / 2 / 3 thiết bị. Khi sniff liên tục 5,8 giây và gửi 3 vòng, thấy máy .65
  chỉ trả lời ở vòng 2 (chậm ~270 ms) → thiết bị di động ngủ/tiết kiệm pin là nguyên nhân dao động,
  không phải code. Đây cũng là lý do `OFFLINE_AFTER_MISSES = 3` là hợp lý.

### Trạng thái

Giai đoạn 3: **XONG**. A đã chạy bằng quyền Administrator và xác nhận 4 thiết bị khớp thực tế
(router + máy A + 2 điện thoại), thời gian quét 6,1 giây.

---

## Giai đoạn 4: Cơ sở dữ liệu SQLite (A4) – HOÀN THÀNH

### Thiết kế

- Một kết nối dùng chung, `check_same_thread=False`, bảo vệ bằng `threading.RLock`.
- `PRAGMA journal_mode=WAL` và `synchronous=NORMAL` → đọc trong lúc ghi vẫn mượt.
- Bảng: `Devices`, `PresenceLog`, `PingLog`, `Alerts`, `Meta` (đúng tên cột trong prompt),
  thêm chỉ mục `(mac, ts)` cho PresenceLog, `(target, ts)` cho PingLog, `(ts)` cho Alerts.
- **Múi giờ hiện tại:** GMT+7 cố định, lưu ISO 8601 không offset (`2026-11-02T08:58:12`)
  → so sánh chuỗi cũng đúng thứ tự thời gian, không bị trộn aware/naive. Chốt ở giai đoạn 5.
- `upsert_device` khi thiết bị đã tồn tại **chỉ** cập nhật `ip, vendor, randomized, is_self,
  online, last_seen`; giữ nguyên `name, note, trusted, first_seen` do người dùng đặt
  (quét lại không xoá tên/tin cậy).
- `set_online` chỉ ghi `PresenceLog` khi trạng thái **đổi** (hoặc bản ghi đầu tiên), tránh
  phình bảng sau mỗi 30 giây; trả về `True` nếu trạng thái đổi.

### File tạo/sửa

- `db/database.py` (mới): `get_connection`, `initialize`, `transaction()` (context manager
  tự commit/rollback), `close`, khối `__main__` tự kiểm tra có **dọn bản ghi thử**.
- `db/repository.py` (mới): `upsert_device`, `get_device`, `list_devices`, `set_trusted`,
  `set_name_note`, `set_online`, `add_ping`, `get_pings`, `add_alert`, `list_alerts`,
  `get_presence`, `get_meta`, `set_meta`.

### Kết quả chạy thật

`python -m db.database` chạy **hai lần liên tiếp** (lần 2 không báo lỗi bảng đã tồn tại):

```
Trạng thái online đổi lần đầu: True
Trạng thái online đổi lần hai (phải là False): False
Thiết bị đọc lại sau khi mở lại: Device(ip='192.168.102.99', mac='02:00:00:00:00:99', ..., trusted=True, online=True)
Ping từ đầu hôm nay: 1
Lịch sử online/offline: [(datetime(2026, 11, 2, 8, 58, 12), True)]
Cảnh báo mới nhất: [Alert(level='info', message='Thử ghi cảnh báo', ...)]
Meta demo_key: demo_value
journal_mode: wal
Đã dọn bản ghi thử. Số thiết bị còn lại: 0
```

Kiểm tra thêm: sau khi chạy demo, cả 5 bảng đều 0 dòng (CSDL sạch, không làm bẩn danh sách
thiết bị thật). Kiểm tra `upsert_device`: đổi IP/vendor nhưng **giữ** `name`, `trusted`,
`first_seen`; `last_seen` mới hơn.

### Trạng thái

Giai đoạn 4: **XONG**.

---

## Giai đoạn 5: Quét định kỳ, baseline, cảnh báo thiết bị lạ (A5 – Mốc 1)

### Quyết định thiết kế

1. **Khi nào cảnh báo:** chỉ cảnh báo khi thiết bị **mới** xuất hiện **sau khi đã chốt
   đường cơ sở** và chưa được đánh dấu tin cậy. Thiết bị đã có trong đường cơ sở thì dù
   chưa tin cậy cũng không bị cảnh báo khi ra/vào mạng lại → tránh bão cảnh báo, đúng ý
   "thiết bị mới chưa tin cậy".
2. **Chống lặp:** cùng thiết bị không báo lại trong `ALERT_DEDUP_MINUTES = 30` phút
   (dùng `repository.last_alert_at`).
3. **Offline:** chỉ đánh dấu offline sau `OFFLINE_AFTER_MISSES = 3` lần quét liên tiếp
   vắng mặt; đếm trong bộ nhớ của `ScanLoop`.
4. **Callback, không Qt:** `ScanLoop(on_device, on_alert)`; `on_device(device, event)` với
   `event` = `new` / `online` / `offline`. `Backend` chỉ bọc callback thành signal.
5. **Test không cần mạng thật:** `ScanLoop` nhận tham số `scanner` (mặc định
   `core.arp_scanner.scan_subnet`) để giai đoạn sau/C viết test bơm dữ liệu giả.
6. `models.now()` cố định **GMT+7** (`TZ_VIETNAM`), không phụ thuộc múi giờ máy.

### Lỗi tự phát hiện và đã sửa

`scan_once()` ban đầu đặt `device.online = True` trước khi `upsert_device()`, nên khi thiết
bị **trở lại online**, `set_online()` thấy "không đổi" và **không ghi** `PresenceLog`
(mất mốc online thứ hai). Đã bỏ dòng đó, chỉ để `set_online()` quyết định.

### File tạo/sửa

- `services/baseline.py` (mới): `is_first_run`, `finish_baseline`, `baseline_at`, `reset_baseline`.
- `services/alerts.py` (mới): `make_stranger_alert`, `should_alert`, `raise_stranger`.
- `services/scan_loop.py` (mới): `ScanLoop` (`start`, `stop`, `is_running`, `scan_once`),
  fallback `"Unknown"`/`False` khi `extras.oui` / `extras.mac_random` còn `NotImplementedError`.
- `db/repository.py`: thêm `last_alert_at`.
- `models.py`: `now()` theo GMT+7.
- `backend.py`: cài phần thiết bị của `Backend` (start/stop/list/set_trusted/rename/
  is_first_run/finish_baseline/get_alerts/get_device_history) + bọc callback thành signal.
- `main.py`: thêm `--cli monitor` và `--cli baseline`.

### Kết quả kiểm tra (đã chạy thật)

**a) Kịch bản 9 chu kỳ với scanner giả** (baseline chốt sau chu kỳ 2):

| Chu kỳ | Tình huống | Kết quả |
|---|---|---|
| 1–2 | chưa chốt baseline, thấy router + máy này | `new` x2, **0 cảnh báo** |
| 3 | sau baseline, xuất hiện máy `.50` | `new` + **1 cảnh báo warning** |
| 4–6 | máy `.50` vẫn online | không cảnh báo lặp |
| 7 | vắng mặt 3 lần | sự kiện `offline` đúng lúc |
| 8 | vẫn vắng | không phát lại |
| 9 | quay lại | sự kiện `online`, **không** cảnh báo (không phải thiết bị mới) |

Lịch sử `PresenceLog` ghi đủ 3 mốc `True → False → True`. Gọi lại `raise_stranger` ngay
sau đó trả `None` (chống lặp hoạt động).

**b) Vòng lặp không chết khi quét lỗi:** scanner giả ném lỗi ở lần 2, luồng vẫn chạy,
`last_error` được ghi, `stop()` dừng sạch.

**c) Monitor thật 40 giây** (`python main.py --cli monitor`):

```
Lần đầu chạy: đang lập đường cơ sở, CHƯA cảnh báo thiết bị lạ.
[09:07:18] NEW     192.168.102.1   28:77:77:db:b5:6c   Unknown
[09:07:18] NEW     192.168.102.3   d4:e8:53:2c:8a:26   Unknown
[09:07:18] NEW     192.168.102.7   ac:74:b1:41:a5:d2   Unknown (máy này)
[09:07:48] NEW     192.168.102.65  72:7c:60:9c:09:5f   Unknown
```

**d) Nhánh Ctrl+C:** mô phỏng `KeyboardInterrupt` → in `Đang dừng...`, gọi `stop()`,
in `Đã dừng theo dõi.`, trả mã thoát 0.
(Gửi Ctrl+Break từ ngoài thì Windows kill tiến trình ngay — mã `0xC000013A` — nên dùng
Ctrl+C thật trong PowerShell để thấy nhánh dừng sạch.)

**e) Trạng thái CSDL để A test tiếp:** 4 thiết bị thật đã lưu (`.1`, `.3`, `.7`, `.65`),
`baseline_done = None` → A có thể chạy monitor rồi chốt baseline để thử cảnh báo.

### Trạng thái

Giai đoạn 5: **code + test giả lập + test thật đã xong**; còn chờ A làm bài thử Mốc 1
(bật điện thoại mới → cảnh báo; tắt Wi-Fi → offline sau 3 chu kỳ).

---

## Giai đoạn 6: ICMP và traceroute (A6) – ĐÃ CÀI ĐẶT, CHỜ ĐỐI CHIẾU MẠNG THẬT

Theo yêu cầu tiếp tục của A, bắt đầu giai đoạn 6 dù Mốc 1 giai đoạn 5 vẫn chưa có log
xác nhận thiết bị mới và trạng thái offline.

### File tạo/sửa

- `core/icmp.py` (mới): `ping_once` dùng `icmplib`, trả RTT mili giây hoặc `None`; `ping_series`
  lặp theo số mẫu và khoảng nghỉ. Lỗi thiếu quyền được đổi thành hướng dẫn chạy Administrator.
- `core/traceroute.py` (mới): traceroute ICMP tăng TTL; trên Windows đọc `tracert.exe` để
  khớp với routing table của hệ điều hành, nền tảng khác dùng `icmplib`. TTL không phản hồi
  được dựng lại thành `ip=None`.
- `find_isp_hop`: tìm gateway trong kết quả rồi chọn hop phản hồi đầu tiên sau gateway, bỏ qua
  hop im lặng; không giả định hop thứ hai là hop nhà mạng.
- `mark_latency_jump`: đánh dấu điểm RTT tăng ít nhất `max(10 ms, 1.5 lần RTT trước)` nếu
  hop phản hồi kế tiếp vẫn duy trì phần lớn mức tăng.
- `main.py`: `python main.py --cli trace [địa_chỉ]` in TTL, IP, RTT, hop nhà mạng được chọn
  và điểm tăng độ trễ.

### Trạng thái xác minh

Chưa chạy kiểm tra mạng thật trong lượt này. Giai đoạn 6 chỉ được coi là hoàn tất sau khi A
đối chiếu `python main.py --cli trace 1.1.1.1` với `tracert -d 1.1.1.1` trong PowerShell
Administrator, khi CloudflareWARP đã tắt, và xác nhận hop nào là hop nhà mạng.

### Sửa sau log traceroute đầu tiên của A

Lần chạy Scapy ban đầu in `MAC address to reach destination not found. Using broadcast.`
Scapy dựa vào bảng route riêng khi gửi L3, không đảm bảo trùng route Windows. Lần kế tiếp
dùng raw socket của `icmplib` nhưng trả toàn `*` dù `tracert` của Windows có hop phản hồi.
Đã chuyển Windows sang gọi `tracert.exe -d -4` và phân tích TTL/IP/RTT; platform khác vẫn
dùng `icmplib`. Chưa chạy lại lệnh mạng thật sau thay đổi này; cần A gửi output mới để xác nhận.

---

## Giai đoạn 7: Ping ba mốc và kết luận tự động (A7) – ĐÃ CÀI ĐẶT, CHỜ CLUMSY

### File tạo/sửa

- core/diagnosis.py: thêm TargetStats, is_bad và diagnose thuần theo ngưỡng trong config.
- services/ping_monitor.py: ping router, hop ISP và 1.1.1.1 theo chu kỳ; lưu PingLog;
  tính median, phân vị 25 làm nền, cửa sổ trượt và chỉ phát kết luận sau số cửa sổ ổn định.
- Nếu chưa tìm thấy hop ISP, dịch vụ dò lại traceroute định kỳ. Lỗi của một ping được tính
  là mất gói và không làm chết luồng.
- backend.py: thêm lịch sử ping, callback chẩn đoán và chạy traceroute nền.
- main.py: thêm --cli diagnose, in số liệu từng chu kỳ và kết luận khi đổi.

### Quy tắc kết luận và ngưỡng hiện hành

| Điều kiện | Kết luận |
|---|---|
| Router xấu | home_issue |
| Router ổn, hop ISP xấu | isp_issue |
| Router và ISP ổn, đích ngoài xấu | internet_issue |
| Router/ISP/đích ngoài ổn | ok |
| Không tìm được hop ISP, đích ngoài xấu | internet_issue, ghi chú chưa xác định hop ISP |
| Thiếu tối thiểu 10 mẫu cần thiết | unknown |

Ngưỡng: mất gói trên 5%; RTT median lớn hơn max(3 × nền phân vị 25, 20 ms);
30 mẫu tối đa/cửa sổ; yêu cầu 10 mẫu tối thiểu; cần 3 cửa sổ ổn định.

### Trạng thái xác minh

Chưa chạy ba kịch bản Clumsy. Cần thử thả gói đến router, hop ISP và 1.1.1.1; kiểm tra
kết luận, độ trễ đổi trạng thái và hiện tượng nhảy qua lại.

---

## Giai đoạn 8: Ghép nối backend, báo cáo và GUI (A8) – BACKEND ĐÃ CÀI; CHỜ B/C

- Backend khởi động/dừng quét, listener ARP và ping; truy vấn lịch sử; phát Qt signals;
  chạy traceroute nền; gom ping, mất gói, kết luận trong phiên và traceroute gần nhất để xuất PDF.
- main.py kiểm tra môi trường, hỗ trợ Backend/FakeBackend và gọi MainWindow của B nếu có.
- docs/architecture.md mô tả kiến trúc và luồng dữ liệu.
- ui/main_window.py chưa có. Không viết thay vì file này thuộc B.
- extras.pdf_report.build_report còn NotImplementedError thuộc phần C; Backend trả thông báo
  rõ ràng thay vì báo xuất thành công.
- Chưa chạy GUI hoặc xác nhận không còn luồng treo; cần B/C ghép xong để kiểm tra.

---

## Giai đoạn 9: Lớp bảo vệ phụ (A9, tùy chọn) – ĐÃ CÀI ĐẶT, CHỜ MÔI TRƯỜNG THỬ

- core/arp_listener.py nghe ARP Reply và gratuitous ARP thụ động; có start/stop.
- services.alerts.ArpAnomalyDetector cảnh báo IP đổi MAC khi thiết bị cũ còn online và MAC
  mới lặp lại; gateway đổi MAC mức danger; hai MAC tranh chấp một IP; một MAC quảng bá ít
  nhất ba IP trong 60 giây.
- Cửa sổ tranh chấp là 30 giây; đổi MAC gateway cần hai lần xác nhận trong 5 giây; thay đổi
  IP thông thường chỉ cảnh báo khi thiết bị cũ còn online gần đây. Cảnh báo được chống lặp.
- Backend và CLI monitor tích hợp listener. Chưa thử trong VM hoặc chạy 30 phút để đánh giá
  báo nhầm.

---

## Giai đoạn 10: Rà soát và tổng kết (A10) – CODE/DOCS CẬP NHẬT, CHỜ KIỂM TRA THỰC TẾ

- README đã có lệnh CLI, baseline, GUI/fake và lưu ý traceroute Windows; architecture.md
  mô tả tầng và luồng dữ liệu.
- Các NotImplementedError còn lại thuộc BackendBase (hợp đồng), FakeBackend PDF và extras/
  của C (OUI, MAC random, CSV, PDF, Wi-Fi, Telegram). Không còn placeholder CLI cho
  diagnose/trace.
- Phụ thuộc chặn GUI: B chưa cung cấp ui/main_window.py. Phụ thuộc chặn PDF: C chưa cung
  cấp extras/pdf_report.build_report.
- Chưa chạy pytest, ba kịch bản Clumsy, thử ARP trong VM, GUI, hoặc phiên ổn định 30 phút.
  Đây là các kiểm tra cần thực hiện trước khi coi bản demo hoàn tất.
- Mốc 1 giai đoạn 5 (thiết bị mới và offline) cũng vẫn chưa được A xác nhận; A đã yêu cầu
  chuyển thẳng đến giai đoạn 10 và sẽ rà từng vấn đề sau.

---
