"""Kiểm tra UI với backend và SQLite riêng, không gửi gói tin ra mạng."""

import os
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.device_columns import DeviceColumn as Col


@pytest.fixture(scope='module')
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def real_ui(monkeypatch, tmp_path, qt_app):
    from backend import Backend
    from db import database

    database.close()
    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 'live-ui.db'))
    monkeypatch.setattr('ui.main_window.NetGuardTrayIcon', Mock())
    backend = Backend()
    window = MainWindow(backend)
    yield backend, window
    backend.stop()
    window.deleteLater()
    qt_app.processEvents()
    database.close()


def test_real_ui_does_not_seed_devices_or_claim_network_ok(real_ui):
    backend, window = real_ui
    assert window.windowTitle() == 'NetGuard - Giám sát mạng LAN'
    assert window.device_table.rowCount() == 0
    assert window.verdict_label.text() != 'ok'
    assert 'Chưa có kết luận' in window.diagnosis_text.text()


def test_real_ui_uses_backend_diagnosis_even_without_ping_history(real_ui):
    from models import Diagnosis

    backend, window = real_ui
    backend._emit_diagnosis(Diagnosis('home_issue', 'Mất kết nối Wi-Fi được xác nhận.'))
    assert window.verdict_label.text() == 'home_issue'
    assert window.diagnosis_text.text() == 'Mất kết nối Wi-Fi được xác nhận.'


def test_saved_successful_ping_does_not_become_live_measurement(real_ui):
    from db import repository
    from models import PingResult

    _, window = real_ui
    repository.add_ping(PingResult('router', 2.0, 0.0))
    window.refresh_diagnosis()
    assert window.verdict_label.text() != 'ok'
    assert window.measurement_table.item(0, 2).text() == '—'
    assert window.measurement_table.item(0, 4).text() == 'Chưa đo trong phiên'


def test_real_scan_updates_ui_and_marks_cached_devices_unverified(real_ui):
    from core.arp_scanner import ScanEntry
    from core.interfaces import NetInterface
    from db import repository
    from models import Device
    from services.scan_loop import ScanLoop

    backend, window = real_ui
    iface = NetInterface('Wi-Fi', 'test', '192.168.1.9', '255.255.255.0',
                         '192.168.1.1', '02:11:22:33:44:55', False, True, 7)
    repository.upsert_device(Device('192.168.1.1', '00:11:22:33:44:66', online=True))
    backend._emit_connection(iface)
    window.refresh_devices()
    assert window.device_table.item(0, Col.STATUS).text() == 'Chưa xác minh trong phiên'
    entry = ScanEntry(iface.ip, iface.mac, True)
    loop = ScanLoop(interface_resolver=lambda: iface, scanner=lambda chosen: [entry],
                    on_device=backend._emit_device, on_scan=backend._emit_scan)
    loop.scan_once()
    row = window._device_rows[iface.mac]
    assert window.device_table.item(row, Col.NAME).text() == 'Máy tính này'
    assert window.device_table.item(row, Col.IP).text() == iface.ip
    assert window.device_table.item(row, Col.STATUS).text() == 'Online'
    assert 'MAC riêng tư' in window.device_table.item(row, Col.MANUFACTURER).text()
    backend._emit_connection(None)
    assert window.device_table.item(row, Col.STATUS).text() == 'Chưa xác minh (mất LAN)'


def test_real_ping_cycle_and_socket_error_reach_ui(real_ui):
    from core.interfaces import NetInterface
    from services.ping_monitor import PingMonitor

    backend, window = real_ui
    iface = NetInterface('Wi-Fi', 'test', '192.168.1.9', '255.255.255.0',
                         '192.168.1.1', '00:11:22:33:44:55', False, True, 7)
    def pinger(address, timeout):
        if address == iface.gateway:
            return 4.25
        raise RuntimeError('source address unavailable')
    backend._ping_monitor = PingMonitor(
        interface_resolver=lambda: iface, pinger=pinger,
        on_cycle=backend._emit_measurements, on_interface=backend._emit_connection,
    )
    backend._ping_monitor._cycle()
    assert window.measurement_table.item(0, 1).text() == iface.gateway
    assert window.measurement_table.item(0, 2).text() == '4.25 ms'
    assert window.measurement_table.item(2, 2).text() == '—'
    assert 'lỗi đo' in window.measurement_table.item(2, 4).text()
    assert iface.ip in window.connection_label.text()


def test_default_main_uses_real_gui(monkeypatch):
    import main

    monkeypatch.setattr(main, 'prepare_gui_launch', Mock(return_value=True))
    run_gui = Mock(return_value=0)
    monkeypatch.setattr(main, 'run_gui', run_gui)
    assert main.main([]) == 0
    run_gui.assert_called_once_with()


def test_removed_demo_option_is_rejected():
    import main

    with pytest.raises(SystemExit) as stopped:
        main.build_parser().parse_args(['--fake'])
    assert stopped.value.code == 2


def test_direct_ui_entrypoint_uses_shared_main(monkeypatch):
    import runpy
    import main
    from pathlib import Path

    start = Mock(return_value=0)
    monkeypatch.setattr(main, 'main', start)
    with pytest.raises(SystemExit) as stopped:
        runpy.run_path(str(Path(__file__).resolve().parents[1] / 'ui/main_window.py'), run_name='__main__')
    assert stopped.value.code == 0
    start.assert_called_once_with()


def test_themed_checkbox_still_saves_trust_by_mouse_and_keyboard(real_ui, qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from db import repository
    from models import Device

    backend, window = real_ui
    device = Device('192.168.1.20', '00:11:22:33:44:55')
    repository.upsert_device(device)
    window.refresh_devices()
    window.show()
    qt_app.processEvents()
    table = window.device_table
    checkbox = table.visualItemRect(table.item(0, Col.TRUSTED)).center()
    QTest.mouseClick(table.viewport(), Qt.LeftButton, Qt.NoModifier, checkbox)
    assert repository.get_device(device.mac).trusted
    table.setCurrentCell(0, Col.TRUSTED)
    QTest.keyClick(table, Qt.Key_Space)
    assert not repository.get_device(device.mac).trusted
    window.hide()
