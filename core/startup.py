"""Khởi động GUI bằng Python của dự án và xin quyền Windows khi cần.

Chỉ dùng thư viện chuẩn để vẫn báo được lỗi khi chưa nạp được Qt.
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import subprocess
import sys
import traceback
from datetime import datetime

from core.interfaces import is_admin

APP_ROOT = Path(__file__).resolve().parent.parent
RELAUNCH_ARGUMENT = "--gui-relaunched"
ERROR_CANCELLED = 1223


def _gui_python() -> Path:
    """Ưu tiên .venv; pythonw giúp launcher không giữ cửa sổ terminal."""
    project_python = APP_ROOT / ".venv" / "Scripts" / "pythonw.exe"
    if project_python.is_file():
        return project_python
    current = Path(sys.executable).resolve()
    windowed = current.with_name("pythonw.exe")
    return windowed if windowed.is_file() else current


def _start_windows_gui(interpreter: Path, *, elevate: bool, history: bool = False) -> None:
    """Mở tiến trình mới; hủy UAC là thoát bình thường, không tự xin lại."""
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    execute = shell32.ShellExecuteW
    execute.argtypes = [
        ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
        ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int,
    ]
    execute.restype = ctypes.c_void_p
    arguments = subprocess.list2cmdline([
        str(APP_ROOT / "main.py"), RELAUNCH_ARGUMENT, *(["--history"] if history else []),
    ])
    ctypes.set_last_error(0)
    result = execute(
        None, "runas" if elevate else "open", str(interpreter),
        arguments, str(APP_ROOT), 1,
    )
    if (result or 0) > 32:
        return
    error = ctypes.get_last_error()
    if error == ERROR_CANCELLED:
        return
    raise OSError(
        error or result or 1,
        "Windows không mở được NetGuard. Hãy kiểm tra môi trường .venv "
        "và quyền chạy ứng dụng.",
    )


def prepare_gui_launch(*, relaunched: bool = False, history: bool = False) -> bool:
    """True: chạy GUI tại đây; False: đã chuyển tiến trình hoặc người dùng hủy.

    Cố định thư mục làm việc để cùng một launcher luôn dùng đúng dữ liệu dự án.
    Tham số nội bộ ngăn lặp yêu cầu quyền nếu Windows không mở đúng môi trường.
    """
    os.chdir(APP_ROOT)
    if sys.platform != "win32":
        return True
    interpreter = _gui_python()
    needs_elevation = not history and not is_admin()
    needs_project_python = Path(sys.executable).resolve().parent != interpreter.resolve().parent
    if not needs_elevation and not needs_project_python:
        return True
    if relaunched:
        raise RuntimeError(
            "NetGuard chưa nhận được quyền Administrator hoặc môi trường Python "
            "cần thiết sau khi mở lại. Hãy chạy Mo_NetGuard.cmd và chấp nhận "
            "hộp thoại cấp quyền của Windows."
        )
    if history:
        _start_windows_gui(interpreter, elevate=False, history=True)
    else:
        _start_windows_gui(interpreter, elevate=needs_elevation)
    return False


def show_startup_error(exc: Exception) -> None:
    """Báo lỗi bằng hộp thoại Windows kể cả khi Python chạy không có console."""
    message = f"Không thể mở NetGuard.\n\n{exc}"
    if isinstance(exc, ModuleNotFoundError):
        message += (
            "\n\nMôi trường Python đang thiếu thư viện. "
            "Hãy cài các thư viện trong requirements.txt theo README.md."
        )
    try:
        log_path = APP_ROOT / "logs" / "startup.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"\n[{datetime.now().isoformat(timespec='seconds')}]\n")
            traceback.print_exception(exc, file=stream)
        message += f"\n\nChi tiết lỗi được lưu tại:\n{log_path}"
    except OSError:
        pass
    if sys.platform == "win32":
        try:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            show = user32.MessageBoxW
            show.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
            show.restype = ctypes.c_int
            show(None, message, "NetGuard - Lỗi khởi động", 0x10)
            return
        except (AttributeError, OSError):
            pass
    if sys.stderr is not None:
        print(message, file=sys.stderr)
