"""Đường cơ sở (baseline): chốt danh sách thiết bị quen thuộc của mạng nhà.

Trước khi chốt (lần chạy đầu), mọi thiết bị tìm thấy đều được lưu với
``trusted = False`` và **không sinh cảnh báo**, tránh bão cảnh báo ngay khi mở app.
Sau khi ``finish_baseline()``, thiết bị **mới** chưa tin cậy xuất hiện sẽ bị cảnh báo.
Trạng thái được lưu trong bảng ``Meta`` nên tắt/mở lại app vẫn nhớ.

Không import Qt.
"""

from __future__ import annotations

from db import repository
from models import now

BASELINE_KEY = "baseline_done"
BASELINE_AT_KEY = "baseline_at"

__all__ = ["is_first_run", "finish_baseline", "reset_baseline", "baseline_at"]


def is_first_run() -> bool:
    """True nếu chưa hoàn tất lập đường cơ sở."""
    return repository.get_meta(BASELINE_KEY) != "1"


def finish_baseline() -> None:
    """Chốt đường cơ sở. Gọi nhiều lần chỉ có tác dụng lần đầu."""
    if not is_first_run():
        return
    repository.set_meta(BASELINE_KEY, "1")
    repository.set_meta(BASELINE_AT_KEY, now().replace(microsecond=0).isoformat())


def baseline_at():
    """Thời điểm chốt đường cơ sở (``datetime``), ``None`` nếu chưa chốt."""
    from datetime import datetime

    value = repository.get_meta(BASELINE_AT_KEY)
    return datetime.fromisoformat(value) if value else None


def reset_baseline() -> None:
    """Xoá cờ đường cơ sở (dùng khi muốn lập lại từ đầu, ví dụ khi chuyển nhà/mạng mới)."""
    repository.set_meta(BASELINE_KEY, "0")
    repository.set_meta(BASELINE_AT_KEY, "")
