"""Mạng lớn dùng dải tính lười và phủ từng phần, không gửi gói thật."""
import ipaddress
from dataclasses import replace
from unittest.mock import Mock

import pytest

from config import OFFLINE_AFTER_MISSES, SETTINGS
from core.arp_scanner import ScanEntry, ScanResult
from core.interfaces import NetInterface, get_subnet_hosts
from core.scan_targets import IPv4Hosts
from core.settings import validate
from db import database, repository
from models import Device, now
from services.scan_loop import ScanLoop


@pytest.fixture
def iface():
    return NetInterface("Wi-Fi", "campus", "10.0.1.9", "255.255.192.0", "10.0.0.1",
                        "00:11:22:33:44:55", False, True, 7, "campus-profile")


def result_for(iface, offset, entries=()):
    hosts = get_subnet_hosts(iface)
    end = min(offset+1024, len(hosts))
    return ScanResult(entries, targets=hosts[offset:end], total_hosts=len(hosts),
                      offset=offset, end_offset=end, network=hosts.network)


@pytest.mark.parametrize("cidr,count", [("10.0.0.0/18", 16382), ("10.0.0.0/16", 65534),
                                      ("10.0.0.0/8", 16777214), ("0.0.0.0/0", 4294967294),
                                      ("192.0.2.0/31", 2), ("192.0.2.1/32", 1)])
def test_all_ipv4_sizes_are_lazy_and_keep_host_boundaries(monkeypatch, cidr, count):
    monkeypatch.setattr(ipaddress.IPv4Network, "hosts", Mock(side_effect=AssertionError("Không liệt kê subnet")))
    network = ipaddress.IPv4Network(cidr)
    hosts = IPv4Hosts(network)
    assert len(hosts) == count
    assert hosts[0] in hosts and hosts[-1] in hosts
    assert len(hosts[:1024]) == min(count, 1024)
    if network.prefixlen < 31:
        assert str(network.network_address) not in hosts
        assert str(network.broadcast_address) not in hosts


def test_large_custom_cidr_is_valid_but_still_must_belong_to_interface(monkeypatch, iface):
    assert validate({"scan_cidr": "10.0.0.0/18"})["scan_cidr"] == "10.0.0.0/18"
    monkeypatch.setitem(SETTINGS, "scan_cidr", "10.1.0.0/18")
    with pytest.raises(ValueError, match="nằm trong subnet"):
        get_subnet_hosts(iface)


def test_full_18_sweep_has_no_gaps_and_refresh_does_not_restart_at_first_page(monkeypatch, iface):
    offsets, coverage = [], set()
    def scan(chosen, *, start_offset, stop_event):
        offsets.append(start_offset)
        result = result_for(chosen, start_offset)
        assert not coverage.intersection(result.targets)
        coverage.update(result.targets)
        return result
    monkeypatch.setattr("services.scan_loop.scan_subnet", scan)
    loop = ScanLoop(interface_resolver=lambda: iface)
    for _ in range(16):
        result = loop.scan_once(reselect=True)
    assert offsets == list(range(0, 16382, 1024))
    assert coverage == set(get_subnet_hosts(iface))
    assert result.progress["sweep_complete"]
    assert result.progress["completed_hosts"] == 16382
    assert loop._scan_offset == 0


def test_failed_page_is_retried_and_connection_change_resets_cursor(monkeypatch, iface):
    active, offsets, fail = [iface], [], [False]
    def scan(chosen, *, start_offset, stop_event):
        offsets.append(start_offset)
        if fail[0]:
            fail[0] = False
            raise RuntimeError("capture hỏng")
        return result_for(chosen, start_offset)
    monkeypatch.setattr("services.scan_loop.scan_subnet", scan)
    loop = ScanLoop(interface_resolver=lambda: active[0])
    loop.scan_once()
    fail[0] = True
    with pytest.raises(RuntimeError, match="capture hỏng"):
        loop.scan_once()
    loop.scan_once()
    active[0] = replace(iface, profile_id="another-campus")
    loop.scan_once()
    assert offsets == [0, 1024, 1024, 0]


def test_only_hosts_in_successful_page_accumulate_misses(iface):
    inside = Device("10.0.0.20", "00:11:22:33:44:66", online=True)
    outside = Device("10.0.60.20", "00:11:22:33:44:77", online=True)
    repository.upsert_device(inside)
    repository.upsert_device(outside)
    loop = ScanLoop(interface_resolver=lambda: iface, scanner=lambda _: result_for(iface, 0))
    for _ in range(OFFLINE_AFTER_MISSES):
        loop.scan_once()
    assert not repository.get_device(inside.mac).online
    assert repository.get_device(outside.mac).online
    assert outside.mac not in loop._misses


def test_database_failure_does_not_skip_uncommitted_page(monkeypatch, iface):
    offsets = []
    def scan(chosen, *, start_offset, stop_event):
        offsets.append(start_offset)
        ip = get_subnet_hosts(chosen)[start_offset]
        mac = (0x020000000000+start_offset).to_bytes(6, "big").hex(":")
        return result_for(chosen, start_offset, [ScanEntry(ip, mac)])
    monkeypatch.setattr("services.scan_loop.scan_subnet", scan)
    loop = ScanLoop(interface_resolver=lambda: iface)
    loop.scan_once()
    original = repository.upsert_device
    monkeypatch.setattr(repository, "upsert_device", Mock(side_effect=RuntimeError("disk full")))
    with pytest.raises(RuntimeError, match="disk full"):
        loop.scan_once()
    assert len(repository.list_devices()) == 1
    monkeypatch.setattr(repository, "upsert_device", original)
    loop.scan_once()
    assert offsets == [0, 1024, 1024]
    assert len(repository.list_devices()) == 2


def test_cli_scan_continues_to_last_page_and_deduplicates_router(monkeypatch, capsys, iface):
    import main
    router = ScanEntry(iface.gateway, "00:11:22:33:44:66")
    own = ScanEntry(iface.ip, iface.mac, True)
    pages = [ScanResult([router], targets=[iface.gateway], total_hosts=3, offset=0, end_offset=2, network="test"),
             ScanResult([router, own], targets=[iface.ip], total_hosts=3, offset=2, end_offset=3, network="test")]
    scan = Mock(side_effect=pages)
    monkeypatch.setattr(main, "get_warnings", lambda: [])
    monkeypatch.setattr(main, "get_active_interface", lambda: iface)
    monkeypatch.setattr("core.arp_scanner.scan_subnet", scan)
    assert main.run_scan() == 0
    assert [call.kwargs["start_offset"] for call in scan.call_args_list] == [0, 2]
    text = capsys.readouterr().out
    assert "3/3" in text and "2 thiết bị" in text


def test_18_network_can_store_more_than_old_ten_thousand_device_cap(iface):
    stamp = now().isoformat()
    hosts = get_subnet_hosts(iface)
    def mac(index):
        return (0x020000000000+index).to_bytes(6, "big").hex(":")
    with database.transaction() as connection:
        connection.executemany("INSERT INTO Devices(mac,ip,first_seen,last_seen) VALUES(?,?,?,?)",
                               ((mac(i), hosts[i], stamp, stamp) for i in range(len(hosts)-1)))
    entry = ScanEntry(hosts[-1], mac(len(hosts)-1))
    page = result_for(iface, 15*1024, [entry])
    loop = ScanLoop(interface_resolver=lambda: iface, scanner=lambda _: page)
    loop.scan_once()
    assert repository.get_device(entry.mac).online
    with database.transaction() as connection:
        assert connection.execute("SELECT count(*) FROM Devices").fetchone()[0] == 16382
