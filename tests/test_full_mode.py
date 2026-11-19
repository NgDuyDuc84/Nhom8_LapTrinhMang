from unittest.mock import Mock

from core import network_mode
from core.interfaces import check_environment


def test_native_mode_never_checks_npcap(monkeypatch):
    monkeypatch.setattr(network_mode, "PACKET_CAPTURE", False)
    monkeypatch.setattr("core.interfaces.is_admin", lambda: True)
    check = Mock(side_effect=AssertionError("Native không cần Npcap"))
    monkeypatch.setattr("core.npcap_runtime.npcap_available", check)
    assert check_environment(require_network=False) == []
    check.assert_not_called()


def test_full_mode_reports_missing_driver_and_accepts_available_driver(monkeypatch):
    monkeypatch.setattr(network_mode, "PACKET_CAPTURE", True)
    monkeypatch.setattr("core.interfaces.is_admin", lambda: True)
    monkeypatch.setattr("core.npcap_runtime.npcap_available", lambda: False)
    assert "NetGuardSetup.exe" in check_environment(require_network=False)[0]
    monkeypatch.setattr("core.npcap_runtime.npcap_available", lambda: True)
    assert check_environment(require_network=False) == []


def test_full_scanner_and_listener_dispatch_to_packet_capture(monkeypatch):
    from core import arp_scanner, arp_listener, pcap_scanner, pcap_listener
    monkeypatch.setattr(network_mode, "PACKET_CAPTURE", True)
    scan = Mock(return_value=["packet-results"])
    capture = Mock()
    monkeypatch.setattr(pcap_scanner, "scan_subnet", scan)
    monkeypatch.setattr(pcap_listener, "ArpListener", capture)
    iface = Mock()
    assert arp_scanner.scan_subnet(iface, timeout=1, rounds=2, start_offset=1024) == ["packet-results"]
    scan.assert_called_once_with(iface, 1, 2, None, 1024)
    callback = Mock()
    assert arp_listener.ArpListener(callback, iface) is capture.return_value
    capture.assert_called_once_with(callback, iface)
