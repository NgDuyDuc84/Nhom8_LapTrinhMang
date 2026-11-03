
"""Kiểm tra địa chỉ MAC có được quản lý cục bộ hay không."""

import re


def is_randomized(mac: str) -> bool:
    """Trả về True nếu bit Locally Administered được bật."""

    if not isinstance(mac, str):
        return False

    mac = mac.strip().replace("-", ":").upper()

    if not re.fullmatch(r"[0-9A-F]{2}(:[0-9A-F]{2}){5}", mac):
        return False

    first_byte = int(mac.split(":")[0], 16)

    return bool(first_byte & 0x02)


if __name__ == "__main__":
    test_macs = [
        "02:11:22:33:44:55",
        "06:AA:BB:CC:DD:EE",
        "0A:12:34:56:78:90",
        "00:11:22:33:44:55",
        "28:77:77:DB:B5:6C",
        "AC:74:B1:41:A5:D2",
    ]

    for mac in test_macs:
        print(f"{mac} -> {is_randomized(mac)}")
