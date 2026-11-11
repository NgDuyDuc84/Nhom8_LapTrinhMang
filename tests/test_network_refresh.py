"""Làm mới mạng trên worker thật với I/O giả và CSDL riêng, không gửi gói mạng."""

import os
import threading
import time
from dataclasses import replace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from backend import Backend
from core.arp_scanner import ScanEntry
from core.interfaces import NetInterface
from db import database, repository
from models import Device, Diagnosis
from services.ping_monitor import PingMonitor
from services.scan_loop import ScanLoop
from ui.main_window import MainWindow


def wait_for(predicate, app, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Hết thời gian chờ kết quả làm mới")


def wait_for_refresh(backend, window, app):
    # CSDL/state cập nhật trước khi Qt giao signal về luồng UI.
    wait_for(lambda: not backend.get_refresh_status()["running"]
             and window.refresh_action.isEnabled(), app)


@pytest.fixture
def iface():
    return NetInterface("Wi-Fi", "test", "192.168.1.9", "255.255.255.0",
                        "192.168.1.1", "00:11:22:33:44:55", False, True, 7)


@pytest.fixture
def ui(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    database.close()
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "refresh.db"))
    monkeypatch.setattr("ui.main_window.NetGuardTrayIcon", Mock())
    backend = Backend()
    window = MainWindow(backend)
    yield backend, window, app
    backend.stop()
    app.processEvents()
    window.deleteLater()
    app.processEvents()
    database.close()


@pytest.fixture
def running_network(monkeypatch, ui, iface):
    backend, window, app = ui
    state = {
        "active": iface,
        "offline": False,
        "entries": [ScanEntry("192.168.1.20", "00:11:22:33:44:66")],
        "scan_calls": [], "pings": [], "scan_error": None, "ping_error": None,
    }
    known = {iface.name: iface}
    scanned, measured = threading.Event(), threading.Event()

    def resolve(preferred=None):
        if state["offline"]:
            raise RuntimeError("Chưa kết nối LAN: Wi-Fi đang tắt.")
        current = state["active"]
        known[current.name] = current
        return known.get(preferred.name, current) if preferred else current

    def scan(chosen):
        state["scan_calls"].append(chosen)
        gate = state.get("scan_gate")
        if gate is not None and not gate.wait(3):
            raise RuntimeError("Test không mở cổng cho scan")
        if state["scan_error"]:
            raise state["scan_error"]
        return list(state["entries"])

    def ping(address, timeout):
        state["pings"].append(address)
        if state["ping_error"]:
            raise state["ping_error"]
        return 4.25

    def on_scan(entries):
        backend._emit_scan(entries)
        scanned.set()

    def on_cycle(results):
        backend._emit_measurements(results)
        measured.set()

    monkeypatch.setattr("services.scan_loop.get_active_interface", resolve)
    monkeypatch.setattr("services.ping_monitor.get_active_interface", resolve)
    backend._loop = ScanLoop(
        iface=iface, interval=600, scanner=scan, on_device=backend._emit_device,
        on_scan=on_scan, on_refresh=backend._on_scan_refresh,
    )
    backend._ping_monitor = PingMonitor(
        iface=iface, interval=600, pinger=ping, tracer=lambda *a, **k: [],
        on_ping=backend.ping_result.emit, on_cycle=on_cycle,
        on_interface=backend._emit_connection, on_diagnosis=backend._emit_diagnosis,
        on_refresh=backend._on_ping_refresh,
    )
    backend._emit_connection(iface)
    backend._loop.start()
    backend._ping_monitor.start()
    wait_for(lambda: scanned.is_set() and measured.is_set(), app)
    return backend, window, app, state


