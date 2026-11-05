
"""Quét kênh Wi-Fi và gợi ý kênh ít nhiễu trên Windows."""

from __future__ import annotations

import re
import subprocess


def _get_band(channel: int) -> str:
    """Xác định băng tần dựa trên số kênh."""
    if 1 <= channel <= 14:
        return "2.4GHz"
    if channel > 14:
        return "5GHz"
    return "Unknown"


def _signal_to_rssi(signal_percent: int) -> int:
    """Ước lượng RSSI (dBm) từ phần trăm tín hiệu của Windows."""
    return round(signal_percent / 2 - 100)


def scan_wifi() -> list[dict]:
    """Quét Wi-Fi bằng netsh, trả danh sách các điểm truy cập."""
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0:
        return []

    # netsh có thể xuất thông tin bằng bảng mã Windows.
    # Nếu thấy ký tự lỗi, chạy lại bằng bảng mã mặc định.
    output = result.stdout

    if "\ufffd" in output:
        try:
            retry = subprocess.run(
                ["netsh", "wlan", "show", "networks", "mode=bssid"],
                capture_output=True,
                timeout=15,
                check=False,
            )
            if retry.returncode == 0:
                output = retry.stdout.decode(
                    "mbcs", errors="replace"
                )
        except (OSError, subprocess.TimeoutExpired):
            pass

    networks = []
    current_ssid = ""
    current_bssid = None
    current_signal = None
    current_channel = None
    current_band = None

    def save_network():
        if current_bssid is None or current_channel is None:
            return

        networks.append({
            "ssid": current_ssid,
            "bssid": current_bssid,
            "channel": current_channel,
            "rssi": (
                _signal_to_rssi(current_signal)
                if current_signal is not None
                else None
            ),
            "band": current_band or _get_band(current_channel),
        })

    for line in output.splitlines():
        line = line.strip()

        # SSID 1 : Ten Wi-Fi
        ssid_match = re.match(
            r"^SSID\s+\d+\s*:\s*(.*)$",
            line,
            re.IGNORECASE,
        )
        if ssid_match:
            save_network()
            current_ssid = ssid_match.group(1).strip()
            current_bssid = None
            current_signal = None
            current_channel = None
            current_band = None
            continue

        # BSSID 1 : aa:bb:cc:dd:ee:ff
        bssid_match = re.match(
            r"^BSSID\s+\d+\s*:\s*"
            r"([0-9a-fA-F:]{17})",
            line,
            re.IGNORECASE,
        )
        if bssid_match:
            save_network()
            current_bssid = bssid_match.group(1).lower()
            current_signal = None
            current_channel = None
            current_band = None
            continue

        band_match = re.match(r"^(?:Band|Băng tần)\s*:\s*(2\.4|5|6)\s*GHz", line, re.IGNORECASE)
        if band_match and current_bssid:
            current_band = f"{band_match.group(1)}GHz"
            continue

        # Signal : 80% hoặc Tín hiệu : 80%
        signal_match = re.match(
            r"^(?:Signal|Tín hiệu)\s*:\s*(\d+)%",
            line,
            re.IGNORECASE,
        )
        if signal_match and current_bssid:
            current_signal = int(signal_match.group(1))
            continue

        # Channel : 6 hoặc Kênh : 6
        channel_match = re.match(
            r"^(?:Channel|Kênh)\s*:\s*(\d+)",
            line,
            re.IGNORECASE,
        )
        if channel_match and current_bssid:
            current_channel = int(channel_match.group(1))

    save_network()
    return networks


def recommend_channel(networks: list[dict]) -> int | None:
    """Gợi ý kênh 1, 6 hoặc 11 ít bị ảnh hưởng nhất ở 2.4 GHz."""
    candidates = [1, 6, 11]
    scores = {channel: 0.0 for channel in candidates}
    measured = False

    for network in networks:
        try:
            channel = int(network["channel"])
        except (KeyError, ValueError, TypeError):
            continue

        if not 1 <= channel <= 14:
            continue
        if network.get("band", "2.4GHz") != "2.4GHz":
            continue
        measured = True

        rssi = network.get("rssi")

        # Tín hiệu mạnh có khả năng gây nhiễu nhiều hơn.
        if isinstance(rssi, (int, float)):
            strength = max(
                0.1,
                min(1.0, (rssi + 100) / 70),
            )
        else:
            strength = 0.5

        for candidate in candidates:
            distance = abs(candidate - channel)

            # Các kênh 2.4 GHz gần nhau có thể chồng lấn.
            if distance < 5:
                overlap = (5 - distance) / 5
                scores[candidate] += strength * overlap

    return min(candidates, key=lambda ch: scores[ch]) if measured else None


if __name__ == "__main__":
    networks = scan_wifi()

    print("=== DANH SACH WI-FI ===")

    if not networks:
        print("Khong tim thay Wi-Fi hoac khong the quet.")
    else:
        for network in networks:
            print(
                f"SSID: {network['ssid']} | "
                f"BSSID: {network['bssid']} | "
                f"Kenh: {network['channel']} | "
                f"RSSI: {network['rssi']} dBm | "
                f"Bang tan: {network['band']}"
            )

    print()
    channel = recommend_channel(networks)
    if channel is None:
        print("Chua du du lieu Wi-Fi 2.4 GHz de de xuat kenh. Bat Wi-Fi va thu quet lai.")
    else:
        print("Kenh 2.4 GHz de xuat (uoc luong):", channel)
