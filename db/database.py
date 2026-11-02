"""Kết nối SQLite dùng chung cho cả chương trình.

Một kết nối duy nhất (mở ở luồng nào cũng được) được bảo vệ bằng ``threading.RLock``,
bật WAL để đọc/ghi song song nhẹ nhàng hơn, và tự tạo bảng nếu chưa có.

Múi giờ: dùng **GMT+7** thống nhất toàn dự án, lưu dạng ISO 8601
không kèm offset (ví dụ ``2026-11-02T09:15:00``) để so sánh chuỗi cũng đúng thứ tự.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS Devices (
    mac         TEXT PRIMARY KEY,
    ip          TEXT NOT NULL,
    vendor      TEXT NOT NULL DEFAULT '',
    name        TEXT NOT NULL DEFAULT '',
    note        TEXT NOT NULL DEFAULT '',
    trusted     INTEGER NOT NULL DEFAULT 0,
    randomized  INTEGER NOT NULL DEFAULT 0,
    is_self     INTEGER NOT NULL DEFAULT 0,
    online      INTEGER NOT NULL DEFAULT 0,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS PresenceLog (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    mac   TEXT NOT NULL,
    online INTEGER NOT NULL,
    ts    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_presence_mac_ts ON PresenceLog(mac, ts);

CREATE TABLE IF NOT EXISTS PingLog (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    target   TEXT NOT NULL,
    rtt_ms   REAL,
    loss_pct REAL NOT NULL,
    ts       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ping_target_ts ON PingLog(target, ts);

CREATE TABLE IF NOT EXISTS Alerts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    level      TEXT NOT NULL,
    message    TEXT NOT NULL,
    device_mac TEXT,
    ts         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_ts ON Alerts(ts);

CREATE TABLE IF NOT EXISTS Meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_lock = threading.RLock()
_connection: sqlite3.Connection | None = None


def get_connection() -> sqlite3.Connection:
    """Trả về kết nối dùng chung, tạo file CSDL và bảng ở lần gọi đầu tiên."""
    global _connection
    with _lock:
        if _connection is None:
            path = Path(DB_PATH)
            path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(path, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.executescript(_SCHEMA)
            connection.commit()
            _connection = connection
        return _connection


def initialize() -> None:
    """Tạo CSDL và bảng nếu chưa có (gọi lúc khởi động chương trình)."""
    get_connection()


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Giữ khoá, cho dùng kết nối chung, commit khi xong và rollback nếu có lỗi."""
    connection = get_connection()
    with _lock:
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def close() -> None:
    """Đóng kết nối dùng chung (gọi khi thoát chương trình). An toàn khi gọi nhiều lần."""
    global _connection
    with _lock:
        if _connection is not None:
            _connection.close()
            _connection = None


def _demo() -> int:
    """Ghi rồi đọc lại vài bản ghi để kiểm tra CSDL hoạt động.

    Chạy trên CSDL thật (``data/netguard.db``) nhưng **dọn sạch bản ghi thử** ở cuối,
    nên không làm bẩn danh sách thiết bị khi chạy ứng dụng sau này.
    """
    from core.console import setup_console_encoding
    from db import repository
    from models import Alert, Device, PingResult, now

    setup_console_encoding()
    initialize()
    demo_mac = "02:00:00:00:00:99"
    started = now()

    device = Device(ip="192.168.102.99", mac=demo_mac, vendor="Demo", name="Máy thử")
    repository.upsert_device(device)
    repository.set_trusted(demo_mac, True)
    print("Trạng thái online đổi lần đầu:", repository.set_online(demo_mac, True))
    print("Trạng thái online đổi lần hai (phải là False):", repository.set_online(demo_mac, True))
    repository.add_ping(PingResult(target="router", rtt_ms=2.5, loss_pct=0, ts=started))
    repository.add_alert(Alert(level="info", message="Thử ghi cảnh báo", device_mac=demo_mac, ts=started))
    repository.set_meta("demo_key", "demo_value")

    close()
    initialize()  # mở lại để chắc chắn dữ liệu đã ghi xuống file

    print("Thiết bị đọc lại sau khi mở lại:", repository.get_device(demo_mac))
    print("Số thiết bị trong CSDL:", len(repository.list_devices()))
    print("Ping từ đầu hôm nay:", len(repository.get_pings("router", started.replace(hour=0, minute=0, second=0))))
    print("Lịch sử online/offline:", repository.get_presence(demo_mac, since=started.replace(hour=0, minute=0, second=0)))
    print("Cảnh báo mới nhất:", repository.list_alerts(1))
    print("Meta demo_key:", repository.get_meta("demo_key"))
    print("journal_mode:", get_connection().execute("PRAGMA journal_mode").fetchone()[0])

    with transaction() as connection:  # dọn bản ghi thử
        connection.execute("DELETE FROM Devices WHERE mac = ?", (demo_mac,))
        connection.execute("DELETE FROM PresenceLog WHERE mac = ?", (demo_mac,))
        connection.execute("DELETE FROM PingLog WHERE ts >= ?", (_to_iso_for_cleanup(started),))
        connection.execute("DELETE FROM Alerts WHERE message = ?", ("Thử ghi cảnh báo",))
        connection.execute("DELETE FROM Meta WHERE key = ?", ("demo_key",))
    print("Đã dọn bản ghi thử. Số thiết bị còn lại:", len(repository.list_devices()))
    return 0


def _to_iso_for_cleanup(moment) -> str:
    """Đổi thời điểm sang ISO 8601 giống cách ``db.repository`` lưu."""
    return moment.replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(_demo())
