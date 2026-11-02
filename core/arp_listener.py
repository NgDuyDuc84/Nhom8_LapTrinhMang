"""Nghe thụ động gratuitous ARP và ARP Reply trên card LAN."""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass
from datetime import datetime
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
    ) -> None:
        self._on_observation = on_observation
        self._iface = iface
        self._sniffer = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Bắt đầu nghe ARP trên card đã chọn."""
        from scapy.all import AsyncSniffer, conf

        with self._lock:
            if self._sniffer is not None and self._sniffer.running:
                return
            iface = self._iface or get_active_interface()
            scapy_iface = next(
                (
                    item
                    for item in conf.ifaces.values()
                    if int(getattr(item, "index", 0) or 0) == iface.index
                ),
                None,
            )
            if scapy_iface is None:
                raise RuntimeError(f"Scapy/Npcap không thấy card '{iface.name}'.")
            self._sniffer = AsyncSniffer(
                iface=scapy_iface,
                filter="arp",
                prn=self._handle_packet,
                store=False,
            )
            try:
                self._sniffer.start()
            except Exception as exc:
                self._sniffer = None
                message = str(exc).lower()
                if "permission" in message or "access is denied" in message or "winerror 5" in message:
                    raise RuntimeError("Chưa chạy bằng quyền Administrator để nghe ARP.") from exc
                if "wpcap" in message or "npcap" in message:
                    raise RuntimeError("Chưa cài Npcap hoặc Npcap chưa chạy.") from exc
                raise RuntimeError(f"Không mở được bộ nghe ARP: {exc}") from exc

    def stop(self) -> None:
        """Dừng bộ nghe và chờ luồng Scapy đóng lại."""
        with self._lock:
            sniffer = self._sniffer
            self._sniffer = None
        if sniffer is not None:
            try:
                if sniffer.running:
                    sniffer.stop(join=True)
            except Exception:
                pass

    def is_running(self) -> bool:
        """True nếu Scapy đang nghe ARP."""
        return bool(self._sniffer is not None and self._sniffer.running)

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
            mac = str(arp.hwsrc).lower()
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
