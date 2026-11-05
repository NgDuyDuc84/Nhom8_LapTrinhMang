"""Điểm vào của NetGuard.

Cách dùng (chạy từ gốc repo, terminal Administrator khi cần gói tin thô):

    python main.py                 # mở giao diện, dữ liệu thật (giai đoạn 8)
    python main.py --cli scan      # quét ARP, in bảng IP/MAC (giai đoạn 3)
    python main.py --cli monitor    # theo dõi thiết bị, in cảnh báo (giai đoạn 5)
    python main.py --cli trace 1.1.1.1   # traceroute (giai đoạn 6)
    python main.py --cli diagnose   # ping ba mốc và in kết luận (giai đoạn 7)

Các chế độ CLI được triển khai trong core/services; GUI dùng BackendBase khi
ui.main_window của B đã có.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import time

from core.console import setup_console_encoding
from core.interfaces import check_environment, get_active_interface, get_warnings

CLI_COMMANDS = ("scan", "baseline", "monitor", "trace", "diagnose")


def build_parser() -> argparse.ArgumentParser:
    """Tạo bộ phân tích tham số dòng lệnh."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="NetGuard - giám sát và chẩn đoán mạng LAN bằng ARP và ICMP.",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="chạy ở chế độ dòng lệnh (không mở giao diện)",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=CLI_COMMANDS,
        help="chế độ dòng lệnh: scan | baseline | monitor | trace | diagnose (mặc định: monitor)",
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="địa chỉ đích cho chế độ trace (mặc định: 1.1.1.1)",
    )
    return parser


def run_scan() -> int:
    """Quét ARP toàn subnet của card đang dùng rồi in bảng IP/MAC (sắp xếp theo IP)."""
    from core.arp_scanner import scan_subnet

    for warning in get_warnings():
        print(f"Cảnh báo: {warning}")

    try:
        iface = get_active_interface()
        print(f"Đang quét {iface.name} ({iface.ip}/{iface.netmask}), chờ chút...")
        started = time.perf_counter()
        entries = scan_subnet(iface)
    except (RuntimeError, ValueError) as exc:
        print(f"LỖI: {exc}")
        return 1

    elapsed = time.perf_counter() - started
    print(f"Xong sau {elapsed:.1f} giây: {len(entries)} thiết bị trả lời ARP.\n")
    print(f"{'IP':<17}{'MAC':<20}GHI CHÚ")
    print("-" * 49)
    for entry in entries:
        note = "máy này" if entry.is_self else ""
        print(f"{entry.ip:<17}{entry.mac:<20}{note}")
    return 0


def run_baseline() -> int:
    """Chốt đường cơ sở: từ đây thiết bị mới chưa tin cậy xuất hiện sẽ bị cảnh báo."""
    from db import database, repository
    from services import baseline

    database.initialize()
    if not baseline.is_first_run():
        print("Đường cơ sở đã được chốt trước đó, lệnh này không thay đổi gì.")
        return 0

    devices = repository.list_devices()
    print(f"Đang có {len(devices)} thiết bị trong mạng nhà:")
    for device in devices:
        trust = "tin cậy" if device.trusted else "chưa tin cậy"
        print(f"  {device.ip:<16}{device.mac:<20}{device.vendor or 'Unknown':<14}{trust}")

    baseline.finish_baseline()
    print("\nĐã chốt đường cơ sở. Từ giờ thiết bị MỚI chưa tin cậy sẽ bị cảnh báo.")
    return 0


