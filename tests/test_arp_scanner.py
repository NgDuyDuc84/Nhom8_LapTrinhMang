"""Hồi quy lỗi 01 với luồng AsyncSniffer thật, thay phần I/O mạng bằng dữ liệu giả."""

import threading
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import scapy.all as scapy

from core import arp_scanner as scanner
from core.interfaces import NetInterface
from config import OFFLINE_AFTER_MISSES
from db import database, repository
from models import Device
from services.scan_loop import ScanLoop


@pytest.fixture
def iface():
    return NetInterface("Wi-Fi", "test", "192.168.1.9", "255.255.255.0",
                        "192.168.1.1", "00:11:22:33:44:55", False, True, 7)


@pytest.fixture
def capture(monkeypatch):
    real_sniffer = scapy.AsyncSniffer
    state = SimpleNamespace(
        mode="healthy", instances=[], opening=threading.Event(), ready=threading.Event(),
        open_gate=threading.Event(), close_gate=threading.Event(), drop=threading.Event(),
        close_error=False, packets=[],
    )
    state.open_gate.set()
    state.close_gate.set()

    def run(sniffer, *, started_callback=None, **kwargs):
        sniffer.running = True
        state.opening.set()
        if state.mode == "open_error":
            raise PermissionError("Access is denied opening capture")
        assert state.open_gate.wait(5), "Test không mở cổng khởi tạo capture"
        stopped = threading.Event()
        sniffer.continue_sniff = True

        def stop():
            sniffer.continue_sniff = False
            stopped.set()
            if state.close_error:
                raise OSError("capture close failed")

        sniffer.stop_cb = stop
        state.ready.set()
        if started_callback is not None and state.mode != "no_ready":
            started_callback()
        while not stopped.wait(0.005):
            if state.drop.is_set():
                if state.mode == "silent_stop":
                    sniffer.running = False
                    return
                raise OSError("capture read failed")
        assert state.close_gate.wait(5), "Test không cho capture đóng xong"
        sniffer.running = False

    def create(**kwargs):
        instance = real_sniffer(**kwargs)
        state.instances.append(instance)
        return instance

    def send(*args, **kwargs):
        instance = state.instances[-1]
        if state.mode in ("read_error", "silent_stop"):
            state.drop.set()
            instance.thread.join(1)
        for packet in state.packets:
            instance.kwargs["prn"](packet)

    monkeypatch.setattr(real_sniffer, "_run", run)
    monkeypatch.setattr(scapy, "AsyncSniffer", create)
    state.send = Mock(side_effect=send)
    monkeypatch.setattr(scapy, "sendp", state.send)
    monkeypatch.setattr(scanner, "_scapy_iface", lambda iface: "fake-interface")
    monkeypatch.setattr(scanner, "get_subnet_hosts", lambda iface: [
        "192.168.1.1", "192.168.1.9", "192.168.1.20",
    ])
    monkeypatch.setattr(scanner, "SNIFFER_START_TIMEOUT_SEC", 1)
    monkeypatch.setattr(scanner, "SNIFFER_STOP_TIMEOUT_SEC", 0.1)
    yield state
    state.open_gate.set()
    state.close_gate.set()
    state.close_error = False
    for instance in state.instances:
        if instance.running:
            instance.stop_cb()
        if instance.thread is not None:
            instance.thread.join(2)


def test_async_capture_open_failure_is_not_a_successful_self_only_scan(capture, iface):
    capture.mode = "open_error"

    with pytest.raises(RuntimeError, match="Administrator"):
        scanner.scan_subnet(iface, timeout=0, rounds=1)

    capture.send.assert_not_called()
    assert not capture.instances[-1].thread.is_alive()


def test_waits_for_ready_callback_before_sending(monkeypatch, capture, iface):
    capture.open_gate.clear()
    monkeypatch.setattr(scanner.time, "sleep", Mock(side_effect=AssertionError("Không ngủ cố định")))
    results, errors = [], []

    def scan():
        try:
            results.append(scanner.scan_subnet(iface, timeout=0, rounds=1))
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=scan)
    worker.start()
    try:
        assert capture.opening.wait(2)
        assert capture.instances[-1].running
        capture.send.assert_not_called()
    finally:
        capture.open_gate.set()
        worker.join(2)

    assert not worker.is_alive()
    assert not errors
    assert results == [[scanner.ScanEntry(iface.ip, iface.mac, is_self=True)]]
    capture.send.assert_called_once()
    assert not capture.instances[-1].thread.is_alive()


