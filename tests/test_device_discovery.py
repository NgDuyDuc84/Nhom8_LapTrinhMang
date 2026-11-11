"""Gói mDNS/NetBIOS tổng hợp và socket giả, không gửi lưu lượng mạng thật."""

import socket
import struct
import threading
from unittest.mock import MagicMock, Mock

import pytest
from scapy.layers.dns import DNS, DNSRR, DNSRRSRV

from core import device_discovery as discovery
from core.interfaces import NetInterface
from models import DeviceHints

PEER = "192.168.1.20"
INSTANCE = "Office._ipp._tcp.local."
HOST = "printer.local."


def mdns(*records, ident=42, flags=None):
    packet = DNS(id=ident, qr=1, aa=1, qd=[], an=list(records))
    payload = bytes(packet)
    if flags is not None:
        payload = payload[:2] + struct.pack("!H", flags) + payload[4:]
    return payload


def printer_records(ip=PEER):
    return [
        DNSRR(rrname="_ipp._tcp.local.", type="PTR", ttl=120, rdata=INSTANCE),
        DNSRRSRV(rrname=INSTANCE, ttl=120, target=HOST, port=631),
        DNSRR(rrname=HOST, type="A", ttl=120, rdata=ip),
        DNSRR(rrname=INSTANCE, type="TXT", ttl=120, rdata=[b"usb_MFG=HP", b"usb_MDL=LaserJet", b"fn=Office Printer"]),
    ]


def test_mdns_combines_service_model_manufacturer_and_friendly_name():
    records = discovery.MdnsRecords({PEER}, 42)
    records.add(mdns(*printer_records()), PEER)
    hint = records.hints()[PEER]
    assert hint.hostname == "printer.local"
    assert hint.name == "Office Printer" and hint.model == "LaserJet"
    assert hint.manufacturer == "HP"
    assert hint.services == {"_ipp._tcp.local"}
    assert not records.followups()


def test_mdns_joins_split_packets_and_requests_missing_records():
    ptr, srv, address, txt = printer_records()
    records = discovery.MdnsRecords({PEER}, 42)
    records.add(mdns(ptr), PEER)
    assert (PEER, INSTANCE.rstrip(".").lower(), 33) in records.followups()
    assert not records.hints()
    records.add(mdns(srv, txt), PEER)
    assert (PEER, HOST.rstrip("."), 1) in records.followups()
    records.add(mdns(address), PEER)
    assert records.hints()[PEER].manufacturer == "HP"


def test_proxy_or_spoofed_other_ip_is_not_assigned_to_sender():
    records = discovery.MdnsRecords({PEER, "192.168.1.30"}, 42)
    records.add(mdns(*printer_records(ip="192.168.1.30")), PEER)
    assert not records.hints()


@pytest.mark.parametrize("payload,peer", [
    (mdns(*printer_records(), ident=43), PEER),
    (mdns(*printer_records()), "192.168.1.99"),
    (mdns(*printer_records(), flags=0), PEER),
    (mdns(*printer_records(), flags=0x8403), PEER),
    (mdns(*printer_records(), flags=0x8600), PEER),
    (b"bad", PEER),
    (struct.pack("!6H", 42, 0x8400, 0, 129, 0, 0), PEER),
])
def test_mdns_rejects_unrelated_invalid_or_truncated_packets(payload, peer):
    records = discovery.MdnsRecords({PEER}, 42)
    records.add(payload, peer)
    assert not records.hints()


def test_mdns_reverse_name_can_identify_private_mac_host_without_service():
    records = discovery.MdnsRecords({PEER}, 42)
    records.add(mdns(DNSRR(rrname="20.1.168.192.in-addr.arpa.", type="PTR",
                           ttl=120, rdata="iphone.local.")), PEER)
    assert records.hints()[PEER].hostname == "iphone.local"


def nbns(names, ident=42):
    raw_name = b"*" + b"\0" * 15
    encoded = bytes(part for value in raw_name for part in (65 + (value >> 4), 65 + (value & 15)))
    question = b"\x20" + encoded + b"\0" + struct.pack("!HH", 0x21, 1)
    rows = [name.encode("ascii").ljust(15, b" ") + bytes([suffix]) + struct.pack("!H", flags)
            for name, suffix, flags in names]
    data = bytes([len(rows)]) + b"".join(rows) + b"\0" * 52
    answer = b"\xc0\x0c" + struct.pack("!HHIH", 0x21, 1, 0, len(data)) + data
    return struct.pack("!6H", ident, 0x8400, 1, 1, 0, 0) + question + answer


