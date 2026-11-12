"""Sinh cảnh báo và chống báo lặp.

Cùng một thiết bị, cùng loại cảnh báo thì không báo lại trong
``ALERT_DEDUP_MINUTES`` phút (mặc định 30) để tránh bão cảnh báo khi thiết bị
ra/vào mạng liên tục.

Không import Qt.
"""

from __future__ import annotations

import time
import ipaddress
from datetime import timedelta
from typing import Iterable, TYPE_CHECKING

from config import ALERT_DEDUP_MINUTES
from db import repository
from models import Alert, Device, now
from extras.device_identity import device_title

if TYPE_CHECKING:
    from core.arp_listener import ArpObservation

__all__ = [
    "make_stranger_alert",
    "should_alert",
    "raise_stranger",
    "raise_anomaly",
    "ArpAnomalyDetector",
]


def make_stranger_alert(device: Device) -> Alert:
    """Tạo cảnh báo mức ``warning`` cho một thiết bị lạ.

    Nếu thiết bị có MAC ngẫu nhiên thì thêm câu giải thích để người dùng không
    hoang mang khi thấy một "thiết bị mới" trùng với điện thoại của mình.
    """
    message = f'Thiết bị chưa tin cậy "{device_title(device)}" (MAC {device.mac}) vừa xuất hiện trong mạng.'
    if device.vendor and device.vendor != "Unknown":
        message += f" Hãng: {device.vendor}."
    if device.randomized_mac:
        message += " MAC quản lý cục bộ/riêng tư; chưa đủ thông tin để xác định hãng hoặc loại thiết bị."
    return Alert(level="warning", message=message, device_mac=device.mac, kind="stranger")


def should_alert(device_mac: str | None, minutes: int = ALERT_DEDUP_MINUTES, kind: str = "stranger") -> bool:
    """True nếu thiết bị chưa có cảnh báo nào trong ``minutes`` phút gần đây."""
    last = repository.last_alert_at(device_mac, kind)
    if last is None:
        return True
    return now() - last >= timedelta(minutes=minutes)


def raise_stranger(device: Device) -> Alert | None:
    """Tạo và lưu cảnh báo thiết bị lạ; trả ``None`` nếu đang trong thời gian chống lặp."""
    alert = make_stranger_alert(device)
    return alert if repository.add_alert_once(alert, ALERT_DEDUP_MINUTES) else None


def raise_anomaly(level: str, message: str, device_mac: str | None = None, *, kind: str = "arp_anomaly") -> Alert | None:
    """Ghi cảnh báo bất thường ARP nếu chưa có cảnh báo gần đây cho thiết bị."""
    if level not in {"info", "warning", "danger"}:
        raise ValueError(f"Mức cảnh báo không hợp lệ: {level}")
    alert = Alert(level=level, message=message, device_mac=device_mac, kind=kind)
    return alert if repository.add_alert_once(alert, ALERT_DEDUP_MINUTES) else None


