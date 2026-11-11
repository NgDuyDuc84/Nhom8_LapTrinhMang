"""Tra hãng giao diện mạng ngoại tuyến bằng dữ liệu đóng gói trong Scapy."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
import re

OUI_FILE = Path(__file__).resolve().parent.parent / "data" / "oui.csv"


def normalize_mac(mac: str) -> str:
    if not isinstance(mac, str):
        return ""
    text = mac.strip().replace("-", ":")
    if not re.fullmatch(r"[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}", text):
        return ""
    return text.lower()


def _prefix_key(text: str) -> tuple[int, int] | None:
    if not isinstance(text, str):
        return None
    prefix, separator, mask = text.strip().partition("/")
    if separator and not mask.isdigit():
        return None
    compact = prefix.replace(":", "").replace("-", "")
    bits = int(mask) if mask.isdigit() else len(compact) * 4
    if bits not in (24, 28, 36) or not re.fullmatch(r"[0-9a-fA-F]+", compact):
        return None
    if len(compact) * 4 < bits:
        return None
    return bits, int(compact, 16) >> (len(compact) * 4 - bits)


@lru_cache(maxsize=1)
def _registry() -> dict[tuple[int, int], str]:
    from scapy.data import MANUFDB

    result = {}
    for prefix in MANUFDB.keys():
        _, vendor = MANUFDB[prefix]
        key = _prefix_key(prefix)
        if key and vendor:
            result[key] = vendor.strip()
    try:
        with OUI_FILE.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                key = _prefix_key(row.get("prefix", ""))
                vendor = (row.get("vendor") or "").strip()
                if key and vendor:
                    result[key] = vendor
    except (OSError, csv.Error):
        pass
    return result


def lookup(mac: str) -> str:
    """Ưu tiên prefix MA-S/M/L; không tra OUI cho MAC cục bộ hoặc multicast."""
    normalized = normalize_mac(mac)
    if not normalized or int(normalized[:2], 16) & 0x03 or normalized == "00:00:00:00:00:00":
        return "Unknown"
    return _lookup_normalized(normalized)


@lru_cache(maxsize=4096)
def _lookup_normalized(normalized: str) -> str:
    address = int(normalized.replace(":", ""), 16)
    registry = _registry()
    for bits in (36, 28, 24):
        vendor = registry.get((bits, address >> (48 - bits)))
        if vendor:
            return vendor
    return "Unknown"
