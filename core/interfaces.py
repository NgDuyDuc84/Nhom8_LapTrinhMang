"""Liệt kê card mạng, xác định card đang dùng, tính dải IP và kiểm tra môi trường.

Không import Qt. Không import ``services`` hay ``db``.
Thông tin card lấy từ Scapy (Npcap) và từ bảng định tuyến IPv4 của Windows
(qua ctypes ``iphlpapi``) để biết cổng mặc định của từng card.

Chạy thử (terminal Administrator để kết quả đầy đủ):

    python -m core.interfaces
"""

from __future__ import annotations

import ctypes
import ipaddress
import socket
import struct
from ctypes import wintypes
from dataclasses import dataclass

from config import MAX_SCAN_HOSTS

# Dấu hiệu nhận biết card ảo (so khớp trên tên + mô tả, không phân biệt hoa thường).
VIRTUAL_MARKERS = (
    "warp",                  # Cloudflare WARP
    "loopback",              # Loopback Pseudo-Interface
    "pseudo-interface",
    "local area connection*",  # WAN Miniport, Microsoft Wi-Fi Direct Virtual Adapter
    "wi-fi direct",
    "wan miniport",
    "vmware",
    "virtualbox",
    "hyper-v",
    "vethernet",
    "tap-",
    "tap adapter",
    "teredo",
    "isatap",
    "tunnel",
    "vpn",
    "bluetooth",
)

__all__ = [
    "NetInterface",
    "list_interfaces",
    "get_active_interface",
    "get_subnet_hosts",
    "check_environment",
]


@dataclass
class NetInterface:
    """Một card mạng của máy.

    ``index`` là IfIndex của Windows (dùng để Scapy gửi/nhận đúng card ở giai đoạn 3).
    ``gateway`` rỗng nghĩa là card không có cổng mặc định (không ra được Internet).
    """

    name: str
    description: str
    ip: str
    netmask: str
    gateway: str
    mac: str
    is_virtual: bool
    is_up: bool
    index: int = 0


# ---------------------------------------------------------------- tiện ích Windows
class _MIB_IPADDRROW(ctypes.Structure):
    """Một dòng của bảng địa chỉ IPv4 (IP + mặt nạ mạng)."""

    _fields_ = [
        ("dwAddr", wintypes.DWORD),
        ("dwIndex", wintypes.DWORD),
        ("dwMask", wintypes.DWORD),
        ("dwBCastAddr", wintypes.DWORD),
        ("dwReasmSize", wintypes.DWORD),
        ("unused1", wintypes.USHORT),
        ("wType", wintypes.USHORT),
    ]


class _MIB_IPFORWARDROW(ctypes.Structure):
    """Một dòng của bảng định tuyến IPv4."""

    _fields_ = [
        ("dwForwardDest", wintypes.DWORD),
        ("dwForwardMask", wintypes.DWORD),
        ("dwForwardPolicy", wintypes.DWORD),
        ("dwForwardNextHop", wintypes.DWORD),
        ("dwForwardIfIndex", wintypes.DWORD),
        ("dwForwardType", wintypes.DWORD),
        ("dwForwardProto", wintypes.DWORD),
        ("dwForwardAge", wintypes.DWORD),
        ("dwForwardNextHopAS", wintypes.DWORD),
        ("dwForwardMetric1", wintypes.DWORD),
        ("dwForwardMetric2", wintypes.DWORD),
        ("dwForwardMetric3", wintypes.DWORD),
        ("dwForwardMetric4", wintypes.DWORD),
        ("dwForwardMetric5", wintypes.DWORD),
    ]


def _iphlpapi() -> ctypes.WinDLL:
    """Mở thư viện iphlpapi của Windows (chỉ dùng trên Windows)."""
    return ctypes.WinDLL("iphlpapi", use_last_error=True)


def _dword_to_ip(value: int) -> str:
    """Đổi một DWORD của Windows (thứ tự byte mạng) thành chuỗi IPv4."""
    return socket.inet_ntoa(struct.pack("<L", value & 0xFFFFFFFF))


