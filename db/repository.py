"""Các hàm đọc/ghi CSDL, trả về dataclass trong ``models.py``.

Quy ước:
- MAC luôn viết thường (``aa:bb:cc:dd:ee:ff``).
- Thời gian lưu dạng ISO 8601 theo GMT+7, không kèm offset.
- Mọi hàm đều an toàn khi gọi từ nhiều luồng (khoá nằm trong ``db.database``).
"""

from __future__ import annotations

import ipaddress
from datetime import datetime

from db.database import transaction
from models import Alert, Device, PingResult, now

__all__ = [
    "upsert_device",
    "get_device",
    "list_devices",
    "set_trusted",
    "set_name_note",
    "set_online",
    "add_ping",
    "get_pings",
    "add_alert",
    "last_alert_at",
    "list_alerts",
    "get_presence",
    "get_meta",
    "set_meta",
]


def _to_iso(moment: datetime) -> str:
    """Đổi ``datetime`` sang chuỗi ISO 8601 (bỏ phần micro giây cho gọn)."""
    return moment.replace(microsecond=0).isoformat()


def _from_iso(text: str) -> datetime:
    """Đổi chuỗi ISO 8601 trong CSDL về ``datetime``."""
    return datetime.fromisoformat(text)


def _row_to_device(row) -> Device:
    """Chuyển một dòng bảng ``Devices`` thành ``Device``."""
    return Device(
        ip=row["ip"],
        mac=row["mac"],
        vendor=row["vendor"],
        name=row["name"],
        note=row["note"],
        trusted=bool(row["trusted"]),
        online=bool(row["online"]),
        randomized_mac=bool(row["randomized"]),
        is_self=bool(row["is_self"]),
        first_seen=_from_iso(row["first_seen"]),
        last_seen=_from_iso(row["last_seen"]),
    )


# ------------------------------------------------------------------ thiết bị
def upsert_device(device: Device) -> None:
    """Thêm thiết bị mới hoặc cập nhật thiết bị đã có.

    Khi thiết bị đã tồn tại, chỉ cập nhật ``ip``, ``vendor``, ``randomized``,
    ``is_self``, ``online`` và ``last_seen``; giữ nguyên ``name``, ``note``,
    ``trusted`` và ``first_seen`` do người dùng đặt.
    """
    with transaction() as connection:
        connection.execute(
            """
            INSERT INTO Devices (mac, ip, vendor, name, note, trusted, randomized, is_self,
                                 online, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(mac) DO UPDATE SET
                ip = excluded.ip,
                vendor = excluded.vendor,
                randomized = excluded.randomized,
                is_self = excluded.is_self,
                online = excluded.online,
                last_seen = excluded.last_seen
            """,
            (
                device.mac.lower(),
                device.ip,
                device.vendor,
                device.name,
                device.note,
                int(device.trusted),
                int(device.randomized_mac),
                int(device.is_self),
                int(device.online),
                _to_iso(device.first_seen),
                _to_iso(device.last_seen),
            ),
        )


def get_device(mac: str) -> Device | None:
    """Lấy một thiết bị theo MAC; trả ``None`` nếu chưa có trong CSDL."""
    with transaction() as connection:
        row = connection.execute("SELECT * FROM Devices WHERE mac = ?", (mac.lower(),)).fetchone()
    return _row_to_device(row) if row else None


def list_devices() -> list[Device]:
    """Trả về toàn bộ thiết bị, sắp xếp theo địa chỉ IP tăng dần."""
    with transaction() as connection:
        rows = connection.execute("SELECT * FROM Devices").fetchall()
    devices = [_row_to_device(row) for row in rows]
    return sorted(devices, key=lambda device: ipaddress.IPv4Address(device.ip))


def set_trusted(mac: str, trusted: bool) -> None:
    """Đặt cờ tin cậy cho thiết bị."""
    with transaction() as connection:
        connection.execute("UPDATE Devices SET trusted = ? WHERE mac = ?", (int(trusted), mac.lower()))


def set_name_note(mac: str, name: str, note: str) -> None:
    """Đổi tên gợi nhớ và ghi chú của thiết bị."""
    with transaction() as connection:
        connection.execute(
            "UPDATE Devices SET name = ?, note = ? WHERE mac = ?", (name, note, mac.lower())
        )