def test_netbios_uses_unique_machine_name_instead_of_workgroup():
    payload = nbns([("WORKGROUP", 0, 0x8400), ("LAPTOP-ABC", 0, 0x0400), ("LAPTOP-ABC", 0x20, 0x0400)])
    hint = discovery.parse_netbios(payload, 42)
    assert hint.hostname == "LAPTOP-ABC"
    assert "netbios-file-server" in hint.services


@pytest.mark.parametrize("payload", [b"bad", nbns([("WORKGROUP", 0, 0x8400)]),
                                     nbns([("MACHINE", 0, 0x0400)], ident=43),
                                     nbns([("MACHINE", 0, 0x0400)])[:-60]])
def test_netbios_rejects_group_names_wrong_ids_and_truncated_responses(payload):
    assert discovery.parse_netbios(payload, 42) is None


def fake_socket(monkeypatch, packets):
    sock = MagicMock()
    sock.__enter__.return_value = sock
    replies = iter(packets)

    def receive(limit):
        try:
            reply = next(replies)
            if isinstance(reply, BaseException):
                raise reply
            return reply
        except StopIteration:
            raise socket.timeout

    sock.recvfrom.side_effect = receive
    monkeypatch.setattr(discovery.socket, "socket", Mock(return_value=sock))
    monkeypatch.setattr(discovery.secrets, "randbelow", lambda bound: 41)
    return sock


def test_mdns_queries_use_selected_source_and_bounded_receive_timeout(monkeypatch):
    sock = fake_socket(monkeypatch, [ConnectionResetError("UDP port closed"), (mdns(*printer_records()), (PEER, 5353))])
    result = discovery.discover_mdns("192.168.1.9", {PEER}, threading.Event())
    sock.bind.assert_called_once_with(("192.168.1.9", 0))
    assert result[PEER].name == "Office Printer"
    assert all(0 < call.args[0] <= 0.1 for call in sock.settimeout.call_args_list)
    assert {call.args[1][0] for call in sock.sendto.call_args_list} <= {PEER, "224.0.0.251"}


def test_netbios_only_accepts_response_matching_requested_peer_and_transaction(monkeypatch):
    payload = nbns([("LAPTOP-ABC", 0, 0x0400)])
    sock = fake_socket(monkeypatch, [ConnectionRefusedError("UDP port closed"),
                                    (payload, ("192.168.1.99", 137)), (payload, (PEER, 137))])
    result = discovery.discover_netbios("192.168.1.9", {PEER}, threading.Event())
    assert result[PEER].hostname == "LAPTOP-ABC"
    sock.bind.assert_called_once_with(("192.168.1.9", 0))


def test_discovery_only_probes_known_unicast_hosts_in_current_subnet(monkeypatch):
    iface = NetInterface("Wi-Fi", "test", "192.168.1.9", "255.255.255.0",
                         "192.168.1.1", "00:11:22:33:44:55", False, True, 7)
    mdns_probe, nbns_probe = Mock(return_value={}), Mock(return_value={})
    monkeypatch.setattr(discovery, "discover_mdns", mdns_probe)
    monkeypatch.setattr(discovery, "discover_netbios", nbns_probe)
    discovery.discover_device_hints(iface, {PEER, iface.ip, "8.8.8.8", "192.168.1.255",
                                          "192.168.1.0", "224.0.0.251", "invalid"}, threading.Event())
    assert mdns_probe.call_args.args[1] == {PEER}
    assert nbns_probe.call_args.args[1] == {PEER}


def test_stop_prevents_discovery_io(monkeypatch):
    iface = NetInterface("Wi-Fi", "test", "192.168.1.9", "255.255.255.0",
                         "192.168.1.1", "00:11:22:33:44:55", False, True, 7)
    sock = Mock()
    monkeypatch.setattr(discovery.socket, "socket", sock)
    stop = threading.Event()
    stop.set()
    assert discovery.discover_device_hints(iface, {PEER}, stop) == {}
    sock.assert_not_called()
