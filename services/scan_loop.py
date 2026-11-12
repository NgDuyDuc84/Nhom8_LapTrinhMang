"""Vòng quét định kỳ: quét ARP, cập nhật CSDL, cảnh báo thiết bị lạ.

Mỗi chu kỳ ``SCAN_INTERVAL_SEC`` giây:
1. Quét ARP subnet của card đang dùng.
2. Tra hãng ngoại tuyến và nhận diện vai trò; hẹn bổ sung tên/dịch vụ ở nền.
3. Cập nhật CSDL, đánh dấu online; thiết bị vắng mặt ``OFFLINE_AFTER_MISSES``
   lần liên tiếp mới bị coi là offline.
4. Phát sự kiện ra ngoài bằng callback: ``on_device(device, event)`` với ``event``
   là ``"new"`` / ``"online"`` / ``"offline"``, và ``on_alert(alert)``.

Vòng lặp **không chết** khi một lần quét lỗi: ghi log rồi thử lại ở chu kỳ sau.
Không import Qt.
"""

from __future__ import annotations

import sys
import logging
import ipaddress
from dataclasses import asdict
from contextlib import nullcontext
from core.network_context import connection_key, network_id, network_scope
from db.database import transaction
import threading
import time
from typing import Callable

from config import OFFLINE_AFTER_MISSES, SCAN_INTERVAL_SEC, MAX_KNOWN_DEVICES, SETTINGS
from core.arp_scanner import ScanEntry, scan_subnet
from core.interfaces import NetInterface, get_active_interface
from db import repository
from extras import mac_random
from extras.device_identity import identify_device
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


