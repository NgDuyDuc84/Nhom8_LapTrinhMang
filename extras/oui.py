
"""Tra cứu hãng sản xuất từ địa chỉ MAC."""

import csv
import re
from pathlib import Path


OUI_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "oui.csv"
)


def lookup(mac: str) -> str:
    """Tra cứu hãng sản xuất dựa trên 3 byte đầu của MAC."""

    if not isinstance(mac, str):
        return "Unknown"

    # Chuẩn hóa địa chỉ MAC
    mac = mac.strip().replace("-", ":").upper()

    # Kiểm tra định dạng MAC
    if not re.fullmatch(
        r"[0-9A-F]{2}(:[0-9A-F]{2}){5}", mac
    ):
        return "Unknown"

    # Lấy 3 byte đầu (OUI)
    prefix = ":".join(mac.split(":")[:3])

    try:
        with open(
            OUI_FILE,
            mode="r",
            encoding="utf-8-sig",
            newline=""
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:
                csv_prefix = (
                    row["prefix"]
                    .strip()
                    .replace("-", ":")
                    .upper()
                )

                if prefix == csv_prefix:
                    return row["vendor"].strip()

    except (OSError, KeyError, AttributeError, csv.Error):
        return "Unknown"

    return "Unknown"


if __name__ == "__main__":
    test_macs = [
        "28:77:77:db:b5:6c",
        "ac:74:b1:41:a5:d2",
        "00:00:00:00:00:00"
    ]

    for mac in test_macs:
        print(f"{mac} -> {lookup(mac)}")
