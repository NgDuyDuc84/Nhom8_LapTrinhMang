"""Ping định kỳ ba mốc, lưu lịch sử và phát kết luận ổn định qua callback."""

from __future__ import annotations

import statistics
import sys
import threading
import time
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
    ) -> None:
        self._on_ping = on_ping or (lambda result: None)
        self._on_diagnosis = on_diagnosis or (lambda result: None)
        self._on_cycle = on_cycle or (lambda results: None)
        self._iface = iface
        self._pinger = pinger or ping_once
        self._tracer = tracer or trace
        self._interval = max(0.1, float(interval))
        self._history: dict[str, deque[float | None]] = {
            name: deque(maxlen=DIAG_WINDOW_SAMPLES)
            for name in ("router", "isp", "external")
        }
        self._isp_ip: str | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._route_thread: threading.Thread | None = None
        self._route_lock = threading.Lock()
        self._last_route_attempt = 0.0
        self._last_emitted_verdict: str | None = None
        self._pending_verdict: str | None = None
        self._pending_windows = 0
        self.last_error: str | None = None

    def start(self) -> None:
        """Khởi động ping và việc tìm hop ISP nếu chưa có."""
        if self.is_running():
            return
        self._iface = self._iface or get_active_interface()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="netguard-ping", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 30.0) -> None:
        """Dừng ping và chờ các luồng phụ kết thúc."""
        self._stop_event.set()
        current = threading.current_thread()
        for thread in (self._thread, self._route_thread):
            if thread is not None and thread is not current and thread.is_alive():
                thread.join(timeout)
        self._thread = None
        self._route_thread = None

    def is_running(self) -> bool:
        """True nếu luồng ping chính đang chạy."""
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        """Lặp ping theo chu kỳ; lỗi một mốc không làm chết monitor."""
        while not self._stop_event.is_set():
            cycle_started = time.monotonic()
            try:
                self._cycle()
            except Exception as exc:
                self.last_error = str(exc)
                _log(f"[ping lỗi] {exc} — sẽ thử lại ở chu kỳ sau")
            self._maybe_start_route_discovery()
            self._stop_event.wait(max(0.0, self._interval - (time.monotonic() - cycle_started)))

    def _cycle(self) -> None:
        iface = self._iface or get_active_interface()
        addresses = {
            "router": iface.gateway or None,
            "isp": self._isp_ip,
            "external": PING_EXTERNAL_TARGET,
        }
        cycle_results: dict[str, PingResult | None] = {name: None for name in addresses}
        for target, address in addresses.items():
            if self._stop_event.is_set():
                return
            if address is None:
                continue
            try:
                rtt = self._pinger(address, PING_TIMEOUT_SEC)
            except Exception as exc:
                self.last_error = str(exc)
                _log(f"[ping {target}] {exc}")
                rtt = None
            loss_pct = 0.0 if rtt is not None else 100.0
            result = PingResult(target=target, rtt_ms=rtt, loss_pct=loss_pct)
            cycle_results[target] = result
            self._history[target].append(rtt)
            repository.add_ping(result)
            self._safe_callback(self._on_ping, result)

        self._safe_callback(self._on_cycle, cycle_results)
        stats = {name: self._stats(name, available=addresses[name] is not None) for name in self._history}
        current = diagnose(stats["router"], stats["isp"], stats["external"])
        self._update_stable_diagnosis(current)

    def _stats(self, target: str, available: bool) -> TargetStats:
        samples = list(self._history[target])
        successful = sorted(value for value in samples if value is not None)
        baseline = None
        median = statistics.median(successful) if successful else None
        if successful:
            baseline = successful[int((len(successful) - 1) * 0.25)]
        loss_pct = (sum(value is None for value in samples) / len(samples) * 100.0) if samples else 0.0
        return TargetStats(
            loss_pct=loss_pct,
            rtt_median=median,
            rtt_baseline=baseline,
            samples=len(samples),
            available=available,
        )

    def _update_stable_diagnosis(self, diagnosis: Diagnosis) -> None:
        if diagnosis.verdict == self._pending_verdict:
            self._pending_windows += 1
        else:
            self._pending_verdict = diagnosis.verdict
            self._pending_windows = 1

        if self._pending_windows < DIAG_STABLE_WINDOWS:
            return
        if diagnosis.verdict == self._last_emitted_verdict:
            return
        self._last_emitted_verdict = diagnosis.verdict
        self._safe_callback(self._on_diagnosis, diagnosis)

    def _maybe_start_route_discovery(self) -> None:
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
                name="netguard-route-discovery",
                daemon=True,
            )
            self._route_thread.start()

    def _discover_isp(self) -> None:
        try:
            iface = self._iface or get_active_interface()
            hops = self._tracer(
                PING_EXTERNAL_TARGET,
                max_hops=TRACE_MAX_HOPS,
                timeout=0.25,
                stop_event=self._stop_event,
            )
            hop = find_isp_hop(hops, iface.gateway)
            if hop is not None:
                self._isp_ip = hop.ip
        except Exception as exc:
            if not self._stop_event.is_set():
                self.last_error = str(exc)
                _log(f"[tìm hop nhà mạng] {exc}")

    @staticmethod
    def _safe_callback(callback: Callable, value) -> None:
        try:
            callback(value)
        except Exception as exc:
            _log(f"[callback ping] {exc}")
