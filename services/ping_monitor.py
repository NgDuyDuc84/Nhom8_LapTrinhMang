"""Ping định kỳ ba mốc, lưu lịch sử và phát kết luận ổn định qua callback."""

from __future__ import annotations

import statistics
import sys
import threading
import time
from contextlib import nullcontext
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor
from core.network_context import network_id, network_scope, connection_key
from config import SETTINGS
from collections import deque
from typing import Callable

from config import (
    DIAG_STABLE_WINDOWS,
    DIAG_WINDOW_SAMPLES,
    PING_EXTERNAL_TARGET,
    PING_INTERVAL_SEC,
    PING_TIMEOUT_SEC,
    TRACE_MAX_HOPS,
)
from core.diagnosis import TargetStats, diagnose
from core.icmp import ping_once
from core.interfaces import NetInterface, get_active_interface
from core.traceroute import find_isp_hop, trace
from db import repository
from models import Diagnosis, PingResult

PingCallback = Callable[[PingResult], None]
DiagnosisCallback = Callable[[Diagnosis], None]
CycleCallback = Callable[[dict[str, PingResult | None]], None]

__all__ = ["PingMonitor"]


def _log(message: str) -> None:
    try:
        print(message, file=sys.stderr)
    except (OSError, UnicodeEncodeError):
        pass


