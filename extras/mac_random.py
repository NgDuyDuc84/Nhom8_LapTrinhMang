"""Nhận diện địa chỉ MAC ngẫu nhiên (phần của C – đây chỉ là file khung)."""

from __future__ import annotations


def is_randomized(mac: str) -> bool:
    """Cho biết ``mac`` có phải MAC ngẫu nhiên cục bộ (locally administered) hay không.

    Đầu vào: ``mac`` dạng ``"aa:bb:cc:dd:ee:ff"``.
    Đầu ra: ``True`` nếu bit locally-administered (bit thứ 2 của byte đầu) được bật,
    thường là do điện thoại đổi MAC để bảo vệ riêng tư; ngược lại ``False``.
    """
    raise NotImplementedError("extras.mac_random.is_randomized chưa được cài đặt (phần của C).")
