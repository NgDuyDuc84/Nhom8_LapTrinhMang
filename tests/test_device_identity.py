"""Nhận diện hãng/loại, lưu dữ liệu và cập nhật nền; không thực hiện I/O mạng."""

import os
import sqlite3
import threading
import time
from dataclasses import replace
from datetime import timedelta
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QDialog

from backend import Backend
from core.arp_scanner import ScanEntry
from core.interfaces import NetInterface
from db import database, repository
from extras import oui
from extras.device_identity import device_title, identify_device, manufacturer_label, type_label
from models import Device, DeviceHints, now
from services.device_identification import DeviceIdentification
from services.scan_loop import ScanLoop
from ui.device_columns import DeviceColumn as Col
from ui.main_window import DeviceDialog, MainWindow


@pytest.fixture
def isolated_db(monkeypatch, tmp_path):
    database.close()
    path = tmp_path / "identity.db"
    monkeypatch.setattr(database, "DB_PATH", str(path))
    yield path
    database.close()


@pytest.fixture
def iface():
    return NetInterface("Wi-Fi", "test", "192.168.1.9", "255.255.255.0",
                        "192.168.1.1", "00:11:22:33:44:55", False, True, 7)


@pytest.mark.parametrize("mac,expected", [
    ("28:77:77:db:b5:6c", "ZTE"), ("AC-74-B1-41-A5-D2", "Intel"),
    ("b8:27:eb:00:00:01", "Raspberry Pi"),
])
def test_offline_vendor_lookup_covers_more_than_old_two_prefixes(mac, expected):
    assert expected.casefold() in oui.lookup(mac).casefold()


@pytest.mark.parametrize("mac", [None, [], "bad", "00:00:00:00:00:00",
                                 "ff:ff:ff:ff:ff:ff", "01:00:5e:00:00:01", "02:74:b1:00:00:01"])
def test_non_vendor_macs_do_not_produce_a_manufacturer(mac):
    assert oui.lookup(mac) == "Unknown"


def test_longest_prefix_wins_for_small_and_medium_assignments(monkeypatch):
    registry = {(24, 0x001122): "Large", (28, 0x0011223): "Medium", (36, 0x001122334): "Small"}
    monkeypatch.setattr(oui, "_registry", lambda: registry)
    oui._lookup_normalized.cache_clear()
    try:
        assert oui.lookup("00:11:22:33:44:55") == "Small"
        assert oui.lookup("00:11:22:35:44:55") == "Medium"
        assert oui.lookup("00:11:22:45:44:55") == "Large"
    finally:
        oui._lookup_normalized.cache_clear()


@pytest.mark.parametrize("vendor", ["Apple", "Samsung", "Intel"])
def test_component_vendor_alone_does_not_claim_phone_or_laptop(monkeypatch, vendor):
    monkeypatch.setattr(oui, "lookup", lambda mac: vendor)
    device = identify_device(Device("192.168.1.20", "00:11:22:33:44:55"))
    assert device.device_type == "unknown"
    assert "(theo MAC)" in manufacturer_label(device)


def test_private_mac_can_use_advertised_name_without_inventing_oui_vendor():
    device = identify_device(Device("192.168.1.20", "02:11:22:33:44:55"), hints=DeviceHints(
        hostname="iphone.local", name="Điện thoại Mẹ", model="iPhone 15", sources={"mDNS"},
    ))
    assert device.vendor == "Unknown"
    assert device.device_type == "mobile"
    assert device_title(device) == "Điện thoại Mẹ"
    assert "gợi ý" in type_label(device)
    assert "MAC riêng tư" in manufacturer_label(device)


def test_gateway_and_current_machine_are_identified_by_role(iface):
    router = identify_device(Device(iface.gateway, "28:77:77:00:00:01"), iface.gateway)
    current = identify_device(Device(iface.ip, iface.mac, is_self=True), iface.gateway)
    assert router.device_type == "router"
    assert current.device_type == "computer" and current.hostname
    assert device_title(current) == "Máy tính này"


