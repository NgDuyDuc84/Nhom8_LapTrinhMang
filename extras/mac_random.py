"""Đọc bit quản lý cục bộ từ địa chỉ MAC quan sát được."""

from __future__ import annotations

import re


def is_randomized(mac: str) -> bool:
    """Cho biết ``mac`` có phải MAC ngẫu nhiên cục bộ (locally administered) hay không.

    Đầu vào: ``mac`` dạng ``"aa:bb:cc:dd:ee:ff"``.
    Đầu ra: ``True`` nếu bit locally-administered (bit thứ 2 của byte đầu) được bật,
    thường là do điện thoại đổi MAC để bảo vệ riêng tư; ngược lại ``False``.
    """
    if not isinstance(mac, str):
        return False
    normalized = mac.strip().replace("-", ":")
    if not re.fullmatch(r"[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}", normalized):
        return False
    return bool(int(normalized[:2], 16) & 0x02)

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
