"""Các hàm đọc/ghi CSDL, trả về dataclass trong ``models.py``.

Quy ước:
- MAC luôn viết thường (``aa:bb:cc:dd:ee:ff``).
- Thời gian lưu dạng ISO 8601 theo GMT+7, không kèm offset.
- Mọi hàm đều an toàn khi gọi từ nhiều luồng (khoá nằm trong ``db.database``).
"""

from __future__ import annotations

import ipaddress
import json
import math
import re
import logging
from datetime import datetime, timedelta
from contextlib import nullcontext

from db.database import transaction
from models import Alert, Device, PingResult, Diagnosis, Hop, now, local_time

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
    "save_identity",
    "set_type_override",
]

_DEVICE_SELECT = """
    SELECT d.*, i.ip AS identity_ip, i.hostname, i.discovered_name,
           i.manufacturer, i.model, i.services, i.device_type, i.confidence,
           i.evidence, i.type_override, i.observed_at
    FROM Devices d LEFT JOIN DeviceIdentity i ON i.mac = d.mac
"""


def _to_iso(moment: datetime) -> str:
    """Đổi ``datetime`` sang chuỗi ISO 8601 (bỏ phần micro giây cho gọn)."""
    return local_time(moment).isoformat(timespec="microseconds")


def _from_iso(text: str) -> datetime:
    """Đổi chuỗi ISO 8601 trong CSDL về ``datetime``."""
    return local_time(datetime.fromisoformat(text))


def valid_mac(value: str) -> str:
    value = value.lower()
    if not re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", value) or value == "00:00:00:00:00:00" or int(value[:2], 16) & 1:
        raise ValueError("Địa chỉ MAC phải là MAC unicast hợp lệ.")
    return value


def _limit(value, maximum=20000):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValueError(f"Số bản ghi phải trong 0–{maximum}.")
    return value


def _row_to_device(row) -> Device:
    """Chuyển một dòng bảng ``Devices`` thành ``Device``."""
    same_ip = row["identity_ip"] == row["ip"]
    try:
        services = json.loads(row["services"] or "[]") if same_ip else []
        if not isinstance(services, list):
            services = []
    except (TypeError, ValueError):
        services = []
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
        hostname=(row["hostname"] or "") if same_ip else "",
        discovered_name=(row["discovered_name"] or "") if same_ip else "",
        manufacturer=(row["manufacturer"] or "") if same_ip else "",
        model=(row["model"] or "") if same_ip else "",
        services=tuple(str(item) for item in services[:32]),
        device_type=(row["device_type"] or "unknown") if same_ip else "unknown",
        identity_confidence=(row["confidence"] or "unknown") if same_ip else "unknown",
        identity_evidence=(row["evidence"] or "") if same_ip else "",
        type_override=row["type_override"] or "",
        identity_seen=_from_iso(row["observed_at"]) if same_ip and row["observed_at"] else None,
    )


# ------------------------------------------------------------------ thiết bị
def upsert_device(device: Device) -> None:
    """Thêm thiết bị mới hoặc cập nhật thiết bị đã có.

    Khi thiết bị đã tồn tại, chỉ cập nhật ``ip``, ``vendor``, ``randomized``,
    ``is_self``, ``online`` và ``last_seen``; giữ nguyên ``name``, ``note``,
    ``trusted`` và ``first_seen`` do người dùng đặt.
    """
    device.mac = valid_mac(device.mac)
    ipaddress.IPv4Address(device.ip)
    if len(device.name) > 500 or len(device.note) > 4000:
        raise ValueError("Tên tối đa 500 ký tự, ghi chú tối đa 4.000 ký tự.")
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
        connection.execute("INSERT OR IGNORE INTO DeviceAlertState(mac,pending) VALUES(?,?)", (device.mac, int(not device.trusted)))


def get_device(mac: str) -> Device | None:
    """Lấy một thiết bị theo MAC; trả ``None`` nếu chưa có trong CSDL."""
    with transaction() as connection:
        row = connection.execute(_DEVICE_SELECT + " WHERE d.mac = ?", (mac.lower(),)).fetchone()
    return _row_to_device(row) if row else None


