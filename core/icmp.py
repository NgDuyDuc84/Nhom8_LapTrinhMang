"""Các thao tác ping ICMP dùng icmplib, không phụ thuộc giao diện Qt."""

from __future__ import annotations

import time

from icmplib import ICMPv4Socket, ICMPRequest
from icmplib.utils import unique_identifier
from icmplib.exceptions import ICMPLibError, TimeoutExceeded, ICMPError
import socket

__all__ = ["ping_once", "ping_series"]


def _source_address() -> str:
    """Chọn IP nguồn của card LAN đang hoạt động nếu xác định được."""
    from core.interfaces import get_active_interface

    return get_active_interface().ip


def _friendly_error(exc: Exception) -> RuntimeError:
    """Chuyển lỗi socket/ICMP thường gặp thành thông báo tiếng Việt."""
    message = str(exc).lower()
    if isinstance(exc, PermissionError) or any(
        marker in message
        for marker in ("permission", "access is denied", "winerror 5", "operation not permitted")
    ):
        return RuntimeError(
            "Không đủ quyền gửi gói ICMP. Hãy mở lại Mo_NetGuard.cmd và chấp nhận cấp quyền."
        )
    if "npcap" in message or "wpcap" in message:
        return RuntimeError("Chưa cài Npcap hoặc Npcap chưa chạy; hãy kiểm tra dịch vụ Npcap.")
    if any(marker in message for marker in ("cannot be assigned", "10049", "address not available")):
        return RuntimeError("IP nguồn không còn thuộc card mạng. Hãy kiểm tra kết nối Wi-Fi/Ethernet.")
    return RuntimeError(f"Không ping được đích mạng: {exc}")


def ping_once(addr: str, timeout: float = 1.0, *, source: str | None = None) -> float | None:
    """Ping một lần; trả RTT theo mili giây hoặc ``None`` nếu không có phản hồi."""
    if not addr.strip():
        raise ValueError("Địa chỉ ping không được để trống.")
    if timeout <= 0:
        raise ValueError("Thời gian chờ ping phải lớn hơn 0.")

    try:
        address = socket.gethostbyname(addr)
        request = ICMPRequest(destination=address, id=unique_identifier(), sequence=0)
        with ICMPv4Socket(source or _source_address(), privileged=True) as sock:
            # Không dùng ping(): phiên bản thư viện này nuốt ngoại lệ send().
            sock.send(request)
            try:
                reply = sock.receive(request, timeout)
                reply.raise_for_status()
            except (TimeoutExceeded, ICMPError):
                return None
            return max(0.0, (reply.time-request.time)*1000)
    except (ICMPLibError, OSError, PermissionError) as exc:
        raise _friendly_error(exc) from exc

def ping_series(
    addr: str,
    count: int,
    interval: float = 1.0,
    timeout: float = 1.0,
) -> list[float | None]:
    """Ping lặp ``count`` lần và trả RTT từng mẫu, ``None`` biểu thị mất gói."""
    if count < 1:
        raise ValueError("Số lần ping phải ít nhất là 1.")
    if interval < 0:
        raise ValueError("Khoảng nghỉ giữa các lần ping không được âm.")
    if timeout <= 0:
        raise ValueError("Thời gian chờ ping phải lớn hơn 0.")

    results: list[float | None] = []
    for index in range(count):
        started = time.monotonic()
        results.append(ping_once(addr, timeout=timeout))
        if index + 1 < count and interval:
            time.sleep(max(0.0, interval - (time.monotonic() - started)))
    return results


if __name__ == "__main__":
    from core.console import setup_console_encoding

    setup_console_encoding()
    try:
        result = ping_once("1.1.1.1", timeout=1.0)
    except (RuntimeError, ValueError) as exc:
        print(f"LỖI: {exc}")
        raise SystemExit(1)
    print("Mất gói hoặc không có phản hồi." if result is None else f"RTT: {result:.2f} ms")
