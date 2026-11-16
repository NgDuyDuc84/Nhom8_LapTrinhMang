"""Nhận diện đang chạy phải hết hiệu lực ngay khi kết nối đổi, trước lượt ARP kế tiếp."""
from dataclasses import replace
import threading
from unittest.mock import Mock

import pytest

from backend import Backend
from core.arp_scanner import ScanEntry
from core.interfaces import NetInterface
from core.network_context import network_scope
from db import repository
from extras.device_identity import identify_device
from models import Device, DeviceHints
from services.device_identification import DeviceIdentification


@pytest.fixture
def iface():
    return NetInterface("Wi-Fi", "test", "192.168.1.9", "255.255.255.0", "192.168.1.1",
                        "00:11:22:33:44:55", False, True, 7, profile_id="network-A", adapter_id="adapter-A")


@pytest.mark.parametrize("transition", ["disconnect", "same_ip_new_network", "dhcp", "different_adapter"])
@pytest.mark.parametrize("discovery_error", [False, True], ids=["late_result", "late_error"])
def test_backend_connection_change_discards_inflight_identity_before_next_scan(monkeypatch, iface, transition, discovery_error):
    backend = Backend()
    backend._scoped = True
    backend._emit_connection(iface)
    original_storage = backend._storage_network
    entry = ScanEntry("192.168.1.20", "02:11:22:33:44:66")
    with network_scope(original_storage):
        device = identify_device(Device(entry.ip, entry.mac, name="Tên thủ công", note="Giữ lại", trusted=True),
                                 hints=DeviceHints(name="Tên quan sát đã lưu"))
        repository.upsert_device(device)
        repository.save_identity(device)
    entered, release, settled = threading.Event(), threading.Event(), threading.Event()
    published = Mock()
    cancellation = []

    def discover(chosen, addresses, stop):
        cancellation.append(stop)
        entered.set()
        assert release.wait(3)
        if discovery_error:
            raise OSError("Lỗi từ kết nối đã hết hiệu lực")
        return {entry.ip: DeviceHints(name="Kết quả đã cũ sau đổi kết nối")}

    worker = DeviceIdentification(discoverer=discover, on_complete=published)
    backend._identifier = worker
    original_wait = worker._wake.wait
    def observe_idle(timeout=None):
        if entered.is_set():
            settled.set()  # Lượt nhận diện đã xử lý xong và quay lại chờ công việc.
        return original_wait(timeout)
    monkeypatch.setattr(worker._wake, "wait", observe_idle)
    worker.start()
    try:
        with network_scope(original_storage):
            worker.request(iface, [entry])
        assert entered.wait(2)
        changed = {"disconnect": None,
                   "same_ip_new_network": replace(iface, profile_id="network-B"),
                   "dhcp": replace(iface, ip="192.168.1.10"),
                   "different_adapter": replace(iface, name="Ethernet", index=8, adapter_id="adapter-B")}[transition]
        backend._emit_connection(changed)
        assert cancellation[0].is_set()
        release.set()
        assert settled.wait(2)
        with network_scope(original_storage):
            saved = repository.get_device(entry.mac)
        assert saved.discovered_name == "Tên quan sát đã lưu"
        assert (saved.name, saved.note, saved.trusted) == ("Tên thủ công", "Giữ lại", True)
        published.assert_not_called()
        assert worker.last_error is None
    finally:
        release.set()
        backend.stop()


def test_unchanged_connection_keeps_valid_identification_running(iface):
    backend = Backend()
    backend._scoped = True
    backend._emit_connection(iface)
    storage = backend._storage_network
    entry = ScanEntry("192.168.1.20", "02:11:22:33:44:66")
    with network_scope(storage):
        repository.upsert_device(Device(entry.ip, entry.mac))
    entered, release, completed = threading.Event(), threading.Event(), threading.Event()
    def discover(chosen, addresses, cancel):
        entered.set()
        assert release.wait(3)
        assert not cancel.is_set()
        return {entry.ip: DeviceHints(name="Nhận diện hợp lệ")}
    backend._identifier = DeviceIdentification(discoverer=discover, on_complete=completed.set)
    backend._identifier.start()
    try:
        with network_scope(storage):
            backend._identifier.request(iface, [entry])
        assert entered.wait(2)
        backend._emit_connection(replace(iface))
        release.set()
        assert completed.wait(2)
        with network_scope(storage):
            assert repository.get_device(entry.mac).discovered_name == "Nhận diện hợp lệ"
    finally:
        release.set()
        backend.stop()


def test_reconnecting_same_network_bypasses_old_cache_and_survives_late_job(iface):
    backend = Backend()
    backend._scoped = True
    backend._emit_connection(iface)
    storage = backend._storage_network
    entry = ScanEntry("192.168.1.20", "02:11:22:33:44:66")
    with network_scope(storage):
        repository.upsert_device(Device(entry.ip, entry.mac, name="Tên thủ công", trusted=True))
    entered, release, completed = threading.Event(), threading.Event(), threading.Event()
    calls = []
    def discover(chosen, addresses, cancel):
        calls.append(cancel)
        if len(calls) == 1:
            return {entry.ip: DeviceHints(name="Tên trước khi mất mạng")}
        if len(calls) == 2:
            entered.set()
            assert release.wait(3)
            return {entry.ip: DeviceHints(name="Kết quả từ phiên đã hủy")}
        assert not cancel.is_set()
        return {entry.ip: DeviceHints(name="Tên sau khi kết nối lại")}
    worker = DeviceIdentification(discoverer=discover, on_complete=completed.set)
    backend._identifier = worker
    worker.start()
    try:
        with network_scope(storage):
            worker.request(iface, [entry])
        assert completed.wait(2)
        completed.clear()
        with network_scope(storage):
            worker.request(iface, [entry], force=True)
        assert entered.wait(2)
        backend._emit_connection(None)
        backend._emit_connection(iface)
        with network_scope(storage):
            worker.request(iface, [entry])  # Không force; cần reset cache của kết nối cũ.
        release.set()
        assert completed.wait(2)
        assert len(calls) == 3
        with network_scope(storage):
            saved = repository.get_device(entry.mac)
        assert saved.discovered_name == "Tên sau khi kết nối lại"
        assert saved.name == "Tên thủ công" and saved.trusted
    finally:
        release.set()
        backend.stop()
