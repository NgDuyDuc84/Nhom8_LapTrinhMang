"""Kết hợp bằng chứng nhận diện và tạo nhãn dễ hiểu; không thực hiện I/O mạng."""

from __future__ import annotations

from dataclasses import replace
import re
import socket

from extras import oui
from extras.mac_random import is_randomized
from models import Device, DeviceHints, now

DEVICE_TYPES = {
    "unknown": "Chưa xác định",
    "computer": "Máy tính",
    "laptop": "Laptop",
    "mobile": "Điện thoại / tablet",
    "router": "Router / gateway",
    "printer": "Máy in / máy chủ in",
    "camera": "Camera",
    "media": "TV / thiết bị phát",
    "speaker": "Loa / âm thanh",
    "file_server": "Máy tính / NAS",
    "iot": "Thiết bị nhúng / IoT",
}


def clean_text(value: str, limit: int = 128) -> str:
    return " ".join("".join(c for c in str(value) if c.isprintable() or c.isspace()).split())[:limit]


def identify_device(device: Device, gateway_ip: str = "", hints: DeviceHints | None = None) -> Device:
    result = replace(device, vendor=oui.lookup(device.mac))
    if hints is not None:
        result.hostname = clean_text(hints.hostname) or result.hostname
        result.discovered_name = clean_text(hints.name) or result.discovered_name
        result.manufacturer = clean_text(hints.manufacturer) or result.manufacturer
        result.model = clean_text(hints.model) or result.model
        result.services = tuple(sorted(set(result.services) | hints.services))[:32]
        result.identity_seen = now()
    evidence = []
    if is_randomized(result.mac):
        evidence.append("MAC quản lý cục bộ/riêng tư: không suy ra hãng card mạng từ tiền tố MAC.")
    elif result.vendor != "Unknown":
        evidence.append(f"Hãng đăng ký tiền tố MAC: {result.vendor}. Đây có thể là hãng card mạng.")
    if result.hostname:
        evidence.append(f"Tên máy trong LAN: {result.hostname}.")
    if result.model:
        evidence.append(f"Model thiết bị tự công bố: {result.model}.")
    if result.services:
        evidence.append("Dịch vụ công bố: " + ", ".join(result.services) + ".")
    if hints and hints.sources:
        evidence.append("Nguồn bổ sung: " + ", ".join(sorted(hints.sources)) + ".")

    kind, confidence, reason = "unknown", "unknown", "Chưa đủ bằng chứng để phân loại thiết bị."
    services = set(result.services)
    text = " ".join((result.hostname, result.discovered_name, result.model)).casefold()
    if result.is_self:
        result.hostname = clean_text(socket.gethostname())
        kind, confidence, reason = "computer", "high", "Đây là máy đang chạy NetGuard."
    elif gateway_ip and result.ip == gateway_ip:
        kind, confidence, reason = "router", "high", "Địa chỉ này là gateway của kết nối đang quét."
    elif services & {"_ipp._tcp.local", "_ipps._tcp.local", "_printer._tcp.local", "_pdl-datastream._tcp.local"}:
        kind, confidence, reason = "printer", "medium", "Có dịch vụ in trong LAN; cũng có thể là máy chủ in."
    elif "_googlecast._tcp.local" in services or "_airplay._tcp.local" in services:
        kind, confidence, reason = "media", "medium", "Có dịch vụ Google Cast/AirPlay; chưa xác định chính xác phần cứng."
    elif "_raop._tcp.local" in services:
        kind, confidence, reason = "speaker", "medium", "Có dịch vụ âm thanh AirPlay."
    elif re.search(r"iphone|ipad|android|galaxy|pixel[- _]?\d", text):
        kind, confidence, reason = "mobile", "low", "Gợi ý theo tên/model thiết bị tự công bố."
    elif re.search(r"macbook|laptop|notebook|surface[- _]?pro", text):
        kind, confidence, reason = "laptop", "low", "Gợi ý theo tên/model; không phải xác minh phần cứng."
    elif re.search(r"ipcam|ip[- _]?camera|hikvision|ezviz|dahua|tapo[- _]?c\d", text):
        kind, confidence, reason = "camera", "low", "Gợi ý theo tên/model thiết bị tự công bố."
    elif re.search(r"printer|laserjet|officejet|deskjet|epson", text):
        kind, confidence, reason = "printer", "low", "Gợi ý theo tên/model thiết bị tự công bố."
    elif "_smb._tcp.local" in services or "netbios-file-server" in services:
        kind, confidence, reason = "file_server", "medium", "Có dịch vụ chia sẻ tệp; chưa phân biệt máy tính với NAS."
    elif "_workstation._tcp.local" in services or re.search(r"desktop[-_]|imac|mac[- _]?mini", text):
        kind, confidence, reason = "computer", "low", "Gợi ý theo tên máy hoặc dịch vụ workstation."
    elif re.search(r"esp32|esp8266|esphome|shelly|tasmota", text):
        kind, confidence, reason = "iot", "low", "Gợi ý theo tên thiết bị nhúng công bố trong LAN."
    # Hãng như Apple/Samsung/Intel sản xuất nhiều loại thiết bị: không đoán loại chỉ từ hãng.
    result.device_type = kind
    result.identity_confidence = confidence
    result.identity_evidence = "\n".join([reason, *evidence])[:2048]
    return result


def effective_type(device: Device) -> str:
    if device.type_override in DEVICE_TYPES and device.type_override:
        return device.type_override
    if device.is_self:
        return "computer"
    return device.device_type if device.device_type in DEVICE_TYPES else "unknown"


def type_label(device: Device, *, automatic: bool = False) -> str:
    if automatic:
        kind = "computer" if device.is_self else device.device_type
        kind = kind if kind in DEVICE_TYPES else "unknown"
    else:
        kind = effective_type(device)
    label = DEVICE_TYPES[kind]
    if device.type_override and not automatic:
        return f"{label} (đã chọn)"
    if kind != "unknown" and not device.is_self and device.device_type != "router":
        return f"{label} (gợi ý)"
    return label


def short_vendor(vendor: str) -> str:
    for key, label in (("intel", "Intel"), ("apple", "Apple"), ("samsung", "Samsung"),
                       ("zte", "ZTE"), ("espressif", "Espressif"), ("raspberry pi", "Raspberry Pi")):
        if vendor.casefold().startswith(key):
            return label
    return clean_text(vendor, 44)


def manufacturer_label(device: Device) -> str:
    if device.manufacturer:
        return clean_text(device.manufacturer)
    if is_randomized(device.mac):
        return "Chưa rõ · MAC riêng tư/cục bộ"
    vendor = device.vendor if device.vendor and device.vendor != "Unknown" else oui.lookup(device.mac)
    return short_vendor(vendor) + " (theo MAC)" if vendor != "Unknown" else "Chưa xác định"


def device_title(device: Device) -> str:
    if device.name:
        return clean_text(device.name)
    if device.is_self:
        return "Máy tính này"
    if device.discovered_name or device.hostname:
        return clean_text(device.discovered_name or device.hostname.removesuffix(".local"))
    suffix = device.mac[-5:].upper()
    kind = effective_type(device)
    if kind != "unknown":
        return f"{DEVICE_TYPES[kind]} · {suffix}"
    vendor = device.vendor if device.vendor and device.vendor != "Unknown" else oui.lookup(device.mac)
    if vendor != "Unknown" and not is_randomized(device.mac):
        return f"Thiết bị · {short_vendor(vendor)} · {suffix}"
    return f"Thiết bị · {suffix}"
