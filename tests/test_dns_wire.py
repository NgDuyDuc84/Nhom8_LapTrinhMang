import struct

import pytest
from scapy.layers.dns import DNS, DNSRR, dns_compress

from core.dns_wire import read_name, query
from core.device_discovery import MdnsRecords


def test_compressed_dns_records_are_read_without_capture_runtime():
    peer = "192.168.1.20"
    packet = DNS(id=42, qr=1, aa=1, qd=[], an=[
        DNSRR(rrname="20.1.168.192.in-addr.arpa.", type="PTR", ttl=120, rdata="printer.local."),
        DNSRR(rrname="printer.local.", type="A", ttl=120, rdata=peer),
    ])
    records = MdnsRecords({peer}, 42)
    records.add(bytes(dns_compress(packet)), peer)
    assert records.hints()[peer].hostname == "printer.local"


@pytest.mark.parametrize("payload", [b"\xc0\x00", b"\xc0\xff", b"\xc0", b"\x40", b"\x03ab"])
def test_bad_compression_and_truncated_names_are_rejected(payload):
    with pytest.raises(ValueError):
        read_name(payload, 0)


def test_generated_query_is_compatible_with_dns_parser():
    parsed = DNS(query(123, "_ipp._tcp.local", 12))
    assert parsed.id == 123 and parsed.rd == 0 and parsed.qdcount == 1
    assert parsed.qd[0].qname == b"_ipp._tcp.local." and parsed.qd[0].qtype == 12


def test_malformed_record_does_not_partially_update_mdns_state():
    peer = "192.168.1.20"
    good = bytes(DNS(id=42, qr=1, aa=1, qd=[], an=[
        DNSRR(rrname="20.1.168.192.in-addr.arpa.", type="PTR", ttl=120, rdata="printer.local.")]))
    bad = good[:6] + struct.pack("!H", 2) + good[8:] + b"\xc0"
    records = MdnsRecords({peer}, 42)
    records.add(bad, peer)
    assert records.hints() == {}