def _is_randomized(mac: str) -> bool:
    """MAC quản lý cục bộ là dấu hiệu địa chỉ riêng tư, không phải xác thực."""
    return bool(mac_random.is_randomized(mac))


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
        on_refresh: Callable[[NetInterface | None, list[ScanEntry] | None, str | None], None] | None = None,
        on_identify: Callable[[NetInterface, list[ScanEntry], bool], None] | None = None,
        scoped: bool = False, generation_provider=None, commit_lock=None, session_provider=None, on_status=None,
    ) -> None:
        self._on_device = on_device or (lambda device, event: None)
        self._on_alert = on_alert or (lambda alert: None)
        self._interval = max(1.0, float(interval))
        self._iface = iface
        self._preferred_iface = iface
        self._resolve_interface = interface_resolver or (lambda: get_active_interface(self._preferred_iface))
        self._on_interface = on_interface or (lambda chosen: None)
        self._on_scan = on_scan or (lambda entries: None)
        self._on_refresh = on_refresh or (lambda iface, entries, error: None)
        self._on_identify = on_identify or (lambda iface, entries, force: None)
        self._network_key: tuple | None = None
        self._scanner = scanner or (lambda chosen: scan_subnet(chosen, stop_event=self._stop_event))
        self._scoped = scoped
        self._owns_session = scoped and session_provider is None
        self._owned_session = ""
        self._storage_network = "legacy"
        self._generation = generation_provider or (lambda: 0)
        self._commit_lock = commit_lock or threading.RLock()
        self._session_provider = session_provider or (lambda: self._owned_session)
        self._on_status = on_status or (lambda status: None)
        self._misses: dict[str, int] = {}
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._refresh_lock = threading.Lock()
        self._refresh_requested = False
        self._thread: threading.Thread | None = None
        self.last_error: str | None = None

    # ------------------------------------------------------------------ vòng đời
    def start(self) -> None:
        """Bắt đầu luồng quét (gọi nhiều lần vẫn an toàn)."""
        if self.is_running():
            return
        self._network_key = None
        self._misses.clear()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="netguard-scan", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 15.0) -> None:
        """Dừng luồng quét và chờ luồng kết thúc (tối đa ``timeout`` giây)."""
        self._stop_event.set()
        self._wake_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout)
            if thread.is_alive():
                raise RuntimeError("Luồng quét chưa dừng; chưa thể đóng CSDL hoặc khởi động lại.")
        self._thread = None
        if self._owns_session and self._owned_session:
            with network_scope(self._storage_network):
                repository.end_session(self._owned_session)
            self._owned_session = ""

    def is_running(self) -> bool:
        """True nếu luồng quét đang chạy."""
        return self._thread is not None and self._thread.is_alive()

    def request_refresh(self) -> None:
        """Hẹn quét ngay trên cùng worker; nhiều yêu cầu đang chờ được gộp lại."""
        with self._refresh_lock:
            if not self.is_running() or self._stop_event.is_set():
                raise RuntimeError("Dịch vụ quét mạng chưa chạy hoặc đang dừng.")
            self._refresh_requested = True
            self._wake_event.set()

    def _run(self) -> None:
        """Thân luồng: quét lặp lại, lỗi thì ghi log và thử lại chu kỳ sau."""
        while not self._stop_event.is_set():
            with self._refresh_lock:
                refresh = self._refresh_requested
                self._refresh_requested = False
                self._wake_event.clear()
            if self._stop_event.is_set():
                break
            started = time.perf_counter()
            entries = None
            try:
                entries = self.scan_once(reselect=refresh)
                self.last_error = None
                self._safe(self._on_status, {"service": "scan", "running": True, "error": ""})
            except Exception as exc:  # mọi lỗi mạng/CSDL đều không được làm chết vòng lặp
                self.last_error = str(exc)
                logging.getLogger(__name__).exception("Lượt quét thất bại")
                self._safe(self._on_status, {"service": "scan", "running": False, "error": str(exc)})
                _log(f"[quét lỗi] {exc} — sẽ thử lại ở chu kỳ sau")
            if refresh:
                try:
                    self._on_refresh(self._iface, entries, self.last_error)
                except Exception as exc:
                    _log(f"[kết quả làm mới quét mạng] {exc}")
            waited = time.perf_counter() - started
            remaining = self._interval - waited
            if remaining > 0:
                self._wake_event.wait(remaining)

    # ------------------------------------------------------------------ một lần quét
    def scan_once(self, *, reselect: bool = False) -> list[ScanEntry]:
        """Quét một lần và cập nhật CSDL; trả về các ``ScanEntry`` vừa thấy."""
        if reselect:
            self._preferred_iface = None
        try:
            iface = self._resolve_interface()
        except (RuntimeError, OSError, ValueError):
            self._update_interface(None, force=reselect)
            raise
        if self._preferred_iface is None:
            self._preferred_iface = iface
        self._update_interface(iface, force=reselect)
        generation = self._generation()
        entries = self._scanner(iface)
        if self._stop_event.is_set():
            raise RuntimeError("Đã hủy lượt quét trước khi ghi dữ liệu.")
        # Đọc lại card sau I/O. Không nhận dữ liệu cũ sau DHCP/đổi mạng.
        current = self._resolve_interface()
        if connection_key(current) != connection_key(iface):
            raise RuntimeError("Kết nối đã thay đổi trong lúc quét; bỏ kết quả cũ.")
        context = network_scope(network_id(iface)) if self._scoped else nullcontext()
        with context, self._commit_lock:
            if generation != self._generation() or self._stop_event.is_set():
                raise RuntimeError("Phiên kết nối đã thay đổi; bỏ kết quả quét cũ.")
            return self._save_scan(iface, entries, reselect)

    def _save_scan(self, iface, entries, reselect):
        moment = now()
        seen = set()
        events, alerts = [], []
        misses_before = dict(self._misses)
        try:
            with transaction() as connection:
                known_count = connection.execute("SELECT count(*) FROM Devices").fetchone()[0]
                connection.execute("UPDATE Devices SET is_self=0 WHERE mac<>? AND is_self=1", (iface.mac.lower(),))
                # Giữ mọi quan sát IP/MAC, kể cả nhiều MAC cùng nhận một IP.
                for entry in entries:
                    repository.record_observation(entry.ip, entry.mac, moment, self._session_provider())
                grouped = {}
                for entry in entries:
                    grouped.setdefault(entry.mac.lower(), []).append(entry)
                for mac, claims in grouped.items():
                    existing = repository.get_device(mac)
                    # Giữ IP chính ổn định nếu một MAC có nhiều IP trong lượt này.
                    entry = next((e for e in claims if existing and e.ip == existing.ip), claims[0])
                    is_new = existing is None
                    if is_new:
                        known_count += 1
                        if known_count > MAX_KNOWN_DEVICES:
                            raise RuntimeError("Đã đạt ngân sách 10.000 hồ sơ thiết bị của mạng này; bỏ lượt quét và giữ dữ liệu hiện tại. Sao lưu, giảm dải quét hoặc lập hồ sơ mới để kiểm tra lưu lượng bất thường.")
                    was_offline = existing is not None and not existing.online
                    if was_offline:
                        repository.pending_device_alert(mac, True)
                    device = existing or Device(ip=entry.ip, mac=mac, first_seen=moment, last_seen=moment)
                    device.ip, device.mac = entry.ip, mac
                    device.randomized_mac = _is_randomized(mac)
                    device.is_self = entry.is_self
                    device.last_seen = moment
                    device = identify_device(device, iface.gateway)
                    repository.upsert_device(device)
                    repository.save_identity(device)
                    repository.set_online(mac, True, ts=moment)
                    self._misses[mac] = 0
                    seen.add(mac)
                    stored = repository.get_device(mac)
                    if is_new or was_offline:
                        events.append((stored, "new" if is_new else "online"))
                    # Thử lại sau lỗi callback và cảnh báo cả thiết bị cũ chưa tin cậy.
                    # add_alert_once() chịu trách nhiệm chống lặp theo loại + MAC.
                    if not baseline.is_first_run() and not stored.trusted and repository.pending_device_alert(mac):
                        alert = alerts_service.raise_stranger(stored)
                        if alert:
                            alerts.append(alert)
                            repository.pending_device_alert(mac, False)
                for device in repository.list_devices():
                    if device.mac in seen:
                        continue
                    probe_range = ipaddress.ip_network(SETTINGS["scan_cidr"] or f"{iface.ip}/{iface.netmask}", strict=False)
                    if ipaddress.ip_address(device.ip) not in probe_range:
                        continue  # Không suy ra vắng mặt cho địa chỉ không được quét.
                    misses = self._misses.get(device.mac, 0) + 1
                    self._misses[device.mac] = misses
                    if misses >= OFFLINE_AFTER_MISSES and device.online:
                        repository.set_online(device.mac, False, ts=moment)
                        events.append((repository.get_device(device.mac), "offline"))
        except Exception:
            self._misses = misses_before
            raise
        for device, event in events:
            self._safe(self._on_device, device, event)
        for alert in alerts:
            self._safe(self._on_alert, alert)
        self._safe(self._on_scan, entries)
        self._safe(self._on_identify, iface, entries, reselect)
        return entries

    @staticmethod
    def _safe(callback, *args):
        try:
            callback(*args)
        except Exception:
            logging.getLogger(__name__).exception("Callback quét mạng thất bại")

    def _update_interface(self, iface: NetInterface | None, *, force: bool = False) -> None:
        key = connection_key(iface)
        self._iface = iface
        # Listener và bộ đếm vắng mặt phải theo cấu hình kết nối mới.
        if force or key != self._network_key:
            if self._owns_session and key != self._network_key:
                with network_scope(self._storage_network):
                    if self._owned_session:
                        repository.end_session(self._owned_session)
                self._owned_session = ""
                if iface is not None:
                    self._storage_network = network_id(iface)
                    with network_scope(self._storage_network):
                        self._owned_session = repository.start_session(asdict(iface))
            if key != self._network_key:
                self._misses.clear()
            self._on_interface(iface)
            self._network_key = key
