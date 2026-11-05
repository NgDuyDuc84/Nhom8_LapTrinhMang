"""Vòng quét định kỳ: quét ARP, cập nhật CSDL, cảnh báo thiết bị lạ.

Mỗi chu kỳ ``SCAN_INTERVAL_SEC`` giây:
1. Quét ARP subnet của card đang dùng.
2. Tra hãng (``extras.oui``) và nhận diện MAC ngẫu nhiên (``extras.mac_random``),
   tạm dùng ``"Unknown"`` / ``False`` khi C chưa làm xong hai module đó.
3. Cập nhật CSDL, đánh dấu online; thiết bị vắng mặt ``OFFLINE_AFTER_MISSES``
   lần liên tiếp mới bị coi là offline.
4. Phát sự kiện ra ngoài bằng callback: ``on_device(device, event)`` với ``event``
   là ``"new"`` / ``"online"`` / ``"offline"``, và ``on_alert(alert)``.

Vòng lặp **không chết** khi một lần quét lỗi: ghi log rồi thử lại ở chu kỳ sau.
Không import Qt.
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Callable

from config import OFFLINE_AFTER_MISSES, SCAN_INTERVAL_SEC
from core.arp_scanner import ScanEntry, scan_subnet
from core.interfaces import NetInterface, get_active_interface
from db import repository
from extras import mac_random, oui
from models import Alert, Device, now
from services import alerts as alerts_service
from services import baseline

DeviceCallback = Callable[[Device, str], None]
AlertCallback = Callable[[Alert], None]

__all__ = ["ScanLoop"]


def _log(message: str) -> None:
    """In thông báo lỗi ra stderr, bỏ qua lỗi bảng mã console (khi chạy không có console)."""
    try:
        print(message, file=sys.stderr)
    except (UnicodeEncodeError, OSError):
        pass


def _lookup_vendor(mac: str) -> str:
    """Tra hãng sản xuất; ``extras.oui`` chưa xong thì tạm trả ``"Unknown"``."""
    try:
        return oui.lookup(mac) or "Unknown"
    except NotImplementedError:
        return "Unknown"


def _is_randomized(mac: str) -> bool:
    """Kiểm tra MAC ngẫu nhiên; ``extras.mac_random`` chưa xong thì tạm trả ``False``."""
    try:
        return bool(mac_random.is_randomized(mac))
    except NotImplementedError:
        return False


class ScanLoop:
    """Luồng nền quét ARP định kỳ và ghi kết quả vào CSDL."""

    def __init__(
        self,
        on_device: DeviceCallback | None = None,
        on_alert: AlertCallback | None = None,
        interval: float = SCAN_INTERVAL_SEC,
        iface: NetInterface | None = None,
        scanner: Callable[[NetInterface], list[ScanEntry]] | None = None,
        interface_resolver: Callable[[], NetInterface] | None = None,
        on_interface: Callable[[NetInterface | None], None] | None = None,
        on_scan: Callable[[list[ScanEntry]], None] | None = None,
    ) -> None:
        self._on_device = on_device or (lambda device, event: None)
        self._on_alert = on_alert or (lambda alert: None)
        self._interval = max(1.0, float(interval))
        self._iface = iface
        self._preferred_iface = iface
        self._resolve_interface = interface_resolver or (lambda: get_active_interface(self._preferred_iface))
        self._on_interface = on_interface or (lambda chosen: None)
        self._on_scan = on_scan or (lambda entries: None)
        self._network_key: tuple | None = None
        self._scanner = scanner or (lambda chosen: scan_subnet(chosen))
        self._misses: dict[str, int] = {}
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error: str | None = None

    # ------------------------------------------------------------------ vòng đời
    def start(self) -> None:
        """Bắt đầu luồng quét (gọi nhiều lần vẫn an toàn)."""
        if self.is_running():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="netguard-scan", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 15.0) -> None:
        """Dừng luồng quét và chờ luồng kết thúc (tối đa ``timeout`` giây)."""
        self._stop_event.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout)

    def is_running(self) -> bool:
        """True nếu luồng quét đang chạy."""
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        """Thân luồng: quét lặp lại, lỗi thì ghi log và thử lại chu kỳ sau."""
        while not self._stop_event.is_set():
            started = time.perf_counter()
            try:
                self.scan_once()
                self.last_error = None
            except Exception as exc:  # mọi lỗi mạng/CSDL đều không được làm chết vòng lặp
                self.last_error = str(exc)
                _log(f"[quét lỗi] {exc} — sẽ thử lại ở chu kỳ sau")
            waited = time.perf_counter() - started
            remaining = self._interval - waited
            if remaining > 0:
                self._stop_event.wait(remaining)

    # ------------------------------------------------------------------ một lần quét
    def scan_once(self) -> list[ScanEntry]:
        """Quét một lần và cập nhật CSDL; trả về các ``ScanEntry`` vừa thấy."""
        try:
            iface = self._resolve_interface()
        except (RuntimeError, OSError, ValueError):
            self._update_interface(None)
            raise
        if self._preferred_iface is None:
            self._preferred_iface = iface
        self._update_interface(iface)
        entries = self._scanner(iface)
        moment = now()
        seen: set[str] = set()

        for entry in entries:
            mac = entry.mac.lower()
            existing = repository.get_device(mac)
            is_new = existing is None
            was_offline = existing is not None and not existing.online

            device = existing or Device(ip=entry.ip, mac=mac, first_seen=moment, last_seen=moment)
            device.ip = entry.ip
            device.mac = mac
            if not device.vendor or device.vendor == "Unknown":
                device.vendor = _lookup_vendor(mac)
            if not device.randomized_mac:
                device.randomized_mac = _is_randomized(mac)
            device.is_self = entry.is_self
            device.last_seen = moment

            # Không tự đặt device.online = True ở đây: để set_online() phát hiện
            # thay đổi và ghi PresenceLog (upsert sẽ ghi đè cờ online trước khi nó chạy).
            repository.upsert_device(device)
            repository.set_online(mac, True, ts=moment)
            self._misses[mac] = 0
            seen.add(mac)

            stored = repository.get_device(mac)
            if stored is None:  # phòng thủ: không xảy ra trong điều kiện bình thường
                continue
            if is_new:
                self._on_device(stored, "new")
            elif was_offline:
                self._on_device(stored, "online")

            # Chỉ cảnh báo thiết bị MỚI xuất hiện sau khi đã chốt đường cơ sở.
            if is_new and not baseline.is_first_run() and not stored.trusted:
                alert = alerts_service.raise_stranger(stored)
                if alert is not None:
                    self._on_alert(alert)

        self._mark_offline(seen, moment)
        self._on_scan(entries)
        return entries

    def _update_interface(self, iface: NetInterface | None) -> None:
        key = (iface.index, iface.ip, iface.netmask, iface.gateway) if iface else None
        self._iface = iface
        # Listener và bộ đếm vắng mặt phải theo cấu hình kết nối mới.
        if key != self._network_key:
            self._misses.clear()
            self._on_interface(iface)
            self._network_key = key

    def _mark_offline(self, seen: set[str], moment) -> None:
        """Đếm số lần vắng mặt; đủ ``OFFLINE_AFTER_MISSES`` thì đánh dấu offline."""
        for device in repository.list_devices():
            if device.mac in seen:
                continue
            misses = self._misses.get(device.mac, 0) + 1
            self._misses[device.mac] = misses
            if misses < OFFLINE_AFTER_MISSES or not device.online:
                continue
            repository.set_online(device.mac, False, ts=moment)
            stored = repository.get_device(device.mac)
            if stored is not None:
                self._on_device(stored, "offline")
