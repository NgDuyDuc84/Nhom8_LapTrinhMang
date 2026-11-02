
"""Xuất danh sách thiết bị và kết quả Ping ra file CSV."""

from __future__ import annotations

import csv
from pathlib import Path

from models import Device, PingResult


def export_devices(devices: list[Device], path: str) -> None:
    """Xuất danh sách thiết bị mạng ra CSV."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            "Địa chỉ IP",
            "Địa chỉ MAC",
            "Hãng sản xuất",
            "Tên thiết bị",
            "Ghi chú",
            "Đáng tin cậy",
            "Trực tuyến",
            "MAC quản lý cục bộ",
            "Thiết bị của tôi",
            "Lần đầu phát hiện",
            "Lần cuối phát hiện",
        ])

        for device in devices:
            writer.writerow([
                device.ip,
                device.mac,
                device.vendor,
                device.name,
                device.note,
                "Có" if device.trusted else "Không",
                "Có" if device.online else "Không",
                "Có" if device.randomized_mac else "Không",
                "Có" if device.is_self else "Không",
                device.first_seen.isoformat(sep=" ", timespec="seconds"),
                device.last_seen.isoformat(sep=" ", timespec="seconds"),
            ])


def export_pings(pings: list[PingResult], path: str) -> None:
    """Xuất kết quả đo Ping ra CSV."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)

        writer.writerow([
            "Mốc kiểm tra",
            "RTT (ms)",
            "Mất gói (%)",
            "Thời điểm",
        ])

        for ping in pings:
            writer.writerow([
                ping.target,
                "" if ping.rtt_ms is None else ping.rtt_ms,
                ping.loss_pct,
                ping.ts.isoformat(sep=" ", timespec="seconds"),
            ])
