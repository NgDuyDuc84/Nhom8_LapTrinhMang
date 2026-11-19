"""Điểm vào bản Full: dùng bộ bắt gói Npcap cho cả quét và nghe ARP."""
import sys

from core import network_mode

network_mode.PACKET_CAPTURE = True

from main import main


if __name__ == "__main__":
    sys.exit(main())