def test_healthy_scan_keeps_replies_filters_duplicates_and_adds_self(capture, iface):
    capture.packets = [
        scapy.ARP(op=2, psrc="192.168.1.20", hwsrc="00:11:22:33:44:66"),
        scapy.ARP(op=2, psrc="192.168.1.1", hwsrc="AA:BB:CC:DD:EE:FF"),
        scapy.ARP(op=2, psrc="192.168.1.20", hwsrc="00:11:22:33:44:66"),
        scapy.ARP(op=2, psrc="192.168.1.9", hwsrc="00:00:00:00:00:00"),
        scapy.ARP(op=1, psrc="192.168.1.20", hwsrc="00:11:22:33:44:77"),
        scapy.ARP(op=2, psrc="192.168.2.20", hwsrc="00:11:22:33:44:88"),
        scapy.Ether() / scapy.IP(src="192.168.1.20"),
    ]

    entries = scanner.scan_subnet(iface, timeout=0.001, rounds=2)

    assert entries == [
        scanner.ScanEntry("192.168.1.1", "aa:bb:cc:dd:ee:ff"),
        scanner.ScanEntry(iface.ip, iface.mac, is_self=True),
        scanner.ScanEntry("192.168.1.20", "00:11:22:33:44:66"),
    ]
    assert capture.send.call_count == 2
    for call in capture.send.call_args_list:
        assert call.kwargs == {"iface": "fake-interface", "verbose": 0, "inter": 0.001}
        assert [packet[scapy.ARP].pdst for packet in call.args[0]] == [
            "192.168.1.1", iface.ip, "192.168.1.20",
        ]
    assert not capture.instances[-1].thread.is_alive()


def test_healthy_capture_without_replies_is_a_valid_self_only_scan(capture, iface):
    assert scanner.scan_subnet(iface, timeout=0, rounds=1) == [
        scanner.ScanEntry(iface.ip, iface.mac, is_self=True),
    ]
    assert not capture.instances[-1].thread.is_alive()


@pytest.mark.parametrize("mode, message", [
    ("read_error", "capture read failed"), ("silent_stop", "dừng ngoài dự kiến"),
])
def test_capture_failure_during_scan_discards_partial_results(capture, iface, mode, message):
    capture.mode = mode
    capture.packets = [scapy.ARP(op=2, psrc="192.168.1.20", hwsrc="00:11:22:33:44:66")]

    with pytest.raises(RuntimeError, match=message):
        scanner.scan_subnet(iface, timeout=1, rounds=2)

    capture.send.assert_called_once()
    assert not capture.instances[-1].thread.is_alive()


def test_missing_ready_callback_times_out_without_sending(monkeypatch, capture, iface):
    capture.mode = "no_ready"
    monkeypatch.setattr(scanner, "SNIFFER_START_TIMEOUT_SEC", 0.02)

    with pytest.raises(RuntimeError, match="Hết thời gian chờ"):
        scanner.scan_subnet(iface, timeout=0, rounds=1)

    capture.send.assert_not_called()
    assert not capture.instances[-1].thread.is_alive()


def test_capture_that_opens_after_timeout_stops_itself(monkeypatch, capture, iface):
    capture.open_gate.clear()
    monkeypatch.setattr(scanner, "SNIFFER_START_TIMEOUT_SEC", 0.02)
    monkeypatch.setattr(scanner, "SNIFFER_STOP_TIMEOUT_SEC", 0.02)

    with pytest.raises(RuntimeError, match="Hết thời gian chờ"):
        scanner.scan_subnet(iface, timeout=0, rounds=1)

    capture.send.assert_not_called()
    instance = capture.instances[-1]
    assert instance.thread.is_alive()
    capture.open_gate.set()
    instance.thread.join(2)
    assert instance.exception is None
    assert not instance.running
    assert not instance.thread.is_alive()


def test_stop_error_invalidates_successful_collection(capture, iface):
    capture.close_error = True

    with pytest.raises(RuntimeError, match="capture close failed"):
        scanner.scan_subnet(iface, timeout=0, rounds=1)

    assert not capture.instances[-1].thread.is_alive()


