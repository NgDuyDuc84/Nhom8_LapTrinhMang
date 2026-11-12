"""Kiểm tra hình thức gói ARP; đây không phải xác thực danh tính thiết bị."""
import ipaddress
import re


def valid_arp_source(packet, iface):
    from scapy.all import ARP, Ether
    if not packet.haslayer(ARP):
        return None
    arp = packet[ARP]
    mac = str(arp.hwsrc).lower()
    if not re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", mac) or mac == "00:00:00:00:00:00" or int(mac[:2], 16) & 1:
        return None
    if packet.haslayer(Ether) and str(packet[Ether].src).lower() != mac:
        return None
    try:
        ip = ipaddress.IPv4Address(str(arp.psrc))
        subnet = ipaddress.IPv4Network(f"{iface.ip}/{iface.netmask}", strict=False)
        if ip not in subnet or (subnet.prefixlen < 31 and ip in {subnet.network_address, subnet.broadcast_address}) or ip.is_multicast:
            return None
    except ValueError:
        return None
    return str(ip), mac
