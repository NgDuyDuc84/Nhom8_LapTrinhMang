"""Xác nhận gateway và luồng ARP; dùng gói tổng hợp, không phát lên mạng thật."""
from dataclasses import replace
import os
import threading
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from scapy.all import ARP, Ether

from backend import Backend
from core.arp_listener import ArpListener, ArpObservation
from core.arp_validation import valid_arp_source
from core.interfaces import NetInterface
from core.network_context import network_id, network_scope
from db import repository
from models import Device, now
from services.alerts import ArpAnomalyDetector


@pytest.fixture
def gateway():
    iface = NetInterface("Wi-Fi", "test", "192.168.1.9", "255.255.255.0", "192.168.1.1",
                         "00:11:22:33:44:55", False, True, 7)
    old, new = "00:11:22:33:44:66", "00:11:22:33:44:77"
    repository.upsert_device(Device(iface.gateway, old))
    repository.upsert_device(Device(iface.gateway, new))
    repository.set_meta("gateway_mac", old)
    detector = ArpAnomalyDetector(iface.gateway, subnet="192.168.1.0/24")
    return iface, old, new, detector


def claim(ip, mac, *, operation=2, gratuitous=False):
    return ArpObservation(ip, mac, operation, gratuitous, now())


def test_confirming_new_router_does_not_alert_from_claims_before_confirmation(gateway):
    iface, old, new, detector = gateway
    backend = Backend()
    backend._emit_connection(iface)
    backend._arp_detector = detector
    try:
        assert detector.observe(claim(iface.gateway, old)) == []
        backend.accept_gateway(new)
        assert repository.get_meta("gateway_mac") == new
        assert detector.observe(claim(iface.gateway, new)) == []
        assert repository.list_alerts() == []
    finally:
        backend.stop()


def test_new_confirmation_resets_unfinished_gateway_candidates(gateway):
    iface, old, new, detector = gateway
    assert detector.observe(claim(iface.gateway, new)) == []
    detector.confirm_gateway(new)
    detector.confirm_gateway(old)
    assert detector.observe(claim(iface.gateway, new)) == []
    emitted = detector.observe(claim(iface.gateway, new))
    assert len(emitted) == 1
    assert emitted[0].kind == "gateway_change" and emitted[0].level == "danger"


def test_fresh_old_router_claims_after_confirmation_are_still_detected(gateway):
    iface, old, new, detector = gateway
    detector.confirm_gateway(new)
    assert detector.observe(claim(iface.gateway, old)) == []
    emitted = detector.observe(claim(iface.gateway, old))
    assert [alert.kind for alert in emitted] == ["gateway_change"]


def test_confirming_gateway_preserves_claims_of_other_devices(gateway):
    iface, old, new, detector = gateway
    assert detector.observe(claim("192.168.1.20", old)) == []
    detector.confirm_gateway(new)
    emitted = detector.observe(claim("192.168.1.20", new))
    assert [alert.kind for alert in emitted] == ["ip_conflict:192.168.1.20"]


def test_failed_confirmation_keeps_saved_baseline_and_evidence(gateway, monkeypatch):
    iface, old, new, detector = gateway
    assert detector.observe(claim(iface.gateway, old)) == []
    monkeypatch.setattr(repository, "set_meta", Mock(side_effect=OSError("write failed")))
    with pytest.raises(OSError, match="write failed"):
        detector.confirm_gateway(new)
    assert repository.get_meta("gateway_mac") == old
    assert detector.observe(claim(iface.gateway, old)) == []
    emitted = detector.observe(claim(iface.gateway, new))
    assert [alert.kind for alert in emitted] == ["gateway_change"]