def list_devices() -> list[Device]:
    """Trả về toàn bộ thiết bị, sắp xếp theo địa chỉ IP tăng dần."""
    with transaction() as connection:
        rows = connection.execute(_DEVICE_SELECT).fetchall()
    devices = []
    for row in rows:
        try:
            ipaddress.IPv4Address(row["ip"])
            valid_mac(row["mac"])
            devices.append(_row_to_device(row))
        except (ValueError, TypeError):
            logging.getLogger(__name__).warning("Bỏ qua hồ sơ thiết bị hỏng: %r", row["mac"])
    return sorted(devices, key=lambda device: ipaddress.IPv4Address(device.ip))


def set_trusted(mac: str, trusted: bool) -> None:
    """Đặt cờ tin cậy cho thiết bị."""
    if not isinstance(trusted, bool):
        raise ValueError("Tin cậy phải là boolean.")
    with transaction() as connection:
        previous = connection.execute("SELECT trusted FROM Devices WHERE mac=?", (mac.lower(),)).fetchone()
        connection.execute("UPDATE Devices SET trusted = ? WHERE mac = ?", (int(trusted), mac.lower()))
        if previous is not None and bool(previous[0]) != trusted:
            connection.execute("INSERT INTO DeviceAlertState VALUES(?,?) ON CONFLICT(mac) DO UPDATE SET pending=excluded.pending", (mac.lower(), int(not trusted)))


def set_name_note(mac: str, name: str, note: str) -> None:
    """Đổi tên gợi nhớ và ghi chú của thiết bị."""
    if len(name) > 500 or len(note) > 4000:
        raise ValueError("Tên hoặc ghi chú quá dài.")
    with transaction() as connection:
        connection.execute(
            "UPDATE Devices SET name = ?, note = ? WHERE mac = ?", (name, note, mac.lower())
        )


def save_identity(device: Device) -> bool:
    """Lưu nhận diện tự động nếu MAC vẫn ở đúng IP; giữ lựa chọn thủ công."""
    with transaction() as connection:
        cursor = connection.execute(
            """
            INSERT INTO DeviceIdentity
                (mac, ip, hostname, discovered_name, manufacturer, model, services,
                 device_type, confidence, evidence, observed_at)
            SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            FROM Devices WHERE mac = ? AND ip = ?
            ON CONFLICT(mac) DO UPDATE SET
                ip=excluded.ip, hostname=excluded.hostname,
                discovered_name=excluded.discovered_name, manufacturer=excluded.manufacturer,
                model=excluded.model, services=excluded.services, device_type=excluded.device_type,
                confidence=excluded.confidence, evidence=excluded.evidence,
                observed_at=excluded.observed_at
            WHERE DeviceIdentity.ip <> excluded.ip OR DeviceIdentity.observed_at IS NULL
               OR (excluded.observed_at IS NOT NULL AND excluded.observed_at >= DeviceIdentity.observed_at)
            """,
            (device.mac.lower(), device.ip, device.hostname, device.discovered_name,
             device.manufacturer, device.model, json.dumps(list(device.services), ensure_ascii=False),
             device.device_type, device.identity_confidence, device.identity_evidence,
             device.identity_seen.isoformat(timespec="microseconds") if device.identity_seen else None,
             device.mac.lower(), device.ip),
        )
    return cursor.rowcount > 0


def set_type_override(mac: str, device_type: str) -> None:
    """Lưu loại do người dùng xác nhận, độc lập với kết quả tự phát hiện."""
    with transaction() as connection:
        connection.execute(
            "INSERT INTO DeviceIdentity (mac, ip, type_override) "
            "SELECT mac, ip, ? FROM Devices WHERE mac = ? "
            "ON CONFLICT(mac) DO UPDATE SET type_override=excluded.type_override",
            (device_type, mac.lower()),
        )


def set_online(mac: str, online: bool, ts: datetime | None = None) -> bool:
    """Cập nhật trạng thái online/offline và ghi ``PresenceLog`` khi có thay đổi.

    Chỉ ghi lịch sử khi trạng thái **đổi** (hoặc khi thiết bị chưa từng có bản ghi
    nào), nhờ vậy bảng không phình lên sau mỗi chu kỳ quét 30 giây mà vẫn dựng được
    biểu đồ online/offline.

    Trả về ``True`` nếu trạng thái đổi so với lần trước (tầng trên dùng để phát sự kiện).
    """
    if not isinstance(online, bool):
        raise ValueError("Trạng thái hiện diện phải là boolean.")
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
        if online:
            connection.execute("UPDATE Devices SET online=1, last_seen=? WHERE mac=?", (_to_iso(moment), mac))
        else:
            connection.execute("UPDATE Devices SET online=0 WHERE mac=?", (mac,))
        if changed or not has_history:
            connection.execute(
                "INSERT INTO PresenceLog (mac, online, ts) VALUES (?, ?, ?)",
                (mac, int(online), _to_iso(moment)),
            )
    return changed


