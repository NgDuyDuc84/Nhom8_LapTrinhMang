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
    rtt_limit: float | None = None


def is_bad(stats: TargetStats) -> bool:
    """True khi mất gói vượt ngưỡng hoặc RTT vượt nền một cách rõ rệt."""
    if not stats.available or stats.samples < DIAG_MIN_SAMPLES:
        return False
    if stats.loss_pct > LOSS_BAD_PCT:
        return True
    if stats.rtt_median is not None and stats.rtt_limit is not None and stats.rtt_median > stats.rtt_limit:
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
    if not external.available or external.samples < DIAG_MIN_SAMPLES:
        return Diagnosis("unknown", "Chưa đủ dữ liệu đích cuối để đối chiếu đường truyền.")
    external_bad = is_bad(external)
    router_bad = is_bad(router)
    hop_bad = bool(isp and is_bad(isp))
    if not router.available or router.samples < DIAG_MIN_SAMPLES:
        return Diagnosis("unknown", "Chưa đủ dữ liệu ping router để đối chiếu.")
    if not external_bad:
        if router_bad or hop_bad:
            return Diagnosis("unknown", "Đích cuối vẫn phản hồi tốt; mốc trung gian có thể hạn chế ICMP. Chưa có bằng chứng lỗi chuyển tiếp.")
        return Diagnosis("ok", "Các phép đo ICMP đang ổn định; chưa kiểm tra DNS, HTTP hoặc băng thông.")
    if router_bad:
        return Diagnosis("home_issue", "Nghi ngờ mạng LAN/router: suy giảm được quan sát cả ở router và đích cuối.")
    if hop_bad:
        return Diagnosis("isp_issue", "Nghi ngờ đường sau gateway: mốc trung gian và đích cuối cùng suy giảm; chưa xác minh chủ sở hữu hop.")
    return Diagnosis("internet_issue", "Đích ngoài phản hồi kém trong khi router ổn định; có thể do đường truyền hoặc đích hạn chế ICMP.")