def set_online(mac: str, online: bool, ts: datetime | None = None) -> bool:
    """Cập nhật trạng thái online/offline và ghi ``PresenceLog`` khi có thay đổi.

    Chỉ ghi lịch sử khi trạng thái **đổi** (hoặc khi thiết bị chưa từng có bản ghi
    nào), nhờ vậy bảng không phình lên sau mỗi chu kỳ quét 30 giây mà vẫn dựng được
    biểu đồ online/offline.

    Trả về ``True`` nếu trạng thái đổi so với lần trước (tầng trên dùng để phát sự kiện).
    """
    moment = ts or now()
    mac = mac.lower()
    with transaction() as connection:
        row = connection.execute("SELECT online FROM Devices WHERE mac = ?", (mac,)).fetchone()
        if row is None:
            return False
        changed = bool(row["online"]) != bool(online)
        has_history = connection.execute(
            "SELECT 1 FROM PresenceLog WHERE mac = ? LIMIT 1", (mac,)
        ).fetchone() is not None
        connection.execute(
            "UPDATE Devices SET online = ?, last_seen = ? WHERE mac = ?",
            (int(online), _to_iso(moment), mac),
        )
        if changed or not has_history:
            connection.execute(
                "INSERT INTO PresenceLog (mac, online, ts) VALUES (?, ?, ?)",
                (mac, int(online), _to_iso(moment)),
            )
    return changed


# ------------------------------------------------------------------ ping
def add_ping(result: PingResult) -> None:
    """Ghi một mẫu ping vào ``PingLog``."""
    with transaction() as connection:
        connection.execute(
            "INSERT INTO PingLog (target, rtt_ms, loss_pct, ts) VALUES (?, ?, ?, ?)",
            (result.target, result.rtt_ms, result.loss_pct, _to_iso(result.ts)),
        )


def get_pings(target: str, since: datetime) -> list[PingResult]:
    """Lấy các mẫu ping của một mốc kể từ ``since``, cũ nhất trước."""
    with transaction() as connection:
        rows = connection.execute(
            "SELECT target, rtt_ms, loss_pct, ts FROM PingLog "
            "WHERE target = ? AND ts >= ? ORDER BY ts",
            (target, _to_iso(since)),
        ).fetchall()
    return [
        PingResult(
            target=row["target"],
            rtt_ms=row["rtt_ms"],
            loss_pct=row["loss_pct"],
            ts=_from_iso(row["ts"]),
        )
        for row in rows
    ]


# ------------------------------------------------------------------ cảnh báo
def add_alert(alert: Alert) -> None:
    """Ghi một cảnh báo vào ``Alerts``."""
    with transaction() as connection:
        connection.execute(
            "INSERT INTO Alerts (level, message, device_mac, ts) VALUES (?, ?, ?, ?)",
            (alert.level, alert.message, alert.device_mac, _to_iso(alert.ts)),
        )


def last_alert_at(device_mac: str | None) -> datetime | None:
    """Thời điểm cảnh báo gần nhất của một thiết bị (dùng để chống báo lặp).

    ``device_mac = None`` là cảnh báo không gắn với thiết bị nào.
    """
    with transaction() as connection:
        if device_mac is None:
            row = connection.execute(
                "SELECT ts FROM Alerts WHERE device_mac IS NULL ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT ts FROM Alerts WHERE device_mac = ? ORDER BY ts DESC LIMIT 1",
                (device_mac.lower(),),
            ).fetchone()
    return _from_iso(row["ts"]) if row else None


def list_alerts(limit: int = 100) -> list[Alert]:
    """Lấy các cảnh báo mới nhất trước, tối đa ``limit`` bản ghi."""
    with transaction() as connection:
        rows = connection.execute(
            "SELECT level, message, device_mac, ts FROM Alerts ORDER BY ts DESC, id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [
        Alert(
            level=row["level"],
            message=row["message"],
            device_mac=row["device_mac"],
            ts=_from_iso(row["ts"]),
        )
        for row in rows
    ]


# ------------------------------------------------------------------ lịch sử hiện diện
def get_presence(mac: str, since: datetime) -> list[tuple[datetime, bool]]:
    """Lấy lịch sử online/offline của thiết bị kể từ ``since``, cũ nhất trước."""
    with transaction() as connection:
        rows = connection.execute(
            "SELECT ts, online FROM PresenceLog WHERE mac = ? AND ts >= ? ORDER BY ts",
            (mac.lower(), _to_iso(since)),
        ).fetchall()
    return [(_from_iso(row["ts"]), bool(row["online"])) for row in rows]


# ------------------------------------------------------------------ Meta
def get_meta(key: str) -> str | None:
    """Đọc một giá trị trong bảng ``Meta``; trả ``None`` nếu chưa có."""
    with transaction() as connection:
        row = connection.execute("SELECT value FROM Meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(key: str, value: str) -> None:
    """Ghi (hoặc cập nhật) một giá trị trong bảng ``Meta``."""
    with transaction() as connection:
        connection.execute(
            "INSERT INTO Meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
