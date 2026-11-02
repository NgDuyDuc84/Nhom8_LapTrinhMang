"""Xuất dữ liệu ra CSV (phần của C – đây chỉ là file khung)."""

from __future__ import annotations


def export_devices(devices: list, path: str) -> None:
    """Ghi danh sách ``Device`` ra file CSV tại ``path``.

    Đầu vào: ``devices`` là ``list[models.Device]``; ``path`` là đường dẫn file ``.csv``.
    Đầu ra: không trả về gì, file CSV được tạo (UTF-8, có dòng tiêu đề tiếng Việt).
    """
    raise NotImplementedError("extras.csv_export.export_devices chưa được cài đặt (phần của C).")


def export_pings(pings: list, path: str) -> None:
    """Ghi danh sách ``PingResult`` ra file CSV tại ``path``.

    Đầu vào: ``pings`` là ``list[models.PingResult]``; ``path`` là đường dẫn file ``.csv``.
    Đầu ra: không trả về gì, mỗi dòng gồm mốc, RTT, mất gói và thời điểm.
    """
    raise NotImplementedError("extras.csv_export.export_pings chưa được cài đặt (phần của C).")
