
"""Mo phong cac tinh huong mang cho NetGuard.

Chi tao du lieu gia lap, khong gui goi tin mang.
"""

from dataclasses import dataclass


@dataclass
class SimulatedDevice:
    ip: str
    mac: str
    hostname: str
    online: bool = True


def detect_ip_conflicts(devices):
    """Tim IP duoc su dung boi nhieu MAC khac nhau."""
    ip_to_macs = {}

    for device in devices:
        if not device.online:
            continue

        ip_to_macs.setdefault(device.ip, set()).add(
            device.mac.lower()
        )

    return {
        ip: sorted(macs)
        for ip, macs in ip_to_macs.items()
        if len(macs) > 1
    }


def detect_new_devices(previous, current):
    """Tim thiet bi moi dua tren dia chi MAC."""
    old_macs = {
        device.mac.lower()
        for device in previous
        if device.online
    }

    return [
        device
        for device in current
        if device.online
        and device.mac.lower() not in old_macs
    ]


def detect_disconnected_devices(previous, current):
    """Tim thiet bi da mat ket noi."""
    current_macs = {
        device.mac.lower()
        for device in current
        if device.online
    }

    return [
        device
        for device in previous
        if device.online
        and device.mac.lower() not in current_macs
    ]


def run_simulation():
    print("=== NETGUARD - MO PHONG MANG ===")

    before = [
        SimulatedDevice(
            "192.168.1.1", "AA:BB:CC:00:00:01", "Router"
        ),
        SimulatedDevice(
            "192.168.1.10", "AA:BB:CC:00:00:10", "Laptop"
        ),
        SimulatedDevice(
            "192.168.1.20", "AA:BB:CC:00:00:20", "Phone"
        ),
    ]

    after = [
        SimulatedDevice(
            "192.168.1.1", "AA:BB:CC:00:00:01", "Router"
        ),
        SimulatedDevice(
            "192.168.1.10", "AA:BB:CC:00:00:10", "Laptop"
        ),
        SimulatedDevice(
            "192.168.1.10", "AA:BB:CC:00:00:30", "Unknown"
        ),
        SimulatedDevice(
            "192.168.1.40", "AA:BB:CC:00:00:40", "Tablet"
        ),
    ]

    print("\n[1] KIEM TRA TRUNG IP")
    conflicts = detect_ip_conflicts(after)

    if conflicts:
        for ip, macs in conflicts.items():
            print(f"CANH BAO: IP {ip} co nhieu MAC: {macs}")
    else:
        print("Khong phat hien trung IP")

    print("\n[2] KIEM TRA THIET BI MOI")
    for device in detect_new_devices(before, after):
        print(f"THIET BI MOI: {device.hostname} - {device.ip}")

    print("\n[3] KIEM TRA MAT KET NOI")
    for device in detect_disconnected_devices(before, after):
        print(f"MAT KET NOI: {device.hostname} - {device.ip}")

    print("\n=== HOAN THANH MO PHONG ===")


if __name__ == "__main__":
    run_simulation()
