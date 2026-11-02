"""Quét kênh Wi-Fi và gợi ý kênh ít nhiễu (phần của C – đây chỉ là file khung)."""

from __future__ import annotations


def scan_wifi() -> list[dict]:
    """Quét các mạng Wi-Fi xung quanh.

    Đầu ra: ``list[dict]``, mỗi phần tử dự kiến có ``ssid``, ``bssid``, ``channel``,
    ``rssi`` (dBm) và ``band`` (``"2.4GHz"`` hoặc ``"5GHz"``); trả list rỗng nếu không quét được.
    """
    raise NotImplementedError("extras.wifi_channels.scan_wifi chưa được cài đặt (phần của C).")


def recommend_channel(networks: list[dict]) -> int:
    """Gợi ý kênh Wi-Fi ít nhiễu nhất dựa trên danh sách mạng quét được.

    Đầu vào: ``networks`` là kết quả của ``scan_wifi()``.
    Đầu ra: số kênh được gợi ý (``int``), ví dụ ``1``, ``6`` hoặc ``11`` cho băng 2.4 GHz.
    """
    raise NotImplementedError("extras.wifi_channels.recommend_channel chưa được cài đặt (phần của C).")
