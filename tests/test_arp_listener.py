import time

import pytest
import scapy.all as scapy

from core.arp_listener import ArpListener
from tests.test_arp_scanner import capture, iface


def wait_for(condition, timeout=3):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(.01)
    raise AssertionError("Listener không phục hồi trong thời hạn")


def test_initial_background_capture_failure_is_reported_and_retried(capture, iface):
    states = []
    capture.mode = "open_error"
    listener = ArpListener(lambda observation: None, iface, states.append)
    try:
        with pytest.raises(RuntimeError, match="Không mở được"):
            listener.start()
        assert not listener.is_running()
        assert any(s["error"] for s in states)
        capture.mode = "healthy"
        wait_for(listener.is_running)
        assert len(capture.instances) >= 2
        assert states[-1]["running"]
    finally:
        listener.stop()
    assert not listener.is_running()
    assert all(not i.thread.is_alive() for i in capture.instances)


def test_listener_detects_runtime_capture_death_and_recovers(capture, iface):
    states = []
    capture.mode = "read_error"
    listener = ArpListener(lambda observation: None, iface, states.append)
    try:
        listener.start()
        old = capture.instances[-1]
        capture.drop.set()
        old.thread.join(1)
        wait_for(lambda: any(not state["running"] for state in states))
        capture.drop.clear()
        capture.mode = "healthy"
        wait_for(lambda: len(capture.instances) >= 2 and listener.is_running())
    finally:
        listener.stop()


def test_listener_filters_spoofed_shape_and_out_of_subnet_frames(iface):
    observations = []
    listener = ArpListener(observations.append, iface)
    valid = scapy.Ether(src="00:11:22:33:44:66") / scapy.ARP(op=2, psrc="192.168.1.20", hwsrc="00:11:22:33:44:66")
    listener._handle_packet(valid)
    listener._handle_packet(scapy.Ether(src="00:11:22:33:44:77") / valid[scapy.ARP])
    listener._handle_packet(scapy.ARP(op=2, psrc="10.0.0.20", hwsrc="00:11:22:33:44:66"))
    listener._handle_packet(scapy.ARP(op=2, psrc="192.168.1.20", hwsrc="01:11:22:33:44:66"))
    assert [(o.ip, o.mac) for o in observations] == [("192.168.1.20", "00:11:22:33:44:66")]
