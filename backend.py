"""Giao diện duy nhất giữa giao diện người dùng (ui/) và lõi (core/, services/, db/).

Quy ước:
- ``BackendBase`` khai báo hợp đồng signal và chữ ký hàm trừu tượng.
- ``Backend`` ghép các worker mạng, SQLite theo hồ sơ và báo cáo nền.
- Chỉ file này được import PySide6; ``core/`` và ``services/`` chỉ phát sự kiện qua callback.
"""

from __future__ import annotations

import threading
import logging
from copy import deepcopy
from functools import wraps
from core.network_context import network_id, network_scope, current_network
from config import SETTINGS
from models import local_time
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from statistics import median

from PySide6.QtCore import QObject, Signal

from db import repository
from models import Alert, Device, Diagnosis, Hop, PingResult, now


def storage_method(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with network_scope(self._storage_network):
            return method(self, *args, **kwargs)
    return call


class BackendBase(QObject):
    """Hợp đồng giữa giao diện và dịch vụ giám sát mạng."""

    # --- Signal: lõi phát sự kiện, giao diện bắt và vẽ lại ---
    service_status_changed = Signal(object)
    report_finished = Signal(object)
    utility_finished = Signal(object)
    device_updated = Signal(object)      # Device: thiết bị mới hoặc vừa đổi trạng thái
    alert_raised = Signal(object)        # Alert: có cảnh báo mới
    ping_result = Signal(object)         # PingResult: một mẫu ping mới
    diagnosis_changed = Signal(object)   # Diagnosis: kết luận chẩn đoán vừa đổi
    traceroute_done = Signal(object)     # list[Hop]: traceroute chạy xong
    connection_changed = Signal(object)  # dict: card, IP, gateway hiện tại
    measurement_changed = Signal(object) # dict: kết quả và lỗi đo từng chu kỳ
    devices_refreshed = Signal()         # bảng thiết bị có dữ liệu mới
    network_refresh_changed = Signal(object)  # dict: tiến độ/kết quả làm mới theo yêu cầu

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    # --- Vòng đời ---
    def start(self) -> None:
        """Bật các luồng nền (quét ARP định kỳ, ping định kỳ)."""
        raise NotImplementedError

    def stop(self) -> None:
        """Tắt các luồng nền và dọn tài nguyên, gọi được nhiều lần."""
        raise NotImplementedError

    def get_connection_status(self) -> dict:
        return {}

    def refresh_network(self) -> bool:
        """Hẹn đọc lại kết nối, quét và đo mới; False nếu một lượt đang chờ."""
        raise NotImplementedError

    def get_refresh_status(self) -> dict:
        return {"request_id": 0, "running": False, "message": "", "errors": []}

    def get_latest_measurements(self) -> dict:
        return {}

    def get_latest_diagnosis(self) -> Diagnosis | None:
        return None

    def get_device_status(self, device: Device) -> str:
        return "Online" if device.online else "Offline"

    # --- Thiết bị ---
    def list_devices(self) -> list[Device]:
        """Trả về toàn bộ thiết bị đã biết (trong CSDL hoặc bộ nhớ)."""
        raise NotImplementedError

    def set_trusted(self, mac: str, trusted: bool) -> None:
        """Đánh dấu thiết bị tin cậy hay không tin cậy, rồi lưu lại."""
        raise NotImplementedError

    def rename(self, mac: str, name: str, note: str) -> None:
        """Đổi tên gợi nhớ và ghi chú của thiết bị."""
        raise NotImplementedError

    def set_device_type(self, mac: str, device_type: str) -> None:
        """Xác nhận loại thủ công; chuỗi rỗng trở lại nhận diện tự động."""
        raise NotImplementedError

    # --- Đường cơ sở (baseline) ---
    def is_first_run(self) -> bool:
        """True nếu chưa hoàn tất lập đường cơ sở (lần chạy đầu tiên)."""
        raise NotImplementedError

    def finish_baseline(self) -> None:
        """Chốt đường cơ sở: từ đây thiết bị chưa tin cậy xuất hiện mới sẽ bị cảnh báo."""
        raise NotImplementedError

    # --- Cảnh báo và lịch sử ---
    def get_alerts(self, limit: int = 100, *, offset=0, query="") -> list[Alert]:
        """Trả về các cảnh báo gần nhất, mới nhất trước, tối đa ``limit`` bản ghi."""
        raise NotImplementedError

    def get_ping_history(self, target: str, minutes: int) -> list[PingResult]:
        """Trả về các mẫu ping của một mốc (``router``/``isp``/``external``) trong ``minutes`` phút."""
        raise NotImplementedError

    def get_device_history(self, mac: str, hours: int) -> list[tuple[datetime, bool | None]]:
        """Trả về lịch sử online/offline của thiết bị trong ``hours`` giờ: ``(thời điểm, online)``."""
        raise NotImplementedError

    # --- Traceroute và báo cáo ---
    def run_traceroute(self, target: str = "1.1.1.1") -> None:
        """Chạy traceroute trong nền, kết quả trả qua signal ``traceroute_done``."""
        raise NotImplementedError

    def export_report(self, start: datetime, end: datetime, path: str) -> None:
        """Xuất báo cáo PDF cho khoảng thời gian ``start``–``end``, gọi ``extras.pdf_report.build_report``."""
        raise NotImplementedError


class Backend(BackendBase):
    """Bản thật: ghép ARP scan, ICMP, traceroute, CSDL và cảnh báo.

    Ghép các dịch vụ mạng với SQLite và chuyển callback nền thành Qt signals.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._storage_network = "legacy"
        self._scoped = False
        self._generation = 0
        self._session_id = ""
        self._services = {}
        self._instance_lock = None
        self._report_thread = None
        self._report_stop = threading.Event()
        self._utility_thread = None
        self._notifications = None
        self._maintenance_times = {}
        self._observation_times = {}
        self._loop = None  # services.scan_loop.ScanLoop, khởi tạo trong start()
        self._ping_monitor = None
        self._arp_listener = None
        self._arp_detector = None
        self._identifier = None
        self._traceroute_thread: threading.Thread | None = None
        self._traceroute_lock = threading.Lock()
        self._traceroute_stop = threading.Event()
        self._state_lock = threading.RLock()
        self._last_traceroute: tuple[datetime, list[Hop]] | None = None
        self._diagnoses: list[Diagnosis] = []
        self._latest_diagnosis: Diagnosis | None = None
        self._connection: dict = {}
        self._latest_measurements: dict = {}
        self._session_macs: set[str] = set()
        self._refresh_pending: set[str] = set()
        self._refresh_errors: list[str] = []
        self._refresh_scan_macs: set[str] | None = None
        self._refresh_scan_connection: tuple | None = None
        self._refresh_request_id = 0
        self._refresh_status = {"request_id": 0, "running": False, "message": "", "errors": []}

    # ------------------------------------------------------------------ vòng đời
    def start(self) -> None:
        """Tạo CSDL (nếu chưa có), bật luồng quét và phát danh sách thiết bị hiện có."""
        from db import database
        from core.interfaces import get_active_interface
        from services.ping_monitor import PingMonitor
        from services.scan_loop import ScanLoop
        from services.device_identification import DeviceIdentification
        from services.notifications import Notifications

        if self._loop is not None:
            return
        if any(service is not None for service in (self._ping_monitor, self._arp_listener, self._identifier, self._notifications)):
            raise RuntimeError("Dịch vụ cũ chưa dừng hoàn toàn; hãy thử dừng lại trước khi khởi động.")
        from core.instance_lock import InstanceLock
        self._instance_lock = InstanceLock(database.DB_PATH)
        self._instance_lock.acquire()
        self._scoped = True
        database.initialize()
        try:
            iface = get_active_interface()
        except RuntimeError:
            iface = None  # Vẫn mở UI để hiển thị mất mạng và chờ kết nối lại.
        except Exception:
            database.close()
            raise
        self._emit_connection(iface)
        self._identifier = DeviceIdentification(on_complete=self.devices_refreshed.emit)
        self._notifications = Notifications(self._service_status)
        self._loop = ScanLoop(
            on_device=self._emit_device,
            on_alert=self._emit_alert,
            iface=iface,
            on_interface=self._refresh_arp_interface,
            on_scan=self._emit_scan,
            on_refresh=self._on_scan_refresh,
            on_identify=self._identifier.request,
            scoped=True, generation_provider=lambda: self._generation, commit_lock=self._state_lock,
            session_provider=lambda: self._session_id, on_status=self._service_status,
        )
        self._ping_monitor = PingMonitor(
            on_ping=self.ping_result.emit,
            on_diagnosis=self._emit_diagnosis,
            iface=iface,
            on_cycle=self._emit_measurements,
            on_interface=self._emit_connection,
            on_refresh=self._on_ping_refresh,
            scoped=True, session_provider=lambda: self._session_id, on_route=self._save_route, generation_provider=lambda: self._generation,
        )
        try:
            for device in self.list_devices():
                self.device_updated.emit(device)
            self._identifier.start()
            self._notifications.start()
            self._loop.start()
            self._ping_monitor.start()
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        """Dừng luồng quét và đóng kết nối CSDL. Gọi nhiều lần vẫn an toàn."""
        from db import database

        with self._state_lock:
            self._refresh_pending.clear()
            self._refresh_status = {
                "request_id": self._refresh_request_id, "running": False, "message": "", "errors": [],
            }
        errors = []
        for attribute in ("_loop", "_arp_listener", "_ping_monitor", "_identifier", "_notifications"):
            service = getattr(self, attribute)
            if service is not None:
                try:
                    service.stop()
                    setattr(self, attribute, None)
                except Exception as exc:
                    errors.append(str(exc))
        self._traceroute_stop.set()
        self._report_stop.set()
        for thread in (self._traceroute_thread, self._report_thread, self._utility_thread):
            if thread and thread is not threading.current_thread() and thread.is_alive():
                thread.join(5)
                if thread.is_alive():
                    errors.append("Công việc nền chưa dừng; giữ CSDL mở.")
        if errors:
            raise RuntimeError(" | ".join(errors))
        with network_scope(self._storage_network):
            if self._session_id:
                repository.end_session(self._session_id)
        with self._state_lock:
            self._generation += 1
            self._session_id = ""
            self._connection = {}
            self._latest_measurements = {}
            self._latest_diagnosis = None
            self._session_macs.clear()
            self._services.clear()
            self._last_traceroute = None
            self._diagnoses.clear()
            self._refresh_scan_macs = None
            self._refresh_scan_connection = None
        database.close()
        if self._instance_lock:
            self._instance_lock.release()
            self._instance_lock = None

    def _refresh_arp_interface(self, iface) -> None:
        """Mở lại listener và nhận diện gateway khi cấu hình card thay đổi."""
        from core.arp_listener import ArpListener
        from services.alerts import ArpAnomalyDetector

        self._emit_connection(iface)
        if self._arp_listener is not None:
            self._arp_listener.stop()
            self._arp_listener = None
        self._arp_detector = None
        if iface is None:
            return
        storage = self._storage_network
        with network_scope(storage):
            self._arp_detector = ArpAnomalyDetector(iface.gateway, repository.list_devices(), subnet=f"{iface.ip}/{iface.netmask}")
        def observed(observation):
            with network_scope(storage):
                if storage == self._storage_network:
                    self._emit_arp_observation(observation)
        def listener_status(status):
            if storage == self._storage_network:
                self._service_status(status)
        self._arp_listener = ArpListener(observed, iface, on_status=listener_status)
        try:
            self._arp_listener.start()
        except RuntimeError as exc:
            self._service_status({"service": "arp_listener", "running": False, "error": str(exc)})

    def _emit_connection(self, iface) -> None:
        status = {
            "connected": iface is not None,
            "name": iface.name if iface else "",
            "ip": iface.ip if iface else "",
            "netmask": iface.netmask if iface else "",
            "gateway": iface.gateway if iface else "",
            "profile_id": getattr(iface, "profile_id", "") if iface else "",
            "adapter_id": getattr(iface, "adapter_id", "") if iface else "",
            "mac": iface.mac if iface else "",
        }
        with self._state_lock:
            if status == self._connection:
                return
            if self._scoped:
                with network_scope(self._storage_network):
                    if self._session_id:
                        repository.end_session(self._session_id)
                if iface is not None:
                    self._storage_network = network_id(iface)
                    with network_scope(self._storage_network):
                        self._session_id = repository.start_session(asdict(iface))
                        repository.purge_history(SETTINGS["retention_days"])
                else:
                    self._session_id = ""
            self._generation += 1
            self._connection = status
            # Các phép đo cũ không thể hiện trạng thái của kết nối mới.
            self._latest_measurements = {}
            self._latest_diagnosis = None
            self._session_macs.clear()
            generation = self._generation
        self.connection_changed.emit({**status, "generation": generation})

    def _emit_measurements(self, results) -> None:
        monitor = self._ping_monitor
        if monitor is None:
            return
        if self._scoped and current_network() != self._storage_network:
            return
        snapshot = {
            "results": dict(results),
            "status": dict(monitor.target_status),
            "addresses": monitor.addresses,
            "ts": now(),
        }
        with self._state_lock:
            if self._scoped and current_network() != self._storage_network:
                return
            snapshot["generation"] = self._generation
            self._latest_measurements = snapshot
        import time
        if time.monotonic()-self._maintenance_times.get(self._storage_network, 0) > 3600:
            with network_scope(self._storage_network):
                repository.purge_history(SETTINGS["retention_days"])
            self._maintenance_times[self._storage_network] = time.monotonic()
        self.measurement_changed.emit(deepcopy(snapshot))

    def _emit_scan(self, entries) -> None:
        if self._scoped and current_network() != self._storage_network:
            return
        with self._state_lock:
            if self._scoped and current_network() != self._storage_network:
                return
            self._session_macs.update(entry.mac.lower() for entry in entries)
        self.devices_refreshed.emit()

    def get_connection_status(self) -> dict:
        with self._state_lock:
            return {**self._connection, "generation": self._generation}

    def get_refresh_status(self) -> dict:
        with self._state_lock:
            return {**self._refresh_status, "errors": list(self._refresh_status["errors"])}

    def refresh_network(self) -> bool:
        """Chạy trên các worker có sẵn; không tạo scan hoặc ping song song mới."""
        with self._state_lock:
            if self._refresh_pending:
                return False
            scan, ping = self._loop, self._ping_monitor
            if scan is None or ping is None or not scan.is_running() or not ping.is_running():
                raise RuntimeError("Dịch vụ mạng chưa sẵn sàng. Hãy mở lại NetGuard rồi thử lại.")
            if self._scoped and self._connection.get("connected"):
                with network_scope(self._storage_network):
                    if self._session_id:
                        repository.end_session(self._session_id)
                    self._session_id = repository.start_session(self._connection)
                self._generation += 1
            self._refresh_pending = {"scan", "ping"}
            self._refresh_request_id += 1
            self._refresh_errors = []
            self._refresh_scan_macs = None
            self._refresh_scan_connection = None
            self._session_macs.clear()
            self._latest_measurements = {}
            self._latest_diagnosis = None
            self._refresh_status = {
                "request_id": self._refresh_request_id,
                "running": True,
                "message": "Đang làm mới kết nối, quét thiết bị và đo lại mạng…",
                "errors": [],
            }
        self.network_refresh_changed.emit(self.get_refresh_status())
        for name, service in (("scan", scan), ("ping", ping)):
            try:
                service.request_refresh()
            except Exception as exc:
                self._finish_refresh(name, str(exc))
        return True

    def _on_scan_refresh(self, iface, entries, error: str | None) -> None:
        with self._state_lock:
            if "scan" not in self._refresh_pending:
                return
            if error is None and entries is not None:
                self._refresh_scan_macs = {entry.mac.lower() for entry in entries}
                self._refresh_scan_connection = (
                    iface.name, iface.ip, iface.netmask, iface.gateway,
                    iface.profile_id, iface.adapter_id, iface.mac,
                ) if iface else None
        self._finish_refresh("scan", error)

    def _on_ping_refresh(self, error: str | None) -> None:
        self._finish_refresh("ping", error)

    def _finish_refresh(self, service: str, error: str | None) -> None:
        with self._state_lock:
            if service not in self._refresh_pending:
                return
            self._refresh_pending.remove(service)
            if error:
                label = "Quét thiết bị" if service == "scan" else "Đo kết nối"
                self._refresh_errors.append(f"{label}: {error}")
            if self._refresh_pending:
                return  # Chỉ worker cuối phát kết quả, tránh đảo thứ tự signal.
            connection = self._connection
            current_key = tuple(connection.get(key, "") for key in ("name", "ip", "netmask", "gateway", "profile_id", "adapter_id", "mac"))
            if self._refresh_scan_macs is not None and self._refresh_scan_connection == current_key:
                # Ping có thể đổi kết nối sau khi scan xong; xác minh lại tại đây.
                self._session_macs = set(self._refresh_scan_macs)
            else:
                self._session_macs.clear()
                if self._refresh_scan_macs is not None:
                    self._refresh_errors.append("Kết nối đã thay đổi trong lúc làm mới; hãy thử lại.")
            if self._refresh_errors:
                message = "Làm mới gặp lỗi. " + " | ".join(self._refresh_errors)
            else:
                message = f"Đã làm mới mạng lúc {now():%H:%M:%S}."
            self._refresh_status = {
                "request_id": self._refresh_request_id,
                "running": False,
                "message": message,
                "errors": list(self._refresh_errors),
            }
            snapshot = self.get_refresh_status()
        self.devices_refreshed.emit()
        self.network_refresh_changed.emit(snapshot)

    def get_latest_measurements(self) -> dict:
        with self._state_lock:
            return deepcopy(self._latest_measurements)

    def get_latest_diagnosis(self) -> Diagnosis | None:
        with self._state_lock:
            return self._latest_diagnosis

    def get_device_status(self, device: Device) -> str:
        with self._state_lock:
            if not self._connection.get("connected"):
                return "Chưa xác minh (mất LAN)"
            if device.mac.lower() not in self._session_macs:
                return "Chưa xác minh trong phiên"
        return "Online" if device.online else "Offline"

    def _emit_device(self, device: Device, event: str) -> None:
        """Callback từ luồng quét, chuyển thành signal Qt."""
        if self._scoped and current_network() != self._storage_network:
            return
        with self._state_lock:
            if self._scoped and current_network() != self._storage_network:
                return
            self._session_macs.add(device.mac.lower())
        self.device_updated.emit(device)

    def _emit_alert(self, alert: Alert) -> None:
        """Callback từ luồng quét, chuyển thành signal Qt."""
        self.alert_raised.emit(replace(alert, network_id=current_network()))
        if self._notifications:
            self._notifications.enqueue(alert)

    def _emit_diagnosis(self, diagnosis: Diagnosis) -> None:
        """Ghi nhớ kết luận trong phiên và chuyển sang signal Qt."""
        if self._scoped and current_network() != self._storage_network:
            return
        with self._state_lock:
            if self._scoped and current_network() != self._storage_network:
                return
            repository.add_diagnosis(diagnosis, self._session_id)
            self._diagnoses.append(diagnosis)
            self._diagnoses = self._diagnoses[-500:]
            self._latest_diagnosis = diagnosis
        self.diagnosis_changed.emit(diagnosis)

    def _emit_arp_observation(self, observation) -> None:
        """Đưa gói ARP quan sát được qua bộ phát hiện rồi phát cảnh báo Qt."""
        if self._arp_detector is None:
            return
        import time
        stamp = time.monotonic()
        key = (observation.ip, observation.mac)
        for old, seen in list(self._observation_times.items()):
            if stamp-seen > 30:
                self._observation_times.pop(old, None)
        # Lưu quan sát thụ động có ngân sách: 10 claim khác nhau/giây, tối đa 1.024 khóa.
        if stamp-self._observation_times.get(key, 0) >= 5 and len(self._observation_times) < 1024 and sum(stamp-t < 1 for t in self._observation_times.values()) < 10:
            repository.record_observation(observation.ip, observation.mac, observation.ts, self._session_id)
            self._observation_times[key] = stamp
        for alert in self._arp_detector.observe(observation):
            self._emit_alert(alert)

    def _service_status(self, status):
        self._services[status["service"]] = dict(status)
        self.service_status_changed.emit(dict(status))
        error = status.get("error")
        if error:
            logging.getLogger(__name__).warning("%s: %s", status["service"], error)
            with network_scope(self._storage_network):
                alert = Alert("warning", f"{status['service']}: {error}", kind=f"service:{status['service']}")
                if repository.add_alert_once(alert):
                    self._emit_alert(alert)

    def _save_route(self, hops):
        if self._scoped and current_network() != self._storage_network:
            return
        with self._state_lock:
            if self._scoped and current_network() != self._storage_network:
                return
            repository.add_route(hops, self._session_id)
            self._last_traceroute = (now(), list(hops))
        self.traceroute_done.emit(hops)

    @storage_method
    def accept_gateway(self, mac):
        device = repository.get_device(mac)
        if device is None or device.ip != self._connection.get("gateway"):
            raise ValueError("Chọn đúng thiết bị ở địa chỉ gateway của mạng hiện tại.")
        repository.set_meta("gateway_mac", repository.valid_mac(mac))
        if self._arp_detector:
            self._arp_detector._gateway_owner = mac.lower()

    # ------------------------------------------------------------------ thiết bị
    @storage_method
    def list_devices(self) -> list[Device]:
        return repository.list_devices()

    @storage_method
    def set_trusted(self, mac: str, trusted: bool) -> None:
        repository.set_trusted(mac, trusted)
        device = repository.get_device(mac)
        if device is not None:
            self.device_updated.emit(device)

    @storage_method
    def rename(self, mac: str, name: str, note: str) -> None:
        repository.set_name_note(mac, name, note)
        device = repository.get_device(mac)
        if device is not None:
            self.device_updated.emit(device)

    @storage_method
    def set_device_type(self, mac: str, device_type: str) -> None:
        from extras.device_identity import DEVICE_TYPES

        if device_type and device_type not in DEVICE_TYPES:
            raise ValueError("Loại thiết bị không hợp lệ.")
        repository.set_type_override(mac, device_type)
        device = repository.get_device(mac)
        if device is not None:
            self.device_updated.emit(device)

    # ------------------------------------------------------------------ đường cơ sở
    @storage_method
    def is_first_run(self) -> bool:
        from services import baseline

        return baseline.is_first_run()

    @storage_method
    def finish_baseline(self) -> None:
        from services import baseline

        baseline.finish_baseline()

    # ------------------------------------------------------------------ cảnh báo, lịch sử
    @storage_method
    def get_alerts(self, limit: int = 100, *, offset=0, query="") -> list[Alert]:
        return repository.list_alerts(limit, offset=offset, query=query)

    @storage_method
    def acknowledge_alert(self, identifier):
        repository.acknowledge_alert(identifier)

    @storage_method
    def get_device_history(self, mac: str, hours: int) -> list[tuple[datetime, bool | None]]:
        if hours < 0:
            raise ValueError("Khoảng thời gian lấy lịch sử thiết bị không được âm.")
        since, end = now()-timedelta(hours=hours), now()
        events = repository.get_presence(mac, since=since)
        sessions = repository.get_sessions(since, end)
        for session in sessions:
            start_at = repository._from_iso(session["started"])
            end_at = repository._from_iso(session["ended"])
            if since <= start_at <= end:
                events.append((start_at, None))
            if since <= end_at <= end:
                events.append((end_at, None))
        if not any(repository._from_iso(s["started"]) <= since <= repository._from_iso(s["ended"]) for s in sessions):
            events.append((since, None))
        return sorted(events, key=lambda event: event[0])

    # ------------------------------------------------------------------ lịch sử ping
    @storage_method
    def get_ping_history(self, target: str, minutes: int) -> list[PingResult]:
        if minutes < 0:
            raise ValueError("Khoảng thời gian lấy lịch sử ping không được âm.")
        return repository.get_pings(target, since=now() - timedelta(minutes=minutes), session_id=self._session_id if self._scoped and self._session_id else None)

    @storage_method
    def backup_database(self, path):
        from db.database import backup_to
        backup_to(path)

    def restore_database(self, path):
        from db.database import backup_to, restore_from, database_path
        from db import database
        from core.instance_lock import InstanceLock
        running = self._loop is not None
        self.stop()
        try:
            with InstanceLock(database.DB_PATH), network_scope(self._storage_network):
                backup_to(str(database_path()) + f".before-restore-{now():%Y%m%d%H%M%S}.bak")
                restore_from(path)
        finally:
            if running:
                self.start()

    def available_profiles(self):
        from pathlib import Path
        from db import database
        import sqlite3
        from contextlib import closing
        base = Path(database.DB_PATH).resolve()
        choices = {"Dữ liệu cũ chưa xác định mạng": "legacy"}
        for path in sorted((base.parent / "networks").glob("*.db")):
            try:
                with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
                    row = connection.execute("SELECT started,interface FROM Sessions ORDER BY started DESC LIMIT 1").fetchone()
                import json
                interface = json.loads(row[1]) if row else {}
                label = f"{interface.get('name', '?')} {interface.get('ip', '?')} - {row[0] if row else '?'} [{path.stem[:8]}]"
                choices[label] = path.stem
            except (ValueError, sqlite3.Error):
                continue
        self._profile_choices = choices
        return list(choices)

    def select_history(self, label):
        selected = self._profile_choices[label]
        self.stop()
        self._storage_network = selected
        self._scoped = True
        self.connection_changed.emit({"connected": False})
        self.devices_refreshed.emit()

    def run_wifi_scan(self):
        if self._utility_thread and self._utility_thread.is_alive():
            raise RuntimeError("Đang chạy công cụ Wi-Fi.")
        def worker():
            from extras.wifi_channels import scan_wifi_status, recommend_channel
            result = scan_wifi_status()
            channel = recommend_channel(result["networks"])
            lines = [f"{n['ssid']} - {n['band']} - kênh {n['channel']} - {n['rssi']} dBm (ước lượng)" for n in result["networks"]]
            text = result["message"] + "\n" + "\n".join(lines)
            text += f"\nGợi ý 2.4 GHz: {channel if channel else 'chưa đủ dữ liệu'}. Ước lượng từ tín hiệu AP, chưa đo channel width, tải, nhiễu ngoài Wi-Fi hoặc AP của chính bạn."
            self.utility_finished.emit(text)
        self._utility_thread = threading.Thread(target=worker, name="netguard-wifi", daemon=True)
        self._utility_thread.start()

    def run_traceroute(self, target: str = "1.1.1.1") -> None:
        from core.traceroute import trace

        from core.interfaces import get_active_interface
        chosen = get_active_interface()
        generation, storage = self._generation, self._storage_network
        with self._traceroute_lock:
            if self._traceroute_thread is not None and self._traceroute_thread.is_alive():
                raise RuntimeError("Traceroute đang chạy, hãy chờ kết quả hiện tại.")
            self._traceroute_stop.clear()

            def worker() -> None:
                try:
                    hops = trace(target, stop_event=self._traceroute_stop, iface=chosen)
                    if generation != self._generation or self._traceroute_stop.is_set():
                        return
                    with network_scope(storage):
                        self._save_route(hops)
                except Exception as exc:
                    if not self._traceroute_stop.is_set():
                        self._service_status({"service": "traceroute", "running": False, "error": str(exc)})
                finally:
                    with self._traceroute_lock:
                        self._traceroute_thread = None

            self._traceroute_thread = threading.Thread(
                target=worker,
                name="netguard-traceroute",
                daemon=True,
            )
            self._traceroute_thread.start()

    @storage_method
    def export_report(self, start: datetime, end: datetime, path: str) -> None:
        import os
        import tempfile
        from pathlib import Path
        from extras.pdf_report import build_report
        from db.database import read_snapshot
        start, end = local_time(start), local_time(end)
        if end < start or end-start > timedelta(days=31):
            raise ValueError("Khoảng báo cáo phải hợp lệ và tối đa 31 ngày.")
        ping_stats, loss_events, coverage = {}, [], []
        with read_snapshot() as connection:
            for target in ("router", "isp", "external"):
                args = (target, repository._to_iso(start), repository._to_iso(end))
                where = "target=? AND ts>=? AND ts<=?"
                row = connection.execute(f"SELECT count(*) AS all_samples, sum(status IN ('ok','timeout')) AS samples, avg(CASE WHEN status IN ('ok','timeout') THEN loss_pct END) AS loss, min(rtt_ms) AS minimum, max(rtt_ms) AS maximum, count(rtt_ms) AS replies FROM PingLog WHERE {where}", args).fetchone()
                replies = row["replies"]
                middle = connection.execute(f"SELECT rtt_ms FROM PingLog WHERE {where} AND rtt_ms IS NOT NULL ORDER BY rtt_ms LIMIT ? OFFSET ?", (*args, 2 if replies%2 == 0 else 1, max(0, (replies-1)//2))).fetchall() if replies else []
                ping_stats[target] = {"samples": row["samples"] or 0, "loss_pct": row["loss"],
                                      "rtt_min_ms": row["minimum"], "rtt_max_ms": row["maximum"],
                                      "rtt_median_ms": median(r[0] for r in middle) if middle else None}
                counts = {r[0]: r[1] for r in connection.execute(f"SELECT status,count(*) FROM PingLog WHERE {where} GROUP BY status", args)}
                coverage.append(f"{target}: {row['all_samples']} mốc đo đã lưu; trạng thái {counts}. N/A là thiếu dữ liệu, lỗi đo hoặc chưa giám sát; loss chỉ tính probe gửi được.")
                loss_events.extend(dict(r) for r in connection.execute(f"SELECT target,min(ts) AS ts,count(*) AS count FROM PingLog WHERE {where} AND status='timeout' GROUP BY target,substr(ts,1,13) ORDER BY ts LIMIT 500", args))
            sessions = repository.get_sessions(start, end, connection=connection)
            diagnoses = repository.get_diagnoses(start, end, connection=connection)
            routes = repository.get_routes(start, end, connection=connection)
        if self._report_stop.is_set():
            raise RuntimeError("Đã hủy xuất báo cáo.")
        coverage.append("Mỗi báo cáo chỉ thuộc hồ sơ mạng đã chọn. Các phiên tách rời không chứng minh kết nối liên tục. Thời gian hiển thị GMT+7. Sự kiện timeout được tổng hợp theo giờ; tối đa 500 nhóm cho mỗi mốc.")
        data = {"interface": sessions[0]["interface"] if len(sessions) == 1 else {},
                "sessions": sessions, "coverage_notes": coverage, "start": start, "end": end,
                "ping_stats": ping_stats, "loss_events": loss_events,
                "diagnoses": diagnoses[:500], "traceroute": routes}
        output = Path(path).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".netguard-", suffix=".pdf", dir=output.parent)
        os.close(descriptor)
        try:
            build_report(data, temporary, self._report_stop)
            if self._report_stop.is_set():
                raise RuntimeError("Đã hủy xuất báo cáo.")
            os.replace(temporary, output)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def export_report_async(self, start, end, path):
        if self._report_thread and self._report_thread.is_alive():
            raise RuntimeError("Một báo cáo đang được tạo.")
        storage = self._storage_network
        self._report_stop.clear()
        def worker():
            try:
                with network_scope(storage):
                    # Giữ hồ sơ đã chọn tại lúc bấm xuất dù kết nối đổi trong khi dựng.
                    Backend.export_report.__wrapped__(self, start, end, path)
                self.report_finished.emit({"ok": True, "path": path})
            except Exception as exc:
                logging.getLogger(__name__).exception("Xuất PDF thất bại")
                self.report_finished.emit({"ok": False, "error": str(exc)})
        self._report_thread = threading.Thread(target=worker, name="netguard-report", daemon=True)
        self._report_thread.start()

    def cancel_report(self):
        self._report_stop.set()
