from __future__ import annotations

import argparse
import importlib.util
import sys
import time
import logging

from core.console import setup_console_encoding
from core.interfaces import check_environment, get_active_interface, get_warnings
from core.startup import RELAUNCH_ARGUMENT, prepare_gui_launch, show_startup_error

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
    parser.add_argument("--history", action="store_true", help="chỉ xem dữ liệu/báo cáo, không xin quyền bắt gói")
    parser.add_argument(RELAUNCH_ARGUMENT, action="store_true", help=argparse.SUPPRESS)
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
    print("\nĐã chốt đường cơ sở. Từ giờ thiết bị chưa tin cậy xuất hiện hoặc cần kiểm tra lại sẽ bị cảnh báo.")
    return 0


def run_monitor() -> int:
    """Chạy vòng quét định kỳ, in thiết bị mới, đổi online/offline và cảnh báo."""
    from config import SCAN_INTERVAL_SEC
    from core.arp_listener import ArpListener
    from db import database, repository
    from services import baseline
    from services.alerts import ArpAnomalyDetector
    from services.scan_loop import ScanLoop
    from core.network_context import network_scope, network_id

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
        print("Đã có đường cơ sở: thiết bị chưa tin cậy xuất hiện hoặc cần kiểm tra lại sẽ bị cảnh báo.")
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
    arp_network = "legacy"

    def on_arp_observation(observation) -> None:
        if detector is None:
            return
        with network_scope(arp_network):
            for alert in detector.observe(observation):
                on_alert(alert)

    def on_interface(chosen) -> None:
        nonlocal detector, listener, arp_network
        if listener is not None:
            listener.stop()
            listener = None
        detector = None
        if chosen is None:
            print("Mất kết nối LAN; chờ kết nối lại ở chu kỳ quét sau.")
            return
        arp_network = network_id(chosen)
        with network_scope(arp_network):
            detector = ArpAnomalyDetector(chosen.gateway, repository.list_devices(), subnet=f"{chosen.ip}/{chosen.netmask}")
        listener = ArpListener(on_observation=on_arp_observation, iface=chosen)
        try:
            listener.start()
        except RuntimeError as exc:
            print(f"Lưu ý: bộ nghe ARP đang thử mở lại: {exc}")
            return
        print("Đang nghe ARP thụ động để phát hiện IP/MAC bất thường.")

    loop = ScanLoop(on_device=on_device, on_alert=on_alert, iface=iface, on_interface=on_interface, scoped=True)
    try:
        loop.start()
        while loop.is_running():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nĐang dừng...")
    finally:
        errors = []
        for service in (loop, listener):
            if service is not None:
                try:
                    service.stop()
                except Exception as exc:
                    errors.append(str(exc))
                    logging.getLogger(__name__).exception("Không dừng được dịch vụ CLI")
        if errors:
            raise RuntimeError(" | ".join(errors))
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
        hops = trace(target, iface=iface)
    except (RuntimeError, ValueError) as exc:
        print(f"LỖI: {exc}")
        return 1

    isp_hop = find_isp_hop(hops, iface.gateway, target)
    print(f"\n{'TTL':<6}{'IP':<20}{'RTT (ms)':<14}GHI CHÚ")
    print("-" * 54)
    for hop in hops:
        rtt = "*" if hop.rtt_ms is None else f"{hop.rtt_ms:.2f}"
        notes: list[str] = []
        if isp_hop is hop:
            notes.append("hop phản hồi sau gateway (chưa xác minh ISP)")
        if hop.flagged:
            notes.append("độ trễ bắt đầu tăng rõ")
        print(f"{hop.ttl:<6}{hop.ip or '*':<20}{rtt:<14}{'; '.join(notes)}")

    if isp_hop is None:
        print(f"\nKhông xác định được hop nhà mạng sau gateway {iface.gateway or '(không rõ)'}.")
    else:
        print(f"\nHop quan sát sau gateway: TTL {isp_hop.ttl}, IP {isp_hop.ip}.")
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
        scoped=True,
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


def run_gui(*, history=False) -> int:
    """Khởi động giao diện với dịch vụ giám sát mạng."""
    from PySide6.QtWidgets import QApplication, QMessageBox
    from ui.theme import apply_light_theme

    app = QApplication.instance() or QApplication(sys.argv)
    apply_light_theme(app)
    problems = [] if history else check_environment(require_network=False)
    if problems:
        QMessageBox.critical(app.activeWindow(), "Không thể khởi động NetGuard", "\n".join(problems))
        return 1
    warnings = get_warnings()

    if importlib.util.find_spec("ui.main_window") is None:
        message = (
            "Thiếu ui/main_window.py. Hãy khôi phục mã nguồn giao diện trước khi chạy."
        )
        QMessageBox.information(app.activeWindow(), "Giao diện chưa sẵn sàng", message)
        return 1

    try:
        from ui.main_window import MainWindow

        from backend import Backend

        backend = Backend()
        window = MainWindow(backend, warnings=warnings)
        if not history:
            backend.start()
    except Exception as exc:
        if "backend" in locals():
            backend.stop()
        QMessageBox.critical(app.activeWindow(), "Không thể khởi động NetGuard", str(exc))
        return 1

    def shutdown():
        try:
            backend.stop()
        except Exception:
            logging.getLogger(__name__).exception("Ứng dụng thoát khi worker chưa dừng hoàn toàn; CSDL chưa bị đóng sớm")
    app.aboutToQuit.connect(shutdown)
    window.show()
    return app.exec()


def _run_cli_command(command: str, target: str | None = None) -> int:
    """Chạy một chế độ dòng lệnh.

    Các lệnh hỗ trợ: scan, baseline, monitor, trace, diagnose.
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


def run_cli(command: str, target: str | None = None) -> int:
    from config import DB_PATH
    from core.instance_lock import InstanceLock
    from core.network_context import network_id, network_scope
    from contextlib import nullcontext
    try:
        chosen = get_active_interface()
        storage = network_id(chosen)
    except RuntimeError:
        storage = "legacy"
    lock = InstanceLock(DB_PATH) if command in {None, "monitor", "diagnose"} else nullcontext()
    try:
        with lock, network_scope(storage):
            return _run_cli_command(command, target)
    except (RuntimeError, ValueError) as exc:
        print(f"LỖI: {exc}")
        return 1


def main(argv: list[str] | None = None) -> int:
    """Điểm vào chính: chọn chế độ CLI hoặc GUI theo tham số."""
    setup_console_encoding()
    from core.logging_setup import setup_logging
    setup_logging()
    args = build_parser().parse_args(argv)

    if args.cli:
        return run_cli(args.command, args.target)
    try:
        if args.history:
            if not prepare_gui_launch(relaunched=args.gui_relaunched, history=True):
                return 0
            return run_gui(history=True)
        if not prepare_gui_launch(relaunched=args.gui_relaunched):
            return 0
        return run_gui()
    except Exception as exc:
        show_startup_error(exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
