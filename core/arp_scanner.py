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
import time
from dataclasses import dataclass

from config import ARP_ROUNDS, ARP_TIMEOUT_SEC
from core.interfaces import NetInterface, get_subnet_hosts

__all__ = ["ScanEntry", "scan_subnet"]

# Npcap cần khoảng thời gian này để mở capture handle; gửi sớm hơn sẽ mất phản hồi.
SNIFFER_WARMUP_SEC = 0.8


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
            "Hãy mở lại PowerShell/VS Code bằng 'Run as administrator' rồi thử lại."
        )
    if "wpcap" in text or "npcap" in text or "winpcap" in text or "no such device" in text:
        return RuntimeError(
            "Chưa cài Npcap hoặc Npcap chưa chạy. Cài từ https://npcap.com rồi kiểm tra "
            "bằng lệnh 'sc query npcap' (phải thấy RUNNING)."
        )
    return RuntimeError(f"Không quét được qua card '{iface.name}': {exc}")


def scan_subnet(
    iface: NetInterface,
    timeout: float = ARP_TIMEOUT_SEC,
    rounds: int = ARP_ROUNDS,
) -> list[ScanEntry]:
    """Quét toàn bộ subnet của ``iface`` bằng ARP request broadcast.

    Đầu vào: ``iface`` là card đang dùng; ``timeout`` là thời gian chờ phản hồi mỗi
    vòng (giây); ``rounds`` là số vòng gửi (gộp kết quả để giảm sót thiết bị).
    Đầu ra: ``list[ScanEntry]`` sắp xếp theo IP, đã loại trùng, chỉ gồm IP trong subnet,
    và luôn có thêm chính máy này (``is_self = True``).

    Ném ``RuntimeError`` với thông báo tiếng Việt nếu không đủ quyền, thiếu Npcap,
    hoặc không mở được card. Ném ``ValueError`` nếu subnet quá lớn.
    """
    from scapy.all import ARP, Ether, AsyncSniffer, sendp

    hosts = get_subnet_hosts(iface)
    host_set = set(hosts)
    scapy_iface = _scapy_iface(iface)
    found: dict[str, str] = {}

    def collect(packet) -> None:
        """Ghi lại các ARP reply hợp lệ (op = 2) thuộc subnet đang quét."""
        if not packet.haslayer(ARP):
            return
        reply = packet[ARP]
        if int(reply.op) != 2:
            return
        ip = str(reply.psrc)
        mac = str(reply.hwsrc).lower()
        if ip in host_set and mac and mac != "00:00:00:00:00:00":
            found.setdefault(ip, mac)

    sniffer = AsyncSniffer(iface=scapy_iface, filter="arp", prn=collect, store=False)
    try:
        sniffer.start()
        time.sleep(SNIFFER_WARMUP_SEC)  # đợi Npcap mở xong handle rồi mới gửi
        requests = [Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=ip) for ip in hosts]
        for _ in range(max(1, int(rounds))):
            # Giãn cách 1 ms/gói: gửi dồn 254 gói một lúc dễ bị router/AP bỏ bớt.
            sendp(requests, iface=scapy_iface, verbose=0, inter=0.001)
            time.sleep(timeout)
    except Exception as exc:  # Scapy/Windows ném nhiều loại khác nhau, cần đổi sang tiếng Việt
        raise _translate_error(exc, iface) from exc
    finally:
        try:
            sniffer.stop()
        except Exception:  # sniffer chưa chạy được thì bỏ qua
            pass

    # Máy này không tự trả lời ARP của chính nó, phải thêm tay.
    if iface.ip and iface.mac:
        found[iface.ip] = iface.mac.lower()

    entries = [ScanEntry(ip=ip, mac=mac) for ip, mac in found.items()]
    for entry in entries:
        entry.is_self = entry.ip == iface.ip and entry.mac == iface.mac.lower()
    entries.sort(key=lambda entry: ipaddress.IPv4Address(entry.ip))
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
