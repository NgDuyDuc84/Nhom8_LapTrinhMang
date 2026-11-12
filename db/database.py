"""Kết nối SQLite dùng chung cho cả chương trình.

Một kết nối duy nhất (mở ở luồng nào cũng được) được bảo vệ bằng ``threading.RLock``,
bật WAL để đọc/ghi song song nhẹ nhàng hơn, và tự tạo bảng nếu chưa có.

Múi giờ: dùng **GMT+7** thống nhất toàn dự án, lưu dạng ISO 8601
không kèm offset (ví dụ ``2026-11-02T09:15:00``) để so sánh chuỗi cũng đúng thứ tự.
"""

from __future__ import annotations

import sqlite3
import threading
import tempfile
from contextlib import contextmanager, closing
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

CREATE TABLE IF NOT EXISTS DeviceIdentity (
    mac                 TEXT PRIMARY KEY,
    ip                  TEXT NOT NULL DEFAULT '',
    hostname            TEXT NOT NULL DEFAULT '',
    discovered_name     TEXT NOT NULL DEFAULT '',
    manufacturer        TEXT NOT NULL DEFAULT '',
    model               TEXT NOT NULL DEFAULT '',
    services            TEXT NOT NULL DEFAULT '[]',
    device_type         TEXT NOT NULL DEFAULT 'unknown',
    confidence          TEXT NOT NULL DEFAULT 'unknown',
    evidence            TEXT NOT NULL DEFAULT '',
    type_override       TEXT NOT NULL DEFAULT '',
    observed_at         TEXT
);

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
_connections: dict[str, sqlite3.Connection] = {}
_depth = threading.local()


def database_path() -> Path:
    from core.network_context import current_network
    network = current_network()
    base = Path(DB_PATH).resolve()
    if network == "legacy":
        return base
    if len(network) != 24 or any(c not in "0123456789abcdef" for c in network):
        raise ValueError("Định danh mạng không hợp lệ.")
    return base.parent / "networks" / f"{network}.db"


def _migrate(connection, path):
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > 3:
        raise RuntimeError("CSDL được tạo bởi phiên bản NetGuard mới hơn; hãy nâng cấp ứng dụng.")
    if version >= 3:
        return
    # backup() lấy snapshot nhất quán, bao gồm các trang còn trong WAL.
    if any(connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
           for table in ("Devices", "PingLog", "Alerts", "PresenceLog", "Meta", "DeviceIdentity")):
        with closing(sqlite3.connect(str(path) + ".pre-v3.bak")) as backup:
            connection.backup(backup)
    additions = {
        "PingLog": {"address": "TEXT NOT NULL DEFAULT ''", "session_id": "TEXT NOT NULL DEFAULT ''",
                    "status": "TEXT NOT NULL DEFAULT 'ok'"},
        "Alerts": {"kind": "TEXT NOT NULL DEFAULT 'general'", "acknowledged": "INTEGER NOT NULL DEFAULT 0"},
    }
    with connection:
        for table, columns in additions.items():
            existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            for name, definition in columns.items():
                if name not in existing:
                    connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        from models import local_time
        from datetime import datetime
        for table, fields in {"Devices": ("first_seen", "last_seen"), "PingLog": ("ts",), "Alerts": ("ts",), "PresenceLog": ("ts",), "DeviceIdentity": ("observed_at",)}.items():
            for field in fields:
                cursor = connection.execute(f"SELECT rowid,{field} FROM {table}")
                while rows := cursor.fetchmany(1000):
                    updates = []
                    for row in rows:
                        try:
                            stamp = local_time(datetime.fromisoformat(row[1])).isoformat(timespec="microseconds")
                            updates.append((stamp, row[0]))
                        except (TypeError, ValueError):
                            continue  # Giữ nguyên bản ghi hỏng để có thể kiểm tra/khôi phục.
                    connection.executemany(f"UPDATE {table} SET {field}=? WHERE rowid=?", updates)
        connection.execute("UPDATE PingLog SET status='timeout' WHERE rtt_ms IS NULL AND status='ok'")
        for statement in (
            "CREATE TABLE IF NOT EXISTS Sessions(id TEXT PRIMARY KEY, started TEXT NOT NULL, ended TEXT, interface TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS DiagnosisLog(id INTEGER PRIMARY KEY, ts TEXT NOT NULL, verdict TEXT NOT NULL, text TEXT NOT NULL, session_id TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS RouteLog(id INTEGER PRIMARY KEY, ts TEXT NOT NULL, hops TEXT NOT NULL, session_id TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS Observations(id INTEGER PRIMARY KEY, ip TEXT NOT NULL, mac TEXT NOT NULL, ts TEXT NOT NULL, session_id TEXT NOT NULL)",
            "CREATE INDEX IF NOT EXISTS idx_observation_time ON Observations(ts)",
            "CREATE INDEX IF NOT EXISTS idx_ping_context ON PingLog(session_id, target, ts)",
            "CREATE INDEX IF NOT EXISTS idx_alert_kind ON Alerts(kind, device_mac, ts)",
            "CREATE TABLE IF NOT EXISTS BaselineMembers(mac TEXT PRIMARY KEY, trusted INTEGER NOT NULL, ts TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS DeviceAlertState(mac TEXT PRIMARY KEY, pending INTEGER NOT NULL CHECK(pending IN (0,1)))",
        ):
            connection.execute(statement)
        connection.execute("INSERT OR IGNORE INTO DeviceAlertState SELECT mac, CASE WHEN trusted=0 AND NOT EXISTS(SELECT 1 FROM Alerts WHERE device_mac=Devices.mac AND kind='stranger') THEN 1 ELSE 0 END FROM Devices")
        connection.execute("PRAGMA user_version=3")