def test_confirmation_waits_for_inflight_detection_before_resetting(gateway, monkeypatch):
    from services import alerts
    iface, _, new, detector = gateway
    assert detector.observe(claim(iface.gateway, new)) == []
    entered, release, confirmation_started, saved = (threading.Event() for _ in range(4))
    original_raise, original_save = alerts.raise_anomaly, repository.set_meta
    errors = []
    def slow_raise(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return original_raise(*args, **kwargs)
    def save(*args):
        original_save(*args)
        saved.set()
    def confirm():
        confirmation_started.set()
        try:
            detector.confirm_gateway(new)
        except Exception as exc:
            errors.append(exc)
    monkeypatch.setattr(alerts, "raise_anomaly", slow_raise)
    monkeypatch.setattr(repository, "set_meta", save)
    observing = threading.Thread(target=lambda: detector.observe(claim(iface.gateway, new)))
    confirming = threading.Thread(target=confirm)
    observing.start()
    try:
        assert entered.wait(2)
        confirming.start()
        assert confirmation_started.wait(2)
        assert not saved.wait(.05)
        release.set()
        observing.join(3)
        confirming.join(3)
        assert not observing.is_alive() and not confirming.is_alive()
        assert errors == [] and saved.is_set()
        assert repository.get_meta("gateway_mac") == new
        assert detector.observe(claim(iface.gateway, new)) == []
    finally:
        release.set()
        observing.join(3)
        if confirming.ident:
            confirming.join(3)


@pytest.mark.parametrize("operation", [0, 3, 4, 8, 9])
def test_unsupported_arp_operations_cannot_create_gateway_alerts(gateway, operation):
    iface, _, new, detector = gateway
    observations = []
    listener = ArpListener(observations.append, iface)
    packet = Ether(src=new) / ARP(op=operation, psrc=iface.gateway, pdst=iface.gateway, hwsrc=new)
    for _ in range(2):
        listener._handle_packet(packet)
        assert detector.observe(claim(iface.gateway, new, operation=operation, gratuitous=True)) == []
    assert valid_arp_source(packet, iface) is None
    assert observations == []
    assert repository.list_alerts() == []


@pytest.mark.parametrize("operation", [1, 2], ids=["announcement", "reply"])
def test_valid_announcement_and_reply_flow_through_listener_to_saved_alert(gateway, operation):
    iface, _, new, detector = gateway
    emitted = []
    listener = ArpListener(lambda observed: emitted.extend(detector.observe(observed)), iface)
    packet = Ether(src=new) / ARP(op=operation, psrc=iface.gateway, pdst=iface.gateway, hwsrc=new)
    listener._handle_packet(packet)
    listener._handle_packet(packet)
    assert len(emitted) == 1 and emitted[0].kind == "gateway_change"
    assert repository.list_alerts()[0].kind == "gateway_change"


@pytest.mark.parametrize("address", ["192.168.1.0", "192.168.1.255", "10.0.0.2", "127.0.0.1", "0.0.0.0", "224.0.0.1"])
def test_invalid_source_addresses_do_not_enter_detector_state(gateway, address):
    iface, _, new, detector = gateway
    assert detector.observe(claim(address, new)) == []
    packet = Ether(src=new) / ARP(op=2, psrc=address, hwsrc=new)
    assert valid_arp_source(packet, iface) is None
    assert repository.list_alerts() == []


@pytest.mark.parametrize("mask", ["255.255.255.254", "255.255.255.255"])
def test_point_to_point_and_single_host_endpoints_remain_valid(gateway, mask):
    iface, _, new, _ = gateway
    iface = replace(iface, ip="192.0.2.1", netmask=mask)
    packet = Ether(src=new) / ARP(op=2, psrc=iface.ip, hwsrc=new)
    assert valid_arp_source(packet, iface) == (iface.ip, new)


def test_recent_claim_overlap_during_dhcp_change_is_presented_as_unconfirmed(gateway):
    _, old, new, _ = gateway
    device = Device("192.168.1.20", old, online=True)
    repository.upsert_device(device)
    detector = ArpAnomalyDetector("192.168.1.1", [device], subnet="192.168.1.0/24")
    assert detector.observe(claim(device.ip, old)) == []
    repository.upsert_device(replace(device, ip="192.168.1.30", last_seen=now()))
    emitted = detector.observe(claim("192.168.1.20", new))
    assert len(emitted) == 1
    assert emitted[0].level == "warning"
    assert "DHCP" in emitted[0].message and "chưa xác minh" in emitted[0].message


def test_multiple_ip_device_still_has_secondary_ip_conflicts_detected(gateway):
    _, old, new, detector = gateway
    repository.upsert_device(Device("192.168.1.20", old, online=True))
    detector.observe(claim("192.168.1.20", old))
    detector.observe(claim("192.168.1.21", old))
    emitted = detector.observe(claim("192.168.1.21", new))
    assert [alert.kind for alert in emitted] == ["ip_conflict:192.168.1.21"]


def test_known_online_owner_change_requires_repeated_claims(gateway):
    _, old, new, _ = gateway
    device = Device("192.168.1.20", old, online=True)
    repository.upsert_device(device)
    detector = ArpAnomalyDetector("192.168.1.1", [device], subnet="192.168.1.0/24")
    assert detector.observe(claim(device.ip, new)) == []
    emitted = detector.observe(claim(device.ip, new))
    assert [alert.kind for alert in emitted] == ["owner_change:192.168.1.20"]
    assert emitted[0].level == "warning"
    assert detector.observe(claim(device.ip, new)) == []


def test_owner_change_claims_outside_confirmation_window_do_not_accumulate(gateway, monkeypatch):
    from services import alerts
    _, old, new, _ = gateway
    clock = [0.0]
    monkeypatch.setattr(alerts, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    device = Device("192.168.1.20", old, online=True)
    repository.upsert_device(device)
    detector = ArpAnomalyDetector("192.168.1.1", [device], subnet="192.168.1.0/24")
    assert detector.observe(claim(device.ip, new)) == []
    clock[0] = 6.0
    assert detector.observe(claim(device.ip, new)) == []
    clock[0] = 6.1
    emitted = detector.observe(claim(device.ip, new))
    assert [alert.kind for alert in emitted] == ["owner_change:192.168.1.20"]


def test_router_confirmation_dialog_cannot_pin_same_mac_in_a_new_network(gateway, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    from ui.main_window import MainWindow
    iface, old, new, _ = gateway
    first, second = replace(iface, profile_id="A"), replace(iface, profile_id="B")
    for network in (first, second):
        with network_scope(network_id(network)):
            repository.upsert_device(Device(network.gateway, new))
            repository.set_meta("gateway_mac", old)
    app = QApplication.instance() or QApplication([])
    backend = Backend()
    backend._scoped = True
    backend._emit_connection(first)
    ui = MainWindow(backend)
    failure = Mock()
    def question(*args):
        backend._emit_connection(second)
        return QMessageBox.Yes
    monkeypatch.setattr(QMessageBox, "question", question)
    monkeypatch.setattr(QMessageBox, "critical", failure)
    try:
        ui.device_table.setCurrentCell(0, 0)
        ui.accept_gateway()
        failure.assert_called_once()
        assert "Kết nối đã đổi" in failure.call_args.args[2]
        for network in (first, second):
            with network_scope(network_id(network)):
                assert repository.get_meta("gateway_mac") == old
    finally:
        backend.stop()
        ui._device_timer.stop()
        ui._diagnosis_timer.stop()
        ui.deleteLater()
        app.processEvents()


def test_valid_ui_confirmation_persists_and_reports_success(gateway, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    from ui.main_window import MainWindow
    iface, old, new, detector = gateway
    app = QApplication.instance() or QApplication([])
    backend = Backend()
    backend._emit_connection(iface)
    backend._arp_detector = detector
    ui = MainWindow(backend)
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.Yes)
    try:
        detector.observe(claim(iface.gateway, old))
        ui.device_table.setCurrentCell(ui._device_rows[new], 0)
        ui.accept_gateway()
        assert repository.get_meta("gateway_mac") == new
        assert "Đã cập nhật mốc MAC router" in ui.statusBar().currentMessage()
        assert detector.observe(claim(iface.gateway, new)) == []
    finally:
        backend.stop()
        ui._device_timer.stop()
        ui._diagnosis_timer.stop()
        ui.deleteLater()
        app.processEvents()
