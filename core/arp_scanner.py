"""Quét LAN bằng ARP của Windows, không cần Npcap."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import ipaddress
import threading
from dataclasses import dataclass

from config import ARP_ROUNDS, ARP_TIMEOUT_SEC, SCAN_HOSTS_PER_PASS
from core.interfaces import NetInterface, get_subnet_hosts
from core.windows_network import resolve_ipv4

# Windows quyết định timeout từng yêu cầu ARP. Giới hạn cả số host mỗi phần
# và số yêu cầu đồng thời để hủy nhanh, không xếp hàng toàn bộ subnet lớn.
NATIVE_HOSTS_PER_PASS = 128
MAX_WORKERS = 32

@dataclass
class ScanEntry:
    """Một thiết bị trả lời ARP: địa chỉ IP và MAC (đã viết thường)."""

    ip: str
    mac: str
    is_self: bool = False


class ScanResult(list[ScanEntry]):
    """Kết quả một phần quét, kèm chính xác các IP đã kiểm tra."""

    def __init__(self, entries, *, targets, total_hosts, offset, end_offset, network):
        super().__init__(entries)
        self.targets = frozenset(targets)
        self.total_hosts = total_hosts
        self.offset = offset
        self.end_offset = end_offset
        self.next_offset = 0 if end_offset >= total_hosts else end_offset
        self.network = str(network)

    @property
    def progress(self):
        return {"network": self.network, "total_hosts": self.total_hosts,
                "completed_hosts": self.end_offset, "batch_hosts": self.end_offset - self.offset,
                "sweep_complete": self.next_offset == 0}


def scan_subnet(
    iface: NetInterface,
    timeout: float = ARP_TIMEOUT_SEC,
    rounds: int = ARP_ROUNDS,
    stop_event: threading.Event | None = None,
    start_offset: int = 0,
) -> ScanResult:
    """Chủ động phân giải lại ARP; chỉ trả về phần quét đã hoàn tất.

    timeout được giữ để tương thích caller; thời hạn ARP do Windows quản lý.
    Lỗi API/hủy làm mất hiệu lực cả phần quét, không đánh offline từ dữ liệu dở.
    """
    from core import network_mode
    if network_mode.PACKET_CAPTURE:
        from core.pcap_scanner import scan_subnet as capture_scan
        return capture_scan(iface, timeout, rounds, stop_event, start_offset)
    if timeout < 0:
        raise ValueError("Thời gian chờ không được âm.")
    stop = stop_event or threading.Event()
    all_hosts = get_subnet_hosts(iface)
    offset = start_offset % len(all_hosts)
    end_offset = min(offset + min(SCAN_HOSTS_PER_PASS, NATIVE_HOSTS_PER_PASS), len(all_hosts))
    hosts = list(all_hosts[offset:end_offset])
    if iface.gateway and iface.gateway in all_hosts and iface.gateway not in hosts:
        hosts.append(iface.gateway)
    found = set()

    def probe(ip):
        if stop.is_set():
            raise RuntimeError("Đã hủy quét mạng.")
        mac = resolve_ipv4(ip, iface.ip, iface.index)
        return ip, mac

    def cancelled():
        if stop.is_set():
            raise RuntimeError("Đã hủy quét mạng.")

    cancelled()
    # Mỗi native call hữu hạn; khi hủy chỉ đợi các call đang chạy, không gửi thêm.
    with ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="netguard-arp") as pool:
        pending = set()
        try:
            for _ in range(max(1, int(rounds))):
                todo = iter(ip for ip in hosts if ip != iface.ip)
                exhausted = False
                while pending or not exhausted:
                    cancelled()
                    while not exhausted and len(pending) < MAX_WORKERS:
                        try:
                            ip = next(todo)
                        except StopIteration:
                            exhausted = True
                            break
                        pending.add(pool.submit(probe, ip))
                    if not pending:
                        break
                    done, pending = wait(pending, timeout=0.05, return_when=FIRST_COMPLETED)
                    for future in done:
                        ip, mac = future.result()
                        if mac:
                            found.add((ip, mac.lower()))
        except Exception as exc:
            for future in pending:
                future.cancel()
            raise RuntimeError(f"Không hoàn tất quét ARP Windows: {exc}") from exc
    cancelled()
    if iface.ip and iface.mac:
        found.add((iface.ip, iface.mac.lower()))
    entries = [ScanEntry(ip, mac, ip == iface.ip and mac == iface.mac.lower()) for ip, mac in found]
    entries.sort(key=lambda entry: (ipaddress.IPv4Address(entry.ip), entry.mac))
    return ScanResult(entries, targets=hosts, total_hosts=len(all_hosts), offset=offset,
                      end_offset=end_offset,
                      network=getattr(all_hosts, "network", f"{iface.ip}/{iface.netmask}"))


if __name__ == "__main__":
    from core.console import setup_console_encoding
    from main import run_scan
    setup_console_encoding()
    raise SystemExit(run_scan())