def test_capture_dying_between_health_check_and_stop_is_still_a_failure(monkeypatch, capture):
    capture.mode = "silent_stop"
    instance = scapy.AsyncSniffer()
    instance.start()
    assert capture.ready.wait(2)
    check = scanner._check_capture

    def check_then_capture_dies(sniffer):
        check(sniffer)
        capture.drop.set()
        sniffer.thread.join(2)

    monkeypatch.setattr(scanner, "_check_capture", check_then_capture_dies)

    assert scanner._stop_capture(instance, require_healthy=True) is not None
    assert not instance.thread.is_alive()


def test_synchronous_start_failure_is_reported_without_sending(monkeypatch, capture, iface):
    def fail_start(sniffer):
        raise OSError("thread start failed")

    # Lấy lớp thật qua factory của fixture, không tạo socket mạng.
    instance = scapy.AsyncSniffer()
    monkeypatch.setattr(type(instance), "start", fail_start)

    with pytest.raises(RuntimeError, match="thread start failed"):
        scanner.scan_subnet(iface, timeout=0, rounds=1)

    capture.send.assert_not_called()


def test_shutdown_timeout_does_not_return_a_successful_scan(monkeypatch, capture, iface):
    capture.close_gate.clear()
    monkeypatch.setattr(scanner, "SNIFFER_STOP_TIMEOUT_SEC", 0.02)

    with pytest.raises(RuntimeError, match="chưa dừng trong thời gian chờ"):
        scanner.scan_subnet(iface, timeout=0, rounds=1)

    capture.close_gate.set()
    capture.instances[-1].thread.join(2)
    assert not capture.instances[-1].thread.is_alive()


def test_send_failure_preserves_primary_cause_when_stop_also_fails(capture, iface):
    capture.send.side_effect = OSError("send failed")
    capture.close_error = True

    with pytest.raises(RuntimeError, match="send failed") as caught:
        scanner.scan_subnet(iface, timeout=0, rounds=1)

    assert "capture close failed" in " ".join(caught.value.__cause__.__notes__)
    assert not capture.instances[-1].thread.is_alive()


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    database.close()
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "scanner.db"))
    database.initialize()
    yield
    database.close()


@pytest.mark.parametrize("mode", ["open_error", "read_error", "silent_stop", "close_error"])
def test_failed_captures_do_not_update_presence_and_next_scan_can_recover(
    capture, iface, isolated_db, mode,
):
    moment = datetime(2026, 11, 11, 9, 0)
    device = Device(ip="192.168.1.20", mac="00:11:22:33:44:66", name="Máy đã biết",
                    note="Giữ ghi chú", trusted=True, first_seen=moment, last_seen=moment)
    repository.upsert_device(device)
    repository.set_online(device.mac, True, ts=moment)
    before = repository.get_device(device.mac)
    presence = repository.get_presence(device.mac, since=moment)
    on_device, on_scan, on_identify = Mock(), Mock(), Mock()
    loop = ScanLoop(interface_resolver=lambda: iface,
                    scanner=lambda chosen: scanner.scan_subnet(chosen, timeout=0, rounds=1),
                    on_device=on_device, on_scan=on_scan, on_identify=on_identify)
    # Giữ một lần vắng mặt đã có từ lượt quét hợp lệ trước đó.
    loop._update_interface(iface)
    loop._misses[device.mac] = 1
    capture.mode = mode
    capture.close_error = mode == "close_error"

    for _ in range(OFFLINE_AFTER_MISSES + 1):
        with pytest.raises(RuntimeError):
            loop.scan_once()
        assert loop._misses == {device.mac: 1}
        assert repository.list_devices() == [before]
        assert repository.get_presence(device.mac, since=moment) == presence

    on_device.assert_not_called()
    on_scan.assert_not_called()
    on_identify.assert_not_called()
    capture.mode = "healthy"
    capture.close_error = False
    capture.drop.clear()
    capture.packets = [scapy.ARP(op=2, psrc=device.ip, hwsrc=device.mac)]
    loop.scan_once()

    stored = repository.get_device(device.mac)
    assert stored.online
    assert (stored.name, stored.note, stored.trusted) == (before.name, before.note, before.trusted)
    assert loop._misses[device.mac] == 0
    assert repository.get_presence(device.mac, since=moment) == presence
    assert repository.get_device(iface.mac).is_self
    on_scan.assert_called_once()
    on_identify.assert_called_once()
