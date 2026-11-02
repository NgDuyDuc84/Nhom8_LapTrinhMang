
from tests.simulate.simulate_network import (
    SimulatedDevice,
    detect_ip_conflicts,
    detect_new_devices,
    detect_disconnected_devices,
)


def test_ip_conflict():
    devices = [
        SimulatedDevice("192.168.1.10", "AA:BB:CC:00:00:01", "Laptop"),
        SimulatedDevice("192.168.1.10", "AA:BB:CC:00:00:02", "Phone"),
    ]

    result = detect_ip_conflicts(devices)

    assert "192.168.1.10" in result
    assert len(result["192.168.1.10"]) == 2


def test_no_ip_conflict():
    devices = [
        SimulatedDevice("192.168.1.10", "AA:BB:CC:00:00:01", "Laptop"),
        SimulatedDevice("192.168.1.20", "AA:BB:CC:00:00:02", "Phone"),
    ]

    assert detect_ip_conflicts(devices) == {}


def test_new_device():
    before = [
        SimulatedDevice("192.168.1.10", "AA:BB:CC:00:00:01", "Laptop"),
    ]

    after = before + [
        SimulatedDevice("192.168.1.20", "AA:BB:CC:00:00:02", "Phone"),
    ]

    result = detect_new_devices(before, after)

    assert len(result) == 1
    assert result[0].hostname == "Phone"


def test_disconnected_device():
    before = [
        SimulatedDevice("192.168.1.10", "AA:BB:CC:00:00:01", "Laptop"),
        SimulatedDevice("192.168.1.20", "AA:BB:CC:00:00:02", "Phone"),
    ]

    after = [
        SimulatedDevice("192.168.1.10", "AA:BB:CC:00:00:01", "Laptop"),
    ]

    result = detect_disconnected_devices(before, after)

    assert len(result) == 1
    assert result[0].hostname == "Phone"
