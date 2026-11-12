"""Kiểm tra thông báo và dọn tài nguyên CLI khi khởi động offline."""

from unittest.mock import Mock

import pytest

import main


@pytest.fixture
def offline_cli(monkeypatch):
    check = Mock(return_value=[])
    monkeypatch.setattr(main, 'check_environment', check)
    monkeypatch.setattr(main, 'get_warnings', lambda: [])
    monkeypatch.setattr(main, 'get_active_interface', Mock(side_effect=RuntimeError('offline')))
    monkeypatch.setattr(main.time, 'sleep', Mock(side_effect=KeyboardInterrupt))
    initialize, close = Mock(), Mock()
    monkeypatch.setattr('db.database.initialize', initialize)
    monkeypatch.setattr('db.database.close', close)
    return check, initialize, close


def test_diagnose_starts_offline_and_displays_measurement_error(monkeypatch, offline_cli, capsys):
    monitor = Mock()
    monitor.is_running.return_value = True
    monitor.target_status = {
        'router': 'không có gateway', 'isp': 'chưa xác định hop', 'external': 'lỗi đo: socket',
    }
    def make_monitor(**kwargs):
        monitor.start.side_effect = lambda: kwargs['on_cycle'](dict.fromkeys(monitor.target_status))
        return monitor
    monkeypatch.setattr('services.ping_monitor.PingMonitor', make_monitor)
    assert main.run_diagnose() == 0
    output = capsys.readouterr().out
    assert 'đang chờ kết nối' in output
    assert 'external=lỗi đo: socket' in output
    assert 'router=không có gateway' in output
    assert 'Đã dừng chẩn đoán' in output
    monitor.stop.assert_called_once()
    offline_cli[0].assert_called_once_with(require_network=False)
    offline_cli[2].assert_called_once()


def test_monitor_starts_offline_and_stops_cleanly(monkeypatch, offline_cli, capsys):
    loop = Mock()
    loop.is_running.return_value = True
    monkeypatch.setattr('services.scan_loop.ScanLoop', Mock(return_value=loop))
    monkeypatch.setattr('services.baseline.is_first_run', lambda: False)
    assert main.run_monitor() == 0
    output = capsys.readouterr().out
    assert 'Đang chờ kết nối LAN' in output
    assert 'Đã dừng theo dõi' in output
    loop.stop.assert_called_once()
    offline_cli[0].assert_called_once_with(require_network=False)
    offline_cli[2].assert_called_once()


def test_cli_keeps_listener_supervisor_after_start_failure_and_stops_it(monkeypatch):
    from core.interfaces import NetInterface
    iface = NetInterface("Wi-Fi", "test", "192.168.1.9", "255.255.255.0",
                         "192.168.1.1", "00:11:22:33:44:55", False, True, 7)
    monkeypatch.setattr(main, "check_environment", lambda **kwargs: [])
    monkeypatch.setattr(main, "get_warnings", lambda: [])
    monkeypatch.setattr(main, "get_active_interface", lambda: iface)
    listener = Mock()
    listener.start.side_effect = RuntimeError("capture open failed")
    monkeypatch.setattr("core.arp_listener.ArpListener", Mock(return_value=listener))
    loop = Mock()
    loop.is_running.return_value = True
    def create_loop(**kwargs):
        loop.start.side_effect = lambda: kwargs["on_interface"](iface)
        return loop
    monkeypatch.setattr("services.scan_loop.ScanLoop", create_loop)
    monkeypatch.setattr(main.time, "sleep", Mock(side_effect=KeyboardInterrupt))
    assert main.run_monitor() == 0
    listener.stop.assert_called_once()
