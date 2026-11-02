"""Tra cứu hãng sản xuất từ địa chỉ MAC (phần của C – đây chỉ là file khung)."""

from __future__ import annotations


def lookup(mac: str) -> str:
    """Trả về tên hãng sản xuất ứng với 3 byte đầu (OUI) của ``mac``.

    Đầu vào: ``mac`` dạng ``"aa:bb:cc:dd:ee:ff"`` (đã viết thường).
    Đầu ra: tên hãng (ví dụ ``"Apple, Inc."``); trả ``"Unknown"`` nếu không tra được.
    """
    raise NotImplementedError("extras.oui.lookup chưa được cài đặt (phần của C).")