def test_refresh_button_runs_new_scan_and_ping_without_erasing_user_data(running_network):
    backend, window, app, state = running_network
    mac = state["entries"][0].mac
    repository.set_name_note(mac, "Điện thoại", "Của gia đình")
    repository.set_trusted(mac, True)
    first_seen = repository.get_device(mac).first_seen
    ping_count = len(state["pings"])
    gate = threading.Event()
    state["scan_gate"] = gate
    state["entries"].append(ScanEntry("192.168.1.30", "00:11:22:33:44:77"))

    try:
        window.refresh_action.click()
        assert not window.refresh_action.isEnabled()
        assert backend.get_refresh_status()["running"]
        assert backend.refresh_network() is False
        gate.set()
        wait_for(lambda: window.refresh_action.isEnabled(), app)
    finally:
        gate.set()

    assert "Đã làm mới mạng lúc" in window.refresh_status_label.text()
    assert len(state["scan_calls"]) == 2
    assert len(state["pings"]) > ping_count
    assert window.device_table.rowCount() == 2
    saved = repository.get_device(mac)
    assert (saved.name, saved.note, saved.trusted, saved.first_seen) == (
        "Điện thoại", "Của gia đình", True, first_seen,
    )
    assert backend.get_latest_diagnosis().verdict == "unknown"


def test_refresh_reselects_active_card_and_measurement_addresses(running_network, iface):
    backend, window, app, state = running_network
    other = replace(iface, name="Ethernet", index=12, ip="10.0.0.9",
                    gateway="10.0.0.1", mac="00:11:22:33:44:88")
    old_mac = state["entries"][0].mac
    new_mac = "00:11:22:33:44:99"
    state["active"] = other
    state["entries"] = [ScanEntry("10.0.0.20", new_mac)]

    window.refresh_action.click()
    wait_for_refresh(backend, window, app)
    app.processEvents()

    assert backend.get_connection_status()["name"] == "Ethernet"
    assert state["scan_calls"][-1] == other
    assert window.measurement_table.item(0, 1).text() == other.gateway
    assert backend.get_device_status(repository.get_device(new_mac)) == "Online"
    assert backend.get_device_status(repository.get_device(old_mac)).startswith("Chưa xác minh")


def test_offline_refresh_reports_error_then_allows_retry(running_network):
    backend, window, app, state = running_network
    mac = state["entries"][0].mac
    state["offline"] = True

    window.refresh_action.click()
    wait_for_refresh(backend, window, app)
    app.processEvents()

    assert "Làm mới gặp lỗi" in window.refresh_status_label.text()
    assert "Chưa kết nối LAN" in window.refresh_status_label.text()
    assert window.refresh_action.isEnabled()
    assert not backend.get_connection_status()["connected"]
    assert repository.get_device(mac).online  # Quét lỗi không làm thiết bị thành Offline.

    state["offline"] = False
    window.refresh_action.click()
    wait_for_refresh(backend, window, app)
    app.processEvents()
    assert not backend.get_refresh_status()["errors"]
    assert "Đã làm mới mạng lúc" in window.refresh_status_label.text()


@pytest.mark.parametrize("error", [
    ValueError("Dải mạng /18 vượt giới hạn quét 1024 host."),
    RuntimeError("Không mở được card mạng để quét."),
])
def test_scan_failure_is_visible_and_refresh_button_recovers(running_network, error):
    backend, window, app, state = running_network
    state["scan_error"] = error

    window.refresh_action.click()
    wait_for_refresh(backend, window, app)
    app.processEvents()

    assert "Quét thiết bị" in window.refresh_status_label.text()
    assert str(error) in window.refresh_status_label.text()
    assert window.refresh_action.isEnabled()


def test_ping_failure_is_visible_without_discarding_successful_scan(running_network):
    backend, window, app, state = running_network
    state["ping_error"] = RuntimeError("Lỗi tạo socket đo mạng")

    window.refresh_action.click()
    wait_for_refresh(backend, window, app)
    app.processEvents()

    assert "Đo kết nối" in window.refresh_status_label.text()
    assert "Lỗi tạo socket" in window.refresh_status_label.text()
    assert backend.get_device_status(repository.get_device(state["entries"][0].mac)) == "Online"
    assert window.refresh_action.isEnabled()


