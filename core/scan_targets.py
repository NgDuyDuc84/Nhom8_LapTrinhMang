"""Dải IPv4 tính lười: không tạo hàng triệu chuỗi khi gặp subnet lớn."""
from collections.abc import Sequence, Iterator
import ipaddress


class IPv4Hosts(Sequence[str]):
    def __init__(self, network: ipaddress.IPv4Network):
        self.network = network
        first = int(network.network_address) + (network.prefixlen < 31)
        end = int(network.broadcast_address) + (network.prefixlen >= 31)
        self._addresses = range(first, end)

    def __len__(self) -> int:
        return len(self._addresses)

    def __getitem__(self, index):
        selected = self._addresses[index]
        if isinstance(selected, range):
            result = IPv4Hosts(self.network)
            result._addresses = selected
            return result
        return str(ipaddress.IPv4Address(selected))

    def __iter__(self) -> Iterator[str]:
        return (str(ipaddress.IPv4Address(value)) for value in self._addresses)

    def __contains__(self, value) -> bool:
        try:
            return int(ipaddress.IPv4Address(value)) in self._addresses
        except (ValueError, TypeError):
            return False
