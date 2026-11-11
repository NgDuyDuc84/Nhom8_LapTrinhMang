"""Hỏi tên/dịch vụ trong LAN qua mDNS và NetBIOS với ngân sách thời gian cố định.

Chỉ nhận phản hồi từ các IPv4 đã được quét thấy trên card được chọn. Không gửi
MAC lên Internet, không quét cổng, không tải URL thiết bị cung cấp.
"""

from __future__ import annotations

import ipaddress
import secrets
import socket
import struct
import threading
import time

from core.interfaces import NetInterface
from models import DeviceHints

MDNS_SERVICES = (
    "_ipp._tcp.local", "_ipps._tcp.local", "_printer._tcp.local",
    "_pdl-datastream._tcp.local", "_googlecast._tcp.local", "_airplay._tcp.local",
    "_raop._tcp.local", "_smb._tcp.local", "_workstation._tcp.local", "_device-info._tcp.local",
)
MAX_TARGETS = 128
MAX_PACKETS = 128


def _text(value, limit=128) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return " ".join("".join(c for c in str(value) if c.isprintable() or c.isspace()).split())[:limit]


def _dns_name(value) -> str:
    return _text(value, 253).rstrip(".").casefold()


class MdnsRecords:
    """Ghép PTR/SRV/TXT/A kể cả khi chúng đến trong nhiều gói khác nhau."""

    def __init__(self, addresses: set[str], query_id: int):
        self.addresses = addresses
        self.query_id = query_id
        self.ptrs: dict[tuple[str, str], tuple[str, str]] = {}
        self.srvs: dict[tuple[str, str], str] = {}
        self.txts: dict[tuple[str, str], dict[str, str]] = {}
        self.hosts: set[tuple[str, str]] = set()
        self.reverse: dict[str, str] = {}

    def add(self, payload: bytes, peer: str) -> None:
        if peer not in self.addresses or not 12 <= len(payload) <= 9000:
            return
        ident, flags, questions, answers, authority, additional = struct.unpack("!6H", payload[:12])
        if ident != self.query_id or not flags & 0x8000 or flags & 0x7A0F:
            return
        if questions > 16 or answers + authority + additional > 128:
            return
        if len(self.ptrs) + len(self.srvs) + len(self.txts) + len(self.hosts) >= 1024:
            return
        try:
            from scapy.layers.dns import DNS

            packet = DNS(payload)
            for rr in [*packet.an, *packet.ns, *packet.ar][:128]:
                if int(rr.rclass) & 0x7FFF != 1 or int(rr.ttl) <= 0:
                    continue
                name = _dns_name(rr.rrname)
                kind = int(rr.type)
                if kind == 1 and str(rr.rdata) == peer:
                    self.hosts.add((peer, name))
                elif kind == 12:
                    target = _dns_name(rr.rdata)
                    if name in MDNS_SERVICES and target.endswith("." + name):
                        display = _text(rr.rdata, 253).rstrip(".")[:-(len(name) + 1)]
                        self.ptrs[peer, target] = name, display
                    elif name == ipaddress.IPv4Address(peer).reverse_pointer and target.endswith(".local"):
                        self.reverse[peer] = _text(rr.rdata, 253).rstrip(".")
                elif kind == 33:
                    target = _dns_name(rr.target)
                    if target.endswith(".local"):
                        self.srvs[peer, name] = target
                elif kind == 16:
                    fields = {}
                    for item in list(rr.rdata)[:32]:
                        key, separator, value = _text(item, 255).partition("=")
                        if separator and key.casefold() in {
                            "fn", "md", "ty", "usb_mfg", "usb_mdl", "manufacturer", "model",
                        }:
                            fields[key.casefold()] = _text(value)
                    self.txts[peer, name] = fields
        except (AttributeError, TypeError, ValueError, IndexError, struct.error):
            return  # Gói hỏng không được làm ngừng việc nhận diện các thiết bị khác.

    def followups(self) -> list[tuple[str, str, int]]:
        queries = set()
        for (peer, instance) in self.ptrs:
            target = self.srvs.get((peer, instance))
            if not target:
                queries.add((peer, instance, 33))
            elif (peer, target) not in self.hosts:
                queries.add((peer, target, 1))
            if (peer, instance) not in self.txts:
                queries.add((peer, instance, 16))
        return sorted(queries)[:64]

    def hints(self) -> dict[str, DeviceHints]:
        result = {peer: DeviceHints(hostname=name, sources={"mDNS"}) for peer, name in self.reverse.items()}
        for (peer, instance), (service, display) in sorted(self.ptrs.items()):
            target = self.srvs.get((peer, instance))
            if not target or (peer, target) not in self.hosts:
                continue  # Không gán dịch vụ của một địa chỉ khác cho máy gửi gói proxy.
            hint = result.setdefault(peer, DeviceHints())
            hint.hostname = target
            hint.services.add(service)
            hint.sources.add("mDNS/DNS-SD")
            fields = self.txts.get((peer, instance), {})
            hint.name = fields.get("fn") or hint.name or display
            hint.manufacturer = fields.get("usb_mfg") or fields.get("manufacturer") or hint.manufacturer
            hint.model = fields.get("usb_mdl") or fields.get("md") or fields.get("model") or fields.get("ty") or hint.model
        return result


def _receive_mdns(sock, records: MdnsRecords, duration: float, stop: threading.Event) -> None:
    deadline = time.monotonic() + duration
    for _ in range(MAX_PACKETS):
        remaining = deadline - time.monotonic()
        if stop.is_set() or remaining <= 0:
            break
        sock.settimeout(min(0.1, remaining))
        try:
            payload, (peer, port) = sock.recvfrom(9001)
        except socket.timeout:
            continue
        except (ConnectionResetError, ConnectionRefusedError):
            continue  # Một máy đóng cổng UDP không làm mất phản hồi của các máy khác.
        if port == 5353:
            records.add(payload, peer)


