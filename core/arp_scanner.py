"""Quét thiết bị trong LAN bằng ARP (Scapy + Npcap).

Gói tin gửi qua đúng card đã chọn (truyền ``iface`` rõ ràng, không dựa vào card
mặc định của Scapy). Máy này không tự trả lời ARP của chính nó nên được thêm tay
vào kết quả với ``is_self = True``.

Vì sao không dùng ``srp``: trên máy Windows + Npcap của nhóm, ``srp``/``srp1`` gửi
được request và router có trả lời (thấy rõ khi sniff) nhưng Scapy không khớp được
cặp request/reply nên luôn trả về rỗng. Cách chạy được đã kiểm chứng là mở
``AsyncSniffer`` (lọc ``arp``) trước, đợi Npcap mở xong handle, rồi ``sendp`` các
ARP request và tự thu các gói ``op == 2``.

Không import Qt. Chạy thử từ gốc repo, terminal Administrator:

    python main.py --cli scan
"""

from __future__ import annotations

import ipaddress
import threading
import time
from dataclasses import dataclass

from config import ARP_ROUNDS, ARP_TIMEOUT_SEC
from core.interfaces import NetInterface, get_subnet_hosts
from core.arp_validation import valid_arp_source

__all__ = ["ScanEntry", "scan_subnet"]

# Đây là thời hạn tối đa; bộ bắt gói sẵn sàng thì gửi ngay, không ngủ cố định.
SNIFFER_START_TIMEOUT_SEC = 3.0
SNIFFER_STOP_TIMEOUT_SEC = 1.0


@dataclass
class ScanEntry:
    """Một thiết bị trả lời ARP: địa chỉ IP và MAC (đã viết thường)."""

    ip: str
    mac: str
    is_self: bool = False


def _scapy_iface(iface: NetInterface):
    """Tìm đối tượng card mạng tương ứng bên Scapy (so khớp theo IfIndex)."""
    from scapy.all import conf

    for candidate in conf.ifaces.values():
        if int(getattr(candidate, "index", -1) or -1) == iface.index:
            return candidate
    raise RuntimeError(
        f"Scapy/Npcap không thấy card '{iface.name}'. "
        "Kiểm tra Npcap đã cài chưa và chạy lại bằng quyền Administrator."
    )


def _translate_error(exc: Exception, iface: NetInterface) -> RuntimeError:
    """Đổi ngoại lệ khó hiểu của Scapy/Windows thành thông báo tiếng Việt."""
    text = str(exc).lower()
    if isinstance(exc, PermissionError) or "permission" in text or "access is denied" in text \
            or "winerror 5" in text or "not permitted" in text:
        return RuntimeError(
            "Chưa chạy bằng quyền Administrator nên không mở được card mạng. "
            "Hãy mở lại Mo_NetGuard.cmd và chấp nhận hộp thoại cấp quyền của Windows."
        )
    if "wpcap" in text or "npcap" in text or "winpcap" in text or "no such device" in text:
        return RuntimeError(
            "Chưa cài Npcap hoặc Npcap chưa chạy. Cài từ https://npcap.com rồi kiểm tra "
            "bằng lệnh 'sc query npcap' (phải thấy RUNNING)."
        )
    return RuntimeError(f"Không quét được qua card '{iface.name}': {exc}")


def _check_capture(sniffer, *, require_running: bool = True) -> None:
    """Scapy có thể giữ lỗi ở luồng nền hoặc dừng vì socket hỏng mà không ném lỗi."""
    if sniffer.exception is not None:
        raise sniffer.exception
    thread = sniffer.thread
    if thread is None or not thread.is_alive() or (require_running and not sniffer.running):
        raise RuntimeError("Bộ bắt gói ARP đã dừng ngoài dự kiến; kết quả quét không hợp lệ.")


def _wait_capture_ready(sniffer, ready: threading.Event) -> None:
    deadline = time.monotonic() + SNIFFER_START_TIMEOUT_SEC
    while not ready.is_set():
        _check_capture(sniffer, require_running=False)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("Hết thời gian chờ bộ bắt gói ARP sẵn sàng; chưa gửi yêu cầu quét.")
        ready.wait(min(0.02, remaining))
    _check_capture(sniffer)


def _stop_capture(sniffer, *, require_healthy: bool) -> Exception | None:
    """Đóng có thời hạn; trả lỗi để caller loại bỏ toàn bộ kết quả của lượt hỏng."""
    error = None
    if require_healthy:
        try:
            _check_capture(sniffer)
        except Exception as exc:
            error = exc
    try:
        # Lượt hợp lệ phải chủ động dừng được capture. Nếu nó vừa tự chết sau
        # bước kiểm tra trên, stop() phải báo lỗi thay vì bỏ qua theo running=False.
        if require_healthy or sniffer.running:
            sniffer.stop(join=False)
    except Exception as exc:
        error = error or exc
    try:
        sniffer.join(SNIFFER_STOP_TIMEOUT_SEC)
    except Exception as exc:
        error = error or exc
    if sniffer.thread is not None and sniffer.thread.is_alive():
        error = error or RuntimeError("Bộ bắt gói ARP chưa dừng trong thời gian chờ; bỏ kết quả quét.")
    return error


