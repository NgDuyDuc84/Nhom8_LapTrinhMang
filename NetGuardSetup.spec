# -*- mode: python ; coding: utf-8 -*-
import hashlib
import json
from pathlib import Path

root = Path(SPECPATH)
payload = root / "output" / "NetGuardFull.exe"
if not payload.is_file():
    raise RuntimeError("Build NetGuardFull.spec trước khi build bộ cài.")
with payload.open("rb") as stream:
    payload_hash = hashlib.file_digest(stream, "sha256").hexdigest()
manifest = root / "tmp" / "setup-payload" / "manifest.json"
manifest.parent.mkdir(parents=True, exist_ok=True)
manifest.write_text(json.dumps({"sha256": payload_hash}), encoding="utf-8")

a = Analysis(
    [str(root / "setup_main.py")], pathex=[str(root)], binaries=[],
    datas=[(str(payload), "payload"), (str(manifest), "payload"),
           (str(root / "assets" / "netguard.svg"), "assets")],
    hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "tkinter", "matplotlib", "scipy", "pandas", "IPython"],
    noarchive=False,
)
a.binaries = [entry for entry in a.binaries
              if not Path(entry[0]).name.lower().startswith("icu")
              and Path(entry[0]).name.lower() not in {"wpcap.dll", "packet.dll", "npcap.sys"}]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="NetGuardSetup",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, icon=str(root / "assets" / "netguard.ico"))
