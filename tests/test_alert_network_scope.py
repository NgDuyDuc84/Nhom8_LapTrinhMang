"""Cảnh báo trên UI phải thuộc đúng mạng, kể cả khi mạng mới chưa có sự kiện."""
import os
from dataclasses import replace
import threading
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from backend import Backend
from core.interfaces import NetInterface
from core.network_context import network_id, network_scope
from db import repository
from models import Alert
from ui.main_window import MainWindow


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def networks():
    first = NetInterface("Wi-Fi", "test", "192.168.1.9", "255.255.255.0", "192.168.1.1",
                         "00:11:22:33:44:55", False, True, 7, "network-A", "adapter-A")
    return first, replace(first, profile_id="network-B")


def close_ui(backend, ui, app):
    backend.stop()
    ui._device_timer.stop()
    ui._diagnosis_timer.stop()
    ui.deleteLater()
    app.processEvents()


def test_live_start_does_not_display_legacy_alerts_before_network_is_known(app):
    repository.add_alert(Alert("warning", "Cảnh báo mạng cũ chưa định danh"))
    backend = Backend()
    ui = MainWindow(backend)
    try:
        assert ui.alert_list.count() == 0
        assert backend.get_alerts() == []
    finally:
        close_ui(backend, ui, app)


def test_switch_to_network_with_no_alerts_clears_previous_list_immediately(app, networks):
    first, second = networks
    backend = Backend()
    backend._scoped = True
    ui = MainWindow(backend)
    try:
        backend._emit_connection(first)
        with network_scope(network_id(first)):
            alert = Alert("warning", "Chỉ thuộc mạng A")
            repository.add_alert(alert)
            backend._emit_alert(alert)
        assert ui.alert_list.count() == 1
        backend._emit_connection(second)
        assert ui.alert_list.count() == 0
        assert backend.get_alerts() == []
    finally:
        close_ui(backend, ui, app)


def save_alert(iface, message):
    with network_scope(network_id(iface)):
        repository.add_alert(Alert("warning", message))
        return repository.list_alerts()[0]


def test_network_change_resets_search_and_page_even_with_same_ip(app, networks):
    first, second = networks
    backend = Backend()
    backend._scoped = True
    backend._emit_connection(first)
    with network_scope(network_id(first)):
        for index in range(110):
            repository.add_alert(Alert("info", f"Mạng A {index}"))
    save_alert(second, "Chỉ mạng B")
    ui = MainWindow(backend)
    try:
        ui.alert_search.setText("Mạng A")
        ui.change_alert_page(100)
        assert ui.alert_list.count() == 10
        backend._emit_connection(second)
        assert ui.alert_search.text() == ""
        assert ui._alert_offset == 0
        assert ui.alert_list.count() == 1
        assert "Chỉ mạng B" in ui.alert_list.item(0).text()
        assert backend.get_alerts()[0].network_id == network_id(second)
        assert backend.get_alerts(query="Mạng A") == []
    finally:
        close_ui(backend, ui, app)


def test_disconnect_clears_alerts_and_ignores_late_queued_event(app, networks):
    first, _ = networks
    backend = Backend()
    backend._scoped = True
    backend._emit_connection(first)
    alert = save_alert(first, "Sự kiện chỉ thuộc kết nối cũ")
    ui = MainWindow(backend)
    try:
        assert ui.alert_list.count() == 1
        def late_event():
            with network_scope(network_id(first)):
                backend._emit_alert(alert)
        worker = threading.Thread(target=late_event)
        worker.start()
        worker.join(2)
        assert not worker.is_alive()
        backend._emit_connection(None)
        app.processEvents()
        assert backend.get_alerts() == []
        assert ui.alert_list.count() == 0
        assert ui.statusBar().currentMessage() == ""
        assert "Chưa có kết nối" in ui.alert_banner.text()
        with network_scope(network_id(first)):
            assert repository.list_alerts()[0].message == alert.message
    finally:
        close_ui(backend, ui, app)


