"""Phạm vi lưu trữ riêng theo hồ sơ mạng; worker giữ ngữ cảnh của chính lượt đo."""
from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
import ipaddress

_network = ContextVar("netguard_network", default="legacy")


def current_network() -> str:
    return _network.get()


@contextmanager
def network_scope(network: str):
    token = _network.set(network or "legacy")
    try:
        yield
    finally:
        _network.reset(token)


def network_id(iface) -> str:
    from config import SETTINGS
    subnet = str(ipaddress.ip_network(f"{iface.ip}/{iface.netmask}", strict=False))
    profile = getattr(iface, "profile_id", "")
    label = SETTINGS.get("network_label", "")
    if profile == "unidentified":
        if not label:
            raise RuntimeError("Windows chưa cung cấp hồ sơ mạng. Mở Mo_LichSu.cmd, đặt nhãn mạng riêng trong Cài đặt rồi mở lại; tránh dùng chung tin cậy giữa hai mạng cùng subnet.")
        profile = f"manual:{label}"
    else:
        profile = f"{profile}|{label}"
    adapter = getattr(iface, "adapter_id", "") or iface.name or iface.mac.lower()
    return sha256(f"{profile}|{adapter}|{subnet}|{iface.gateway}".encode()).hexdigest()[:24]


def connection_key(iface):
    return (network_id(iface), iface.index, iface.name, iface.ip, iface.netmask, iface.gateway, iface.mac) if iface else None
