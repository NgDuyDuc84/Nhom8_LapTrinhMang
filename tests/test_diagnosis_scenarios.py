"""Kịch bản lỗi/phục hồi qua PingMonitor và SQLite thật; probe ICMP dùng giả."""
from datetime import timedelta
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from config import SETTINGS
from core.interfaces import NetInterface
from db import repository
from models import now
from services.ping_monitor import PingMonitor


@pytest.fixture
def scenario(monkeypatch):
    monkeypatch.setattr("core.diagnosis.LOSS_BAD_PCT", 5)
    monkeypatch.setitem(SETTINGS, "router_rtt_ms", 50)
    monkeypatch.setitem(SETTINGS, "external_rtt_ms", 250)
    monkeypatch.setattr("services.ping_monitor.PING_EXTERNAL_TARGET", "1.1.1.1")
    iface = NetInterface("Wi-Fi", "test", "192.168.1.9", "255.255.255.0", "192.168.1.1",
                         "00:11:22:33:44:55", False, True, 7)
    outcomes = {"router": 2.0, "isp": 5.0, "external": 20.0}
    events = []
    def probe(address, timeout):
        target = "router" if address == iface.gateway else "isp" if address == "10.0.0.1" else "external"
        value = outcomes[target]
        if isinstance(value, Exception):
            raise value
        return value
    monitor = PingMonitor(interface_resolver=lambda: iface, pinger=probe, on_diagnosis=events.append)
    monitor._set_interface(iface)
    monitor._isp_ip = "10.0.0.1"
    def cycles(count):
        for _ in range(count):
            monitor._cycle()
    return SimpleNamespace(monitor=monitor, outcomes=outcomes, events=events, cycles=cycles)


@pytest.mark.parametrize("before", ["ok", "home_issue", "isp_issue", "internet_issue"])
@pytest.mark.parametrize("failed_target", ["router", "external"])
def test_measurement_error_invalidates_previous_conclusive_verdict_immediately(scenario, before, failed_target):
    if before != "ok":
        scenario.outcomes["external"] = None
    if before == "home_issue":
        scenario.outcomes["router"] = None
    if before == "isp_issue":
        scenario.outcomes["isp"] = None
    scenario.cycles(30)
    assert scenario.events[-1].verdict == before
    scenario.outcomes[failed_target] = RuntimeError("Không tạo/đọc được socket ICMP")
    scenario.cycles(1)
    assert scenario.events[-1].verdict == "unknown"
    samples = repository.get_pings(failed_target, now()-timedelta(minutes=5))
    assert samples[-1].status == "measurement_error"
    assert samples[-1].loss_pct == 0  # Lỗi đo không được quy thành 100% mất gói.


def test_recovery_requires_fresh_confirmation_and_does_not_repeat_same_verdict(scenario):
    scenario.cycles(30)
    scenario.outcomes["external"] = RuntimeError("socket error")
    scenario.cycles(1)
    assert scenario.events[-1].verdict == "unknown"
    scenario.outcomes["external"] = 20.0
    scenario.cycles(2)
    assert scenario.events[-1].verdict == "unknown"
    scenario.cycles(1)
    assert scenario.events[-1].verdict == "ok"
    before = len(scenario.events)
    scenario.cycles(10)
    assert len(scenario.events) == before


@pytest.mark.parametrize("verdict,bad_targets", [
    ("home_issue", ["router", "external"]),
    ("isp_issue", ["isp", "external"]),
    ("internet_issue", ["external"]),
])
@pytest.mark.parametrize("failure", ["latency", "loss"])
def test_sustained_degradation_and_recovery_do_not_flap(scenario, verdict, bad_targets, failure):
    scenario.cycles(30)
    for target in bad_targets:
        scenario.outcomes[target] = None if failure == "loss" else 600.0
    scenario.cycles(30)
    assert scenario.events[-1].verdict == verdict
    if failure == "loss":
        stats = scenario.monitor._stats("external", available=True)
        assert stats.loss_pct == 100
        assert scenario.events[-1].verdict != "unknown"
    scenario.outcomes.update(router=2.0, isp=5.0, external=20.0)
    scenario.cycles(35)
    assert [event.verdict for event in scenario.events if event.verdict != "unknown"] == ["ok", verdict, "ok"]


