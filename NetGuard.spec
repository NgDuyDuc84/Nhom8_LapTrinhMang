# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH)

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / "assets"), "assets"),
           (str(root / "data" / "oui.csv"), "data")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "tkinter", "matplotlib", "scipy",
              "pandas", "IPython", "jupyter", "OpenGL", "scapy.all", "scapy.arch",
              "scapy.sendrecv", "scapy.supersocket"],
    noarchive=False,
)
# Qt 6.12 dùng ICU có sẵn của Windows 10/11. ICU từ công cụ khác trên PATH
# có symbol gắn phiên bản và sẽ làm Qt không nạp được nếu bị đóng gói theo.
a.binaries = [entry for entry in a.binaries
              if not Path(entry[0]).name.lower().startswith("icu")
              and Path(entry[0]).name.lower() not in {"wpcap.dll", "packet.dll", "npcap.sys"}]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="NetGuard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(root / "assets" / "netguard.ico"),
)