def _read_table(func, row_type: type) -> list:
    """Đọc một bảng của iphlpapi: gọi lần đầu lấy kích thước, lần sau lấy dữ liệu."""
    size = wintypes.ULONG(0)
    func(None, ctypes.byref(size), False)
    if size.value == 0:
        return []
    buffer = ctypes.create_string_buffer(size.value)
    if func(buffer, ctypes.byref(size), False) != 0:
        return []
    count = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD)).contents.value
    offset = ctypes.sizeof(wintypes.DWORD)
    rows = ctypes.cast(ctypes.addressof(buffer) + offset, ctypes.POINTER(row_type))
    return [rows[i] for i in range(count)]


def _ipv4_table() -> dict[int, tuple[str, str]]:
    """Trả về ``{IfIndex: (ip, netmask)}`` từ bảng địa chỉ IPv4 của Windows."""
    result: dict[int, tuple[str, str]] = {}
    try:
        lib = _iphlpapi()
        lib.GetIpAddrTable.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.ULONG), wintypes.BOOL]
        for row in _read_table(lib.GetIpAddrTable, _MIB_IPADDRROW):
            result[int(row.dwIndex)] = (_dword_to_ip(row.dwAddr), _dword_to_ip(row.dwMask))
    except (AttributeError, OSError):
        pass
    return result


def _gateway_table() -> dict[int, str]:
    """Trả về ``{IfIndex: gateway}`` từ các dòng route mặc định (0.0.0.0/0)."""
    result: dict[int, str] = {}
    metrics: dict[int, tuple[int, int]] = {}
    try:
        lib = _iphlpapi()
        lib.GetIpForwardTable.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.ULONG), wintypes.BOOL]
        for row in _read_table(lib.GetIpForwardTable, _MIB_IPFORWARDROW):
            if int(row.dwForwardDest) != 0 or int(row.dwForwardMask) != 0:
                continue
            index = int(row.dwForwardIfIndex)
            # Nhiều route mặc định trên cùng một card: giữ cái có metric nhỏ nhất.
            metric = (int(row.dwForwardMetric1), int(row.dwForwardMetric2))
            if index not in metrics or metric < metrics[index]:
                result[index] = _dword_to_ip(row.dwForwardNextHop)
                metrics[index] = metric
    except (AttributeError, OSError):
        pass
    return result


