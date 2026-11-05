"""Quy tắc thuần để kết luận vị trí có vấn đề mạng."""

from __future__ import annotations

from dataclasses import dataclass

from config import (
    DIAG_MIN_SAMPLES,
    LOSS_BAD_PCT,
    RTT_BAD_FACTOR,
    RTT_BAD_MIN_MS,
)
from models import Diagnosis

__all__ = ["TargetStats", "is_bad", "diagnose"]


@dataclass(frozen=True)
class TargetStats:
    """Thống kê cửa sổ ping của một mốc mạng."""

    loss_pct: float
    rtt_median: float | None
    rtt_baseline: float | None
    samples: int
    available: bool = True


def is_bad(stats: TargetStats) -> bool:
    """True khi mất gói vượt ngưỡng hoặc RTT vượt nền một cách rõ rệt."""
    if not stats.available or stats.samples < DIAG_MIN_SAMPLES:
        return False
    if stats.loss_pct > LOSS_BAD_PCT:
        return True
    if stats.rtt_median is None or stats.rtt_baseline is None:
        return False
    threshold = max(RTT_BAD_FACTOR * stats.rtt_baseline, RTT_BAD_MIN_MS)
    return stats.rtt_median > threshold


def diagnose(
    router: TargetStats,
    isp: TargetStats | None,
    external: TargetStats,
) -> Diagnosis:
    """Kết luận lỗi ở mạng nhà, ISP, Internet hoặc chưa đủ dữ liệu."""
    if router.available and router.samples >= DIAG_MIN_SAMPLES and is_bad(router):
        return Diagnosis("home_issue", "Lỗi trong mạng nhà (Wi-Fi, tín hiệu hoặc router).")

    if not router.available:
        return Diagnosis("unknown", "Không đo được router; hãy kiểm tra gateway và kết nối LAN.")

    if router.samples < DIAG_MIN_SAMPLES:
        return Diagnosis("unknown", "Chưa đủ dữ liệu ping router để kết luận.")

    if isp is not None and isp.available and isp.samples >= DIAG_MIN_SAMPLES and is_bad(isp):
        return Diagnosis("isp_issue", "Lỗi ở đường truyền hoặc phía nhà mạng.")

    external_bad = external.available and external.samples >= DIAG_MIN_SAMPLES and is_bad(external)
    if not external.available or external.samples < DIAG_MIN_SAMPLES:
        return Diagnosis("unknown", "Chưa đủ dữ liệu ping máy chủ bên ngoài để kết luận.")

    if isp is None or not isp.available or isp.samples < DIAG_MIN_SAMPLES:
        if external_bad:
            return Diagnosis(
                "internet_issue",
                "Lỗi phía Internet hoặc server đích; chưa xác định được hop nhà mạng.",
            )
        return Diagnosis("unknown", "Chưa xác định được hop nhà mạng để kết luận đầy đủ.")

    if external_bad:
        return Diagnosis("internet_issue", "Lỗi xa hơn, phía Internet hoặc server đích.")
    return Diagnosis("ok", "Mạng bình thường: ba mốc ping đều ổn định.")
