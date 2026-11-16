"""Đóng GUI phải thoát event loop và dừng worker; I/O mạng được thay bằng giả."""
from pathlib import Path
import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("history", [False, True], ids=["monitor", "history"])
def test_closing_window_exits_application_and_stops_services(tmp_path, history):
    # Event loop thật trong tiến trình riêng, không ảnh hưởng QApplication của test khác.
    script = """
import sys
import threading
from unittest.mock import Mock
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from backend import Backend
from core.interfaces import NetInterface
from db import database
import core.interfaces
import core.arp_listener
import services.scan_loop
import services.ping_monitor
import services.device_identification
import main

database.DB_PATH = sys.argv[1]
iface = NetInterface('Wi-Fi', 'test', '192.168.1.9', '255.255.255.0',
                     '192.168.1.1', '00:11:22:33:44:55', False, True, 7)
resolve = lambda preferred=None: iface
core.interfaces.get_active_interface = resolve
services.scan_loop.get_active_interface = resolve
services.ping_monitor.get_active_interface = resolve
services.scan_loop.scan_subnet = lambda chosen, **kwargs: []
services.ping_monitor.ping_once = lambda *args, **kwargs: 1.0
services.ping_monitor.trace = lambda *args, **kwargs: []
services.device_identification.discover_device_hints = lambda *args: {}
core.arp_listener.ArpListener = Mock()
main.check_environment = lambda **kwargs: []
main.get_warnings = lambda: []

instances = []
class ObservedBackend(Backend):
    def __init__(self):
        super().__init__()
        self.stop_calls = 0
        instances.append(self)
    def stop(self):
        self.stop_calls += 1
        super().stop()

import backend
backend.Backend = ObservedBackend
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
closed = []
active_before_close = []
def close_window():
    from ui.main_window import MainWindow
    window = next(w for w in app.topLevelWidgets() if isinstance(w, MainWindow))
    active_before_close.extend(t.name for t in threading.enumerate() if t.name.startswith('netguard-'))
    closed.append(window.close())

QTimer.singleShot(0, close_window)
# Hành vi cũ chỉ ẩn cửa sổ sẽ không tự thoát; watchdog giúp test không bị treo.
QTimer.singleShot(5000, lambda: app.exit(91))
history = sys.argv[2] == 'history'
result = main.run_gui(history=history)
assert result == 0, result
assert closed == [True], closed
assert app.quitOnLastWindowClosed()
assert instances[0].stop_calls == 1
assert not database._connections
assert not [t.name for t in threading.enumerate() if t.name.startswith('netguard-')]
if history:
    assert not active_before_close
else:
    assert 'netguard-scan' in active_before_close
    assert 'netguard-ping' in active_before_close
    assert 'netguard-identification' in active_before_close
    assert instances[0]._loop is None
    assert instances[0]._ping_monitor is None
    assert instances[0]._identifier is None
print('closed and stopped')
"""
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "gui.db"), "history" if history else "monitor"],
        cwd=Path(__file__).resolve().parents[1], env=environment,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "closed and stopped" in result.stdout