def _best_interface_index(target: str = "1.1.1.1") -> int | None:
    """Hỏi Windows xem card nào thật sự được dùng để đi tới ``target``.

    Đây là quyết định định tuyến thật của hệ điều hành, đáng tin hơn bảng route
    dựng lại bằng Scapy (Scapy có thể chọn nhầm card VPN).
    """
    try:
        lib = _iphlpapi()
        lib.GetBestInterface.argtypes = [wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        lib.GetBestInterface.restype = wintypes.DWORD
        address = struct.unpack("<L", socket.inet_aton(target))[0]
        best = wintypes.DWORD(0)
        if lib.GetBestInterface(wintypes.DWORD(address), ctypes.byref(best)) == 0:
            return int(best.value)
    except (AttributeError, OSError, socket.error):
        pass
    return None


# ---------------------------------------------------------------- kiểm tra môi trường
def is_admin() -> bool:
    """True nếu tiến trình đang chạy với quyền Administrator."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def has_npcap() -> bool:
    """True nếu Scapy đã nạp được Npcap (wpcap.dll) và mở được socket gói tin."""
    try:
        from scapy.all import conf
    except Exception:
        return False
    return bool(getattr(conf, "use_pcap", False)) and conf.L2socket is not None


# ---------------------------------------------------------------- danh sách card
def _is_virtual(name: str, description: str) -> bool:
    """Đoán card ảo dựa trên tên và mô tả (VPN, loopback, Hyper-V, VMware...)."""
    text = f"{name} {description}".lower()
    return any(marker in text for marker in VIRTUAL_MARKERS)


def _has_usable_ipv4(ip: str) -> bool:
    """True nếu card có IPv4 dùng được (không rỗng, không link-local, không loopback)."""
    if not ip or ip.startswith("169.254.") or ip.startswith("127."):
        return False
    return True


def _pick_ipv4(ips) -> str:
    """Chọn IPv4 phù hợp nhất trong ``iface.ips[4]``: ưu tiên địa chỉ dùng được."""
    candidates = list(ips or [])
    for ip in candidates:
        if _has_usable_ipv4(ip):
            return ip
    return candidates[0] if candidates else ""


def list_interfaces() -> list[NetInterface]:
    """Liệt kê toàn bộ card mạng, kèm cờ card ảo và trạng thái hoạt động.

    Đầu ra sắp xếp: card thật đang hoạt động trước, card ảo và card tắt ở sau.
    """
    from scapy.all import conf  # import muộn để module vẫn import được khi thiếu Npcap

    addresses = _ipv4_table()
    gateways = _gateway_table()
    interfaces: list[NetInterface] = []

    for iface in conf.ifaces.values():
        index = int(getattr(iface, "index", 0) or 0)
        ipv4, netmask = addresses.get(index, ("", ""))
        if not ipv4:
            ipv4 = _pick_ipv4(getattr(iface, "ips", {}).get(4))
        name = str(getattr(iface, "name", "") or "")
        description = str(getattr(iface, "description", "") or "")
        interfaces.append(
            NetInterface(
                name=name,
                description=description,
                ip=ipv4,
                netmask=netmask,
                gateway=gateways.get(index, ""),
                mac=str(getattr(iface, "mac", "") or "").lower(),
                is_virtual=_is_virtual(name, description),
                is_up=_has_usable_ipv4(ipv4),
                index=index,
            )
        )

    interfaces.sort(key=lambda i: (i.is_virtual, not i.is_up, i.name.lower()))
    return interfaces


def get_active_interface() -> NetInterface:
    """Trả về card thật đang dùng để ra Internet.

    Ưu tiên: card thật, đang hoạt động, có cổng mặc định, và là card mà Windows
    chọn cho đường ra Internet. Ném ``RuntimeError`` (tiếng Việt) nếu không có.
    """
    interfaces = list_interfaces()
    candidates = [i for i in interfaces if i.is_up and not i.is_virtual and i.gateway]
    if not candidates:  # nới lỏng: card thật đang hoạt động nhưng thiếu cổng mặc định
        candidates = [i for i in interfaces if i.is_up and not i.is_virtual]
    if not candidates:
        raise RuntimeError(
            "Không tìm thấy card mạng thật nào đang hoạt động. "
            "Hãy kiểm tra Wi-Fi/Ethernet đã kết nối chưa và tắt VPN."
        )

    best_index = _best_interface_index()
    for candidate in candidates:
        if candidate.index == best_index:
            return candidate
    # Windows không trả lời hoặc chọn card khác: lấy card thật có cổng mặc định đầu tiên.
    candidates.sort(key=lambda i: (not i.gateway, i.name.lower()))
    return candidates[0]


def get_subnet_hosts(iface: NetInterface) -> list[str]:
    """Liệt kê IP host trong subnet của ``iface`` (bỏ địa chỉ mạng và broadcast).

    Ném ``ValueError`` nếu card thiếu IP/mặt nạ, hoặc subnet có nhiều hơn
    ``MAX_SCAN_HOSTS`` host (tránh quét cả mạng /8).
    """
    if not iface.ip or not iface.netmask:
        raise ValueError(
            f"Card '{iface.name}' chưa có IPv4/mặt nạ mạng nên không tính được dải quét."
        )
    try:
        network = ipaddress.IPv4Network(f"{iface.ip}/{iface.netmask}", strict=False)
    except ValueError as exc:
        raise ValueError(f"Không hiểu địa chỉ {iface.ip}/{iface.netmask}: {exc}") from exc

    hosts = [str(host) for host in network.hosts()]
    if len(hosts) > MAX_SCAN_HOSTS:
        raise ValueError(
            f"Dải {network} có {len(hosts)} địa chỉ host, vượt giới hạn "
            f"MAX_SCAN_HOSTS = {MAX_SCAN_HOSTS}. Hãy chọn mạng nhỏ hơn (ví dụ /24)."
        )
    return hosts


def check_environment() -> list[str]:
    """Kiểm tra môi trường và trả về danh sách vấn đề **chặn chạy**, bằng tiếng Việt.

    Danh sách rỗng nghĩa là chạy được. Chỉ gồm ba điều kiện bắt buộc: quyền
    Administrator, Npcap và card mạng hợp lệ. Cảnh báo không chặn chạy (ví dụ VPN
    đang bật) nằm ở ``get_warnings()`` để giao diện hiển thị mà vẫn cho khởi động.
    """
    problems: list[str] = []
    if not is_admin():
        problems.append(
            "Chưa chạy bằng quyền Administrator: hãy mở lại VS Code/PowerShell bằng "
            "'Run as administrator', nếu không sẽ không gửi/nhận được gói tin thô."
        )
    if not has_npcap():
        problems.append(
            "Chưa cài Npcap hoặc Npcap chưa chạy: tải bản mới nhất ở https://npcap.com, "
            "cài xong kiểm tra bằng lệnh 'sc query npcap'."
        )
    try:
        get_active_interface()
    except RuntimeError as exc:
        problems.append(str(exc))
    return problems


def get_warnings() -> list[str]:
    """Trả về cảnh báo **không chặn chạy** (tiếng Việt), ví dụ đang bật VPN.

    Giao diện nên hiển thị các cảnh báo này nhưng vẫn cho người dùng tiếp tục.
    Danh sách rỗng nghĩa là không có gì đáng lưu ý.
    """
    warnings: list[str] = []
    try:
        vpn = [i for i in list_interfaces() if i.is_virtual and i.is_up and "warp" in i.name.lower()]
    except Exception:
        vpn = []
    if vpn:
        warnings.append(
            f"Đang bật VPN ({vpn[0].name}): kết quả ping/traceroute có thể sai. "
            "Nên tắt VPN trước khi đo."
        )
    return warnings


# ---------------------------------------------------------------- tự kiểm tra
def _print_interfaces(interfaces: list[NetInterface], chosen: NetInterface | None) -> None:
    """In bảng card mạng; card được chọn có dấu '*' ở đầu."""
    header = f"{'':2}{'TÊN':<28}{'IP':<17}{'MẶT NẠ':<17}{'GATEWAY':<17}{'MAC':<18}{'LOẠI':<7}UP"
    print(header)
    print("-" * len(header))
    for iface in interfaces:
        mark = "*" if chosen is not None and iface.name == chosen.name else " "
        kind = "ảo" if iface.is_virtual else "thật"
        up = "có" if iface.is_up else "không"
        print(
            f"{mark:2}{iface.name[:27]:<28}{iface.ip or '-':<17}{iface.netmask or '-':<17}"
            f"{iface.gateway or '-':<17}{iface.mac or '-':<18}{kind:<7}{up}"
        )
        print(f"    └ {iface.description}")


def main() -> int:
    """In bảng card mạng, card được chọn, dải quét và kết quả kiểm tra môi trường."""
    from core.console import setup_console_encoding

    setup_console_encoding()

    interfaces = list_interfaces()
    try:
        chosen: NetInterface | None = get_active_interface()
    except RuntimeError as exc:
        chosen = None
        print(f"LỖI: {exc}")

    print(f"Tìm thấy {len(interfaces)} card mạng (dấu * là card đang dùng):\n")
    _print_interfaces(interfaces, chosen)

    if chosen is not None:
        print(
            f"\nCard được chọn: {chosen.name} | {chosen.ip}/{chosen.netmask} | "
            f"gateway {chosen.gateway} | MAC {chosen.mac} | IfIndex {chosen.index}"
        )
        try:
            hosts = get_subnet_hosts(chosen)
            print(f"Sẽ quét {len(hosts)} host: {hosts[0]} ... {hosts[-1]}")
        except ValueError as exc:
            print(f"LỖI dải quét: {exc}")

    problems = check_environment()
    print("\nKiểm tra môi trường (điều kiện bắt buộc):")
    if not problems:
        print("  OK - không có vấn đề gì.")
    for problem in problems:
        print(f"  - {problem}")

    warnings = get_warnings()
    if warnings:
        print("\nCảnh báo (không chặn chạy):")
        for warning in warnings:
            print(f"  - {warning}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