class PingMonitor:
    """Theo dõi router, hop ISP và máy chủ ngoài trong một luồng nền."""

    ROUTE_RETRY_SEC = 60.0
    ROUTE_REFRESH_SEC = 300.0

    def __init__(
        self,
        on_ping: PingCallback | None = None,
        on_diagnosis: DiagnosisCallback | None = None,
        on_cycle: CycleCallback | None = None,
        iface: NetInterface | None = None,
        pinger: Callable[[str, float], float | None] | None = None,
        tracer: Callable[..., list] | None = None,
        interval: float = PING_INTERVAL_SEC,
        interface_resolver: Callable[[], NetInterface] | None = None,
        on_interface: Callable[[NetInterface | None], None] | None = None,
        on_refresh: Callable[[str | None], None] | None = None,
        scoped=False, session_provider=None, on_route=None, generation_provider=None,
    ) -> None:
        self._storage_network = "legacy"
        self._generation_provider = generation_provider or (lambda: 0)
        self._cycle_session = ""
        self._scoped = scoped
        self._owns_session = scoped and session_provider is None
        self._owned_session = ""
        self._session_provider = session_provider or (lambda: self._owned_session)
        self._on_route = on_route or (lambda hops: None)
        self._sample_times = {}
        self._baselines = {}
        self._sample_addresses = {}
        self._on_ping = on_ping or (lambda result: None)
        self._on_diagnosis = on_diagnosis or (lambda result: None)
        self._on_cycle = on_cycle or (lambda results: None)
        self._on_interface = on_interface or (lambda chosen: None)
        self._on_refresh = on_refresh or (lambda error: None)
        self._iface = iface
        self._preferred_iface = iface
        self._resolve_interface = interface_resolver or (lambda: get_active_interface(self._preferred_iface))
        self._pinger = pinger or (lambda address, timeout: ping_once(
            address, timeout, source=self._iface.ip,
        ))
        self._tracer = tracer or trace
        self._interval = max(0.1, float(interval))
        self._history: dict[str, deque[float | None]] = {
            name: deque(maxlen=DIAG_WINDOW_SAMPLES)
            for name in ("router", "isp", "external")
        }
        self._timestamps = {name: deque(maxlen=DIAG_WINDOW_SAMPLES) for name in self._history}
        self._isp_ip: str | None = None
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._refresh_lock = threading.Lock()
        self._refresh_requested = False
        self._thread: threading.Thread | None = None
        self._route_thread: threading.Thread | None = None
        self._route_lock = threading.RLock()
        self._last_route_attempt = 0.0
        self._last_emitted_verdict: str | None = None
        self._pending_verdict: str | None = None
        self._pending_windows = 0
        self.last_error: str | None = None
        self.target_status: dict[str, str] = {}
        self._network_key: tuple | None = None
        self._network_generation = 0
        self._last_emitted_text: str | None = None
        self._addresses: dict[str, str | None] = dict.fromkeys(self._history)

    @property
    def addresses(self) -> dict[str, str | None]:
        return dict(self._addresses)

    def start(self) -> None:
        """Khởi động ping và việc tìm hop ISP nếu chưa có."""
        if self.is_running():
            return
        self._network_key = None
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="netguard-ping", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 30.0) -> None:
        """Dừng ping và chờ các luồng phụ kết thúc."""
        self._stop_event.set()
        self._wake_event.set()
        current = threading.current_thread()
        for thread in (self._thread, self._route_thread):
            if thread is not None and thread is not current and thread.is_alive():
                thread.join(timeout)
        if any(thread and thread.is_alive() for thread in (self._thread, self._route_thread)):
            raise RuntimeError("Luồng đo mạng chưa dừng; giữ tài nguyên để dừng lại an toàn.")
        self._thread = None
        self._route_thread = None
        if self._owns_session and self._owned_session:
            with network_scope(self._storage_network):
                repository.end_session(self._owned_session)
            self._owned_session = ""

    def is_running(self) -> bool:
        """True nếu luồng ping chính đang chạy."""
        return self._thread is not None and self._thread.is_alive()

    def request_refresh(self) -> None:
        """Đánh thức worker để chọn lại card và thu mẫu mới, không đo chồng nhau."""
        with self._refresh_lock:
            if not self.is_running() or self._stop_event.is_set():
                raise RuntimeError("Dịch vụ đo mạng chưa chạy hoặc đang dừng.")
            self._refresh_requested = True
            self._wake_event.set()

    def _run(self) -> None:
        """Lặp ping theo chu kỳ; lỗi một mốc không làm chết monitor."""
        while not self._stop_event.is_set():
            with self._refresh_lock:
                refresh = self._refresh_requested
                self._refresh_requested = False
                self._wake_event.clear()
            if self._stop_event.is_set():
                break
            cycle_started = time.monotonic()
            try:
                error = self._cycle(reselect=refresh)
            except Exception as exc:
                self.last_error = str(exc)
                error = str(exc)
                _log(f"[ping lỗi] {exc} — sẽ thử lại ở chu kỳ sau")
            if refresh:
                self._safe_callback(self._on_refresh, error)
            self._maybe_start_route_discovery()
            self._wake_event.wait(max(0.0, self._interval - (time.monotonic() - cycle_started)))

    def _cycle(self, *, reselect: bool = False) -> str | None:
        """Trả lỗi của chính chu kỳ này để báo kết quả làm mới, nếu có."""
        self.last_error = None
        self._cycle_session = self._session_provider()
        self.target_status = {}
        self._addresses = dict.fromkeys(self._history)
        if reselect:
            self._preferred_iface = None
        try:
            iface = self._resolve_interface()
        except (RuntimeError, OSError, ValueError) as exc:
            self._set_interface(None, force=reselect)
            self.last_error = str(exc)
            self.target_status = {name: "chưa kết nối LAN" for name in self._history}
            self._record_unavailable("offline")
            self._safe_callback(self._on_cycle, {name: None for name in self._history})
            self._update_stable_diagnosis(Diagnosis(
                "home_issue", f"Máy đang mất kết nối LAN hoặc chưa có cấu hình IPv4. {exc}",
            ), immediate=True)
            return str(exc)

        self._set_interface(iface, force=reselect)
        self._cycle_session = self._session_provider()
        generation = self._generation_provider()
        if self._preferred_iface is None:
            self._preferred_iface = iface
        if not iface.gateway:
            self.target_status = {
                "router": "không có gateway",
                "isp": "không có gateway",
                "external": "chưa đo: không có gateway",
            }
            self._record_unavailable("unavailable")
            self._safe_callback(self._on_cycle, {name: None for name in self._history})
            self._update_stable_diagnosis(Diagnosis(
                "unknown", f"Card '{iface.name}' có IPv4 nhưng không có gateway mặc định; "
                "chưa thể chẩn đoán đường ra Internet.",
            ), immediate=True)
            return "Không có gateway mặc định; chưa đo được kết nối Internet."
        if reselect:
            self._update_stable_diagnosis(Diagnosis(
                "unknown", "Đã làm mới mạng; đang thu thập mẫu mới để chẩn đoán.",
            ), immediate=True)
        addresses = {
            "router": iface.gateway or None,
            "isp": self._isp_ip,
            "external": PING_EXTERNAL_TARGET,
        }
        self._addresses = addresses
        cycle_results: dict[str, PingResult | None] = {name: None for name in addresses}
        cycle_error = None
        # I/O độc lập chạy cùng lúc; callback/SQLite vẫn chỉ chạy trên worker chính.
        def measure(address):
            if self._stop_event.is_set():
                return None, RuntimeError("Đã dừng đo mạng")
            try:
                return self._pinger(address, PING_TIMEOUT_SEC), None
            except Exception as exc:
                return None, exc
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="netguard-probe") as pool:
            futures = {target: pool.submit(measure, address) for target, address in addresses.items() if address}
            for target, address in addresses.items():
                if self._stop_event.is_set():
                    return "Đã dừng đo mạng."
                if address is None:
                    self.target_status[target] = "chưa xác định hop (sẽ thử lại)"
                    self._store(PingResult(target, None, 0, status="unavailable", session_id=self._cycle_session))
                    continue
                rtt, error = futures[target].result()
                if self._stop_event.is_set() or generation != self._generation_provider():
                    return "Phiên kết nối đã thay đổi trong lúc đo; bỏ mẫu cũ."
                if error:
                    self.last_error = cycle_error = str(error)
                    self.target_status[target] = f"lỗi đo: {error}"
                    self._store(PingResult(target, None, 0, address=address, session_id=self._cycle_session, status="measurement_error"))
                    continue
                with self._route_lock:
                    self._expire(target, address)
                    if target == "isp" and address != self._isp_ip:
                        self.target_status[target] = "hop vừa thay đổi; chờ mẫu mới"
                        continue
                    result = PingResult(target, rtt, 0.0 if rtt is not None else 100.0,
                                        address=address, session_id=self._cycle_session,
                                        status="ok" if rtt is not None else "timeout")
                    cycle_results[target] = result
                    self._history[target].append(rtt)
                    self._timestamps[target].append(time.monotonic())
                    self._sample_times[target] = time.monotonic()
                self._store(result)
                self._safe_callback(self._on_ping, result)

        self._safe_callback(self._on_cycle, cycle_results)
        stats = {name: self._stats(name, available=cycle_results[name] is not None)
                 for name in self._history}
        current = diagnose(stats["router"], stats["isp"], stats["external"])
        self._update_stable_diagnosis(current)
        return cycle_error

    def _set_interface(self, iface: NetInterface | None, *, force: bool = False) -> None:
        key = connection_key(iface)
        with self._route_lock:
            previous_storage = self._storage_network
            self._iface = iface
            if iface is not None and self._scoped:
                self._storage_network = network_id(iface)
            if key == self._network_key and not force:
                return
            if self._owns_session:
                with network_scope(previous_storage):
                    if self._owned_session:
                        repository.end_session(self._owned_session)
                self._owned_session = ""
                if iface is not None:
                    with network_scope(self._storage_network):
                        self._owned_session = repository.start_session(asdict(iface))
            self._network_key = key
            self._network_generation += 1
            self._isp_ip = None
            self._last_route_attempt = 0.0
            self._pending_windows = 0
            self._pending_verdict = None
            self._last_emitted_verdict = None
            self._last_emitted_text = None
            self._sample_times.clear()
            self._sample_addresses.clear()
            self._baselines.clear()
            for history in self._history.values():
                history.clear()
            for timestamps in self._timestamps.values():
                timestamps.clear()
        self._safe_callback(self._on_interface, iface)

    def _stats(self, target: str, available: bool) -> TargetStats:
        with self._route_lock:
            self._expire(target, self._addresses.get(target))
            samples = list(self._history[target])
            successful = sorted(value for value in samples if value is not None)
            baseline = None
            median = statistics.median(successful) if successful else None
            if successful:
                candidate = successful[int((len(successful) - 1) * 0.25)]
                self._baselines[target] = min(candidate, self._baselines.get(target, candidate))
                baseline = self._baselines[target]
            loss_pct = (sum(value is None for value in samples) / len(samples) * 100.0) if samples else 0.0
            return TargetStats(
                loss_pct=loss_pct,
                rtt_median=median,
                rtt_baseline=baseline,
                samples=len(samples),
                available=available,
                rtt_limit=SETTINGS["router_rtt_ms"] if target == "router" else SETTINGS["external_rtt_ms"],
            )

    def _update_stable_diagnosis(self, diagnosis: Diagnosis, *, immediate: bool = False) -> None:
        if diagnosis.verdict == self._pending_verdict:
            self._pending_windows += 1
        else:
            self._pending_verdict = diagnosis.verdict
            self._pending_windows = 1

        if not immediate and self._pending_windows < DIAG_STABLE_WINDOWS:
            return
        if (diagnosis.verdict, diagnosis.text) == (self._last_emitted_verdict, self._last_emitted_text):
            return
        self._last_emitted_verdict = diagnosis.verdict
        self._last_emitted_text = diagnosis.text
        if self._owns_session:
            with network_scope(self._storage_network):
                repository.add_diagnosis(diagnosis, self._owned_session)
        self._safe_callback(self._on_diagnosis, diagnosis)

    def _maybe_start_route_discovery(self) -> None:
        if self._iface is None or not self._iface.gateway:
            return
        now = time.monotonic()
        interval = self.ROUTE_RETRY_SEC if self._isp_ip is None else self.ROUTE_REFRESH_SEC
        if now - self._last_route_attempt < interval:
            return
        with self._route_lock:
            if self._route_thread is not None and self._route_thread.is_alive():
                return
            self._last_route_attempt = now
            self._route_thread = threading.Thread(
                target=self._discover_isp,
                args=(self._iface, self._network_generation),
                name="netguard-route-discovery",
                daemon=True,
            )
            self._route_thread.start()

    def _discover_isp(self, iface: NetInterface, generation: int) -> None:
        try:
            hops = self._tracer(
                PING_EXTERNAL_TARGET,
                max_hops=TRACE_MAX_HOPS,
                timeout=0.25,
                stop_event=self._stop_event,
                iface=iface,
            )
            hop = find_isp_hop(hops, iface.gateway, PING_EXTERNAL_TARGET)
            with self._route_lock:
                if generation != self._network_generation or self._stop_event.is_set():
                    return  # Kết quả traceroute của kết nối cũ không được dùng lại.
                new_address = hop.ip if hop is not None else None
                if new_address != self._isp_ip:
                    self._history["isp"].clear()
                    self._timestamps["isp"].clear()
                    self._baselines.pop("isp", None)
                    self._sample_times.pop("isp", None)
                self._isp_ip = new_address
            context = network_scope(network_id(iface)) if self._scoped else nullcontext()
            with context:
                if self._owns_session:
                    repository.add_route(hops, self._owned_session)
                self._safe_callback(self._on_route, hops)
        except Exception as exc:
            if not self._stop_event.is_set():
                self.last_error = str(exc)
                _log(f"[tìm hop nhà mạng] {exc}")

    def _expire(self, target, address):
        old_address = self._sample_addresses.get(target)
        expired = time.monotonic()-self._sample_times.get(target, time.monotonic()) > max(15, self._interval*DIAG_WINDOW_SAMPLES*2)
        if expired or (old_address is not None and address != old_address):
            self._history[target].clear()
            self._timestamps[target].clear()
            self._baselines.pop(target, None)
        horizon = max(15, self._interval*DIAG_WINDOW_SAMPLES*2)
        stamps = self._timestamps[target]
        if len(stamps) == len(self._history[target]):
            while stamps and time.monotonic()-stamps[0] > horizon:
                stamps.popleft()
                self._history[target].popleft()
        self._sample_addresses[target] = address

    def _store(self, result):
        context = network_scope(self._storage_network) if self._scoped else nullcontext()
        with context:
            repository.add_ping(result)

    def _record_unavailable(self, status):
        for target in self._history:
            self._store(PingResult(target, None, 0, session_id=self._cycle_session, status=status))

    def _safe_callback(self, callback: Callable, value) -> None:
        try:
            context = network_scope(self._storage_network) if self._scoped else nullcontext()
            with context:
                callback(value)
        except Exception as exc:
            _log(f"[callback ping] {exc}")
