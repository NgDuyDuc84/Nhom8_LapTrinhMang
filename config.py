"""Hằng số cấu hình của NetGuard.

Giá trị ở đây là tạm thời, sẽ tinh chỉnh sau khi thử bằng Clumsy (giai đoạn 7).
Chưa dùng .env: mọi thứ viết cứng trong file này.
"""

from __future__ import annotations

# --- Quét ARP ---
SCAN_INTERVAL_SEC = 30        # chu kỳ quét lại toàn mạng LAN
ARP_TIMEOUT_SEC = 2           # thời gian chờ phản hồi ARP mỗi vòng
ARP_ROUNDS = 2                # số vòng gửi ARP mỗi lần quét (gộp kết quả, giảm sót)
OFFLINE_AFTER_MISSES = 3      # vắng mặt bao nhiêu lần quét liên tiếp thì coi là offline

# --- Ping / chẩn đoán ---
PING_INTERVAL_SEC = 2         # chu kỳ ping mỗi mốc
PING_TIMEOUT_SEC = 1          # thời gian chờ mỗi gói ping
PING_EXTERNAL_TARGET = "1.1.1.1"
DIAG_WINDOW_SAMPLES = 30      # số mẫu trong cửa sổ trượt để tính thống kê
DIAG_MIN_SAMPLES = 10         # dưới ngưỡng này thì kết luận là "unknown"
LOSS_BAD_PCT = 5              # mất gói vượt ngưỡng này (%) thì coi là xấu
RTT_BAD_FACTOR = 3            # RTT xấu khi vượt RTT_BAD_FACTOR lần đường cơ sở...
RTT_BAD_MIN_MS = 20           # ...và cũng phải vượt mức tối thiểu này (ms)
DIAG_STABLE_WINDOWS = 3       # kết luận phải giữ ổn định bao nhiêu cửa sổ liên tiếp mới phát

# --- Traceroute ---
TRACE_MAX_HOPS = 15

# --- Cảnh báo ---
ALERT_DEDUP_MINUTES = 30      # không lặp lại cùng loại cảnh báo cho cùng thiết bị trong bao lâu

# --- Giới hạn và đường dẫn ---
MAX_SCAN_HOSTS = 1024         # subnet lớn hơn ngưỡng này thì từ chối quét
DB_PATH = "data/netguard.db"
