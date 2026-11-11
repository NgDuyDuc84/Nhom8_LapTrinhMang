"""Bổ sung tên/loại thiết bị ở nền, chỉ giữ yêu cầu quét mới nhất."""

from __future__ import annotations

import threading
import time
from typing import Callable

from core.arp_scanner import ScanEntry
from core.device_discovery import discover_device_hints
from core.interfaces import NetInterface
from db import repository
from extras.device_identity import identify_device
from models import Device


class DeviceIdentification:
    CACHE_SECONDS = 300

    def __init__(self, on_device: Callable[[Device], None] | None = None, discoverer=None,
                 on_complete: Callable[[], None] | None = None):
        self._on_device = on_device or (lambda device: None)
        self._on_complete = on_complete or (lambda: None)
        self._discoverer = discoverer or discover_device_hints
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._pending = None
        self._generation = 0
        self._last_fingerprint = None
        self._last_discovered = 0.0
        self.last_error: str | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="netguard-identification", daemon=True)
        self._thread.start()

    def request(self, iface: NetInterface, entries: list[ScanEntry], force: bool = False) -> None:
        fingerprint = (
            iface.index, iface.ip, iface.netmask, iface.gateway,
            frozenset((item.mac.lower(), item.ip) for item in entries),
        )
        with self._lock:
            if self._stop.is_set():
                return
            self._generation += 1
            self._pending = (self._generation, iface, tuple(entries), force, fingerprint)
            self._wake.set()

    def stop(self) -> None:
        """Đợi I/O có timeout kết thúc trước khi backend đóng CSDL."""
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join()
        self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            self._wake.wait()
            with self._lock:
                job = self._pending
                self._pending = None
                self._wake.clear()
            if self._stop.is_set():
                break
            if job is None:
                continue
            generation, iface, entries, force, fingerprint = job
            if not force and fingerprint == self._last_fingerprint and time.monotonic() - self._last_discovered < self.CACHE_SECONDS:
                continue
            try:
                hints = self._discoverer(iface, {item.ip for item in entries if not item.is_self}, self._stop)
                changed = False
                for entry in entries:
                    with self._lock:
                        if generation != self._generation or self._stop.is_set():
                            break
                        device = repository.get_device(entry.mac)
                        if device is None or device.ip != entry.ip or entry.ip not in hints:
                            continue
                        identified = identify_device(device, iface.gateway, hints[entry.ip])
                        if not repository.save_identity(identified):
                            continue
                        stored = repository.get_device(entry.mac)
                    if stored is not None:
                        changed = True
                        self._on_device(stored)
                self._last_fingerprint = fingerprint
                self._last_discovered = time.monotonic()
                self.last_error = None
                if changed and generation == self._generation and not self._stop.is_set():
                    self._on_complete()
            except Exception as exc:
                # Nhận diện chỉ bổ sung metadata, lỗi không làm hỏng kết quả ARP.
                self.last_error = str(exc)