# ------------------------------------------------------------------ ping
def add_ping(result: PingResult) -> None:
    """Ghi một mẫu ping vào ``PingLog``."""
    if result.target not in {"router", "isp", "external"} or result.status not in {"ok", "timeout", "measurement_error", "offline", "unavailable"}:
        raise ValueError("Vai trò/trạng thái phép đo không hợp lệ.")
    if result.rtt_ms is not None and (not math.isfinite(result.rtt_ms) or result.rtt_ms < 0):
        raise ValueError("RTT phải hữu hạn và không âm.")
    if not math.isfinite(result.loss_pct) or not 0 <= result.loss_pct <= 100:
        raise ValueError("Mất gói phải trong 0–100%.")
    if result.address:
        ipaddress.IPv4Address(result.address)
    status = "timeout" if result.status == "ok" and result.rtt_ms is None else result.status
    with transaction() as connection:
        connection.execute(
            "INSERT INTO PingLog (target, rtt_ms, loss_pct, ts, address, session_id, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (result.target, result.rtt_ms, result.loss_pct, _to_iso(result.ts), result.address, result.session_id, status),
        )


def get_pings(target: str, since: datetime, end: datetime | None = None, *, session_id: str | None = None, limit: int = 20000) -> list[PingResult]:
    """Lấy các mẫu ping của một mốc kể từ ``since``, cũ nhất trước."""
    _limit(limit)
    filters = "target = ? AND ts >= ? AND ts <= ?"
    args = [target, _to_iso(since), _to_iso(end or now())]
    if session_id is not None:
        filters += " AND session_id = ?"
        args.append(session_id)
    with transaction() as connection:
        rows = connection.execute(
            f"SELECT * FROM (SELECT * FROM PingLog WHERE {filters} ORDER BY ts DESC, id DESC LIMIT ?) ORDER BY ts, id",
            (*args, limit),
        ).fetchall()
    return [
        PingResult(
            target=row["target"],
            rtt_ms=row["rtt_ms"],
            loss_pct=row["loss_pct"],
            ts=_from_iso(row["ts"]),
            address=row["address"], session_id=row["session_id"], status=row["status"],
        )
        for row in rows
    ]


# ------------------------------------------------------------------ cảnh báo
def add_alert(alert: Alert) -> None:
    """Ghi một cảnh báo vào ``Alerts``."""
    if alert.level not in {"info", "warning", "danger"} or not alert.kind or len(alert.message) > 10000:
        raise ValueError("Cảnh báo không hợp lệ.")
    with transaction() as connection:
        connection.execute(
            "INSERT INTO Alerts (level, message, device_mac, ts, kind) VALUES (?, ?, ?, ?, ?)",
            (alert.level, alert.message, alert.device_mac, _to_iso(alert.ts), alert.kind),
        )


def last_alert_at(device_mac: str | None, kind: str | None = None) -> datetime | None:
    """Thời điểm cảnh báo gần nhất của một thiết bị (dùng để chống báo lặp).

    ``device_mac = None`` là cảnh báo không gắn với thiết bị nào.
    """
    with transaction() as connection:
        if kind is not None:
            row = connection.execute("SELECT ts FROM Alerts WHERE device_mac IS ? AND kind=? ORDER BY ts DESC LIMIT 1", (device_mac, kind)).fetchone()
            return _from_iso(row["ts"]) if row else None
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


def list_alerts(limit: int = 100, *, offset: int = 0, query: str = "") -> list[Alert]:
    """Lấy các cảnh báo mới nhất trước, tối đa ``limit`` bản ghi."""
    _limit(limit, 1000)
    if offset < 0:
        raise ValueError("Offset không được âm.")
    with transaction() as connection:
        rows = connection.execute(
            "SELECT * FROM Alerts WHERE message LIKE ? ORDER BY ts DESC, id DESC LIMIT ? OFFSET ?",
            (f"%{query[:500]}%", limit, offset),
        ).fetchall()
    return [
        Alert(
            level=row["level"],
            message=row["message"],
            device_mac=row["device_mac"],
            ts=_from_iso(row["ts"]),
            kind=row["kind"],
            id=row["id"], acknowledged=bool(row["acknowledged"]),
        )
        for row in rows
    ]


