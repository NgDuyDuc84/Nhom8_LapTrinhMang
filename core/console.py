"""Tiện ích console dùng chung.

Windows mặc định dùng bảng mã cp1252/cp437 nên ``print`` chữ tiếng Việt sẽ ném
``UnicodeEncodeError``. Gọi ``setup_console_encoding()`` một lần ở đầu chương trình
(hoặc trong khối ``if __name__ == "__main__":``) là in được bình thường.
"""

from __future__ import annotations

import sys


def setup_console_encoding() -> None:
    """Ép console Windows dùng UTF-8 để in được tiếng Việt.

    Đặt codepage console về 65001 và đổi ``stdout``/``stderr`` sang UTF-8. Nếu không
    làm được (chạy nền, output bị chuyển hướng, IDE...) thì bỏ qua, không báo lỗi.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:  # không có console thật - bỏ qua
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
