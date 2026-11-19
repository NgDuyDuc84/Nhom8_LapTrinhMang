"""Cài bản Full theo người dùng; Npcap tải trực tiếp, không nhúng/phân phối lại."""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from urllib.parse import urlparse

from core.npcap_runtime import npcap_available

NPCAP_URL = "https://npcap.com/dist/npcap-1.90.exe"
NPCAP_SHA256 = "682b57e1c05ef375931975c9d6ded40888f4bfdf9f4b11571e654f962f1199b6"
MAX_DOWNLOAD = 20 * 1024 * 1024


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def default_target() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Programs" / "NetGuardFull"


@contextmanager
def system_dll_search():
    """Tiến trình bên ngoài dùng DLL hệ thống, không thừa kế đường tìm DLL của Qt."""
    frozen = getattr(sys, "frozen", False) and sys.platform == "win32"
    if frozen:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.restype = ctypes.c_int
        kernel.SetDllDirectoryW(None)
    try:
        yield
    finally:
        if frozen:
            kernel.SetDllDirectoryW(str(sys._MEIPASS))


def powershell(script: str, *, variables=None, timeout=60):
    executable = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    env = {**os.environ, **(variables or {})}
    # PowerShell 7 của môi trường phát triển có thể truyền module .NET mới vào
    # Windows PowerShell 5.1. Chỉ dùng module hệ thống cho các lệnh Windows này.
    env["PSModulePath"] = str(executable.parent / "Modules")
    with system_dll_search():
        result = subprocess.run([str(executable), "-NoProfile", "-NonInteractive", "-Command", script],
                                env=env, capture_output=True, text=True, errors="replace",
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Windows không thực hiện được tác vụ cài đặt.")
    return result.stdout.strip()


def verify_npcap(path: Path):
    if digest(path) != NPCAP_SHA256:
        raise RuntimeError("Bộ cài Npcap tải về không khớp SHA256 đã xác minh. Chưa chạy file tải về.")
    script = """$ErrorActionPreference='Stop'
$s=Get-AuthenticodeSignature -LiteralPath $env:NETGUARD_NPCAP_FILE
if ($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch 'CN=Nmap Software LLC(?:,|$)') {
    throw 'Chu ky bo cai Npcap khong hop le.'
}
"""
    powershell(script, variables={"NETGUARD_NPCAP_FILE": str(path)})


def download_npcap(destination: Path, progress=lambda text: None):
    request = urllib.request.Request(NPCAP_URL, headers={"User-Agent": "NetGuardSetup/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response, destination.open("wb") as output:
        url = urlparse(response.geturl())
        if url.scheme != "https" or url.hostname != "npcap.com":
            raise RuntimeError("Địa chỉ tải Npcap không thuộc trang chính thức.")
        total = 0
        while chunk := response.read(64 * 1024):
            total += len(chunk)
            if total > MAX_DOWNLOAD:
                raise RuntimeError("Kích thước bộ cài Npcap không hợp lệ.")
            output.write(chunk)
            progress(f"Đang tải Npcap: {total // 1024:,} KB…")


def run_npcap(path: Path) -> int:
    # /S chỉ có trên OEM; người dùng xác nhận giấy phép trong wizard chính thức.
    # Không thay WinPcap hiện có hoặc kết thúc ứng dụng đang dùng Npcap.
    # ShellExecute/RunAs mở UAC cho bộ cài driver từ tiến trình không nâng quyền.
    # CreateProcess/Popen trực tiếp sẽ lỗi WinError 740 trên máy chưa cài Npcap.
    script = """$ErrorActionPreference='Stop'
try {
    $p=Start-Process -FilePath $env:NETGUARD_NPCAP_FILE -ArgumentList '/winpcap_mode=no','/no_kill=yes' -Verb RunAs -Wait -PassThru -WindowStyle Normal
    $p.Refresh()
    Write-Output ([int]$p.ExitCode)
} catch {
    if ($_.Exception.NativeErrorCode -eq 1223 -or $_.Exception.InnerException.NativeErrorCode -eq 1223) {
        Write-Output 1
    } else { throw }
}
"""
    return int(powershell(script, variables={"NETGUARD_NPCAP_FILE": str(path)}, timeout=None))


def create_shortcuts(target: Path):
    script = """$ErrorActionPreference='Stop'
$ws=New-Object -ComObject WScript.Shell
$desktop=[Environment]::GetFolderPath('Desktop')
$menu=Join-Path ([Environment]::GetFolderPath('Programs')) 'NetGuard Full'
New-Item -ItemType Directory -Path $menu -Force | Out-Null
foreach ($folder in @($desktop,$menu)) {
    $s=$ws.CreateShortcut((Join-Path $folder 'NetGuard Full.lnk'))
    $s.TargetPath=$env:NETGUARD_FULL_EXE
    $s.WorkingDirectory=$env:NETGUARD_FULL_FOLDER
    $s.Description='NetGuard Full - Giam sat mang LAN'
    $s.Save()
}
$h=$ws.CreateShortcut((Join-Path $menu 'Xem lich su.lnk'))
$h.TargetPath=$env:NETGUARD_FULL_EXE
$h.Arguments='--history'
$h.WorkingDirectory=$env:NETGUARD_FULL_FOLDER
$h.Save()
"""
    powershell(script, variables={"NETGUARD_FULL_EXE": str(target / "NetGuardFull.exe"),
                                 "NETGUARD_FULL_FOLDER": str(target)})


@dataclass(frozen=True)
class InstallResult:
    executable: Path
    reboot_required: bool = False
    shortcut_error: str = ""


def install(payload: Path, target: Path, expected_hash: str, progress=lambda text: None,
            *, check_npcap=None, downloader=None, verifier=None, runner=None, shortcuts=None):
    check = check_npcap or npcap_available
    downloader = downloader or download_npcap
    verifier = verifier or verify_npcap
    runner = runner or run_npcap
    shortcuts = shortcuts or create_shortcuts
    if not payload.is_file() or digest(payload) != expected_hash:
        raise RuntimeError("File NetGuard Full trong bộ cài bị thiếu hoặc hỏng.")
    target = target.expanduser().resolve()
    if target == payload.resolve().parent:
        raise ValueError("Chọn thư mục cài đặt khác thư mục giải nén bộ cài.")
    reboot = False
    progress("Đang kiểm tra Npcap…")
    if not check():
        with tempfile.TemporaryDirectory(prefix="netguard-npcap-") as temporary:
            installer = Path(temporary) / "npcap-1.90.exe"
            downloader(installer, progress)
            progress("Đang xác minh bộ cài Npcap…")
            verifier(installer)
            progress("Hãy hoàn tất trình cài Npcap và chấp nhận hộp thoại quyền của Windows nếu xuất hiện.")
            code = runner(installer)
            if code == 1:
                raise RuntimeError("Bạn đã hủy cài Npcap. NetGuard Full chưa được cài.")
            if code not in (0, 3010):
                raise RuntimeError(f"Npcap chưa cài thành công (mã {code}). NetGuard Full chưa được cài.")
            reboot = code == 3010
            if not reboot and not check():
                raise RuntimeError("Chưa nạp được Npcap sau khi cài. Hãy khởi động lại Windows rồi chạy lại bộ cài.")
    progress("Đang cài NetGuard Full…")
    target.mkdir(parents=True, exist_ok=True)
    executable = target / "NetGuardFull.exe"
    # Chỉ thay file chương trình sau khi đã chép đủ; không chạm data/ hoặc logs/.
    with tempfile.NamedTemporaryFile(prefix=".netguard-", suffix=".tmp", dir=target, delete=False) as stream:
        staged = Path(stream.name)
    try:
        shutil.copyfile(payload, staged)
        if digest(staged) != expected_hash:
            raise RuntimeError("Không xác minh được file chương trình sau khi chép.")
        os.replace(staged, executable)
    except PermissionError as exc:
        raise RuntimeError("Hãy đóng NetGuard Full đang chạy rồi thử cài lại.") from exc
    finally:
        staged.unlink(missing_ok=True)
    shortcut_error = ""
    try:
        shortcuts(target)
    except Exception as exc:
        shortcut_error = str(exc)
    return InstallResult(executable, reboot, shortcut_error)


def bundled_payload() -> tuple[Path, str]:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    manifest = json.loads((root / "payload" / "manifest.json").read_text(encoding="utf-8"))
    return root / "payload" / "NetGuardFull.exe", manifest["sha256"]


def launch_app(executable: Path):
    # App mới tồn tại độc lập với bộ cài onefile đang thoát.
    env = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    with system_dll_search():
        subprocess.Popen([str(executable)], cwd=executable.parent, env=env)