def acknowledge_alert(identifier: int):
    if not isinstance(identifier, int) or identifier <= 0:
        raise ValueError("Định danh cảnh báo không hợp lệ.")
    with transaction() as connection:
        connection.execute("UPDATE Alerts SET acknowledged=1 WHERE id=?", (identifier,))


# ------------------------------------------------------------------ lịch sử hiện diện
def get_presence(mac: str, since: datetime) -> list[tuple[datetime, bool]]:
    """Lấy lịch sử online/offline của thiết bị kể từ ``since``, cũ nhất trước."""
    with transaction() as connection:
        rows = connection.execute(
            "SELECT ts, online FROM PresenceLog WHERE mac = ? AND ts >= ? ORDER BY ts",
            (mac.lower(), _to_iso(since)),
        ).fetchall()
        previous = connection.execute("SELECT ts,online FROM PresenceLog WHERE mac=? AND ts<? ORDER BY ts DESC,id DESC LIMIT 1", (mac.lower(), _to_iso(since))).fetchone()
    return [(_from_iso(row["ts"]), bool(row["online"])) for row in ([previous] if previous else []) + list(rows)]


def add_alert_once(alert: Alert, minutes=30) -> bool:
    """Quyết định chống lặp và ghi trong cùng BEGIN IMMEDIATE, kể cả nhiều process."""
    with transaction() as connection:
        row = connection.execute("SELECT level,ts FROM Alerts WHERE device_mac IS ? AND kind=? AND ts>=? ORDER BY ts DESC,id DESC LIMIT 1",
                                 (alert.device_mac, alert.kind, _to_iso(alert.ts - timedelta(minutes=minutes)))).fetchone()
        rank = {"info": 0, "warning": 1, "danger": 2}
        if row and rank[alert.level] <= rank[row["level"]]:
            return False
        # Ngân sách tổng thể; giữ ưu tiên cho sự kiện nguy hiểm.
        count = connection.execute("SELECT count(*) FROM Alerts WHERE ts>=? AND level=?", (_to_iso(alert.ts-timedelta(minutes=1)), alert.level)).fetchone()[0]
        if count >= (30 if alert.level == "danger" else 10):
            return False
        add_alert(alert)
        return True


def pending_device_alert(mac, pending=None):
    with transaction() as connection:
        if pending is not None:
            connection.execute("INSERT INTO DeviceAlertState VALUES(?,?) ON CONFLICT(mac) DO UPDATE SET pending=excluded.pending", (mac.lower(), int(bool(pending))))
        row = connection.execute("SELECT pending FROM DeviceAlertState WHERE mac=?", (mac.lower(),)).fetchone()
    return bool(row and row[0])


def record_observation(ip, mac, ts, session_id=""):
    ipaddress.IPv4Address(ip)
    mac = valid_mac(mac)
    with transaction() as connection:
        connection.execute("INSERT INTO Observations(ip,mac,ts,session_id) VALUES(?,?,?,?)", (ip, mac, _to_iso(ts), session_id))


def get_observations(since, end=None, limit=1000):
    with transaction() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM Observations WHERE ts>=? AND ts<=? ORDER BY ts DESC LIMIT ?", (_to_iso(since), _to_iso(end or now()), _limit(limit)))]


def start_session(interface: dict) -> str:
    from uuid import uuid4
    identifier = uuid4().hex
    with transaction() as connection:
        # Phiên trước không kết thúc sạch chỉ được xem là đã ngừng quan sát.
        connection.execute("UPDATE Sessions SET ended=coalesce((SELECT max(ts) FROM PingLog WHERE session_id=Sessions.id),started) WHERE ended IS NULL")
        connection.execute("INSERT INTO Sessions VALUES(?,?,NULL,?)", (identifier, _to_iso(now()), json.dumps(interface, ensure_ascii=False)))
        connection.execute("INSERT INTO DiagnosisLog(ts,verdict,text,session_id) VALUES(?,?,?,?)", (_to_iso(now()), "unknown", "Bắt đầu phiên mới; chưa đủ dữ liệu chẩn đoán.", identifier))
    return identifier