class ArpAnomalyDetector:
    """Phát hiện thay đổi IP/MAC, IP tranh chấp và MAC nhận nhiều IP."""

    CONFLICT_WINDOW_SEC = 30.0
    GATEWAY_CONFIRM_SEC = 5.0
    CLAIM_WINDOW_SEC = 60.0
    MULTI_IP_THRESHOLD = 3
    MAX_ENTRIES = 1024

    def __init__(self, gateway_ip: str, known_devices: Iterable[Device] = (), *, subnet: str = "") -> None:
        self._gateway_ip = gateway_ip
        self._known_owner: dict[str, str] = {}
        self._gateway_owner: str | None = None
        self._recent_claims: dict[str, dict[str, float]] = {}
        self._mac_ips: dict[str, dict[str, float]] = {}
        self._gateway_candidates: dict[str, tuple[float, int]] = {}
        self._change_candidates: dict[tuple[str, str], tuple[float, int]] = {}
        self._known_seen: dict[str, float] = {}
        self._subnet = ipaddress.ip_network(subnet, strict=False) if subnet else None
        for device in known_devices:
            self._known_owner[device.ip] = device.mac.lower()
            self._known_seen[device.ip] = time.monotonic()
        pinned = repository.get_meta("gateway_mac")
        if pinned:
            self._gateway_owner = pinned

    def observe(self, observation: "ArpObservation") -> list[Alert]:
        """Nhận một ARP Reply/announcement và trả các cảnh báo mới được lưu."""
        moment = time.monotonic()
        ip = observation.ip
        mac = observation.mac.lower()
        try:
            repository.valid_mac(mac)
            address = ipaddress.IPv4Address(ip)
            if address.is_unspecified or address.is_multicast or (self._subnet and address not in self._subnet):
                return []
        except ValueError:
            return []
        self._prune(moment)
        claims = self._recent_claims.setdefault(ip, {})
        claims = {
            owner: seen
            for owner, seen in claims.items()
            if moment - seen <= self.CONFLICT_WINDOW_SEC
        }
        prior_live_owners = {owner for owner in claims if owner != mac}
        claims[mac] = moment
        if len(claims) > 16:
            del claims[min(claims, key=claims.get)]
        self._recent_claims[ip] = claims

        mac_claims = self._mac_ips.setdefault(mac, {})
        mac_claims = {
            claimed_ip: seen
            for claimed_ip, seen in mac_claims.items()
            if moment - seen <= self.CLAIM_WINDOW_SEC
        }
        mac_claims[ip] = moment
        if len(mac_claims) > 32:
            del mac_claims[min(mac_claims, key=mac_claims.get)]
        self._mac_ips[mac] = mac_claims

        alerts: list[Alert] = []
        known_mac = self._known_owner.get(ip)
        is_gateway = bool(self._gateway_ip and ip == self._gateway_ip)
        update_owner = True

        if is_gateway and self._gateway_owner and self._gateway_owner != mac:
            first, count = self._gateway_candidates.get(mac, (moment, 0))
            if moment - first > self.GATEWAY_CONFIRM_SEC:
                first, count = moment, 0
            count += 1
            self._gateway_candidates[mac] = (first, count)
            if prior_live_owners or count >= 2:
                alert = raise_anomaly(
                    "danger",
                    f"Địa chỉ gateway {ip} đang được MAC {mac} sử dụng thay cho "
                    f"{self._gateway_owner}.",
                    mac,
                    kind="gateway_change",
                )
                if alert is not None:
                    alerts.append(alert)
        elif prior_live_owners:
            owners = ", ".join(sorted(prior_live_owners))
            level = "danger" if is_gateway else "warning"
            alert = raise_anomaly(
                level,
                f"Phát hiện tranh chấp IP {ip}: có phản hồi từ MAC {owners} và {mac} trong "
                f"{self.CONFLICT_WINDOW_SEC:.0f} giây.",
                mac,
                kind=f"ip_conflict:{ip}",
            )
            if alert is not None:
                alerts.append(alert)
        elif known_mac and known_mac != mac:
            old_device = repository.get_device(known_mac)
            old_still_active = bool(
                old_device
                and old_device.online
                and old_device.ip == ip
                and now() - old_device.last_seen <= timedelta(minutes=5)
            )
            if old_still_active:
                key = (ip, mac)
                first, count = self._change_candidates.get(key, (moment, 0))
                if moment - first > self.GATEWAY_CONFIRM_SEC:
                    first, count = moment, 0
                count += 1
                self._change_candidates[key] = (first, count)
                if count >= 2:
                    alert = raise_anomaly(
                        "warning",
                        f"IP {ip} đổi MAC từ {known_mac} sang {mac}, trong khi thiết bị cũ "
                        "vẫn được ghi nhận online.",
                        mac,
                        kind=f"owner_change:{ip}",
                    )
                    if alert is not None:
                        alerts.append(alert)
                else:
                    # Chờ thêm một ARP claim để loại bớt đổi DHCP thoáng qua.
                    update_owner = False

        if len(mac_claims) >= self.MULTI_IP_THRESHOLD:
            ips = ", ".join(sorted(mac_claims))
            alert = raise_anomaly(
                "warning",
                f"MAC {mac} đang quảng bá nhiều IP trong thời gian ngắn: {ips}.",
                mac,
                kind="multi_ip",
            )
            if alert is not None:
                alerts.append(alert)

        # DHCP có thể đổi chủ IP; chỉ cập nhật chủ đã biết sau khi kiểm tra tranh chấp.
        if update_owner and not is_gateway:
            self._known_owner[ip] = mac
            self._known_seen[ip] = moment
        return alerts

    def _prune(self, moment):
        for mapping in (self._recent_claims, self._mac_ips):
            for key in list(mapping):
                mapping[key] = {k: t for k, t in mapping[key].items() if moment-t <= self.CLAIM_WINDOW_SEC}
                if not mapping[key]:
                    del mapping[key]
            while len(mapping) >= self.MAX_ENTRIES:
                del mapping[next(iter(mapping))]
        for mapping in (self._gateway_candidates, self._change_candidates):
            for key, (stamp, _) in list(mapping.items()):
                if moment-stamp > self.GATEWAY_CONFIRM_SEC:
                    del mapping[key]
            while len(mapping) >= self.MAX_ENTRIES:
                del mapping[next(iter(mapping))]
        for ip in list(self._known_owner):
            if moment-self._known_seen.get(ip, 0) > self.CLAIM_WINDOW_SEC:
                self._known_owner.pop(ip, None)
                self._known_seen.pop(ip, None)
        while len(self._known_owner) >= self.MAX_ENTRIES:
            ip = next(iter(self._known_owner))
            self._known_owner.pop(ip, None)
            self._known_seen.pop(ip, None)
