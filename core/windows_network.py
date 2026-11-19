"""API mạng Windows, không nạp Scapy hay driver bắt gói.

ResolveIpNetEntry2 chủ động phân giải lại từng IP, không coi bản ghi ARP cũ
là bằng chứng thiết bị đang online. Các buffer/handle đều thuộc từng lần gọi.
"""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
import ipaddress
import socket


class _Adapter(C.Structure):
    pass


_Adapter._fields_ = [
    ("Length", W.ULONG), ("IfIndex", W.ULONG), ("Next", C.POINTER(_Adapter)),
    ("AdapterName", C.c_char_p),
    *[(name, C.c_void_p) for name in ("Unicast", "Anycast", "Multicast", "DnsServer")],
    ("DnsSuffix", W.LPWSTR), ("Description", W.LPWSTR), ("FriendlyName", W.LPWSTR),
    ("PhysicalAddress", C.c_ubyte * 8), ("PhysicalAddressLength", W.ULONG),
    ("Flags", W.ULONG), ("Mtu", W.ULONG), ("IfType", W.ULONG), ("OperStatus", C.c_int),
]


class SockaddrIn(C.Structure):
    _fields_ = [("family", W.USHORT), ("port", W.USHORT),
                ("address", C.c_ubyte * 4), ("zero", C.c_ubyte * 8)]


class SockaddrInet(C.Union):
    # sockaddr_in6 có alignment 4 và kích thước 28.
    _fields_ = [("ipv4", SockaddrIn), ("ipv6", C.c_uint32 * 7)]


class NeighborRow(C.Structure):
    _fields_ = [("Address", SockaddrInet), ("InterfaceIndex", W.ULONG),
                ("InterfaceLuid", C.c_uint64), ("PhysicalAddress", C.c_ubyte * 32),
                ("PhysicalAddressLength", W.ULONG), ("State", C.c_int),
                ("Flags", C.c_ubyte), ("ReachabilityTime", W.ULONG)]


class _NeighborTable(C.Structure):
    _fields_ = [("NumEntries", W.ULONG), ("Table", NeighborRow * 1)]


@dataclass(frozen=True)
class Adapter:
    index: int
    name: str
    description: str
    mac: str
    guid: str
    up: bool


def _library():
    return C.WinDLL("iphlpapi.dll", use_last_error=True)


def _error(code: int, operation: str):
    raise OSError(code, f"{operation}: {C.FormatError(code).strip()}")


def adapters() -> list[Adapter]:
    lib = _library()
    func = lib.GetAdaptersAddresses
    func.argtypes = [W.ULONG, W.ULONG, C.c_void_p, C.POINTER(_Adapter), C.POINTER(W.ULONG)]
    func.restype = W.ULONG
    size = W.ULONG(15000)
    for _ in range(3):
        buffer = C.create_string_buffer(size.value)
        head = C.cast(buffer, C.POINTER(_Adapter))
        code = func(socket.AF_INET, 0x2 | 0x4 | 0x8, None, head, C.byref(size))
        if code == 111:  # ERROR_BUFFER_OVERFLOW: card có thể thay đổi giữa hai lần gọi.
            continue
        if code == 232:  # ERROR_NO_DATA
            return []
        if code:
            _error(code, "Không đọc được card mạng Windows")
        result = []
        while head:
            row = head.contents
            result.append(Adapter(
                int(row.IfIndex), row.FriendlyName or "", row.Description or "",
                bytes(row.PhysicalAddress[:min(8, row.PhysicalAddressLength)]).hex(":"),
                (row.AdapterName or b"").decode("ascii", errors="replace").strip("{}").lower(),
                row.OperStatus == 1,
            ))
            head = row.Next
        return result
    raise RuntimeError("Danh sách card mạng thay đổi liên tục; hãy thử lại.")


def _sockaddr(ip: str) -> SockaddrInet:
    result = SockaddrInet()
    result.ipv4.family = socket.AF_INET
    result.ipv4.address[:] = ipaddress.IPv4Address(ip).packed
    return result


def valid_mac(mac: str) -> bool:
    try:
        raw = bytes.fromhex(mac.replace(":", ""))
        return len(raw) == 6 and any(raw) and not raw[0] & 1
    except ValueError:
        return False


def resolve_ipv4(ip: str, source: str, index: int) -> str | None:
    """ARP chủ động trên đúng card; None chỉ dành cho đích không phản hồi."""
    lib = _library()
    func = lib.ResolveIpNetEntry2
    func.argtypes = [C.POINTER(NeighborRow), C.POINTER(SockaddrInet)]
    func.restype = W.ULONG
    row = NeighborRow()
    row.Address = _sockaddr(ip)
    row.InterfaceIndex = index
    origin = _sockaddr(source)
    code = func(C.byref(row), C.byref(origin))
    if code == 67:  # ERROR_BAD_NET_NAME: không có ARP reply.
        return None
    if code:
        _error(code, f"Không phân giải được ARP cho {ip}")
    mac = bytes(row.PhysicalAddress[:min(32, row.PhysicalAddressLength)]).hex(":")
    return mac if valid_mac(mac) else None


def neighbors(index: int) -> list[tuple[str, str]]:
    """Snapshot chỉ gồm IPv4 reachable; không dùng snapshot này để đánh online."""
    lib = _library()
    table = C.c_void_p()
    lib.GetIpNetTable2.argtypes = [W.USHORT, C.POINTER(C.c_void_p)]
    lib.GetIpNetTable2.restype = W.ULONG
    lib.FreeMibTable.argtypes = [C.c_void_p]
    lib.FreeMibTable.restype = None
    code = lib.GetIpNetTable2(socket.AF_INET, C.byref(table))
    try:
        if code == 1168:
            return []
        if code:
            _error(code, "Không đọc được bảng ARP Windows")
        if not table.value:
            return []
        count = C.cast(table, C.POINTER(W.ULONG)).contents.value
        rows = C.cast(table.value + _NeighborTable.Table.offset, C.POINTER(NeighborRow))
        result = []
        for i in range(count):
            row = rows[i]
            if row.InterfaceIndex != index or row.State != 5 or row.Address.ipv4.family != socket.AF_INET:
                continue
            ip = socket.inet_ntoa(bytes(row.Address.ipv4.address))
            mac = bytes(row.PhysicalAddress[:min(32, row.PhysicalAddressLength)]).hex(":")
            if valid_mac(mac):
                result.append((ip, mac))
        return result
    finally:
        if table.value:
            lib.FreeMibTable(table)