def test_intermediate_loss_without_downstream_loss_never_blames_isp(scenario):
    scenario.cycles(30)
    scenario.outcomes["isp"] = None
    scenario.cycles(30)
    assert scenario.events[-1].verdict == "unknown"
    assert "trung gian" in scenario.events[-1].text
    assert not any(event.verdict in {"isp_issue", "internet_issue", "home_issue"} for event in scenario.events)


def test_optional_hop_measurement_error_does_not_invalidate_healthy_endpoints(scenario):
    scenario.cycles(30)
    scenario.outcomes["isp"] = RuntimeError("hop socket error")
    scenario.cycles(5)
    assert scenario.events[-1].verdict == "ok"
    assert scenario.monitor.target_status["isp"].startswith("lỗi đo")
    assert not any(event.verdict == "unknown" for event in scenario.events[1:])


def test_one_latency_spike_does_not_become_a_confirmed_network_fault(scenario):
    scenario.cycles(30)
    scenario.outcomes.update(router=600.0, isp=600.0, external=600.0)
    scenario.cycles(1)
    scenario.outcomes.update(router=2.0, isp=5.0, external=20.0)
    scenario.cycles(5)
    assert [event.verdict for event in scenario.events if event.verdict != "unknown"] == ["ok"]


def test_alternating_external_timeouts_still_produce_one_stable_degradation(scenario):
    scenario.cycles(30)
    for index in range(30):
        scenario.outcomes["external"] = None if index % 2 == 0 else 20.0
        scenario.cycles(1)
    assert [event.verdict for event in scenario.events if event.verdict != "unknown"] == ["ok", "internet_issue"]


@pytest.mark.parametrize("verdict,bad_targets", [
    ("home_issue", ["router", "external"]),
    ("isp_issue", ["isp", "external"]),
    ("internet_issue", ["external"]),
])
def test_slow_connection_from_start_is_not_learned_as_healthy_baseline(scenario, verdict, bad_targets):
    for target in bad_targets:
        scenario.outcomes[target] = 600.0
    scenario.cycles(15)
    assert scenario.events[-1].verdict == verdict
    assert not any(event.verdict == "ok" for event in scenario.events)


def test_measurement_error_updates_ui_and_persisted_diagnosis_immediately(scenario):
    from PySide6.QtWidgets import QApplication
    from backend import Backend
    from ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    backend = Backend()
    backend._emit_connection(scenario.monitor._iface)
    backend._ping_monitor = scenario.monitor
    scenario.monitor._on_diagnosis = backend._emit_diagnosis
    scenario.monitor._on_cycle = backend._emit_measurements
    ui = MainWindow(backend)
    try:
        scenario.cycles(30)
        ui.refresh_diagnosis()
        assert ui.verdict_label.text() == "ok"
        scenario.outcomes["external"] = RuntimeError("socket unavailable")
        scenario.cycles(1)
        app.processEvents()
        ui.refresh_diagnosis()
        assert ui.verdict_label.text() == "unknown"
        assert backend.get_latest_diagnosis().verdict == "unknown"
        assert ui.measurement_table.item(2, 2).text() == "—"
        assert "lỗi đo" in ui.measurement_table.item(2, 4).text()
        diagnoses = repository.get_diagnoses(now()-timedelta(minutes=5), now())
        assert diagnoses[-1].verdict == "unknown"
    finally:
        backend.stop()
        ui._device_timer.stop()
        ui._diagnosis_timer.stop()
        ui.deleteLater()
        app.processEvents()
