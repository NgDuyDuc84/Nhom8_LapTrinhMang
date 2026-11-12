"""Cấu hình JSON đã kiểm tra; không chứa token gửi tin."""
import ipaddress
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "data" / "settings.json"
DEFAULTS = {"scan_interval": 30, "ping_interval": 2, "ping_timeout": 1,
            "external_target": "1.1.1.1", "retention_days": 30,
            "scan_cidr": "", "interface_name": "", "network_label": "",
            "loss_bad_pct": 5, "router_rtt_ms": 50, "external_rtt_ms": 250}


def validate(values):
    result = {**DEFAULTS, **values}
    if set(result) != set(DEFAULTS):
        raise ValueError("Cấu hình có khóa không được hỗ trợ.")
    for key, lo, hi in (("scan_interval", 5, 3600), ("ping_interval", .2, 300),
                        ("ping_timeout", .1, 10), ("retention_days", 1, 3650),
                        ("loss_bad_pct", 0, 100), ("router_rtt_ms", 1, 1000),
                        ("external_rtt_ms", 1, 5000)):
        if isinstance(result[key], bool) or not isinstance(result[key], (int, float)) or not lo <= result[key] <= hi:
            raise ValueError(f"{key} phải nằm trong {lo}–{hi}.")
    ipaddress.IPv4Address(result["external_target"])
    if not isinstance(result["retention_days"], int):
        raise ValueError("Số ngày giữ lịch sử phải là số nguyên.")
    if result["scan_cidr"]:
        net = ipaddress.IPv4Network(result["scan_cidr"], strict=False)
        if net.num_addresses > 1024:
            raise ValueError("Dải quét tùy chọn tối đa 1.024 địa chỉ.")
    for key in ("interface_name", "network_label", "scan_cidr"):
        if not isinstance(result[key], str) or len(result[key]) > 200:
            raise ValueError(f"{key} không hợp lệ.")
    return result


def load():
    if not PATH.exists():
        return dict(DEFAULTS)
    return validate(json.loads(PATH.read_text(encoding="utf-8")))


def save(values):
    values = validate(values)
    PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, PATH)