def run_monitor() -> int:
    """Chạy vòng quét định kỳ, in thiết bị mới, đổi online/offline và cảnh báo."""
    from config import SCAN_INTERVAL_SEC
    from core.arp_listener import ArpListener
    from db import database, repository
    from services import baseline
    from services.alerts import ArpAnomalyDetector
    from services.scan_loop import ScanLoop

    database.initialize()
    problems = check_environment(require_network=False)
    if problems:
        for problem in problems:
            print(f"LỖI môi trường: {problem}")
        database.close()
        return 1
    for warning in get_warnings():
        print(f"Cảnh báo: {warning}")

    try:
        iface = get_active_interface()
    except RuntimeError as exc:
        iface = None
        print(f"Đang chờ kết nối LAN: {exc}")

    label = f"{iface.name} ({iface.ip}/{iface.netmask})" if iface else "kết nối LAN (đang chờ)"
    print(f"\nTheo dõi {label}, quét mỗi {SCAN_INTERVAL_SEC:.0f} giây.")
    if baseline.is_first_run():
        print("Lần đầu chạy: đang lập đường cơ sở, CHƯA cảnh báo thiết bị lạ.")
        print("Khi đã thấy đủ thiết bị của mình, mở terminal khác chạy: python main.py --cli baseline")
    else:
        print("Đã có đường cơ sở: thiết bị MỚI chưa tin cậy sẽ bị cảnh báo.")
    print("Nhấn Ctrl+C để dừng.\n")

    def on_device(device, event: str) -> None:
        stamp = device.last_seen.strftime("%H:%M:%S")
        label = device.vendor or "Unknown"
        if device.is_self:
            label += " (máy này)"
        print(f"[{stamp}] {event.upper():<8}{device.ip:<16}{device.mac:<20}{label}")

    def on_alert(alert) -> None:
        print(f"[{alert.ts:%H:%M:%S}] CẢNH BÁO ({alert.level}): {alert.message}")

    detector = None
    listener = None

    def on_arp_observation(observation) -> None:
        if detector is None:
            return
        for alert in detector.observe(observation):
            on_alert(alert)

    def on_interface(chosen) -> None:
        nonlocal detector, listener
        if listener is not None:
            listener.stop()
            listener = None
        detector = None
        if chosen is None:
            print("Mất kết nối LAN; chờ kết nối lại ở chu kỳ quét sau.")
            return
        detector = ArpAnomalyDetector(chosen.gateway, repository.list_devices())
        listener = ArpListener(on_observation=on_arp_observation, iface=chosen)
        try:
            listener.start()
        except RuntimeError as exc:
            listener = None
            print(f"Lưu ý: không bật được nghe ARP: {exc}")
            return
        print("Đang nghe ARP thụ động để phát hiện IP/MAC bất thường.")

    loop = ScanLoop(on_device=on_device, on_alert=on_alert, iface=iface, on_interface=on_interface)
    try:
        loop.start()
        while loop.is_running():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nĐang dừng...")
    finally:
        loop.stop()
        if listener is not None:
            listener.stop()
        database.close()
    print("Đã dừng theo dõi.")
    return 0


def run_trace(target: str | None = None) -> int:
    """Chạy traceroute ICMP, in hop nhà mạng và các điểm tăng độ trễ."""
    from core.traceroute import find_isp_hop, trace

    target = target or "1.1.1.1"
    for warning in get_warnings():
        print(f"Cảnh báo: {warning}")

    try:
        iface = get_active_interface()
        print(f"Traceroute tới {target}, qua card {iface.name} ({iface.ip}), chờ phản hồi...")
        hops = trace(target)
    except (RuntimeError, ValueError) as exc:
        print(f"LỖI: {exc}")
        return 1

    isp_hop = find_isp_hop(hops, iface.gateway)
    print(f"\n{'TTL':<6}{'IP':<20}{'RTT (ms)':<14}GHI CHÚ")
    print("-" * 54)
    for hop in hops:
        rtt = "*" if hop.rtt_ms is None else f"{hop.rtt_ms:.2f}"
        notes: list[str] = []
        if isp_hop is hop:
            notes.append("hop nhà mạng đầu tiên sau gateway")
        if hop.flagged:
            notes.append("độ trễ bắt đầu tăng rõ")
        print(f"{hop.ttl:<6}{hop.ip or '*':<20}{rtt:<14}{'; '.join(notes)}")

    if isp_hop is None:
        print(f"\nKhông xác định được hop nhà mạng sau gateway {iface.gateway or '(không rõ)'}.")
    else:
        print(f"\nHop được chọn làm mốc nhà mạng: TTL {isp_hop.ttl}, IP {isp_hop.ip}.")
    return 0


