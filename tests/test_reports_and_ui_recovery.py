import os
import time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QAbstractItemView

from backend import Backend
from db import repository
from models import Alert, Device, PingResult, now
from ui.device_columns import DeviceColumn as Col


@pytest.fixture
def window(monkeypatch):
    from ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr("ui.main_window.NetGuardTrayIcon", Mock())
    backend = Backend()
    ui = MainWindow(backend)
    yield backend, ui, app
    backend.stop()
    ui._device_timer.stop()
    ui._diagnosis_timer.stop()
    ui.deleteLater()
    app.processEvents()


def test_refresh_keeps_selection_item_and_scroll(window):
    backend, ui, _ = window
    device = Device("192.168.1.20", "00:11:22:33:44:66", name="Máy quen")
    repository.upsert_device(device)
    ui.refresh_devices()
    ui.device_table.selectRow(0)
    item = ui.device_table.item(0, Col.NAME)
    repository.upsert_device(replace(device, online=True))
    ui.refresh_devices()
    assert ui.device_table.item(0, Col.NAME) is item
    assert ui.device_table.selectedIndexes()
    assert not ui._refreshing


def test_load_failure_preserves_table_and_allows_later_save(window, monkeypatch):
    backend, ui, _ = window
    repository.upsert_device(Device("192.168.1.20", "00:11:22:33:44:66"))
    ui.refresh_devices()
    original = backend.list_devices
    monkeypatch.setattr(backend, "list_devices", Mock(side_effect=RuntimeError("temporary database error")))
    ui.refresh_devices()
    assert ui.device_table.rowCount() == 1
    assert not ui._refreshing
    monkeypatch.setattr(backend, "list_devices", original)
    ui.device_table.item(0, Col.TRUSTED).setCheckState(Qt.Checked)
    assert repository.list_devices()[0].trusted


def test_pending_edit_cannot_be_saved_into_a_new_connection_generation(window):
    backend, ui, _ = window
    device = Device("192.168.1.20", "00:11:22:33:44:66", name="Original")
    repository.upsert_device(device)
    ui.refresh_devices()
    backend._generation += 1
    ui.device_table.item(0, Col.NAME).setText("Stale edit")
    assert repository.get_device(device.mac).name == "Original"
    assert "Kết nối đã đổi" in ui.statusBar().currentMessage()


def test_refresh_waits_while_inline_editor_is_open(window):
    _, ui, _ = window
    repository.upsert_device(Device("192.168.1.20", "00:11:22:33:44:66"))
    ui.refresh_devices()
    item = ui.device_table.item(0, Col.NAME)
    ui.device_table.editItem(item)
    assert ui.device_table.state() == QAbstractItemView.EditingState
    ui.refresh_devices()
    assert ui.device_table.item(0, Col.NAME) is item
    assert ui._device_timer.isActive()


def test_many_device_signals_are_coalesced_into_one_refresh(window, monkeypatch):
    backend, ui, app = window
    reader = Mock(wraps=backend.list_devices)
    monkeypatch.setattr(backend, "list_devices", reader)
    for index in range(50):
        backend.device_updated.emit(Device("192.168.1.20", "00:11:22:33:44:66"))
    assert reader.call_count == 0
    deadline = time.monotonic()+3
    while reader.call_count == 0 and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert reader.call_count == 1


def test_service_error_is_persisted_and_reaches_alert_list(window):
    backend, ui, _ = window
    backend._service_status({"service": "scan", "running": False, "error": "capture failed"})
    assert any("capture failed" in a.message for a in repository.list_alerts())
    assert ui.alert_list.count() == 1


def test_alert_paging_search_and_acknowledgement(window):
    backend, ui, _ = window
    for index in range(110):
        repository.add_alert(Alert("info", f"Event {index}"))
    ui.refresh_alerts()
    assert ui.alert_list.count() == 100
    ui.change_alert_page(100)
    assert ui.alert_list.count() == 10
    ui.alert_search.setText("Event 109")
    ui.change_alert_page(0, reset=True)
    assert ui.alert_list.count() == 1
    ui.alert_list.setCurrentRow(0)
    ui.acknowledge_selected_alert()
    assert "Đã xử lý" in ui.alert_list.item(0).text()


def test_tray_has_packaged_icon_when_theme_is_empty(window, monkeypatch):
    from PySide6.QtGui import QIcon
    from ui.tray import NetGuardTrayIcon
    monkeypatch.setattr(QIcon, "fromTheme", lambda name: QIcon())
    tray = NetGuardTrayIcon()
    assert not tray.icon().isNull()