def test_refresh_waits_for_running_scan_and_coalesces_requests(ui, iface):
    _, _, app = ui
    started, release, refreshed = threading.Event(), threading.Event(), threading.Event()
    calls, worker_ids = [], []
    active = 0
    max_active = 0

    def scan(chosen):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        calls.append(chosen)
        worker_ids.append(threading.get_ident())
        try:
            if len(calls) == 1:
                started.set()
                assert release.wait(3)
            return []
        finally:
            active -= 1

    loop = ScanLoop(interface_resolver=lambda: iface, scanner=scan, interval=600,
                    on_refresh=lambda *args: refreshed.set())
    loop.start()
    try:
        assert started.wait(2)
        for _ in range(20):
            loop.request_refresh()
        assert len(calls) == 1
        release.set()
        wait_for(refreshed.is_set, app)
        assert len(calls) == 2 and max_active == 1
        assert len(set(worker_ids)) == 1
    finally:
        release.set()
        loop.stop(timeout=2)


def test_ping_refresh_discards_old_isp_and_statistics(ui, iface):
    backend, _, _ = ui
    monitor = PingMonitor(interface_resolver=lambda: iface, pinger=lambda *args: 5,
                          on_diagnosis=backend._emit_diagnosis)
    monitor._cycle()
    old_generation = monitor._network_generation
    monitor._history["router"].extend([100] * 30)
    monitor._isp_ip = "10.0.0.1"
    backend._emit_diagnosis(Diagnosis("ok", "Kết luận cũ"))

    assert monitor._cycle(reselect=True) is None

    assert monitor._isp_ip is None
    assert monitor._network_generation == old_generation + 1
    assert list(monitor._history["router"]) == [5]
    assert not monitor._history["isp"]
    assert backend.get_latest_diagnosis().verdict == "unknown"
    assert "mẫu mới" in backend.get_latest_diagnosis().text


def test_ping_refresh_waits_for_inflight_measurement_and_wakes_long_interval(ui, iface):
    _, _, app = ui
    started, release, refreshed = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def ping(address, timeout):
        calls.append((address, threading.get_ident()))
        if len(calls) == 1:
            started.set()
            assert release.wait(3)
        return 5

    monitor = PingMonitor(interface_resolver=lambda: iface, pinger=ping,
                          tracer=lambda *a, **k: [], interval=600,
                          on_refresh=lambda error: refreshed.set())
    monitor.start()
    try:
        assert started.wait(2)
        for _ in range(20):
            monitor.request_refresh()
        assert len(calls) == 1
        release.set()
        wait_for(refreshed.is_set, app)
        assert len(calls) == 4  # Hai mốc có địa chỉ, hai chu kỳ; chưa biết hop ISP.
        assert len({worker for address, worker in calls}) == 1
    finally:
        release.set()
        monitor.stop(timeout=2)


def test_refresh_without_gateway_shows_why_measurement_cannot_run(running_network, iface):
    backend, window, app, state = running_network
    state["active"] = replace(iface, gateway="")

    window.refresh_action.click()
    wait_for_refresh(backend, window, app)

    assert "Không có gateway" in window.refresh_status_label.text()
    assert "không có gateway" in window.measurement_table.item(0, 4).text()
    assert window.refresh_action.isEnabled()


def stub_services(backend):
    backend._loop = Mock()
    backend._ping_monitor = Mock()
    backend._loop.is_running.return_value = True
    backend._ping_monitor.is_running.return_value = True


def test_scan_finishing_before_connection_update_is_verified_after_both_parts(ui, iface):
    backend, window, _ = ui
    stub_services(backend)
    other = replace(iface, ip="10.0.0.9", gateway="10.0.0.1")
    entry = ScanEntry("10.0.0.20", "00:11:22:33:44:99")
    repository.upsert_device(Device(entry.ip, entry.mac, online=True))
    backend._emit_connection(iface)

    assert backend.refresh_network()
    backend._on_scan_refresh(other, [entry], None)
    assert backend.get_refresh_status()["running"]
    assert not window.refresh_action.isEnabled()
    backend._emit_connection(other)
    backend._on_ping_refresh(None)

    assert not backend.get_refresh_status()["errors"]
    assert backend.get_device_status(repository.get_device(entry.mac)) == "Online"
    assert window.refresh_action.isEnabled()