def discover_mdns(source: str, addresses: set[str], stop: threading.Event) -> dict[str, DeviceHints]:
    from scapy.layers.dns import DNS, DNSQR

    ident = secrets.randbelow(65535) + 1
    records = MdnsRecords(addresses, ident)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(0.1)
        sock.bind((source, 0))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(source))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)

        def send(peer, name, kind):
            if not stop.is_set():
                sock.sendto(bytes(DNS(id=ident, rd=0, qd=DNSQR(qname=name + ".", qtype=kind))), (peer, 5353))

        for service in MDNS_SERVICES:
            send("224.0.0.251", service, 12)
        for peer in sorted(addresses):
            send(peer, ipaddress.IPv4Address(peer).reverse_pointer, 12)
        _receive_mdns(sock, records, 0.35, stop)
        for duration in (0.2, 0.15):
            queries = records.followups()
            if not queries or stop.is_set():
                break
            for peer, name, kind in queries:
                send(peer, name, kind)
            _receive_mdns(sock, records, duration, stop)
    return records.hints()


def _skip_name(payload: bytes, offset: int) -> int:
    for _ in range(128):
        length = payload[offset]
        if length & 0xC0 == 0xC0:
            if offset + 1 >= len(payload):
                raise ValueError("Con trỏ tên bị cắt")
            return offset + 2
        if length > 63:
            raise ValueError("Nhãn tên không hợp lệ")
        offset += 1
        if length == 0:
            return offset
        offset += length
    raise ValueError("Tên quá dài")


def parse_netbios(payload: bytes, query_id: int) -> DeviceHints | None:
    """Đọc NBSTAT theo RFC 1002; bỏ tên nhóm, không coi đây là xác minh Windows."""
    try:
        ident, flags, questions, answers, _, _ = struct.unpack("!6H", payload[:12])
        if ident != query_id or not flags & 0x8000 or flags & 0x780F or questions > 1 or not 1 <= answers <= 8:
            return None
        offset = 12
        for _ in range(questions):
            offset = _skip_name(payload, offset) + 4
        for _ in range(answers):
            offset = _skip_name(payload, offset)
            kind, klass, _, length = struct.unpack_from("!HHIH", payload, offset)
            offset += 10
            data = payload[offset:offset + length]
            offset += length
            if kind != 0x21 or klass != 1 or not data or len(data) != length:
                continue
            count = data[0]
            if count > 64 or len(data) < 1 + count * 18:
                continue
            hint = DeviceHints(sources={"NetBIOS"})
            for index in range(count):
                row = data[1 + index * 18:1 + (index + 1) * 18]
                suffix, name_flags = row[15], struct.unpack("!H", row[16:])[0]
                name = _text(row[:15].decode("ascii", errors="replace").rstrip(" \x00"))
                if name_flags & 0x8000 or not name or "\ufffd" in name:
                    continue
                if suffix in (0, 0x20):
                    hint.hostname = hint.hostname or name
                    if suffix == 0x20:
                        hint.services.add("netbios-file-server")
            return hint if hint.hostname else None
    except (ValueError, IndexError, struct.error):
        return None
    return None


def discover_netbios(source: str, addresses: set[str], stop: threading.Event) -> dict[str, DeviceHints]:
    wildcard = b"*" + b"\0" * 15
    encoded = bytes(part for value in wildcard for part in (65 + (value >> 4), 65 + (value & 15)))
    question = b"\x20" + encoded + b"\0" + struct.pack("!HH", 0x21, 1)
    requests, result = {}, {}
    first_id = secrets.randbelow(65000) + 1
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(0.1)
        sock.bind((source, 0))
        for index, peer in enumerate(sorted(addresses)):
            if stop.is_set():
                return result
            ident = first_id + index
            requests[ident] = peer
            sock.sendto(struct.pack("!6H", ident, 0, 1, 0, 0, 0) + question, (peer, 137))
        deadline = time.monotonic() + 0.3
        for _ in range(MAX_PACKETS):
            remaining = deadline - time.monotonic()
            if stop.is_set() or remaining <= 0:
                break
            sock.settimeout(min(0.1, remaining))
            try:
                payload, (peer, port) = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except (ConnectionResetError, ConnectionRefusedError):
                continue
            if port != 137 or len(payload) < 12:
                continue
            ident = struct.unpack("!H", payload[:2])[0]
            if requests.get(ident) != peer:
                continue
            hint = parse_netbios(payload, ident)
            if hint:
                result[peer] = hint
    return result


def discover_device_hints(iface: NetInterface, addresses: set[str], stop: threading.Event) -> dict[str, DeviceHints]:
    network = ipaddress.IPv4Network(f"{iface.ip}/{iface.netmask}", strict=False)
    allowed = set()
    for value in addresses:
        try:
            address = ipaddress.IPv4Address(value)
        except ipaddress.AddressValueError:
            continue
        is_endpoint = network.prefixlen >= 31 or address not in (network.network_address, network.broadcast_address)
        if (address in network and is_endpoint and str(address) != iface.ip
                and not address.is_multicast and not address.is_unspecified and not address.is_loopback):
            allowed.add(str(address))
    allowed = set(sorted(allowed)[:MAX_TARGETS])
    if not allowed or stop.is_set():
        return {}
    try:
        result = discover_mdns(iface.ip, allowed, stop)
    except OSError:
        result = {}
    remaining = allowed - result.keys() - {iface.gateway}
    if remaining and not stop.is_set():
        try:
            result.update(discover_netbios(iface.ip, remaining, stop))
        except OSError:
            pass
    return result