def test_stale_selection_cannot_acknowledge_same_id_in_new_network(app, networks, monkeypatch):
    first, second = networks
    old = save_alert(first, "Cảnh báo A")
    new = save_alert(second, "Cảnh báo B")
    assert old.id == new.id
    backend = Backend()
    backend._scoped = True
    backend._emit_connection(first)
    ui = MainWindow(backend)
    warning = Mock()
    monkeypatch.setattr("ui.main_window.QMessageBox.warning", warning)
    try:
        ui.alert_list.setCurrentRow(0)
        # Backend đã đổi trước khi Qt giao cập nhật kết nối tới UI.
        backend.blockSignals(True)
        try:
            backend._emit_connection(second)
        finally:
            backend.blockSignals(False)
        ui.acknowledge_selected_alert()
        warning.assert_called_once()
        assert "đã đổi" in warning.call_args.args[2]
        assert ui.alert_list.count() == 1
        assert "Cảnh báo B" in ui.alert_list.item(0).text()
        with network_scope(network_id(second)):
            assert not repository.list_alerts()[0].acknowledged
        ui.alert_list.setCurrentRow(0)
        ui.acknowledge_selected_alert()
        with network_scope(network_id(second)):
            assert repository.list_alerts()[0].acknowledged
        with network_scope(network_id(first)):
            assert not repository.list_alerts()[0].acknowledged
    finally:
        close_ui(backend, ui, app)


def test_legacy_alerts_require_explicit_history_mode(app):
    repository.add_alert(Alert("warning", "Lịch sử chưa định danh mạng"))
    backend = Backend(history=True)
    ui = MainWindow(backend)
    try:
        assert ui.alert_list.count() == 1
        assert "Đang xem lịch sử" in ui.alert_scope_label.text()
        assert backend.get_alert_context()["mode"] == "history"
    finally:
        close_ui(backend, ui, app)


@pytest.mark.parametrize("connected", [True, False], ids=["resume-connected", "resume-offline"])
def test_explicit_history_is_separate_from_resumed_live_view(app, networks, monkeypatch, connected):
    first, second = networks
    backend = Backend()
    backend._scoped = True
    backend._emit_connection(first)
    save_alert(first, "Lịch sử mạng A")
    backend._emit_connection(second)
    save_alert(second, "Cảnh báo mạng B")
    ui = MainWindow(backend)
    backend.available_profiles()
    label = next(label for label, value in backend._profile_choices.items() if value == network_id(first))
    def current_interface():
        if not connected:
            raise RuntimeError("offline")
        return second
    monkeypatch.setattr("core.interfaces.get_active_interface", current_interface)
    for method in ("services.scan_loop.ScanLoop.start", "services.ping_monitor.PingMonitor.start",
                   "services.device_identification.DeviceIdentification.start"):
        monkeypatch.setattr(method, Mock())
    try:
        backend.select_history(label)
        assert backend.get_alert_context()["mode"] == "history"
        assert ui.alert_list.count() == 1
        assert "Lịch sử mạng A" in ui.alert_list.item(0).text()
        assert "Đang xem lịch sử" in ui.alert_scope_label.text()
        backend.start()
        assert backend.get_alert_context()["mode"] == "live"
        assert ui.alert_list.count() == (1 if connected else 0)
        if connected:
            assert "Cảnh báo mạng B" in ui.alert_list.item(0).text()
        else:
            assert backend.get_alerts() == []
    finally:
        close_ui(backend, ui, app)


def test_query_failure_after_switch_does_not_keep_old_network_rows(app, networks, monkeypatch):
    first, second = networks
    backend = Backend()
    backend._scoped = True
    backend._emit_connection(first)
    save_alert(first, "Không được giữ lại trên mạng B")
    ui = MainWindow(backend)
    reader = backend.get_alerts
    try:
        assert ui.alert_list.count() == 1
        monkeypatch.setattr(backend, "get_alerts", Mock(side_effect=RuntimeError("read failure")))
        backend._emit_connection(second)
        assert ui.alert_list.count() == 0
        assert "Không tải được" in ui.alert_banner.text()
        monkeypatch.setattr(backend, "get_alerts", reader)
        ui.refresh_alerts()
        assert ui.alert_list.count() == 0
    finally:
        close_ui(backend, ui, app)


def test_old_network_event_cannot_replace_new_network_list_or_status(app, networks):
    first, second = networks
    old = save_alert(first, "Tin đến muộn từ mạng A")
    save_alert(second, "Đúng mạng B")
    backend = Backend()
    backend._scoped = True
    backend._emit_connection(second)
    ui = MainWindow(backend)
    try:
        with network_scope(network_id(first)):
            backend._emit_alert(old)
        assert ui.alert_list.count() == 1
        assert "Đúng mạng B" in ui.alert_list.item(0).text()
        assert ui.statusBar().currentMessage() == ""
    finally:
        close_ui(backend, ui, app)
