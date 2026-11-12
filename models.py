"""Các dataclass dùng chung giữa lõi (core/), dịch vụ (services/), CSDL (db/) và giao diện.

Quy ước chung:
- MAC luôn viết thường, dạng ``aa:bb:cc:dd:ee:ff``.
- Thời gian dùng **giờ Đông Dương GMT+7** cố định, dạng naive (không offset) để lưu
  ISO 8601 thống nhất và so sánh được bằng chuỗi.
- Chỉ chứa dữ liệu, không chứa logic mạng và không import Qt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

# Múi giờ Việt Nam (GMT+7), cố định để dữ liệu không phụ thuộc cấu hình máy.
TZ_VIETNAM = timezone(timedelta(hours=7))


def now() -> datetime:
    """Trả về thời gian hiện tại theo GMT+7, dạng naive (không kèm offset)."""
    return datetime.now(TZ_VIETNAM).replace(tzinfo=None)


def local_time(value: datetime) -> datetime:
    """API nhận aware datetime hoặc giờ Việt Nam naive; lưu thống nhất GMT+7."""
    if not isinstance(value, datetime):
        raise ValueError("Thời gian phải là datetime.")
    return value.astimezone(TZ_VIETNAM).replace(tzinfo=None) if value.tzinfo else value


@dataclass
class Device:
    """Một thiết bị nhìn thấy trong mạng LAN."""

    ip: str
    mac: str
    vendor: str = ""
    name: str = ""
    note: str = ""
    trusted: bool = False
    online: bool = False
    randomized_mac: bool = False
    is_self: bool = False
    first_seen: datetime = field(default_factory=now)
    last_seen: datetime = field(default_factory=now)
    hostname: str = ""
    discovered_name: str = ""
    manufacturer: str = ""
    model: str = ""
    services: tuple[str, ...] = ()
    device_type: str = "unknown"
    identity_confidence: str = "unknown"
    identity_evidence: str = ""
    type_override: str = ""
    identity_seen: datetime | None = None


@dataclass
class DeviceHints:
    """Thông tin thiết bị tự công bố trong LAN; không phải dữ liệu xác thực."""

    hostname: str = ""
    name: str = ""
    manufacturer: str = ""
    model: str = ""
    services: set[str] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class PingResult:
    """Một lần đo ping tới một mốc.

    ``target`` nhận một trong ba giá trị: ``"router"``, ``"isp"``, ``"external"``.
    ``rtt_ms = None`` nghĩa là mất gói (không có phản hồi).
    """

    target: str
    rtt_ms: float | None
    loss_pct: float
    ts: datetime = field(default_factory=now)
    address: str = ""
    session_id: str = ""
    status: str = "ok"


@dataclass
class Alert:
    """Một cảnh báo hiển thị cho người dùng.

    ``level`` nhận ``"info"``, ``"warning"`` hoặc ``"danger"``.
    ``device_mac`` là ``None`` nếu cảnh báo không gắn với thiết bị nào.
    """

    level: str
    message: str
    device_mac: str | None = None
    ts: datetime = field(default_factory=now)
    kind: str = "general"
    id: int | None = None
    acknowledged: bool = False
    network_id: str = ""


@dataclass(frozen=True)
class Diagnosis:
    """Kết luận chẩn đoán mạng.

    ``verdict`` nhận ``"ok"``, ``"home_issue"``, ``"isp_issue"``, ``"internet_issue"``
    hoặc ``"unknown"``. ``text`` là câu giải thích tiếng Việt cho người dùng.
    """

    verdict: str
    text: str
    ts: datetime = field(default_factory=now)


@dataclass(frozen=True)
class Hop:
    """Một chặng trên đường đi của traceroute."""

    ttl: int
    ip: str | None = None
    rtt_ms: float | None = None
    flagged: bool = False
