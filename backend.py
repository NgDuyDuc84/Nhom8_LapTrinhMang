"""Giao diện duy nhất giữa giao diện người dùng (ui/) và lõi (core/, services/, db/).

Quy ước:
- ``BackendBase`` khai báo signal và chữ ký hàm; hàm chưa làm thì ``raise NotImplementedError``.
- ``Backend`` là bản thật (làm dần từ giai đoạn 5), dùng Scapy/icmplib/SQLite.
- ``FakeBackend`` (trong ``ui/fake_data.py``) dùng dữ liệu giả, để B làm giao diện trước.
- Chỉ file này được import PySide6; ``core/`` và ``services/`` chỉ phát sự kiện qua callback.
"""

from __future__ import annotations

import threading
from dataclasses import asdict
from datetime import datetime, timedelta
from statistics import mean, median

from PySide6.QtCore import QObject, Signal

from db import repository
from models import Alert, Device, Diagnosis, Hop, PingResult, now


class BackendBase(QObject):
    """Bộ khung chung mà cả Backend thật và FakeBackend đều kế thừa."""

    # --- Signal: lõi phát sự kiện, giao diện bắt và vẽ lại ---
    device_updated = Signal(object)      # Device: thiết bị mới hoặc vừa đổi trạng thái
    alert_raised = Signal(object)        # Alert: có cảnh báo mới
    ping_result = Signal(object)         # PingResult: một mẫu ping mới
    diagnosis_changed = Signal(object)   # Diagnosis: kết luận chẩn đoán vừa đổi
    traceroute_done = Signal(object)     # list[Hop]: traceroute chạy xong

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    # --- Vòng đời ---
    def start(self) -> None:
        """Bật các luồng nền (quét ARP định kỳ, ping định kỳ)."""
        raise NotImplementedError

    def stop(self) -> None:
        """Tắt các luồng nền và dọn tài nguyên, gọi được nhiều lần."""
        raise NotImplementedError

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

    # --- Đường cơ sở (baseline) ---
    def is_first_run(self) -> bool:
        """True nếu chưa hoàn tất lập đường cơ sở (lần chạy đầu tiên)."""
        raise NotImplementedError

    def finish_baseline(self) -> None:
        """Chốt đường cơ sở: từ đây thiết bị chưa tin cậy xuất hiện mới sẽ bị cảnh báo."""
        raise NotImplementedError

    # --- Cảnh báo và lịch sử ---
    def get_alerts(self, limit: int = 100) -> list[Alert]:
        """Trả về các cảnh báo gần nhất, mới nhất trước, tối đa ``limit`` bản ghi."""
        raise NotImplementedError

    def get_ping_history(self, target: str, minutes: int) -> list[PingResult]:
        """Trả về các mẫu ping của một mốc (``router``/``isp``/``external``) trong ``minutes`` phút."""
        raise NotImplementedError

    def get_device_history(self, mac: str, hours: int) -> list[tuple[datetime, bool]]:
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
        self._loop = None  # services.scan_loop.ScanLoop, khởi tạo trong start()
        self._ping_monitor = None
        self._arp_listener = None
        self._arp_detector = None
        self._traceroute_thread: threading.Thread | None = None
        self._traceroute_lock = threading.Lock()
        self._traceroute_stop = threading.Event()
        self._state_lock = threading.RLock()
        self._last_traceroute: tuple[datetime, list[Hop]] | None = None
        self._diagnoses: list[Diagnosis] = []

    # ------------------------------------------------------------------ vòng đời
    def start(self) -> None:
        """Tạo CSDL (nếu chưa có), bật luồng quét và phát danh sách thiết bị hiện có."""
        from db import database
        from core.interfaces import get_active_interface
        from core.arp_listener import ArpListener
        from services.ping_monitor import PingMonitor
        from services.scan_loop import ScanLoop
        from services.alerts import ArpAnomalyDetector

        if self._loop is not None:
            return
        database.initialize()
        try:
            iface = get_active_interface()
        except Exception:
            database.close()
            raise
        devices = repository.list_devices()
        self._arp_detector = ArpAnomalyDetector(iface.gateway, devices)
        self._arp_listener = ArpListener(self._emit_arp_observation, iface)
        self._loop = ScanLoop(
            on_device=self._emit_device,
            on_alert=self._emit_alert,
            iface=iface,
        )
        self._ping_monitor = PingMonitor(
            on_ping=self.ping_result.emit,
            on_diagnosis=self._emit_diagnosis,
            iface=iface,
        )
        try:
            try:
                self._arp_listener.start()
            except RuntimeError as exc:
                self._arp_listener = None
                self.alert_raised.emit(Alert(level="warning", message=f"Không bật được nghe ARP: {exc}"))
            for device in repository.list_devices():
                self.device_updated.emit(device)
            self._loop.start()
            self._ping_monitor.start()
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        """Dừng luồng quét và đóng kết nối CSDL. Gọi nhiều lần vẫn an toàn."""
        from db import database

        if self._arp_listener is not None:
            self._arp_listener.stop()
            self._arp_listener = None
        if self._ping_monitor is not None:
            self._ping_monitor.stop()
            self._ping_monitor = None
        if self._loop is not None:
            self._loop.stop()
            self._loop = None
        trace_thread = self._traceroute_thread
        if trace_thread is not None and trace_thread.is_alive():
            self._traceroute_stop.set()
            trace_thread.join(5.0)
        database.close()

    def _emit_device(self, device: Device, event: str) -> None:
        """Callback từ luồng quét, chuyển thành signal Qt."""
        self.device_updated.emit(device)

    def _emit_alert(self, alert: Alert) -> None:
        """Callback từ luồng quét, chuyển thành signal Qt."""
        self.alert_raised.emit(alert)

    def _emit_diagnosis(self, diagnosis: Diagnosis) -> None:
        """Ghi nhớ kết luận trong phiên và chuyển sang signal Qt."""
        with self._state_lock:
            self._diagnoses.append(diagnosis)
            self._diagnoses = self._diagnoses[-500:]
        self.diagnosis_changed.emit(diagnosis)

    def _emit_arp_observation(self, observation) -> None:
        """Đưa gói ARP quan sát được qua bộ phát hiện rồi phát cảnh báo Qt."""
        if self._arp_detector is None:
            return
        for alert in self._arp_detector.observe(observation):
            self.alert_raised.emit(alert)

    # ------------------------------------------------------------------ thiết bị
    def list_devices(self) -> list[Device]:
        return repository.list_devices()

    def set_trusted(self, mac: str, trusted: bool) -> None:
        repository.set_trusted(mac, trusted)
        device = repository.get_device(mac)
        if device is not None:
            self.device_updated.emit(device)

    def rename(self, mac: str, name: str, note: str) -> None:
        repository.set_name_note(mac, name, note)
        device = repository.get_device(mac)
        if device is not None:
            self.device_updated.emit(device)

    # ------------------------------------------------------------------ đường cơ sở
    def is_first_run(self) -> bool:
        from services import baseline

        return baseline.is_first_run()

    def finish_baseline(self) -> None:
        from services import baseline

        baseline.finish_baseline()

    # ------------------------------------------------------------------ cảnh báo, lịch sử
    def get_alerts(self, limit: int = 100) -> list[Alert]:
        return repository.list_alerts(limit)

    def get_device_history(self, mac: str, hours: int) -> list[tuple[datetime, bool]]:
        if hours < 0:
            raise ValueError("Khoảng thời gian lấy lịch sử thiết bị không được âm.")
        return repository.get_presence(mac, since=now() - timedelta(hours=hours))

    # ------------------------------------------------------------------ lịch sử ping
    def get_ping_history(self, target: str, minutes: int) -> list[PingResult]:
        if minutes < 0:
            raise ValueError("Khoảng thời gian lấy lịch sử ping không được âm.")
        return repository.get_pings(target, since=now() - timedelta(minutes=minutes))

    def run_traceroute(self, target: str = "1.1.1.1") -> None:
        from core.traceroute import trace

        with self._traceroute_lock:
            if self._traceroute_thread is not None and self._traceroute_thread.is_alive():
                raise RuntimeError("Traceroute đang chạy, hãy chờ kết quả hiện tại.")
            self._traceroute_stop.clear()

            def worker() -> None:
                try:
                    hops = trace(target, stop_event=self._traceroute_stop)
                    with self._state_lock:
                        self._last_traceroute = (now(), hops)
                    self.traceroute_done.emit(hops)
                except Exception as exc:
                    if not self._traceroute_stop.is_set():
                        self.alert_raised.emit(
                            Alert(level="warning", message=f"Traceroute thất bại: {exc}")
                        )
                finally:
                    with self._traceroute_lock:
                        self._traceroute_thread = None

            self._traceroute_thread = threading.Thread(
                target=worker,
                name="netguard-traceroute",
                daemon=True,
            )
            self._traceroute_thread.start()

    def export_report(self, start: datetime, end: datetime, path: str) -> None:
        if end < start:
            raise ValueError("Thời điểm kết thúc báo cáo phải sau thời điểm bắt đầu.")
        from core.interfaces import get_active_interface
        from extras.pdf_report import build_report

        ping_history = {
            target: [
                sample
                for sample in repository.get_pings(target, since=start)
                if sample.ts <= end
            ]
            for target in ("router", "isp", "external")
        }
        ping_stats: dict[str, dict] = {}
        loss_events: list[dict] = []
        for target, samples in ping_history.items():
            rtts = [sample.rtt_ms for sample in samples if sample.rtt_ms is not None]
            ping_stats[target] = {
                "samples": len(samples),
                "loss_pct": mean(sample.loss_pct for sample in samples) if samples else 0.0,
                "rtt_median_ms": median(rtts) if rtts else None,
                "rtt_min_ms": min(rtts) if rtts else None,
                "rtt_max_ms": max(rtts) if rtts else None,
            }
            loss_events.extend(
                {"target": target, "ts": sample.ts}
                for sample in samples
                if sample.rtt_ms is None
            )

        try:
            interface = asdict(get_active_interface())
        except (RuntimeError, OSError):
            interface = {}
        with self._state_lock:
            diagnoses = [item for item in self._diagnoses if start <= item.ts <= end]
            last_trace = self._last_traceroute
        traceroute_data = []
        if last_trace is not None:
            trace_time, hops = last_trace
            if start <= trace_time <= end:
                traceroute_data = [{"ts": trace_time, "hops": hops}]

        data = {
            "interface": interface,
            "start": start,
            "end": end,
            "ping_stats": ping_stats,
            "loss_events": sorted(loss_events, key=lambda event: event["ts"]),
            "diagnoses": diagnoses,
            "traceroute": traceroute_data,
        }
        try:
            build_report(data, path)
        except NotImplementedError as exc:
            raise RuntimeError(
                "Chưa thể xuất PDF: module extras.pdf_report của C chưa được cài đặt."
            ) from exc