def scan_subnet(
    iface: NetInterface,
    timeout: float = ARP_TIMEOUT_SEC,
    rounds: int = ARP_ROUNDS,
    stop_event: threading.Event | None = None,
) -> list[ScanEntry]:
    """Quét toàn bộ subnet của ``iface`` bằng ARP request broadcast.

    Đầu vào: ``iface`` là card đang dùng; ``timeout`` là thời gian chờ phản hồi mỗi
    vòng (giây); ``rounds`` là số vòng gửi (gộp kết quả để giảm sót thiết bị).
    Đầu ra: ``list[ScanEntry]`` sắp xếp theo IP, đã loại trùng, chỉ gồm IP trong subnet,
    và luôn có thêm chính máy này (``is_self = True``). Chỉ trả kết quả khi capture
    sẵn sàng, còn hoạt động suốt lượt quét và đã dừng thành công.

    Ném ``RuntimeError`` với thông báo tiếng Việt nếu không đủ quyền, thiếu Npcap,
    hoặc capture lỗi/hết thời gian chờ. Ném ``ValueError`` nếu subnet quá lớn.
    """
    from scapy.all import ARP, Ether, AsyncSniffer, sendp

    hosts = get_subnet_hosts(iface)
    host_set = set(hosts)
    scapy_iface = _scapy_iface(iface)
    found: set[tuple[str, str]] = set()
    overflow = threading.Event()

    def collect(packet) -> None:
        """Ghi lại các ARP reply hợp lệ (op = 2) thuộc subnet đang quét."""
        if not packet.haslayer(ARP):
            return
        reply = packet[ARP]
        if int(reply.op) != 2:
            return
        source = valid_arp_source(packet, iface)
        if source and source[0] in host_set and str(reply.pdst) in (iface.ip, "0.0.0.0"):
            if len(found) >= 4096 and source not in found:
                overflow.set()
                return
            found.add(source)

    ready = threading.Event()
    closing = threading.Event()

    def capture_started() -> None:
        ready.set()
        if closing.is_set():
            # Driver có thể mở xong sau khi caller hết thời gian chờ. Dừng ngay
            # từ callback, không tự join luồng đang thực hiện chính callback này.
            sniffer.stop(join=False)

    sniffer = AsyncSniffer(
        iface=scapy_iface, filter="arp", prn=collect, store=False,
        started_callback=capture_started,
    )
    error = None
    try:
        sniffer.start()
        _wait_capture_ready(sniffer, ready)
        requests = [Ether(src=iface.mac, dst="ff:ff:ff:ff:ff:ff") /
                    ARP(hwsrc=iface.mac, psrc=iface.ip, pdst=ip) for ip in hosts]
        for _ in range(max(1, int(rounds))):
            _check_capture(sniffer)
            # Giãn cách 1 ms/gói: gửi dồn 254 gói một lúc dễ bị router/AP bỏ bớt.
            if stop_event is None:
                sendp(requests, iface=scapy_iface, verbose=0, inter=0.001)
            else:
                for offset in range(0, len(requests), 64):
                    if stop_event.is_set():
                        raise RuntimeError("Đã hủy quét mạng.")
                    sendp(requests[offset:offset+64], iface=scapy_iface, verbose=0, inter=0.001)
            # join(timeout) chờ phản hồi nhưng tỉnh ngay nếu capture chết và
            # chuyển tiếp lỗi Scapy; hết timeout vẫn cần capture còn hoạt động.
            deadline = time.monotonic() + timeout
            while True:
                if stop_event is not None and stop_event.is_set():
                    raise RuntimeError("Đã hủy quét mạng.")
                remaining = max(0, deadline-time.monotonic())
                sniffer.join(min(remaining, 0.1))
                _check_capture(sniffer)
                if remaining <= 0.1:
                    break
            _check_capture(sniffer)
    except Exception as exc:  # Scapy/Windows ném nhiều loại khác nhau, cần đổi sang tiếng Việt
        error = exc
    finally:
        closing.set()
        close_error = _stop_capture(sniffer, require_healthy=error is None)
        if close_error is not None:
            if error is None:
                error = close_error
            elif close_error is not error:
                error.add_note(f"Lỗi khi dừng bộ bắt gói: {close_error}")

    if error is not None:
        raise _translate_error(error, iface) from error
    if overflow.is_set():
        raise RuntimeError("Quá nhiều claim ARP trong một lượt; bỏ kết quả để tránh dữ liệu không đầy đủ.")

    # Máy này không tự trả lời ARP của chính nó, phải thêm tay.
    if iface.ip and iface.mac:
        found.add((iface.ip, iface.mac.lower()))

    entries = [ScanEntry(ip=ip, mac=mac) for ip, mac in found]
    for entry in entries:
        entry.is_self = entry.ip == iface.ip and entry.mac == iface.mac.lower()
    entries.sort(key=lambda entry: (ipaddress.IPv4Address(entry.ip), entry.mac))
    return entries


def _main() -> int:
    """Quét thử và in kết quả (tiện cho A chạy tay khi cần)."""
    from core.console import setup_console_encoding
    from core.interfaces import get_active_interface, get_warnings

    setup_console_encoding()
    for warning in get_warnings():
        print(f"Cảnh báo: {warning}")
    try:
        iface = get_active_interface()
        started = time.perf_counter()
        entries = scan_subnet(iface)
    except (RuntimeError, ValueError) as exc:
        print(f"LỖI: {exc}")
        return 1
    elapsed = time.perf_counter() - started
    print(f"Quét {iface.name} ({iface.ip}/{iface.netmask}) mất {elapsed:.1f} giây, "
          f"thấy {len(entries)} thiết bị:")
    for entry in entries:
        note = "  (máy này)" if entry.is_self else ""
        print(f"  {entry.ip:<16}{entry.mac}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