def end_session(identifier):
    with transaction() as connection:
        connection.execute("UPDATE Sessions SET ended=? WHERE id=?", (_to_iso(now()), identifier))


def add_diagnosis(diagnosis, session_id=""):
    with transaction() as connection:
        connection.execute("INSERT INTO DiagnosisLog(ts,verdict,text,session_id) VALUES(?,?,?,?)", (_to_iso(diagnosis.ts), diagnosis.verdict, diagnosis.text, session_id))


def get_diagnoses(start, end, *, connection=None):
    with (nullcontext(connection) if connection else transaction()) as connection:
        rows = list(connection.execute("SELECT * FROM DiagnosisLog WHERE ts>=? AND ts<=? ORDER BY ts LIMIT 5000", (_to_iso(start), _to_iso(end))))
        previous = connection.execute("SELECT d.* FROM DiagnosisLog d JOIN Sessions s ON s.id=d.session_id WHERE d.ts<? AND s.started<=? AND coalesce(s.ended,(SELECT max(ts) FROM PingLog WHERE session_id=s.id),s.started)>=? ORDER BY d.ts DESC LIMIT 1", (_to_iso(start), _to_iso(start), _to_iso(start))).fetchone()
        return [Diagnosis(row["verdict"], row["text"], _from_iso(row["ts"])) for row in ([previous] if previous else []) + rows]


def add_route(hops, session_id=""):
    from dataclasses import asdict
    with transaction() as connection:
        connection.execute("INSERT INTO RouteLog(ts,hops,session_id) VALUES(?,?,?)", (_to_iso(now()), json.dumps([asdict(h) for h in hops]), session_id))


def get_routes(start, end, *, connection=None):
    with (nullcontext(connection) if connection else transaction()) as connection:
        return [{"ts": _from_iso(row["ts"]), "hops": [Hop(**h) for h in json.loads(row["hops"])]} for row in connection.execute("SELECT * FROM RouteLog WHERE ts>=? AND ts<=? ORDER BY ts LIMIT 100", (_to_iso(start), _to_iso(end)))]


def get_sessions(start, end, *, connection=None):
    with (nullcontext(connection) if connection else transaction()) as connection:
        rows = connection.execute("SELECT s.*,coalesce(s.ended,(SELECT max(ts) FROM PingLog WHERE session_id=s.id),s.started) AS observed_until FROM Sessions s WHERE started<=? AND coalesce(s.ended,(SELECT max(ts) FROM PingLog WHERE session_id=s.id),s.started)>=? ORDER BY started LIMIT 1000", (_to_iso(end), _to_iso(start)))
        return [{**dict(row), "ended": row["ended"] or row["observed_until"],
                 "clean_end": row["ended"] is not None, "interface": json.loads(row["interface"])} for row in rows]


def purge_history(days=30):
    if not 1 <= days <= 3650:
        raise ValueError("Retention phải từ 1 đến 3650 ngày.")
    cutoff = _to_iso(now()-timedelta(days=days))
    with transaction() as connection:
        for table in ("PingLog", "Alerts", "PresenceLog", "Observations", "DiagnosisLog", "RouteLog"):
            # Giữ trạng thái biên của hiện diện/chẩn đoán, không suy diễn xuyên phiên.
            keep = " AND id NOT IN (SELECT max(id) FROM PresenceLog GROUP BY mac)" if table == "PresenceLog" else " AND id<>(SELECT max(id) FROM DiagnosisLog)" if table == "DiagnosisLog" else ""
            connection.execute(f"DELETE FROM {table} WHERE ts<?{keep}", (cutoff,))
        connection.execute("DELETE FROM Devices WHERE online=0 AND trusted=0 AND name='' AND note='' AND last_seen<?", (cutoff,))
        connection.execute("DELETE FROM DeviceIdentity WHERE mac NOT IN (SELECT mac FROM Devices)")
        connection.execute("DELETE FROM DeviceAlertState WHERE mac NOT IN (SELECT mac FROM Devices)")
        connection.execute("DELETE FROM Sessions WHERE ended IS NOT NULL AND ended<?", (cutoff,))


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
