"""Hồi quy theo báo cáo rà soát: dịch vụ thật, CSDL tạm, không gửi gói thật."""
import csv
import threading
import time
from dataclasses import replace
from datetime import timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from core.interfaces import NetInterface
from core.network_context import network_id, network_scope
from db import database, repository
from models import Alert, Device, Hop, PingResult, now
from services import alerts, baseline
from services.scan_loop import ScanLoop
from services.ping_monitor import PingMonitor


@pytest.fixture
def iface():
    return NetInterface("Wi-Fi", "test", "192.168.1.9", "255.255.255.0", "192.168.1.1",
                        "00:11:22:33:44:55", False, True, 7, "profile-home")


def test_network_profiles_keep_trust_identity_baseline_and_pings_separate(iface):
    other = replace(iface, profile_id="profile-office")
    mac = "00:11:22:33:44:66"
    with network_scope(network_id(iface)):
        repository.upsert_device(Device("192.168.1.20", mac, trusted=True, name="Ở nhà"))
        repository.set_type_override(mac, "mobile")
        baseline.finish_baseline()
        repository.add_ping(PingResult("router", 1, 0, address=iface.gateway))
    with network_scope(network_id(other)):
        assert repository.list_devices() == []
        assert baseline.is_first_run()
        assert repository.get_pings("router", now()-timedelta(hours=1)) == []
        repository.upsert_device(Device("192.168.1.20", mac))
        assert not repository.get_device(mac).trusted
    with network_scope(network_id(iface)):
        assert repository.get_device(mac).name == "Ở nhà"
        assert repository.get_device(mac).type_override == "mobile"
        assert not baseline.is_first_run()


def test_own_adapter_randomized_mac_does_not_merge_or_replace_network_profile(iface):
    fixed_adapter = replace(iface, adapter_id="stable-adapter-id")
    randomized = replace(fixed_adapter, mac="02:11:22:33:44:77")
    assert network_id(fixed_adapter) == network_id(randomized)
    assert network_id(randomized) != network_id(replace(randomized, profile_id="other-network"))


def test_scan_rejects_network_change_before_writing(iface):
    from core.arp_scanner import ScanEntry
    resolver = Mock(side_effect=[iface, replace(iface, profile_id="other")])
    loop = ScanLoop(interface_resolver=resolver, scanner=lambda _: [ScanEntry("192.168.1.20", "00:11:22:33:44:66")])
    with pytest.raises(RuntimeError, match="thay đổi"):
        loop.scan_once()
    assert not repository.list_devices()
    assert not repository.get_observations(now()-timedelta(hours=1))


def test_scan_rejects_stale_generation_even_when_interface_is_back(iface):
    generation = [1]
    def scan(_):
        generation[0] += 2
        return []
    loop = ScanLoop(interface_resolver=lambda: iface, scanner=scan, generation_provider=lambda: generation[0])
    with pytest.raises(RuntimeError, match="Phiên kết nối"):
        loop.scan_once()


def test_last_seen_is_not_changed_by_offline_transition():
    device = Device("192.168.1.20", "00:11:22:33:44:66", last_seen=now()-timedelta(minutes=5))
    repository.upsert_device(device)
    repository.set_online(device.mac, True, device.last_seen)
    repository.set_online(device.mac, False, now())
    assert repository.get_device(device.mac).last_seen == device.last_seen


def test_scan_preserves_many_to_many_claims(iface):
    from core.arp_scanner import ScanEntry
    entries = [ScanEntry("192.168.1.20", "00:11:22:33:44:66"),
               ScanEntry("192.168.1.21", "00:11:22:33:44:66"),
               ScanEntry("192.168.1.20", "00:11:22:33:44:77")]
    loop = ScanLoop(interface_resolver=lambda: iface, scanner=lambda _: entries)
    loop.scan_once()
    claims = repository.get_observations(now()-timedelta(hours=1))
    assert {(r["ip"], r["mac"]) for r in claims} == {(e.ip, e.mac) for e in entries}
    assert len(repository.list_devices()) == 2


