"""Kiểm tra ABI và phân biệt lỗi API với đích không phản hồi."""
import ctypes as C
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import windows_network as native


@pytest.fixture
def library(monkeypatch):
    lib = SimpleNamespace(ResolveIpNetEntry2=Mock(return_value=0),
                          GetIpNetTable2=Mock(return_value=0), FreeMibTable=Mock(),
                          GetAdaptersAddresses=Mock())
    monkeypatch.setattr(native, "_library", lambda: lib)
    return lib


def test_resolve_uses_correct_windows_layout_source_and_index(library):
    assert C.sizeof(native.NeighborRow) == 88
    assert native.NeighborRow.InterfaceLuid.offset == 32
    assert native.NeighborRow.ReachabilityTime.offset == 84
    def resolve(pointer, source):
        row = C.cast(pointer, C.POINTER(native.NeighborRow)).contents
        origin = C.cast(source, C.POINTER(native.SockaddrInet)).contents
        assert bytes(row.Address.ipv4.address) == b"\xc0\xa8\x01\x01"
        assert bytes(origin.ipv4.address) == b"\xc0\xa8\x01\x09"
        assert row.InterfaceIndex == 7 and row.InterfaceLuid == 0
        row.PhysicalAddress[:6] = bytes.fromhex("001122334466")
        row.PhysicalAddressLength = 6
        return 0
    library.ResolveIpNetEntry2.side_effect = resolve
    assert native.resolve_ipv4("192.168.1.1", "192.168.1.9", 7) == "00:11:22:33:44:66"


@pytest.mark.parametrize("code", [5, 87, 1168, 1231])
def test_resolver_failure_is_not_a_missing_host(library, code):
    library.ResolveIpNetEntry2.return_value = code
    with pytest.raises(OSError) as error:
        native.resolve_ipv4("192.168.1.1", "192.168.1.9", 7)
    assert error.value.errno == code


def test_unanswered_arp_is_none(library):
    library.ResolveIpNetEntry2.return_value = 67
    assert native.resolve_ipv4("192.168.1.20", "192.168.1.9", 7) is None


def test_neighbor_table_alignment_scope_state_and_free(library):
    class Table(C.Structure):
        _fields_ = [("count", C.c_uint32), ("rows", native.NeighborRow * 3)]
    table = Table()
    table.count = 3
    assert Table.rows.offset == native._NeighborTable.Table.offset == 8
    for index, row in enumerate(table.rows):
        row.InterfaceIndex = 7 if index < 2 else 8
        row.State = 5 if index != 1 else 4  # stale cache không xác nhận reachable
        row.Address = native._sockaddr(f"192.168.1.{20 + index}")
        row.PhysicalAddress[:6] = bytes.fromhex("001122334466")
        row.PhysicalAddressLength = 6
    def get(family, pointer):
        C.cast(pointer, C.POINTER(C.c_void_p))[0] = C.addressof(table)
        return 0
    library.GetIpNetTable2.side_effect = get
    assert native.neighbors(7) == [("192.168.1.20", "00:11:22:33:44:66")]
    assert library.FreeMibTable.call_args.args[0].value == C.addressof(table)


def test_adapter_buffer_growth_and_unicode_names(library):
    row = native._Adapter()
    row.IfIndex = 7
    row.FriendlyName = "Wi-Fi phòng khách"
    row.Description = "Wireless adapter"
    row.AdapterName = b"{12345678-1234-1234-1234-123456789ABC}"
    row.PhysicalAddress[:6] = bytes.fromhex("001122334455")
    row.PhysicalAddressLength = 6
    row.OperStatus = 1
    calls = []
    def get(family, flags, reserved, pointer, size):
        calls.append(family)
        if len(calls) == 1:
            C.cast(size, C.POINTER(native.W.ULONG)).contents.value = 20000
            return 111
        C.memmove(pointer, C.byref(row), C.sizeof(row))
        return 0
    library.GetAdaptersAddresses.side_effect = get
    result = native.adapters()
    assert len(calls) == 2 and len(result) == 1
    assert result[0].name == "Wi-Fi phòng khách" and result[0].mac == "00:11:22:33:44:55"
    assert result[0].guid == "12345678-1234-1234-1234-123456789abc" and result[0].up
