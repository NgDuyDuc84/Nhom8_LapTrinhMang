"""Giám sát IP/MAC định kỳ bằng Windows; không bắt gói và không cần Npcap."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import ipaddress
import logging
import threading

from core.interfaces import NetInterface, get_active_interface
from core.windows_network import neighbors, resolve_ipv4, valid_mac
from models import now


@dataclass(frozen=True)
class ArpObservation:
    ip: str
    mac: str
    operation: int
    gratuitous: bool
    ts: datetime
    source: str = "packet"


class ArpListener:
    """Đọc thay đổi bảng ARP và chủ động kiểm tra gateway mỗi hai giây.

    Cache chỉ là thông tin IP/MAC; không dùng để chứng minh thiết bị online.
    Luồng có retry và dừng có thời hạn như các worker khác.
    """
    INTERVAL_SEC = 2.0

    def __new__(cls, *args, **kwargs):
        from core import network_mode
        if network_mode.PACKET_CAPTURE:
            from core.pcap_listener import ArpListener as CaptureListener
            return CaptureListener(*args, **kwargs)
        return super().__new__(cls)

    def __init__(self, on_observation, iface: NetInterface | None = None, on_status=None):
        self._on_observation = on_observation
        self._iface = iface
        self._on_status = on_status or (lambda status: None)
        self._stop_event = threading.Event()
        self._thread = None
        self._running = False
        self._previous = {}

    def _status(self, running, error=""):
        self._running = running
        try:
            self._on_status({"service": "arp_listener", "running": running,
                             "error": error, "mode": "windows_periodic", "passive_capture": False})
        except Exception:
            logging.getLogger(__name__).exception("Không giao được trạng thái giám sát ARP")

    def _emit(self, ip, mac, source):
        if self._stop_event.is_set():
            return
        iface = self._iface
        try:
            address = ipaddress.IPv4Address(ip)
            network = ipaddress.IPv4Network(f"{iface.ip}/{iface.netmask}", strict=False)
            if (address not in network or address.is_multicast or address.is_unspecified
                    or address.is_loopback or not valid_mac(mac)
                    or (network.prefixlen < 31 and address in (network.network_address, network.broadcast_address))):
                return
        except (ValueError, AttributeError):
            return
        self._on_observation(ArpObservation(ip, mac.lower(), 2, False, now(), source))

    def _poll(self):
        iface = self._iface
        snapshot = dict(neighbors(iface.index))
        for ip, mac in snapshot.items():
            if ip != iface.gateway and self._previous.get(ip) != mac:
                self._emit(ip, mac, "neighbor_cache")
        self._previous = snapshot
        if iface.gateway and not self._stop_event.is_set():
            mac = resolve_ipv4(iface.gateway, iface.ip, iface.index)
            if mac:
                self._emit(iface.gateway, mac, "active_probe")

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self._poll()
                if not self._stop_event.is_set():
                    self._status(True)
            except Exception as exc:
                self._status(False, f"Không kiểm tra được ARP Windows: {exc}")
            self._stop_event.wait(self.INTERVAL_SEC)
        self._running = False

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._iface = self._iface or get_active_interface()
        self._stop_event.clear()
        self._previous = {}
        self._thread = threading.Thread(target=self._run, name="netguard-arp-windows", daemon=True)
        self._thread.start()

    def stop(self, timeout=10.0):
        self._stop_event.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout)
            if self._thread.is_alive():
                raise RuntimeError("Giám sát ARP Windows chưa dừng; giữ CSDL mở.")
        self._running = False

    def is_running(self):
        return bool(self._thread and self._thread.is_alive() and self._running)