def test_network_change_during_refresh_does_not_confirm_stale_scan(ui, iface):
    backend, window, _ = ui
    stub_services(backend)
    backend._emit_connection(iface)
    entry = ScanEntry("192.168.1.20", "00:11:22:33:44:66")
    repository.upsert_device(Device(entry.ip, entry.mac, online=True))

    backend.refresh_network()
    backend._on_scan_refresh(iface, [entry], None)
    backend._emit_connection(replace(iface, ip="10.0.0.9", gateway="10.0.0.1"))
    backend._on_ping_refresh(None)

    assert "Kết nối đã thay đổi" in window.refresh_status_label.text()
    assert backend.get_device_status(repository.get_device(entry.mac)).startswith("Chưa xác minh")
    assert window.refresh_action.isEnabled()


def test_failed_request_does_not_leave_refresh_running(ui, iface):
    backend, window, _ = ui
    stub_services(backend)
    backend._emit_connection(iface)
    backend._loop.request_refresh.side_effect = RuntimeError("Dịch vụ quét đang dừng")
    backend._ping_monitor.request_refresh.side_effect = RuntimeError("Dịch vụ đo đang dừng")

    window.refresh_action.click()

    assert not backend.get_refresh_status()["running"]
    assert len(backend.get_refresh_status()["errors"]) == 2
    assert window.refresh_action.isEnabled()


def test_late_completion_signal_cannot_enable_button_during_next_refresh(ui, iface):
    backend, window, _ = ui
    stub_services(backend)
    backend._emit_connection(iface)
    backend.refresh_network()
    backend._on_scan_refresh(iface, [], None)
    backend._on_ping_refresh(None)
    previous = backend.get_refresh_status()

    backend.refresh_network()
    backend.network_refresh_changed.emit(previous)

    assert backend.get_refresh_status()["running"]
    assert not window.refresh_action.isEnabled()
    assert window._network_refresh_running


def test_refresh_before_services_start_has_clear_message(ui):
    _, window, _ = ui
    window.refresh_action.click()
    assert "Dịch vụ mạng chưa sẵn sàng" in window.refresh_status_label.text()
    assert window.refresh_action.isEnabled()


def test_backend_start_wires_refresh_to_real_service_workers(monkeypatch, ui, iface):
    backend, window, app = ui
    scanner = Mock(return_value=[ScanEntry(iface.ip, iface.mac, True)])
    listener = Mock()
    listener_factory = Mock(return_value=listener)
    resolve = lambda preferred=None: iface
    monkeypatch.setattr("core.interfaces.get_active_interface", resolve)
    monkeypatch.setattr("services.scan_loop.get_active_interface", resolve)
    monkeypatch.setattr("services.ping_monitor.get_active_interface", resolve)
    monkeypatch.setattr("services.scan_loop.scan_subnet", scanner)
    monkeypatch.setattr("services.ping_monitor.ping_once", lambda *a, **k: 3.5)
    monkeypatch.setattr("services.ping_monitor.trace", lambda *a, **k: [])
    monkeypatch.setattr("core.arp_listener.ArpListener", listener_factory)

    backend.start()
    wait_for(lambda: scanner.call_count >= 1 and bool(backend.get_latest_measurements()), app)
    window.refresh_action.click()
    wait_for_refresh(backend, window, app)

    assert scanner.call_count >= 2
    assert listener_factory.call_count >= 2
    assert not backend.get_refresh_status()["errors"]
    assert backend.get_device_status(repository.get_device(iface.mac)) == "Online"
    assert "Đã làm mới mạng lúc" in window.refresh_status_label.text()
