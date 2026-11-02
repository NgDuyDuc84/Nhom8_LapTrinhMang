"""Tạo báo cáo PDF làm bằng chứng gửi nhà mạng (phần của C – đây chỉ là file khung)."""

from __future__ import annotations


def build_report(data: dict, path: str) -> None:
    """Dựng file PDF từ dữ liệu tổng hợp do ``Backend.export_report`` gom sẵn.

    Đầu vào:
        ``data`` là ``dict`` gồm các khóa dự kiến: ``interface`` (thông tin mạng),
        ``start``/``end`` (khoảng thời gian), ``ping_stats`` (thống kê từng mốc),
        ``loss_events`` (các mốc thời gian mất gói), ``diagnoses`` (kết luận),
        ``traceroute`` (list ``Hop`` gần nhất).
        ``path`` là đường dẫn file ``.pdf`` cần tạo.
    Đầu ra: không trả về gì, file PDF được ghi ra ``path``.
    """
    raise NotImplementedError("extras.pdf_report.build_report chưa được cài đặt (phần của C).")
