"""Nghe thụ động gratuitous ARP và ARP Reply trên card LAN."""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from core.arp_validation import valid_arp_source
from core.arp_scanner import _wait_capture_ready, _stop_capture
from typing import Callable

from core.interfaces import NetInterface, get_active_interface
from models import now

ArpCallback = Callable[["ArpObservation"], None]

__all__ = ["ArpObservation", "ArpListener"]


@dataclass(frozen=True)
class ArpObservation:
    """Một thông báo ARP đáng quan tâm, MAC chuẩn hóa chữ thường."""

    ip: str
    mac: str
    operation: int
    gratuitous: bool
    ts: datetime


class ArpListener:
    """Luồng nghe ARP chỉ nhận gói, không phát yêu cầu hoặc thay đổi mạng."""

    def __init__(
        self,
        on_observation: ArpCallback,
        iface: NetInterface | None = None,
        on_status=None,
    ) -> None:
        self._on_observation = on_observation
        self._iface = iface
        self._sniffer = None
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._watchdog = None
        self._on_status = on_status or (lambda status: None)
        self._ready = threading.Event()

    def _status(self, running, error=""):
        try:
            self._on_status({"service": "arp_listener", "running": running, "error": error})
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Không giao được trạng thái ARP")

    def _open(self):
        from scapy.all import AsyncSniffer
        from core.arp_scanner import _scapy_iface
        iface = self._iface or get_active_interface()
        self._iface = iface
        ready, closing = threading.Event(), threading.Event()
        self._ready = ready

        def started():
            ready.set()
            if closing.is_set() or self._stop_event.is_set():
                sniffer.stop(join=False)

        sniffer = AsyncSniffer(iface=_scapy_iface(iface), filter="arp", prn=self._handle_packet,
                               store=False, started_callback=started)
        self._sniffer = sniffer
        try:
            sniffer.start()
            _wait_capture_ready(sniffer, ready)
        except Exception as exc:
            closing.set()
            _stop_capture(sniffer, require_healthy=False)
            self._status(False, str(exc))
            raise RuntimeError(f"Không mở được bộ nghe ARP: {exc}") from exc
        self._status(True)

    def start(self) -> None:
        with self._lock:
            if self._watchdog and self._watchdog.is_alive():
                return
            self._stop_event.clear()
            try:
                self._open()
            finally:
                self._watchdog = threading.Thread(target=self._supervise, name="netguard-arp-health", daemon=True)
                self._watchdog.start()

    def _supervise(self):
        delay = 1.0
        while not self._stop_event.wait(0.2):
            if self.is_running():
                delay = 1.0
                continue
            sniffer = self._sniffer
            self._status(False, str(getattr(sniffer, "exception", "") or "Bộ nghe ARP đã dừng; đang thử lại."))
            if self._stop_event.wait(delay):
                break
            with self._lock:
                if self._stop_event.is_set():
                    break
                if sniffer:
                    _stop_capture(sniffer, require_healthy=False)
                    if sniffer.thread and sniffer.thread.is_alive():
                        delay = min(30, delay*2)
                        continue
                try:
                    self._open()
                except RuntimeError:
                    delay = min(30, delay*2)

    def stop(self, timeout=5.0) -> None:
        self._stop_event.set()
        thread = self._watchdog
        if thread and thread is not threading.current_thread():
            thread.join(timeout)
            if thread.is_alive():
                raise RuntimeError("Bộ giám sát ARP chưa dừng.")
        with self._lock:
            sniffer = self._sniffer
            if sniffer:
                error = _stop_capture(sniffer, require_healthy=False)
                if sniffer.thread and sniffer.thread.is_alive():
                    raise RuntimeError("Bộ bắt gói ARP chưa dừng; chưa đóng CSDL.") from error
            self._sniffer = None
            self._watchdog = None

    def is_running(self) -> bool:
        sniffer = self._sniffer
        return bool(self._ready.is_set() and sniffer and sniffer.running and sniffer.thread and sniffer.thread.is_alive()
                    and sniffer.exception is None)

    def _handle_packet(self, packet) -> None:
        try:
            from scapy.layers.l2 import ARP

            if not packet.haslayer(ARP):
                return
            arp = packet[ARP]
            operation = int(arp.op)
            source_ip = str(arp.psrc)
            target_ip = str(arp.pdst)
            gratuitous = source_ip == target_ip or source_ip == "0.0.0.0"
            if operation != 2 and not gratuitous:
                return
            source = valid_arp_source(packet, self._iface)
            if source is None:
                return
            source_ip, mac = source
            if not source_ip or source_ip == "0.0.0.0" or not mac:
                return
            self._on_observation(
                ArpObservation(
                    ip=source_ip,
                    mac=mac,
                    operation=operation,
                    gratuitous=gratuitous,
                    ts=now(),
                )
            )
        except Exception as exc:
            try:
                print(f"[ARP listener] {exc}", file=sys.stderr)
            except OSError:
                pass
