"""Hằng số cấu hình của NetGuard.

Cấu hình người dùng tại data/settings.json được validate lúc mở ứng dụng.
Thay đổi có hiệu lực sau khi mở lại; các hằng còn lại là giới hạn an toàn.
"""

from __future__ import annotations
from core.settings import ROOT, load, DEFAULTS

SETTINGS_ERROR = ""
try:
    SETTINGS = load()
except (ValueError, TypeError, OSError) as exc:
    SETTINGS = dict(DEFAULTS)
    SETTINGS_ERROR = f"Cấu hình không hợp lệ, đang dùng mặc định: {exc}"

# --- Quét ARP ---
SCAN_INTERVAL_SEC = SETTINGS["scan_interval"]
ARP_TIMEOUT_SEC = 2           # thời gian chờ phản hồi ARP mỗi vòng
ARP_ROUNDS = 2                # số vòng gửi ARP mỗi lần quét (gộp kết quả, giảm sót)
OFFLINE_AFTER_MISSES = 3      # vắng mặt bao nhiêu lần quét liên tiếp thì coi là offline

# --- Ping / chẩn đoán ---
PING_INTERVAL_SEC = SETTINGS["ping_interval"]
PING_TIMEOUT_SEC = SETTINGS["ping_timeout"]
PING_EXTERNAL_TARGET = SETTINGS["external_target"]
DIAG_WINDOW_SAMPLES = 30      # số mẫu trong cửa sổ trượt để tính thống kê
DIAG_MIN_SAMPLES = 10         # dưới ngưỡng này thì kết luận là "unknown"
LOSS_BAD_PCT = SETTINGS["loss_bad_pct"]
RTT_BAD_FACTOR = 3            # RTT xấu khi vượt RTT_BAD_FACTOR lần đường cơ sở...
RTT_BAD_MIN_MS = 20           # ...và cũng phải vượt mức tối thiểu này (ms)
DIAG_STABLE_WINDOWS = 3       # kết luận phải giữ ổn định bao nhiêu cửa sổ liên tiếp mới phát

# --- Traceroute ---
TRACE_MAX_HOPS = 15

# --- Cảnh báo ---
ALERT_DEDUP_MINUTES = 30      # không lặp lại cùng loại cảnh báo cho cùng thiết bị trong bao lâu

# --- Giới hạn và đường dẫn ---
MAX_SCAN_HOSTS = 1024         # subnet lớn hơn ngưỡng này thì từ chối quét
MAX_KNOWN_DEVICES = 10000    # ngân sách hồ sơ một mạng, không ghi vô hạn từ MAC tự khai báo
DB_PATH = str(ROOT / "data" / "netguard.db")
