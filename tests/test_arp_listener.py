"""Giám sát bảng ARP và gateway, không dùng bộ bắt gói."""
import time
from unittest.mock import Mock

import pytest

from core import arp_listener as module
from core.arp_listener import ArpListener
from core.interfaces import NetInterface


@pytest.fixture
def iface():
    return NetInterface("Wi-Fi", "test", "192.168.1.9", "255.255.255.0",
                        "192.168.1.1", "00:11:22:33:44:55", False, True, 7)


def wait_for(condition, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(.01)
    raise AssertionError("Listener không phục hồi")


def test_native_listener_retries_api_failure_and_stops(monkeypatch, iface):
    snapshot = Mock(side_effect=OSError(5, "denied"))
    monkeypatch.setattr(module, "neighbors", snapshot)
    monkeypatch.setattr(module, "resolve_ipv4", lambda *args: None)
    states = []
    listener = ArpListener(lambda value: None, iface, states.append)
    listener.INTERVAL_SEC = .01
    try:
        listener.start()
        wait_for(lambda: any(s["error"] for s in states))
        snapshot.side_effect = None
        snapshot.return_value = []
        wait_for(listener.is_running)
        assert states[-1]["mode"] == "windows_periodic"
        assert states[-1]["passive_capture"] is False
    finally:
        listener.stop()
    assert not listener.is_running() and not listener._thread.is_alive()


def test_cache_emits_only_changes_but_gateway_probes_are_fresh(monkeypatch, iface):
    mac = "00:11:22:33:44:66"
    monkeypatch.setattr(module, "neighbors", lambda index: [("192.168.1.20", mac), (iface.gateway, mac)])
    resolve = Mock(return_value="00:11:22:33:44:77")
    monkeypatch.setattr(module, "resolve_ipv4", resolve)
    values = []
    listener = ArpListener(values.append, iface)
    listener._poll()
    listener._poll()
    assert [(v.ip, v.source) for v in values] == [("192.168.1.20", "neighbor_cache"), (iface.gateway, "active_probe"), (iface.gateway, "active_probe")]
    assert all(c.args == (iface.gateway, iface.ip, iface.index) for c in resolve.call_args_list)


@pytest.mark.parametrize("ip,mac", [("10.0.0.20", "00:11:22:33:44:66"), ("192.168.1.255", "00:11:22:33:44:66"),
                                   ("192.168.1.20", "01:11:22:33:44:66"), ("192.168.1.20", "00:00:00:00:00:00")])
def test_invalid_or_out_of_scope_samples_are_filtered(iface, ip, mac):
    values = []
    ArpListener(values.append, iface)._emit(ip, mac, "neighbor_cache")
    assert not values


def test_cached_neighbor_does_not_become_online_presence(monkeypatch, iface):
    from backend import Backend
    from core.arp_listener import ArpObservation
    from db import repository
    from models import now
    backend = Backend()
    backend._arp_detector = Mock()
    backend._arp_detector.observe.return_value = []
    record = Mock()
    monkeypatch.setattr(repository, "record_observation", record)
    backend._emit_arp_observation(ArpObservation("192.168.1.20", "00:11:22:33:44:66", 2, False, now(), "neighbor_cache"))
    record.assert_not_called()
    backend._arp_detector.observe.assert_called_once()
    backend.stop()
