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
