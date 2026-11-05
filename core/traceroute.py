"""Traceroute ICMP và một số phép phân tích hop, không import Qt."""

from __future__ import annotations

import ipaddress
import math
import re
import shutil
import subprocess
import sys
import time
from dataclasses import replace
from threading import Event

from icmplib import traceroute as icmp_traceroute
from icmplib.exceptions import ICMPLibError

from config import TRACE_MAX_HOPS
from models import Hop

__all__ = ["trace", "find_isp_hop", "mark_latency_jump"]


def _require_active_interface(target: str) -> None:
    """Xác nhận có card LAN hoạt động trước khi chạy traceroute."""
    from core.interfaces import get_active_interface

    iface = get_active_interface()
    if not iface.ip:
        raise RuntimeError(f"Card '{iface.name}' không có địa chỉ IPv4 để chạy traceroute.")
    try:
        is_local = ipaddress.ip_address(target) in ipaddress.ip_network(
            f"{iface.ip}/{iface.netmask}", strict=False,
        )
    except ValueError:
        is_local = False
    if not iface.gateway and not is_local:
        raise RuntimeError(f"Card '{iface.name}' không có gateway để traceroute ra Internet.")


def _windows_trace(
    target: str,
    max_hops: int,
    timeout: float,
    stop_event: Event | None = None,
) -> list[Hop]:
    """Gọi tracert.exe của Windows và chuyển bảng kết quả thành Hop."""
    executable = shutil.which("tracert.exe")
    if executable is None:
        raise RuntimeError("Không tìm thấy tracert.exe trong Windows.")

    timeout_ms = max(1, math.ceil(timeout * 1000))
    command = [executable, "-d", "-4", "-h", str(max_hops), "-w", str(timeout_ms), target]
    deadline = time.monotonic() + max(15.0, max_hops * timeout * 3 + 15)
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
        )
    except OSError as exc:
        raise RuntimeError(f"Không chạy được tracert.exe: {exc}") from exc

    while True:
        if stop_event is not None and stop_event.is_set():
            process.terminate()
            try:
                process.communicate(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
            raise RuntimeError("Traceroute đã được dừng.")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            process.kill()
            process.communicate()
            raise RuntimeError("Lệnh tracert.exe chạy quá thời gian chờ.")
        try:
            stdout, stderr = process.communicate(timeout=min(0.2, remaining))
            break
        except subprocess.TimeoutExpired:
            continue

    rows: dict[int, Hop] = {}
    ip_pattern = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
    rtt_pattern = re.compile(r"(?<!\w)(\*|<?\s*\d+\s*ms)", re.IGNORECASE)
    for line in stdout.splitlines():
        row_match = re.match(r"^\s*(\d+)\s+(.+)$", line)
        if row_match is None:
            continue
        ttl = int(row_match.group(1))
        if not 1 <= ttl <= max_hops:
            continue
        remainder = row_match.group(2)
        if not rtt_pattern.search(remainder):
            raise RuntimeError(f"Không gửi được probe traceroute: {line.strip()}")
        ip_matches = ip_pattern.findall(remainder)
        ip = ip_matches[-1] if ip_matches else None
        rtt_values: list[float] = []
        for sample in rtt_pattern.findall(remainder):
            if sample.strip() == "*":
                continue
            number = re.search(r"\d+", sample)
            if number:
                rtt_values.append(float(number.group()))
        rows[ttl] = Hop(
            ttl=ttl,
            ip=ip,
            rtt_ms=(sum(rtt_values) / len(rtt_values)) if rtt_values else None,
        )

    if not rows:
        details = stderr.strip() or stdout.strip()
        raise RuntimeError(f"Không đọc được kết quả tracert.exe. {details}")

    if process.returncode != 0:
        raise RuntimeError(f"Traceroute thất bại. {stderr.strip() or stdout.strip()}")

    last_ttl = max(rows)
    hops = [rows.get(ttl, Hop(ttl=ttl)) for ttl in range(1, last_ttl + 1)]
    return mark_latency_jump(hops)


def _friendly_error(exc: Exception) -> RuntimeError:
    """Chuyển lỗi socket/Windows thường gặp thành thông báo tiếng Việt."""
    message = str(exc).lower()
    if isinstance(exc, PermissionError) or any(
        marker in message
        for marker in ("permission", "access is denied", "winerror 5", "not permitted")
    ):
        return RuntimeError(
            "Không đủ quyền tạo gói ICMP. Hãy mở PowerShell bằng 'Run as administrator' "
            "rồi chạy lại."
        )
    if isinstance(exc, ICMPLibError) and "permission" in message:
        return RuntimeError(
            "Không đủ quyền tạo socket ICMP. Hãy mở PowerShell bằng 'Run as administrator' "
            "rồi chạy lại."
        )
    return RuntimeError(f"Không chạy được traceroute: {exc}")


def trace(
    target: str,
    max_hops: int = TRACE_MAX_HOPS,
    timeout: float = 1.0,
    count: int = 1,
    stop_event: Event | None = None,
) -> list[Hop]:
    """Tăng TTL từng bước; hop im lặng được ghi với ``ip=None`` và tiếp tục.

    Trên Windows, ``tracert.exe`` gửi ba gói mỗi TTL; trên nền tảng khác
    ``icmplib`` gửi ``count`` gói. RTT là trung bình các phản hồi của hop.
    """
    if not target.strip():
        raise ValueError("Địa chỉ đích traceroute không được để trống.")
    if max_hops < 1:
        raise ValueError("Số hop tối đa phải ít nhất là 1.")
    if count < 1:
        raise ValueError("Số gói mỗi hop phải ít nhất là 1.")
    if timeout <= 0:
        raise ValueError("Thời gian chờ traceroute phải lớn hơn 0.")

    try:
        _require_active_interface(target)
        if sys.platform == "win32":
            # Windows tracert dùng ICMP và chọn interface theo routing table của OS.
            # Nó cũng tránh khác biệt raw-socket/Npcap giữa các bản Windows.
            return _windows_trace(target, max_hops, timeout, stop_event)

        replies = icmp_traceroute(
            target,
            count=count,
            interval=0,
            timeout=timeout,
            first_hop=1,
            max_hops=max_hops,
            family=4,
        )
        by_ttl = {
            int(reply.distance): Hop(
                ttl=int(reply.distance),
                ip=str(reply.address),
                rtt_ms=float(reply.avg_rtt) if reply.avg_rtt is not None else None,
            )
            for reply in replies
        }
        last_ttl = max(by_ttl, default=max_hops)
        hops = [by_ttl.get(ttl, Hop(ttl=ttl)) for ttl in range(1, last_ttl + 1)]
        return mark_latency_jump(hops)
    except (RuntimeError, ValueError):
        raise
    except Exception as exc:
        raise _friendly_error(exc) from exc


def find_isp_hop(hops: list[Hop], gateway_ip: str) -> Hop | None:
    """Trả hop phản hồi đầu tiên sau gateway; bỏ qua hop không phản hồi.

    Nếu gateway không xuất hiện trong câu trả lời (router có thể lọc ICMP), xem
    TTL 1 là vị trí gateway và tìm phản hồi đầu tiên từ TTL lớn hơn 1.
    """
    if not gateway_ip:
        return None
    try:
        gateway = str(ipaddress.ip_address(gateway_ip))
    except ValueError:
        return None

    gateway_index = next((index for index, hop in enumerate(hops) if hop.ip == gateway), None)
    if gateway_index is not None:
        candidates = hops[gateway_index + 1:]
    else:
        candidates = [hop for hop in hops if hop.ttl > 1]
    return next((hop for hop in candidates if hop.ip is not None), None)


def mark_latency_jump(hops: list[Hop]) -> list[Hop]:
    """Đánh dấu hop đầu tiên có độ trễ tăng rõ và vẫn cao ở hop kế tiếp.

    Bỏ qua hop không phản hồi. Ngưỡng tăng là ít nhất ``max(10 ms, 1.5 lần RTT
    trước đó)``; cần thêm một hop phản hồi phía sau vẫn giữ ít nhất 70% mức tăng.
    Nhờ vậy một router chỉ trả lời ICMP chậm đơn lẻ không bị đánh dấu.
    """
    result = [replace(hop, flagged=False) for hop in hops]
    responsive = [index for index, hop in enumerate(result) if hop.rtt_ms is not None]

    for position in range(1, len(responsive) - 1):
        previous_index = responsive[position - 1]
        current_index = responsive[position]
        next_index = responsive[position + 1]
        previous_rtt = result[previous_index].rtt_ms
        current_rtt = result[current_index].rtt_ms
        next_rtt = result[next_index].rtt_ms
        if previous_rtt is None or current_rtt is None or next_rtt is None:
            continue

        threshold = max(10.0, previous_rtt * 1.5)
        increase = current_rtt - previous_rtt
        if increase >= threshold and next_rtt >= previous_rtt + threshold * 0.7:
            result[current_index] = replace(result[current_index], flagged=True)
            break

    return result


if __name__ == "__main__":
    from core.console import setup_console_encoding
    from core.interfaces import get_active_interface

    setup_console_encoding()
    try:
        gateway = get_active_interface().gateway
        route = trace("1.1.1.1")
    except (RuntimeError, ValueError) as exc:
        print(f"LỖI: {exc}")
        raise SystemExit(1)
    isp = find_isp_hop(route, gateway)
    print(f"{'TTL':<6}{'IP':<20}{'RTT (ms)':<14}GHI CHÚ")
    for hop in route:
        note = "Nhà mạng" if isp is hop else "Độ trễ tăng" if hop.flagged else ""
        rtt = "*" if hop.rtt_ms is None else f"{hop.rtt_ms:.2f}"
        print(f"{hop.ttl:<6}{hop.ip or '*':<20}{rtt:<14}{note}")
