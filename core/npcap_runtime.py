"""Kiểm tra Npcap đã cài trên Windows; không đóng gói DLL của driver."""
import ctypes
import os
from pathlib import Path


def npcap_available() -> bool:
    folder = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32" / "Npcap"
    library = folder / "wpcap.dll"
    if not library.is_file():
        return False
    try:
        with os.add_dll_directory(str(folder)):
            pcap = ctypes.WinDLL(str(library), use_last_error=True)
            pcap.pcap_lib_version.argtypes = []
            pcap.pcap_lib_version.restype = ctypes.c_char_p
            return b"npcap" in (pcap.pcap_lib_version() or b"").lower()
    except (AttributeError, OSError):
        return False