def run_diagnose() -> int:
    """Ping ba mốc liên tục, in số liệu từng chu kỳ và kết luận khi ổn định."""
    from db import database
    from models import now
    from services.ping_monitor import PingMonitor

    problems = check_environment(require_network=False)
    if problems:
        for problem in problems:
            print(f"LỖI môi trường: {problem}")
        return 1
    for warning in get_warnings():
        print(f"Cảnh báo: {warning}")

    database.initialize()
    try:
        iface = get_active_interface()
    except RuntimeError:
        iface = None

    def show_cycle(results) -> None:
        parts: list[str] = []
        for target in ("router", "isp", "external"):
            result = results.get(target)
            if result is None:
                parts.append(f"{target}={monitor.target_status.get(target, 'chưa đo được')}")
            elif result.rtt_ms is None:
                parts.append(f"{target}=mất gói")
            else:
                parts.append(f"{target}={result.rtt_ms:.1f} ms, mất {result.loss_pct:.0f}%")
        print(f"[{now():%H:%M:%S}] " + " | ".join(parts))

    def show_diagnosis(diagnosis) -> None:
        print(f"  KẾT LUẬN [{diagnosis.verdict}]: {diagnosis.text}")

    monitor = PingMonitor(
        on_cycle=show_cycle,
        on_diagnosis=show_diagnosis,
        iface=iface,
    )
    label = f"{iface.name} ({iface.ip}, gateway {iface.gateway or 'chưa có'})" if iface else "LAN (đang chờ kết nối)"
    print(f"Chẩn đoán mạng qua {label}; nhấn Ctrl+C để dừng.")
    try:
        monitor.start()
        while monitor.is_running():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nĐang dừng chẩn đoán...")
    except (RuntimeError, ValueError) as exc:
        print(f"LỖI: {exc}")
        return 1
    finally:
        monitor.stop()
        database.close()
    print("Đã dừng chẩn đoán.")
    return 0


def run_gui() -> int:
    """Khởi động giao diện với dịch vụ giám sát mạng."""
    from PySide6.QtWidgets import QApplication, QMessageBox
    from ui.theme import apply_light_theme

    app = QApplication.instance() or QApplication(sys.argv)
    apply_light_theme(app)
    problems = check_environment(require_network=False)
    if problems:
        QMessageBox.critical(app.activeWindow(), "Không thể khởi động NetGuard", "\n".join(problems))
        return 1
    warnings = get_warnings()

    if importlib.util.find_spec("ui.main_window") is None:
        message = (
            "Chưa có ui/main_window.py của B. Hãy ghép giao diện rồi chạy lại NetGuard."
        )
        QMessageBox.information(app.activeWindow(), "Giao diện chưa sẵn sàng", message)
        return 1

    try:
        from ui.main_window import MainWindow

        from backend import Backend

        backend = Backend()
        window = MainWindow(backend, warnings=warnings)
        backend.start()
    except Exception as exc:
        if "backend" in locals():
            backend.stop()
        QMessageBox.critical(app.activeWindow(), "Không thể khởi động NetGuard", str(exc))
        return 1

    app.aboutToQuit.connect(backend.stop)
    window.show()
    return app.exec()


def run_cli(command: str, target: str | None = None) -> int:
    """Chạy một chế độ dòng lệnh.

    Đã có: ``scan`` (giai đoạn 3), ``baseline`` và ``monitor`` (giai đoạn 5).
    ``trace`` và ``diagnose`` đã có; chế độ GUI thuộc giai đoạn 8.
    """
    command = command or "monitor"
    if command == "scan":
        return run_scan()
    if command == "baseline":
        return run_baseline()
    if command == "monitor":
        return run_monitor()
    if command == "trace":
        return run_trace(target)
    if command == "diagnose":
        return run_diagnose()
    return 1


def main(argv: list[str] | None = None) -> int:
    """Điểm vào chính: chọn chế độ CLI hoặc GUI theo tham số."""
    setup_console_encoding()
    args = build_parser().parse_args(argv)

    if args.cli:
        return run_cli(args.command, args.target)
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