@pytest.mark.parametrize("hints,kind", [
    (DeviceHints(services={"_ipp._tcp.local"}), "printer"),
    (DeviceHints(services={"_googlecast._tcp.local"}), "media"),
    (DeviceHints(services={"_raop._tcp.local"}), "speaker"),
    (DeviceHints(services={"netbios-file-server"}), "file_server"),
    (DeviceHints(hostname="LAPTOP-ABCD"), "laptop"),
    (DeviceHints(hostname="DESKTOP-ABCD"), "computer"),
    (DeviceHints(model="Tapo C210"), "camera"),
    (DeviceHints(hostname="esphome-sensor.local"), "iot"),
])
def test_service_and_name_hints_have_explanations(hints, kind):
    device = identify_device(Device("192.168.1.20", "02:11:22:33:44:55"), hints=hints)
    assert device.device_type == kind
    assert device.identity_evidence
    assert "gợi ý" in type_label(device)


def test_identity_storage_preserves_user_fields_and_manual_type(isolated_db):
    device = Device("192.168.1.20", "02:11:22:33:44:55", name="Tên của tôi", note="Ghi chú", trusted=True)
    repository.upsert_device(device)
    repository.set_type_override(device.mac, "laptop")
    detected = identify_device(device, hints=DeviceHints(name="Printer", services={"_ipp._tcp.local"}))
    assert repository.save_identity(detected)
    database.close()
    saved = repository.get_device(device.mac)
    assert (saved.name, saved.note, saved.trusted, saved.type_override) == ("Tên của tôi", "Ghi chú", True, "laptop")
    assert saved.device_type == "printer" and "đã chọn" in type_label(saved)
    assert type_label(saved, automatic=True).startswith("Máy in")
    repository.set_type_override(device.mac, "")
    assert "gợi ý" in type_label(repository.get_device(device.mac))


def test_late_identity_cannot_overwrite_new_ip_or_newer_observation(isolated_db):
    original = Device("192.168.1.20", "00:11:22:33:44:55")
    repository.upsert_device(original)
    newer = replace(original, hostname="new.local", identity_seen=now())
    assert repository.save_identity(newer)
    older = replace(newer, hostname="old.local", identity_seen=newer.identity_seen - timedelta(seconds=1))
    assert not repository.save_identity(older)
    assert repository.get_device(original.mac).hostname == "new.local"
    repository.upsert_device(replace(original, ip="192.168.1.30"))
    assert not repository.save_identity(newer)
    assert repository.get_device(original.mac).hostname == ""
    assert repository.save_identity(identify_device(repository.get_device(original.mac)))


def test_existing_database_gets_identity_table_without_losing_data(isolated_db):
    connection = sqlite3.connect(isolated_db)
    old_schema = database._SCHEMA.split("CREATE TABLE IF NOT EXISTS PresenceLog")[0]
    connection.executescript(old_schema)
    stamp = now().isoformat()
    connection.execute("INSERT INTO Devices(mac,ip,name,note,trusted,first_seen,last_seen) VALUES(?,?,?,?,?,?,?)",
                       ("00:11:22:33:44:55", "192.168.1.20", "Tên cũ", "Ghi chú cũ", 1, stamp, stamp))
    connection.commit()
    connection.close()
    database.initialize()
    saved = repository.get_device("00:11:22:33:44:55")
    assert saved.name == "Tên cũ" and saved.note == "Ghi chú cũ" and saved.trusted
    assert saved.device_type == "unknown"
    repository.set_type_override(saved.mac, "mobile")
    assert repository.get_device(saved.mac).type_override == "mobile"