def test_report_uses_stored_context_and_sql_upper_bound(monkeypatch, tmp_path):
    backend = Backend()
    start = now()-timedelta(hours=1)
    end = now()
    session = repository.start_session({"name": "Card lúc đo", "ip": "192.168.1.9"})
    end = now()
    repository.add_ping(PingResult("router", 2, 0, end, "192.168.1.1", session))
    repository.add_ping(PingResult("router", 999, 0, end+timedelta(minutes=1), "10.0.0.1", "other"))
    captured = {}
    def build(data, path, stop=None):
        captured.update(data)
        Path(path).write_bytes(b"%PDF-test")
    monkeypatch.setattr("extras.pdf_report.build_report", build)
    backend.export_report(start, end, str(tmp_path / "report.pdf"))
    assert captured["interface"]["name"] == "Card lúc đo"
    assert captured["ping_stats"]["router"]["rtt_median_ms"] == 2
    assert captured["ping_stats"]["external"]["loss_pct"] is None
    assert captured["ping_stats"]["external"]["samples"] == 0


def test_report_failure_never_overwrites_previous_pdf(monkeypatch, tmp_path):
    backend = Backend()
    output = tmp_path / "report.pdf"
    output.write_bytes(b"previous")
    monkeypatch.setattr("extras.pdf_report.build_report", Mock(side_effect=RuntimeError("render failed")))
    with pytest.raises(RuntimeError):
        backend.export_report(now()-timedelta(hours=1), now(), str(output))
    assert output.read_bytes() == b"previous"
    assert list(tmp_path.glob(".netguard-*.pdf")) == []


def test_measurement_snapshot_cannot_modify_backend_state(window):
    backend, _, _ = window
    backend._latest_measurements = {"results": {}, "status": {"router": "original"}}
    snapshot = backend.get_latest_measurements()
    snapshot["status"]["router"] = "changed"
    assert backend.get_latest_measurements()["status"]["router"] == "original"


def test_report_picker_uses_vietnam_time_even_for_utc_input(window):
    from PySide6.QtCore import QDateTime
    _, ui, _ = window
    ui.end_time.setDateTime(QDateTime.fromString("2026-11-12T01:00:00Z", Qt.ISODate))
    assert ui.end_time.dateTime().toString("HH:mm") == "08:00"
    assert ui.end_time.dateTime().offsetFromUtc() == 7*3600


def test_late_queued_diagnosis_does_not_reappear_after_connection_reset(window):
    from models import Diagnosis
    backend, ui, _ = window
    old = Diagnosis("ok", "old network")
    backend._emit_diagnosis(old)
    backend._emit_connection(None)
    ui.on_diagnosis_changed(old)
    assert ui._latest_diagnosis is None


def test_backend_stop_does_not_close_database_while_worker_is_alive(window, monkeypatch):
    from db import database
    backend, _, _ = window
    worker = Mock()
    worker.stop.side_effect = RuntimeError("still running")
    backend._loop = worker
    close = Mock(wraps=database.close)
    monkeypatch.setattr(database, "close", close)
    with pytest.raises(RuntimeError, match="still running"):
        backend.stop()
    close.assert_not_called()
    assert backend._loop is worker
    worker.stop.side_effect = None


def test_real_pdf_build_works_with_only_declared_runtime_dependencies(tmp_path):
    from extras.pdf_report import build_report
    output = tmp_path / "report.pdf"
    build_report({"start": now(), "end": now(), "ping_stats": {
        "router": {"samples": 0, "loss_pct": None, "rtt_median_ms": None}},
        "interface": {"name": "Tên card tiếng Việt có dấu"}}, str(output))
    content = output.read_bytes()
    assert content.startswith(b"%PDF-")
    assert b"/FontFile2" in content
    assert len(content) > 10000


def test_settings_reject_invalid_cidr_and_save_atomically(tmp_path, monkeypatch):
    from core import settings
    monkeypatch.setattr(settings, "PATH", tmp_path / "settings.json")
    with pytest.raises(ValueError):
        settings.save({"scan_cidr": "10.0.0.0/8"})
    with pytest.raises(ValueError):
        settings.save({"ping_timeout": -1})
    settings.save({"scan_cidr": "192.168.1.0/24", "network_label": "Mạng riêng"})
    assert settings.load()["network_label"] == "Mạng riêng"