def test_callback_failure_does_not_lose_alert_or_remaining_devices(iface):
    from core.arp_scanner import ScanEntry
    baseline.finish_baseline()
    callback = Mock(side_effect=RuntimeError("UI callback failed"))
    loop = ScanLoop(interface_resolver=lambda: iface, scanner=lambda _: [
        ScanEntry("192.168.1.20", "00:11:22:33:44:66"), ScanEntry("192.168.1.21", "00:11:22:33:44:77")], on_device=callback)
    loop.scan_once()
    assert len(repository.list_devices()) == 2
    assert len(repository.list_alerts()) == 2


def test_old_untrusted_device_is_alerted_after_baseline(iface):
    from core.arp_scanner import ScanEntry
    device = Device("192.168.1.20", "00:11:22:33:44:66")
    repository.upsert_device(device)
    baseline.finish_baseline()
    loop = ScanLoop(interface_resolver=lambda: iface, scanner=lambda _: [ScanEntry(device.ip, device.mac)])
    loop.scan_once()
    loop.scan_once()
    assert len(repository.list_alerts()) == 1
    with database.transaction() as connection:
        assert connection.execute("SELECT count(*) FROM BaselineMembers").fetchone()[0] == 1


def test_dedup_keeps_kinds_separate_and_allows_severity_upgrade():
    mac = "00:11:22:33:44:66"
    assert alerts.raise_anomaly("warning", "new", mac, kind="stranger")
    assert alerts.raise_anomaly("danger", "gateway", mac, kind="gateway_change")
    assert alerts.raise_anomaly("warning", "conflict", mac, kind="ip_conflict")
    assert alerts.raise_anomaly("danger", "conflict worse", mac, kind="ip_conflict")
    assert alerts.raise_anomaly("danger", "repeat", mac, kind="ip_conflict") is None