def test_background_identity_is_cached_and_manual_refresh_bypasses_cache(isolated_db, iface):
    entry = ScanEntry("192.168.1.20", "02:11:22:33:44:55")
    before = Device(entry.ip, entry.mac, name="Tên riêng", note="Không đổi", trusted=True, online=False)
    repository.upsert_device(before)
    completed = threading.Event()
    discover = Mock(return_value={entry.ip: DeviceHints(name="iPhone", model="iPhone")})
    worker = DeviceIdentification(lambda device: completed.set(), discover)
    worker.start()
    try:
        worker.request(iface, [entry])
        assert completed.wait(2)
        completed.clear()
        worker.request(iface, [entry])
        deadline = time.monotonic() + 2
        while worker._pending is not None and time.monotonic() < deadline:
            time.sleep(0.01)
        worker.request(iface, [entry], force=True)
        assert completed.wait(2)
        assert discover.call_count == 2
        saved = repository.get_device(entry.mac)
        assert (saved.name, saved.note, saved.trusted, saved.online, saved.last_seen) == (
            before.name, before.note, True, False, before.last_seen.replace(microsecond=0),
        )
    finally:
        worker.stop()


def test_superseded_identification_job_cannot_apply_old_result(isolated_db, iface):
    entry = ScanEntry("192.168.1.20", "02:11:22:33:44:55")
    repository.upsert_device(Device(entry.ip, entry.mac))
    entered, release, completed = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def discover(*args):
        calls.append(1)
        if len(calls) == 1:
            entered.set()
            assert release.wait(2)
            return {entry.ip: DeviceHints(name="Tên cũ")}
        return {entry.ip: DeviceHints(name="Tên mới")}

    worker = DeviceIdentification(lambda device: completed.set(), discover)
    worker.start()
    try:
        worker.request(iface, [entry])
        assert entered.wait(2)
        worker.request(iface, [entry], force=True)
        release.set()
        assert completed.wait(2)
        assert repository.get_device(entry.mac).discovered_name == "Tên mới"
    finally:
        release.set()
        worker.stop()


def test_optional_discovery_error_does_not_invalidate_successful_arp_scan(isolated_db, iface):
    identify = Mock(side_effect=OSError("Multicast unavailable"))
    loop = ScanLoop(interface_resolver=lambda: iface,
                    scanner=lambda chosen: [ScanEntry(iface.gateway, "28:77:77:00:00:01")],
                    on_identify=identify)
    assert len(loop.scan_once()) == 1
    assert repository.get_device("28:77:77:00:00:01").online


def test_stopping_identifier_waits_for_bounded_io_without_applying_result(isolated_db, iface):
    entry = ScanEntry("192.168.1.20", "02:11:22:33:44:55")
    repository.upsert_device(Device(entry.ip, entry.mac))
    entered = threading.Event()
    callback = Mock()

    def discover(chosen, addresses, stop):
        entered.set()
        stop.wait(2)
        return {entry.ip: DeviceHints(name="Không áp dụng sau khi dừng")}

    worker = DeviceIdentification(callback, discover)
    worker.start()
    worker.request(iface, [entry])
    assert entered.wait(2)
    worker.stop()
    assert repository.get_device(entry.mac).discovered_name == ""
    callback.assert_not_called()


def test_identifier_publishes_one_table_refresh_per_batch(isolated_db, iface):
    entries = [ScanEntry(f"192.168.1.{20+i}", f"02:11:22:33:44:{i:02x}") for i in range(4)]
    for entry in entries:
        repository.upsert_device(Device(entry.ip, entry.mac))
    completed = threading.Event()
    changes = []

    def complete():
        changes.append(1)
        completed.set()

    worker = DeviceIdentification(
        discoverer=lambda *a: {entry.ip: DeviceHints(name=f"Máy {index}") for index, entry in enumerate(entries)},
        on_complete=complete,
    )
    worker.start()
    try:
        worker.request(iface, entries)
        assert completed.wait(2)
        assert len(changes) == 1
        assert all(repository.get_device(entry.mac).discovered_name for entry in entries)
    finally:
        worker.stop()


