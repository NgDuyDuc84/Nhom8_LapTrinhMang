"""Render kiểm tra theme bằng lịch sử có sẵn, không khởi động dịch vụ mạng."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QPA_FONTDIR'] = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from unittest.mock import Mock
from PySide6.QtWidgets import QApplication
from backend import Backend
import ui.main_window as module

app = QApplication([])
module.NetGuardTrayIcon = Mock()
backend = Backend()
window = module.MainWindow(backend, warnings=['VPN (CloudflareWARP): kết quả ping/traceroute có thể bị ảnh hưởng.'])
window.resize(1280, 840)
window.show()
output = Path(__file__).resolve().parent / 'theme-preview'
output.mkdir(parents=True, exist_ok=True)
for index, name in enumerate(('devices', 'alerts', 'diagnosis', 'report')):
    window.tabs.setCurrentIndex(index)
    app.processEvents()
    window.grab().save(str(output / (name + '.png')))
window.tabs.setCurrentIndex(0)
if window.device_table.rowCount():
    window.device_table.selectRow(0)
    app.processEvents()
    window.grab().save(str(output / 'selected.png'))
    dialog = module.DeviceDialog(backend.list_devices()[0], window)
    dialog.show()
    app.processEvents()
    dialog.grab().save(str(output / 'dialog.png'))
    dialog.hide()
backend.stop()
print('Rendered four tabs, selected row and device dialog to', output)
