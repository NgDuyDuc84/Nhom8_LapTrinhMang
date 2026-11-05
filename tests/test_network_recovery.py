"""Hồi quy khi card mất kết nối, đổi IP và kết nối lại; không gửi gói thật."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import interfaces
from core.interfaces import NetInterface
from models import Hop
from services.ping_monitor import PingMonitor
from services.scan_loop import ScanLoop


@pytest.fixture
def iface():
    return NetInterface('Wi-Fi', 'test adapter', '192.168.1.7', '255.255.255.0',
                        '192.168.1.1', '00:11:22:33:44:55', False, True, 7)


@pytest.mark.parametrize('ip', ['', '0.0.0.0', '127.0.0.1', '169.254.1.2', '224.0.0.1', 'invalid'])
def test_invalid_source_address(ip):
    assert not interfaces._has_usable_ipv4(ip)


@pytest.mark.parametrize('mask,up', [('', True), ('255.255.255.0', False)])
def test_incomplete_or_disconnected_card_is_not_selected(monkeypatch, iface, mask, up):
    monkeypatch.setattr(interfaces, 'list_interfaces', lambda: [replace(iface, netmask=mask, is_up=up)])
    with pytest.raises(RuntimeError):
        interfaces.get_active_interface()


def test_scapy_cached_ip_is_not_used(monkeypatch):
    import scapy.all
    cached = SimpleNamespace(index=7, name='Wi-Fi', description='test',
                             mac='00:11:22:33:44:55', ips={4: ['192.168.1.7']})
    monkeypatch.setattr(scapy.all, 'conf', SimpleNamespace(ifaces={7: cached}))
    monkeypatch.setattr(interfaces, '_ipv4_table', lambda: {})
    monkeypatch.setattr(interfaces, '_gateway_table', lambda: {})
    monkeypatch.setattr(interfaces, '_link_table', lambda: {7: False})
    actual = interfaces.list_interfaces()[0]
    assert (actual.ip, actual.netmask, actual.is_up) == ('', '', False)


def test_link_down_overrides_retained_ip(monkeypatch, iface):
    import scapy.all
    cached = SimpleNamespace(index=7, name=iface.name, description='test', mac=iface.mac)
    monkeypatch.setattr(scapy.all, 'conf', SimpleNamespace(ifaces={7: cached}))
    monkeypatch.setattr(interfaces, '_ipv4_table', lambda: {7: (iface.ip, iface.netmask)})
    monkeypatch.setattr(interfaces, '_gateway_table', lambda: {7: iface.gateway})
    monkeypatch.setattr(interfaces, '_link_table', lambda: {7: False})
    assert not interfaces.list_interfaces()[0].is_up


def test_preferred_card_refreshes_ip_and_index(monkeypatch, iface):
    current = replace(iface, index=19, ip='192.168.2.8', gateway='192.168.2.1')
    monkeypatch.setattr(interfaces, 'list_interfaces', lambda: [current])
    assert interfaces.get_active_interface(iface) == current


def test_same_wifi_card_can_reconnect_with_randomized_mac(monkeypatch, iface):
    current = replace(iface, mac='02:11:22:33:44:66', index=19)
    monkeypatch.setattr(interfaces, 'list_interfaces', lambda: [current])
    assert interfaces.get_active_interface(iface) == current


def test_preferred_card_does_not_silently_switch_network(monkeypatch, iface):
    other = replace(iface, name='Ethernet', mac='00:11:22:33:44:66')
    monkeypatch.setattr(interfaces, 'list_interfaces', lambda: [other])
    with pytest.raises(RuntimeError, match='Wi-Fi'):
        interfaces.get_active_interface(iface)


def test_large_subnet_rejected_before_host_enumeration(iface):
    with pytest.raises(ValueError, match='MAX_SCAN_HOSTS'):
        interfaces.get_subnet_hosts(replace(iface, netmask='255.0.0.0'))


@pytest.fixture
def saved_pings(monkeypatch):
    saved = []
    monkeypatch.setattr('services.ping_monitor.repository.add_ping', saved.append)
    return saved


def test_missing_gateway_is_reported_immediately(iface, saved_pings):
    diagnoses, cycles = [], []
    pinger = Mock()
    monitor = PingMonitor(interface_resolver=lambda: replace(iface, gateway=''),
                          pinger=pinger, on_diagnosis=diagnoses.append, on_cycle=cycles.append)
    monitor._cycle()
    assert diagnoses[0].verdict == 'unknown'
    assert 'không có gateway' in diagnoses[0].text
    assert monitor.target_status['router'] == 'không có gateway'
    assert cycles == [dict.fromkeys(('router', 'isp', 'external'))]
    pinger.assert_not_called()
    assert not saved_pings


def test_socket_failure_does_not_count_as_packet_loss(iface, saved_pings):
    cycles = []
    def pinger(address, timeout):
        if address == iface.gateway:
            return 2.0
        raise RuntimeError('source address unavailable')
    monitor = PingMonitor(interface_resolver=lambda: iface, pinger=pinger, on_cycle=cycles.append)
    monitor._cycle()
    assert [item.target for item in saved_pings] == ['router']
    assert not monitor._history['external']
    assert cycles[-1]['external'] is None
    assert 'lỗi đo' in monitor.target_status['external']


def test_actual_ping_timeout_still_counts_as_packet_loss(iface, saved_pings):
    monitor = PingMonitor(interface_resolver=lambda: iface, pinger=lambda address, timeout: None)
    monitor._cycle()
    assert len(saved_pings) == 2
    assert all(item.rtt_ms is None and item.loss_pct == 100 for item in saved_pings)


def test_offline_start_recovers_then_detects_another_disconnect(iface, saved_pings):
    resolver = Mock(side_effect=[RuntimeError('offline'), iface, RuntimeError('offline'), iface])
    diagnoses = []
    monitor = PingMonitor(interface_resolver=resolver, pinger=lambda address, timeout: 2.0,
                          on_diagnosis=diagnoses.append)
    monitor._cycle()
    assert diagnoses[-1].verdict == 'home_issue'
    assert monitor.target_status['router'] == 'chưa kết nối LAN'
    monitor._cycle()
    assert len(monitor._history['router']) == 1
    monitor._isp_ip = '10.0.0.1'
    monitor._cycle()
    assert not monitor._history['router'] and monitor._isp_ip is None
    monitor._cycle()
    assert len(monitor._history['router']) == 1
    assert monitor.last_error is None


def test_new_ip_clears_statistics_and_isp(iface, saved_pings):
    current = replace(iface, ip='192.168.2.8', gateway='192.168.2.1')
    resolver = Mock(side_effect=[iface, current])
    pinger = Mock(return_value=3.0)
    monitor = PingMonitor(interface_resolver=resolver, pinger=pinger)
    monitor._cycle()
    monitor._isp_ip = '10.0.0.1'
    monitor._cycle()
    assert len(monitor._history['router']) == 1
    assert monitor._isp_ip is None
    assert pinger.call_args_list[-2].args[0] == current.gateway


def test_default_pinger_uses_updated_source(monkeypatch, iface, saved_pings):
    updated = replace(iface, ip='192.168.1.9')
    ping = Mock(return_value=2.0)
    monkeypatch.setattr('services.ping_monitor.ping_once', ping)
    monitor = PingMonitor(iface=iface, interface_resolver=Mock(side_effect=[iface, updated]))
    monitor._cycle()
    monitor._cycle()
    assert ping.call_args.kwargs['source'] == updated.ip


def test_stale_traceroute_cannot_restore_old_isp(iface):
    updated = replace(iface, gateway='192.168.2.1', ip='192.168.2.9')
    monitor = PingMonitor(interface_resolver=lambda: iface)
    monitor._set_interface(iface)
    old_generation = monitor._network_generation
    def tracer(*args, **kwargs):
        monitor._set_interface(updated)
        return [Hop(1, iface.gateway, 1.0), Hop(2, '10.0.0.1', 3.0)]
    monitor._tracer = tracer
    monitor._discover_isp(iface, old_generation)
    assert monitor._isp_ip is None


def test_offline_does_not_start_traceroute():
    tracer = Mock()
    monitor = PingMonitor(tracer=tracer)
    monitor._maybe_start_route_discovery()
    tracer.assert_not_called()
    assert monitor._route_thread is None


def test_scan_refreshes_card_and_preserves_devices_on_failure(monkeypatch, iface):
    updated = replace(iface, ip='192.168.2.8', gateway='192.168.2.1')
    scanner = Mock(return_value=[])
    changed = []
    monkeypatch.setattr('services.scan_loop.repository.list_devices', lambda: [])
    loop = ScanLoop(iface=iface, interface_resolver=Mock(side_effect=[
        iface, RuntimeError('offline'), updated,
    ]), scanner=scanner, on_interface=changed.append)
    loop.scan_once()
    mark_offline = Mock()
    monkeypatch.setattr(loop, '_mark_offline', mark_offline)
    with pytest.raises(RuntimeError, match='offline'):
        loop.scan_once()
    mark_offline.assert_not_called()
    loop.scan_once()
    assert changed == [iface, None, updated]
    assert [call.args[0] for call in scanner.call_args_list] == [iface, updated]


def test_ping_source_error_is_readable():
    from core.icmp import _friendly_error
    assert 'IP nguồn' in str(_friendly_error(OSError('The requested address cannot be assigned to the socket')))


def test_trace_without_gateway_fails_before_probing(monkeypatch, iface):
    from core.traceroute import trace
    monkeypatch.setattr(interfaces, 'get_active_interface', lambda: replace(iface, gateway=''))
    with pytest.raises(RuntimeError, match='gateway'):
        trace('1.1.1.1')


def test_windows_trace_does_not_hide_transmit_error(monkeypatch):
    from core.traceroute import _windows_trace
    process = Mock(returncode=0)
    process.communicate.return_value = ('  1  Transmit error: code 1231.\n', '')
    monkeypatch.setattr('core.traceroute.shutil.which', lambda name: 'tracert.exe')
    monkeypatch.setattr('core.traceroute.subprocess.Popen', Mock(return_value=process))
    with pytest.raises(RuntimeError, match='probe traceroute'):
        _windows_trace('1.1.1.1', 15, 1)


def test_windows_trace_timeout_hop_is_still_valid(monkeypatch):
    from core.traceroute import _windows_trace
    process = Mock(returncode=0)
    process.communicate.return_value = (
        '  1    *    *    *    Request timed out.\n'
        '  2    2 ms    4 ms    3 ms    10.0.0.1\n', '',
    )
    monkeypatch.setattr('core.traceroute.shutil.which', lambda name: 'tracert.exe')
    monkeypatch.setattr('core.traceroute.subprocess.Popen', Mock(return_value=process))
    hops = _windows_trace('1.1.1.1', 15, 1)
    assert hops[0].ip is None
    assert hops[1].ip == '10.0.0.1' and hops[1].rtt_ms == 3.0