def test_alert_uses_readable_device_name_instead_of_requiring_ip():
    from services.alerts import make_stranger_alert

    device = Device("192.168.1.20", "02:11:22:33:44:55", name="Điện thoại Mẹ", randomized_mac=True)
    message = make_stranger_alert(device).message
    assert "Điện thoại Mẹ" in message and device.mac in message
    assert device.ip not in message


def test_backend_enriches_devices_through_its_real_scan_pipeline(monkeypatch, isolated_db, iface):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("ui.main_window.NetGuardTrayIcon", Mock())
    entry = ScanEntry("192.168.1.20", "02:11:22:33:44:55")
    resolve = lambda preferred=None: iface
    monkeypatch.setattr("core.interfaces.get_active_interface", resolve)
    monkeypatch.setattr("services.scan_loop.get_active_interface", resolve)
    monkeypatch.setattr("services.ping_monitor.get_active_interface", resolve)
    monkeypatch.setattr("services.scan_loop.scan_subnet", lambda chosen: [entry])
    monkeypatch.setattr("services.ping_monitor.ping_once", lambda *a, **k: 3)
    monkeypatch.setattr("services.ping_monitor.trace", lambda *a, **k: [])
    monkeypatch.setattr("core.arp_listener.ArpListener", Mock())
    monkeypatch.setattr("services.device_identification.discover_device_hints", lambda *a: {
        entry.ip: DeviceHints(name="iPhone của Mẹ", model="iPhone", sources={"mDNS"}),
    })
    backend = Backend()
    window = MainWindow(backend)
    try:
        backend.start()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            app.processEvents()
            saved = repository.get_device(entry.mac)
            if saved and saved.device_type == "mobile" and window.device_table.item(0, Col.NAME).text() == "iPhone của Mẹ":
                break
            time.sleep(0.01)
        else:
            raise AssertionError("Chưa nhận được tên/loại từ worker nhận diện")
        assert backend.get_device_status(saved) == "Online"
        assert "gợi ý" in window.device_table.item(0, Col.TYPE).text()
        assert window.device_table.isColumnHidden(Col.IP)
    finally:
        backend.stop()
        window.deleteLater()
        app.processEvents()


def test_device_table_uses_names_and_manual_confirmation_survives_refresh(monkeypatch, isolated_db):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("ui.main_window.NetGuardTrayIcon", Mock())
    device = identify_device(Device("192.168.1.20", "02:11:22:33:44:55"), hints=DeviceHints(name="iPhone của Mẹ", model="iPhone"))
    repository.upsert_device(device)
    repository.save_identity(device)
    backend = Backend()
    window = MainWindow(backend)
    try:
        assert window.device_table.item(0, Col.NAME).text() == "iPhone của Mẹ"
        assert "gợi ý" in window.device_table.item(0, Col.TYPE).text()
        assert window.device_table.isColumnHidden(Col.IP)
        window.show_network_details.setChecked(True)
        assert not window.device_table.isColumnHidden(Col.IP)
        assert window.device_table.item(0, Col.IP).text() == device.ip

        # Sửa ghi chú không được biến tên tự phát hiện thành tên thủ công.
        window.device_table.item(0, Col.NOTE).setText("Của gia đình")
        assert repository.get_device(device.mac).name == ""
        dialog = DeviceDialog(repository.get_device(device.mac), window)
        dialog.name_edit.setText("Điện thoại Mẹ")
        dialog.type_combo.setCurrentIndex(dialog.type_combo.findData("mobile"))
        monkeypatch.setattr(dialog, "exec", lambda: QDialog.Accepted)
        monkeypatch.setattr("ui.main_window.DeviceDialog", Mock(return_value=dialog))
        window.device_table.setCurrentCell(0, Col.NAME)
        window.rename_selected_device()
        saved = repository.get_device(device.mac)
        assert saved.name == "Điện thoại Mẹ" and saved.type_override == "mobile"
        window.refresh_devices()
        assert "đã chọn" in window.device_table.item(0, Col.TYPE).text()
        assert "192.168" not in dialog.windowTitle()
    finally:
        backend.stop()
        window.deleteLater()
        app.processEvents()
