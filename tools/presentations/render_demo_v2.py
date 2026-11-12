"""Capture the real Qt UI with isolated in-memory demo data. No network or database IO."""
import os, sys, math
from pathlib import Path
from datetime import timedelta
from unittest.mock import Mock
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QT_QPA_FONTDIR']=r'C:\Windows\Fonts'
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from PySide6.QtWidgets import QApplication
from backend import BackendBase
from models import Device, PingResult, Diagnosis, now
from services.alerts import make_stranger_alert
import ui.main_window as ui

class DemoData(BackendBase):
    def __init__(self):
        super().__init__()
        self.devices=[
            Device('192.168.1.1','00:11:22:33:44:01',name='Router',trusted=True,online=True),
            Device('192.168.1.10','00:11:22:33:44:10',name='Laptop',trusted=True,online=True,is_self=True),
            Device('192.168.1.20','02:11:22:33:44:20',name='Điện thoại',note='Thiết bị cá nhân',trusted=True,online=True),
            Device('192.168.1.25','02:11:22:33:44:25',name='',trusted=False,online=True),
        ]
        stamp=now()
        self.hist={}
        for target,base in [('router',3.0),('isp',12.0),('external',25.0)]:
            self.hist[target]=[PingResult(target,round(base+math.sin(i*.31)*base*.17+(5 if i in (36,78) else 0),2),0,stamp-timedelta(seconds=(119-i)*2)) for i in range(120)]
        self.alerts=[make_stranger_alert(self.devices[-1])]
    def start(self): pass
    def stop(self): pass
    def list_devices(self):return self.devices
    def get_alerts(self,limit=100,**kwargs):return self.alerts[:limit]
    def get_connection_status(self):return dict(connected=True,name='Wi-Fi',ip='192.168.1.10',netmask='255.255.255.0',gateway='192.168.1.1')
    def get_ping_history(self,target,minutes):return self.hist[target]
    def get_latest_measurements(self):return dict(results={k:v[-1] for k,v in self.hist.items()},addresses={'router':'192.168.1.1','isp':'10.0.0.1','external':'1.1.1.1'})
    def get_latest_diagnosis(self):return Diagnosis('ok','Mạng bình thường: ba mốc ping đều ổn định. (Dữ liệu mô phỏng)')
    def set_trusted(self,mac,trusted):pass
    def rename(self,mac,name,note):pass

app=QApplication([])
ui.NetGuardTrayIcon=Mock()
demo=DemoData()
window=ui.MainWindow(demo,warnings=['MÔ PHỎNG DEMO: dữ liệu trong bộ nhớ, không đo mạng thật.'])
window.resize(1440,900)
window.show()
app.processEvents()
out=ROOT/'.presentation-build/demo-v2'
out.mkdir(parents=True,exist_ok=True)
window.device_table.grab().save(str(out/'devices.png'))
window.tabs.setCurrentIndex(1)
window.alert_list.setStyleSheet('QListWidget { font-size: 18px; background: white; }')
window.alert_banner.setStyleSheet('QLabel { font-size: 18px; color: #C2410C; background: #FFEDD5; padding: 12px; }')
app.processEvents()
window.alerts_tab.grab().save(str(out/'alerts.png'))
window.tabs.setCurrentIndex(2)
window._measurements=demo.get_latest_measurements()
window._latest_diagnosis=demo.get_latest_diagnosis()
window.refresh_diagnosis()
app.processEvents()
window.diagnosis_plot.grab().save(str(out/'rtt.png'))
dialog=ui.DeviceDialog(demo.devices[2],window)
dialog.resize(620,300)
dialog.setStyleSheet('QLabel,QLineEdit,QPushButton { font-size: 22px; } QLineEdit { min-height: 42px; }')
dialog.show()
dialog.name_edit.clearFocus()
app.processEvents()
dialog.grab().save(str(out/'dialog.png'))
dialog.hide();window.hide()
print('Captured 4 demo screenshots, using isolated data only.')