def test_dedup_decision_and_insert_are_atomic_across_threads():
    barrier = threading.Barrier(8)
    results = []
    def writer():
        barrier.wait(2)
        results.append(alerts.raise_anomaly("warning", "same", "00:11:22:33:44:66", kind="same"))
    threads = [threading.Thread(target=writer) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(3)
        assert not thread.is_alive()
    assert sum(r is not None for r in results) == 1
    assert len(repository.list_alerts()) == 1


def test_dhcp_owner_moving_to_another_ip_does_not_raise_false_change():
    from core.arp_listener import ArpObservation
    device = Device("192.168.1.20", "00:11:22:33:44:66", online=True)
    repository.upsert_device(device)
    detector = alerts.ArpAnomalyDetector("192.168.1.1", [device])
    repository.upsert_device(replace(device, ip="192.168.1.30"))
    for _ in range(2):
        assert detector.observe(ArpObservation("192.168.1.20", "00:11:22:33:44:77", 2, False, now())) == []


@pytest.mark.parametrize("scenario,kind,level", [
    ("conflict", "ip_conflict:192.168.1.20", "warning"),
    ("gateway", "gateway_change", "danger"),
    ("multi", "multi_ip", "warning"),
])
def test_real_detector_persists_positive_anomaly_rules(scenario, kind, level):
    from core.arp_listener import ArpObservation
    old, new = "00:11:22:33:44:66", "00:11:22:33:44:77"
    if scenario == "gateway":
        repository.set_meta("gateway_mac", old)
        assert alerts.raise_stranger(Device("192.168.1.20", new))
    detector = alerts.ArpAnomalyDetector("192.168.1.1", subnet="192.168.1.0/24")
    claims = [("192.168.1.20", old), ("192.168.1.20", new)] if scenario == "conflict" else [
        ("192.168.1.1", new), ("192.168.1.1", new)] if scenario == "gateway" else [
        ("192.168.1.20", new), ("192.168.1.21", new), ("192.168.1.22", new)]
    emitted = []
    for ip, mac in claims:
        emitted.extend(detector.observe(ArpObservation(ip, mac, 2, False, now())))
    assert len(emitted) == 1
    assert (emitted[0].kind, emitted[0].level) == (kind, level)
    assert any(a.kind == kind and a.level == level for a in repository.list_alerts())


def test_anomaly_state_has_global_bounds_and_filters_outside_subnet():
    from core.arp_listener import ArpObservation
    detector = alerts.ArpAnomalyDetector("10.0.0.1", subnet="10.0.0.0/16")
    detector.MAX_ENTRIES = 10
    for index in range(30):
        detector.observe(ArpObservation(f"10.0.1.{index+1}", f"00:11:22:33:44:{index+1:02x}", 2, False, now()))
    assert len(detector._recent_claims) <= 10
    assert len(detector._known_owner) <= 10
    assert detector.observe(ArpObservation("192.168.1.20", "00:11:22:33:44:66", 2, False, now())) == []


def test_real_icmp_socket_send_error_is_not_timeout(monkeypatch):
    from core import icmp
    from icmplib.exceptions import SocketUnavailableError
    sock = Mock()
    sock.send.side_effect = SocketUnavailableError()
    monkeypatch.setattr(icmp, "ICMPv4Socket", Mock(return_value=SimpleNamespace(__enter__=None)))
    factory = Mock()
    factory.return_value.__enter__ = Mock(return_value=sock)
    factory.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(icmp, "ICMPv4Socket", factory)
    with pytest.raises(RuntimeError, match="Không ping được"):
        icmp.ping_once("192.168.1.1", source="192.168.1.9")
    sock.receive.assert_not_called()


def test_icmp_actual_receive_timeout_stays_loss(monkeypatch):
    from core import icmp
    from icmplib.exceptions import TimeoutExceeded
    factory = Mock()
    sock = Mock()
    sock.receive.side_effect = TimeoutExceeded(1)
    factory.return_value.__enter__ = Mock(return_value=sock)
    factory.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(icmp, "ICMPv4Socket", factory)
    assert icmp.ping_once("192.168.1.1", source="192.168.1.9") is None
    sock.send.assert_called_once()


def test_successful_icmp_probe_returns_milliseconds_and_binds_selected_source(monkeypatch):
    from core import icmp
    factory, sock = Mock(), Mock()
    factory.return_value.__enter__ = Mock(return_value=sock)
    factory.return_value.__exit__ = Mock(return_value=False)
    sock.send.side_effect = lambda request: setattr(request, "_time", 10.0)
    sock.receive.return_value = SimpleNamespace(time=10.012, raise_for_status=lambda: None)
    monkeypatch.setattr(icmp, "ICMPv4Socket", factory)
    assert icmp.ping_once("192.168.1.1", source="192.168.1.9") == pytest.approx(12)
    factory.assert_called_once_with("192.168.1.9", privileged=True)


def test_sustained_slow_router_is_bad_even_with_slow_baseline(iface):
    from core.diagnosis import is_bad
    monitor = PingMonitor(iface=iface)
    monitor._history["router"].extend([120]*30)
    assert is_bad(monitor._stats("router", available=True))


def test_intermediate_icmp_loss_without_downstream_impact_does_not_blame_isp():
    from core.diagnosis import TargetStats, diagnose
    good = TargetStats(0, 10, 10, 30)
    bad = TargetStats(100, None, None, 30)
    assert diagnose(good, bad, good).verdict == "unknown"
    assert "trung gian" in diagnose(good, bad, good).text


def test_external_target_cannot_be_selected_as_intermediate_hop():
    from core.traceroute import find_isp_hop
    assert find_isp_hop([Hop(1, "192.168.1.1", 1), Hop(4, "1.1.1.1", 10)], "192.168.1.1") is None


def test_changed_hop_and_stale_measurements_clear_history(iface):
    monitor = PingMonitor(iface=iface, tracer=lambda *a, **k: [Hop(2, "10.0.0.2", 5)])
    monitor._set_interface(iface)
    monitor._isp_ip = "10.0.0.1"
    monitor._history["isp"].extend([5]*30)
    monitor._discover_isp(iface, monitor._network_generation)
    assert monitor._isp_ip == "10.0.0.2"
    assert not monitor._history["isp"]
    monitor._history["router"].extend([1]*30)
    monitor._sample_times["router"] = time.monotonic()-1000
    assert monitor._stats("router", True).samples == 0


def test_probes_run_concurrently_but_writes_stay_in_one_cycle(iface):
    barrier = threading.Barrier(2)
    def ping(*args):
        barrier.wait(2)
        return 3
    monitor = PingMonitor(interface_resolver=lambda: iface, pinger=ping)
    assert monitor._cycle() is None
    samples = repository.get_pings("external", now()-timedelta(hours=1))
    assert samples[0].address == "1.1.1.1" and samples[0].status == "ok"


def test_stop_timeout_keeps_worker_handle_and_prevents_late_scan_write(iface):
    from core.arp_scanner import ScanEntry
    entered, release = threading.Event(), threading.Event()
    def scan(_):
        entered.set()
        assert release.wait(3)
        return [ScanEntry("192.168.1.20", "00:11:22:33:44:66")]
    loop = ScanLoop(interface_resolver=lambda: iface, scanner=scan)
    loop.start()
    try:
        assert entered.wait(2)
        original = loop._thread
        with pytest.raises(RuntimeError, match="chưa dừng"):
            loop.stop(.01)
        assert loop.is_running()
        loop.start()
        assert loop._thread is original
    finally:
        release.set()
        loop.stop(2)
    assert not repository.list_devices()


def test_nested_business_transaction_rolls_back_all_changes():
    with pytest.raises(RuntimeError):
        with database.transaction():
            repository.upsert_device(Device("192.168.1.20", "00:11:22:33:44:66"))
            repository.add_alert(Alert("warning", "pending"))
            raise RuntimeError("abort")
    assert not repository.list_devices()
    assert not repository.list_alerts()


def test_read_snapshot_does_not_block_writer_and_keeps_consistent_view():
    device = Device("192.168.1.20", "00:11:22:33:44:66", name="Before")
    repository.upsert_device(device)
    ready, release = threading.Event(), threading.Event()
    names = []
    def reader():
        with database.read_snapshot() as connection:
            names.append(connection.execute("SELECT name FROM Devices").fetchone()[0])
            ready.set()
            assert release.wait(3)
            names.append(connection.execute("SELECT name FROM Devices").fetchone()[0])
    thread = threading.Thread(target=reader)
    thread.start()
    try:
        assert ready.wait(2)
        repository.set_name_note(device.mac, "After", "")
    finally:
        release.set()
        thread.join(3)
    assert not thread.is_alive()
    assert names == ["Before", "Before"]
    assert repository.get_device(device.mac).name == "After"


def test_continuously_present_device_does_not_alert_again_just_because_cooldown_expired(iface):
    from core.arp_scanner import ScanEntry
    baseline.finish_baseline()
    mac = "00:11:22:33:44:66"
    loop = ScanLoop(interface_resolver=lambda: iface, scanner=lambda _: [ScanEntry("192.168.1.20", mac)])
    loop.scan_once()
    with database.transaction() as connection:
        connection.execute("UPDATE Alerts SET ts=?", (repository._to_iso(now()-timedelta(hours=1)),))
    loop.scan_once()
    assert len(repository.list_alerts()) == 1
    repository.set_trusted(mac, True)
    repository.set_trusted(mac, False)
    loop.scan_once()
    assert len(repository.list_alerts()) == 2


def test_scoped_monitor_records_its_session_interface_and_ends_it_on_stop(iface):
    monitor = PingMonitor(interface_resolver=lambda: iface, pinger=lambda *args: 2, scoped=True)
    monitor._cycle()
    with network_scope(network_id(iface)):
        sessions = repository.get_sessions(now()-timedelta(hours=1), now())
        samples = repository.get_pings("router", now()-timedelta(hours=1))
        assert len(sessions) == 1
        assert sessions[0]["interface"]["name"] == iface.name
        assert samples[0].session_id == sessions[0]["id"]
    monitor.stop()
    with network_scope(network_id(iface)):
        assert repository.get_sessions(now()-timedelta(hours=1), now())[0]["clean_end"]


def test_small_scan_range_is_allowed_inside_large_subnet(monkeypatch, iface):
    from config import SETTINGS
    from core.interfaces import get_subnet_hosts
    monkeypatch.setitem(SETTINGS, "scan_cidr", "10.0.1.0/24")
    hosts = get_subnet_hosts(replace(iface, ip="10.0.1.9", netmask="255.0.0.0"))
    assert len(hosts) == 254
    assert hosts[0] == "10.0.1.1" and hosts[-1] == "10.0.1.254"


def test_partial_scan_does_not_mark_unprobed_devices_offline(monkeypatch, iface):
    from config import SETTINGS, OFFLINE_AFTER_MISSES
    monkeypatch.setitem(SETTINGS, "scan_cidr", "192.168.1.0/25")
    inside = Device("192.168.1.20", "00:11:22:33:44:66", online=True)
    outside = Device("192.168.1.200", "00:11:22:33:44:77", online=True)
    repository.upsert_device(inside)
    repository.upsert_device(outside)
    loop = ScanLoop(interface_resolver=lambda: iface, scanner=lambda _: [])
    for _ in range(OFFLINE_AFTER_MISSES):
        loop.scan_once()
    assert not repository.get_device(inside.mac).online
    assert repository.get_device(outside.mac).online
    assert outside.mac not in loop._misses


def test_ping_only_legacy_database_is_backed_up_before_migration():
    import sqlite3
    from pathlib import Path
    from contextlib import closing
    with closing(sqlite3.connect(database.DB_PATH)) as connection:
        connection.executescript(database._SCHEMA)
        connection.execute("INSERT INTO PingLog(target,rtt_ms,loss_pct,ts) VALUES(?,?,?,?)", ("router", 2, 0, now().isoformat()))
        connection.commit()
    database.initialize()
    assert Path(database.DB_PATH + ".pre-v3.bak").is_file()
    assert len(repository.get_pings("router", now()-timedelta(hours=1))) == 1


def test_point_to_point_31_addresses_are_not_rejected_as_network_broadcast(iface):
    import scapy.all as scapy
    from core.arp_validation import valid_arp_source
    point_to_point = replace(iface, ip="192.0.2.0", netmask="255.255.255.254")
    packet = scapy.ARP(op=2, psrc="192.0.2.1", hwsrc="00:11:22:33:44:66")
    assert valid_arp_source(packet, point_to_point) == ("192.0.2.1", "00:11:22:33:44:66")


def test_backup_restore_uses_consistent_sqlite_snapshot(tmp_path):
    device = Device("192.168.1.20", "00:11:22:33:44:66", name="Tên tiếng Việt")
    repository.upsert_device(device)
    path = tmp_path / "backup.sqlite"
    database.backup_to(str(path))
    repository.set_name_note(device.mac, "Đã đổi", "")
    database.restore_from(str(path))
    assert repository.get_device(device.mac).name == device.name


@pytest.mark.parametrize("invalid", ["incomplete", "future"])
def test_invalid_restore_cannot_replace_current_database(tmp_path, invalid):
    import sqlite3
    from contextlib import closing
    device = Device("192.168.1.20", "00:11:22:33:44:66", name="Giữ nguyên dữ liệu")
    repository.upsert_device(device)
    path = tmp_path / "invalid.sqlite"
    if invalid == "future":
        database.backup_to(str(path))
    with closing(sqlite3.connect(path)) as connection:
        if invalid == "incomplete":
            connection.execute("CREATE TABLE Devices(mac TEXT PRIMARY KEY)")
        connection.execute(f"PRAGMA user_version={999 if invalid == 'future' else 3}")
        connection.commit()
    with pytest.raises(ValueError):
        database.restore_from(str(path))
    assert repository.get_device(device.mac).name == device.name
    assert database.get_connection().execute("PRAGMA user_version").fetchone()[0] == 3


def test_legacy_restore_is_migrated_before_replacing_current_database(tmp_path):
    import sqlite3
    from contextlib import closing
    path = tmp_path / "legacy.sqlite"
    stamp = now().isoformat()
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(database._SCHEMA.split(";")[0])
        connection.execute("INSERT INTO Devices(mac,ip,name,first_seen,last_seen) VALUES(?,?,?,?,?)",
                           ("00:11:22:33:44:66", "192.168.1.20", "Máy đời cũ", stamp, stamp))
        connection.commit()
    database.restore_from(str(path))
    device = repository.get_device("00:11:22:33:44:66")
    assert device.name == "Máy đời cũ"
    assert device.device_type == "unknown"
    assert database.get_connection().execute("PRAGMA user_version").fetchone()[0] == 3


def test_failed_restore_restarts_previous_monitoring_without_losing_data(tmp_path, monkeypatch):
    import sqlite3
    from contextlib import closing
    from backend import Backend
    device = Device("192.168.1.20", "00:11:22:33:44:66", name="Không ghi đè")
    repository.upsert_device(device)
    path = tmp_path / "wrong.sqlite"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE unrelated(value TEXT)")
    backend = Backend()
    loop = Mock()
    backend._loop = loop
    restart = Mock()
    monkeypatch.setattr(backend, "start", restart)
    with pytest.raises(ValueError):
        backend.restore_database(str(path))
    loop.stop.assert_called_once()
    restart.assert_called_once()
    assert repository.get_device(device.mac).name == device.name


def test_retention_and_bounded_queries_preserve_user_metadata():
    old = now()-timedelta(days=100)
    repository.upsert_device(Device("192.168.1.20", "00:11:22:33:44:66", name="Giữ tên", last_seen=old))
    repository.add_ping(PingResult("router", 1, 0, old))
    repository.add_ping(PingResult("router", 2, 0))
    repository.purge_history(30)
    assert len(repository.get_pings("router", old)) == 1
    assert repository.list_devices()[0].name == "Giữ tên"
    with pytest.raises(ValueError):
        repository.list_alerts(-1)


def test_timezone_boundary_and_presence_start_state_are_preserved():
    stamp = now().replace(microsecond=123456)
    device = Device("192.168.1.20", "00:11:22:33:44:66")
    repository.upsert_device(device)
    repository.set_online(device.mac, True, stamp)
    assert repository.get_presence(device.mac, stamp+timedelta(seconds=1)) == [(stamp, True)]
    aware = stamp.replace(tzinfo=timezone(timedelta(hours=7)))
    assert repository._to_iso(aware) == repository._to_iso(stamp)


@pytest.mark.parametrize("text", ["=1+1", "+SUM(A1)", "-1+2", "@cmd", "\t=1", "  =1"])
def test_csv_text_is_literal_for_spreadsheet_consumers(tmp_path, text):
    from extras.csv_export import export_devices
    path = tmp_path / "devices.csv"
    export_devices([Device("192.168.1.20", "00:11:22:33:44:66", name=text, note=text)], str(path))
    with path.open(encoding="utf-8-sig", newline="") as stream:
        row = list(csv.reader(stream))[1]
    assert row[3].startswith("'") and row[4].startswith("'")
