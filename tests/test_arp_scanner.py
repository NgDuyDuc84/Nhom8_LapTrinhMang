"""Quét Windows với native resolver giả; không gửi gói tin thật."""
from dataclasses import replace
from datetime import datetime
import threading
from unittest.mock import Mock

import pytest

from core import arp_scanner as scanner
from core.interfaces import NetInterface
from config import OFFLINE_AFTER_MISSES
from db import repository
from models import Device
from services.scan_loop import ScanLoop


@pytest.fixture
def iface():
    return NetInterface("Wi-Fi", "test", "192.168.1.9", "255.255.255.0",
                        "192.168.1.1", "00:11:22:33:44:55", False, True, 7)


@pytest.fixture
def resolver(monkeypatch):
    resolve = Mock(return_value=None)
    monkeypatch.setattr(scanner, "resolve_ipv4", resolve)
    monkeypatch.setattr(scanner, "get_subnet_hosts", lambda iface: [iface.gateway, iface.ip, "192.168.1.20"])
    return resolve


def test_native_scan_selects_source_and_interface_and_adds_self(resolver, iface):
    resolver.side_effect = lambda ip, source, index: {iface.gateway: "aa:bb:cc:dd:ee:ff", "192.168.1.20": "00:11:22:33:44:66"}.get(ip)
    result = scanner.scan_subnet(iface, rounds=2)
    assert result == [scanner.ScanEntry(iface.gateway, "aa:bb:cc:dd:ee:ff"),
                      scanner.ScanEntry(iface.ip, iface.mac, True),
                      scanner.ScanEntry("192.168.1.20", "00:11:22:33:44:66")]
    assert resolver.call_count == 4
    assert all(c.args[1:] == (iface.ip, iface.index) for c in resolver.call_args_list)
    assert not any(c.args[0] == iface.ip for c in resolver.call_args_list)


def test_no_replies_is_valid_self_only_scan(resolver, iface):
    assert scanner.scan_subnet(iface, rounds=1) == [scanner.ScanEntry(iface.ip, iface.mac, True)]


@pytest.mark.parametrize("failure", [PermissionError("access denied"), OSError(87, "invalid interface"), OSError(1231, "network lost")])
def test_api_errors_discard_whole_scan(resolver, iface, failure):
    resolver.side_effect = failure
    with pytest.raises(RuntimeError, match="Không hoàn tất"):
        scanner.scan_subnet(iface, rounds=1)


def test_large_subnet_has_bounded_page_and_probes_gateway_every_page(monkeypatch, iface):
    from core.interfaces import get_subnet_hosts
    monkeypatch.setattr(scanner, "get_subnet_hosts", get_subnet_hosts)
    resolve = Mock(return_value=None)
    monkeypatch.setattr(scanner, "resolve_ipv4", resolve)
    large = replace(iface, ip="10.0.1.9", gateway="10.0.0.1", netmask="255.255.192.0")
    result = scanner.scan_subnet(large, rounds=1, start_offset=1024)
    assert result.total_hosts == 16382 and result.next_offset == 1152
    assert len(result.targets) == 129 and large.gateway in result.targets
    assert {c.args[0] for c in resolve.call_args_list} == result.targets


def test_cancel_stops_scheduling_and_joins_active_workers(monkeypatch, iface):
    stop = threading.Event()
    calls = []
    def resolve(*args):
        calls.append(args)
        stop.set()
        return None
    monkeypatch.setattr(scanner, "resolve_ipv4", resolve)
    monkeypatch.setattr(scanner, "MAX_WORKERS", 1)
    with pytest.raises(RuntimeError, match="hủy"):
        scanner.scan_subnet(iface, rounds=2, stop_event=stop)
    assert len(calls) == 1
    assert not any(t.name.startswith("netguard-arp_") for t in threading.enumerate())


def test_cancel_before_scan_performs_no_io(resolver, iface):
    stop = threading.Event()
    stop.set()
    with pytest.raises(RuntimeError, match="hủy"):
        scanner.scan_subnet(iface, stop_event=stop)
    resolver.assert_not_called()


def test_failed_native_scan_preserves_presence_and_next_scan_recovers(resolver, iface):
    moment = datetime(2026, 11, 11, 9, 0)
    device = Device(ip="192.168.1.20", mac="00:11:22:33:44:66", name="Máy đã biết",
                    note="Giữ ghi chú", trusted=True, first_seen=moment, last_seen=moment)
    repository.upsert_device(device)
    repository.set_online(device.mac, True, ts=moment)
    before = repository.get_device(device.mac)
    presence = repository.get_presence(device.mac, since=moment)
    on_scan = Mock()
    loop = ScanLoop(interface_resolver=lambda: iface,
                    scanner=lambda chosen: scanner.scan_subnet(chosen, rounds=1), on_scan=on_scan)
    loop._update_interface(iface)
    loop._misses[device.mac] = 1
    resolver.side_effect = OSError(5, "denied")
    for _ in range(OFFLINE_AFTER_MISSES + 1):
        with pytest.raises(RuntimeError):
            loop.scan_once()
        assert loop._misses == {device.mac: 1}
        assert repository.list_devices() == [before]
        assert repository.get_presence(device.mac, since=moment) == presence
    on_scan.assert_not_called()
    resolver.side_effect = lambda ip, *args: device.mac if ip == device.ip else None
    loop.scan_once()
    stored = repository.get_device(device.mac)
    assert stored.online and (stored.name, stored.note, stored.trusted) == (before.name, before.note, before.trusted)
    assert loop._misses[device.mac] == 0
    on_scan.assert_called_once()