def get_connection() -> sqlite3.Connection:
    """Trả về kết nối dùng chung, tạo file CSDL và bảng ở lần gọi đầu tiên."""
    global _connection
    with _lock:
        path = database_path()
        key = str(path)
        if key not in _connections:
            path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(path, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.executescript(_SCHEMA)
            connection.commit()
            try:
                _migrate(connection, path)
                connection.execute("CREATE INDEX IF NOT EXISTS idx_ping_session_time ON PingLog(session_id,ts)")
            except Exception:
                connection.close()
                raise
            _connections[key] = connection
        _connection = _connections[key]
        return _connection


def initialize() -> None:
    """Tạo CSDL và bảng nếu chưa có (gọi lúc khởi động chương trình)."""
    get_connection()


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Giữ khoá, cho dùng kết nối chung, commit khi xong và rollback nếu có lỗi."""
    with _lock:
        connection = get_connection()
        depth = getattr(_depth, "value", 0)
        savepoint = f"netguard_{depth}"
        connection.execute("BEGIN IMMEDIATE" if depth == 0 else f"SAVEPOINT {savepoint}")
        _depth.value = depth + 1
        try:
            yield connection
            if depth == 0:
                connection.commit()
            else:
                connection.execute(f"RELEASE SAVEPOINT {savepoint}")
        except Exception:
            if depth == 0:
                connection.rollback()
            else:
                connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            raise
        finally:
            _depth.value = depth


def close() -> None:
    """Đóng kết nối dùng chung (gọi khi thoát chương trình). An toàn khi gọi nhiều lần."""
    global _connection
    with _lock:
        for connection in _connections.values():
            connection.close()
        _connections.clear()
        _connection = None


@contextmanager
def read_snapshot():
    """Connection đọc riêng cho báo cáo: snapshot WAL không giữ khóa UI/writer."""
    with _lock:
        get_connection()
        path = database_path()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN")
        try:
            yield connection
        finally:
            connection.rollback()


def backup_to(path: str) -> None:
    destination = Path(path).resolve()
    with _lock:
        if destination == database_path() or str(destination) in _connections:
            raise ValueError("Không ghi bản sao đè lên CSDL đang dùng.")
        with closing(sqlite3.connect(destination)) as output:
            get_connection().backup(output)


def restore_from(path: str) -> None:
    """Nâng cấp/kiểm tra bản sao ở file tạm trước khi thay CSDL đang dùng."""
    destination = database_path()
    if Path(path).resolve() == destination:
        raise ValueError("Không khôi phục CSDL từ chính file đang dùng.")
    with _lock, closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as source:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".netguard-restore-", dir=destination.parent) as temporary:
            # TemporaryDirectory chỉ dọn thư mục con vừa tạo trong thư mục CSDL.
            assert Path(temporary).resolve().is_relative_to(destination.parent.resolve())
            staged_path = Path(temporary) / "staged.db"
            with closing(sqlite3.connect(staged_path)) as staged:
                try:
                    if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise ValueError("Bản sao CSDL bị hỏng.")
                    if not source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Devices'").fetchone():
                        raise ValueError("Đây không phải bản sao NetGuard.")
                    source.backup(staged)
                    staged.executescript(_SCHEMA)
                    _migrate(staged, staged_path)
                    # So sánh với schema chuẩn, kể cả bản sao tự nhận version mới
                    # nhưng thiếu bảng/cột mà repository cần.
                    with closing(sqlite3.connect(":memory:")) as expected:
                        expected.executescript(_SCHEMA)
                        _migrate(expected, staged_path)
                        for (table,) in expected.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
                            required = {row[1] for row in expected.execute(f"PRAGMA table_info({table})")}
                            actual = {row[1] for row in staged.execute(f"PRAGMA table_info({table})")}
                            if not required <= actual:
                                raise ValueError(f"Bản sao thiếu bảng/cột NetGuard: {table}.")
                    staged.execute("CREATE INDEX IF NOT EXISTS idx_ping_session_time ON PingLog(session_id,ts)")
                    staged.commit()
                except (sqlite3.Error, RuntimeError) as exc:
                    raise ValueError("Bản sao NetGuard không tương thích hoặc bị hỏng.") from exc
                # Chỉ thay dữ liệu sau khi migration và validation đều thành công.
                staged.backup(get_connection())


def _demo() -> int:
    """Demo trong CSDL tạm riêng; không dọn hoặc ghi dữ liệu của ứng dụng."""
    from db import database as shared, repository
    from models import Device, PingResult, Alert, now
    from core.console import setup_console_encoding
    setup_console_encoding()
    previous = shared.DB_PATH
    temporary_root = Path(tempfile.gettempdir()).resolve()
    with tempfile.TemporaryDirectory(prefix="netguard-demo-", dir=temporary_root) as temporary:
        assert Path(temporary).resolve().is_relative_to(temporary_root)
        shared.close()
        shared.DB_PATH = str(Path(temporary) / "demo.db")
        try:
            shared.initialize()
            device = Device("192.0.2.99", "02:00:00:00:00:99", name="Máy thử")
            repository.upsert_device(device)
            repository.set_online(device.mac, True)
            repository.add_ping(PingResult("router", 2.5, 0))
            repository.add_alert(Alert("info", "Demo CSDL tạm"))
            print("Demo dùng CSDL tạm, không chạm dữ liệu đang dùng.")
            print("Thiết bị:", repository.get_device(device.mac))
            print("Lịch sử:", repository.get_presence(device.mac, now().replace(hour=0, minute=0, second=0)))
            print("Cảnh báo:", repository.list_alerts(1))
        finally:
            shared.close()
            shared.DB_PATH = previous
    return 0


if __name__ == "__main__":
    raise SystemExit(_demo())
