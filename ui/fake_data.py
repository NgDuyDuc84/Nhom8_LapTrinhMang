"""Dữ liệu giả cho giao diện (B dùng trước khi lõi xong).

``FakeBackend`` kế thừa ``BackendBase`` nên B chỉ cần đổi ``Backend()`` thành
``FakeBackend()`` là giao diện chạy được với dữ liệu mẫu, không phải sửa gì thêm.
Toàn bộ dữ liệu nằm trong bộ nhớ, không ghi CSDL và không gửi gói tin thật.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, QTimer

from backend import BackendBase
from models import Alert, Device, Diagnosis, Hop, PingResult, now

TARGETS = ("router", "isp", "external")


class FakeBackend(BackendBase):
    """Backend giả: sinh thiết bị, ping, cảnh báo, chẩn đoán và traceroute mẫu."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rng = random.Random(8)
        self._devices: list[Device] = self._build_devices()
        self._alerts: list[Alert] = []
        self._pings: dict[str, list[PingResult]] = {t: [] for t in TARGETS}
        self._presence: dict[str, list[tuple[datetime, bool]]] = {}
        self._baseline_done = False
        self._last_verdict = "ok"
        self._tick_count = 0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)  # mỗi giây sinh một mẫu ping
        self._timer.timeout.connect(self._on_tick)

    # ------------------------------------------------------------------ dựng dữ liệu
    def _build_devices(self) -> list[Device]:
        """Tạo 8 thiết bị mẫu: vài thiết bị tin cậy, ba thiết bị lạ, một MAC ngẫu nhiên."""
        base = now()
        raw = [
            # ip,            mac,                 vendor,            name,            trusted, randomized, is_self
            ("192.168.102.1", "28:77:77:db:b5:6c", "Router", "Router nhà", True, False, False),
            ("192.168.102.7", "ac:74:b1:41:a5:d2", "Intel", "Máy của tôi", True, False, True),
            ("192.168.102.12", "b8:27:eb:11:22:33", "Raspberry Pi", "Pi làm NAS", True, False, False),
            ("192.168.102.15", "3c:5a:b4:77:88:99", "Samsung", "TV phòng khách", True, False, False),
            ("192.168.102.18", "f0:18:98:aa:bb:cc", "Apple", "MacBook của B", True, False, False),
            ("192.168.102.23", "d2:4a:8c:1e:55:01", "Unknown", "", False, True, False),
            ("192.168.102.31", "00:1a:2b:3c:4d:5e", "Espressif", "", False, False, False),
            ("192.168.102.44", "5c:aa:fd:9b:ee:77", "Unknown", "", False, False, False),
        ]
        devices: list[Device] = []
        for index, (ip, mac, vendor, name, trusted, randomized, is_self) in enumerate(raw):
            devices.append(
                Device(
                    ip=ip,
                    mac=mac,
                    vendor=vendor,
                    name=name,
                    trusted=trusted,
                    online=index != 4,  # một thiết bị đang offline cho UI có dữ liệu
                    randomized_mac=randomized,
                    is_self=is_self,
                    first_seen=base - timedelta(hours=6 - index),
                    last_seen=base - timedelta(seconds=index * 7),
                )
            )
        return devices

    # ------------------------------------------------------------------ vòng đời
    def start(self) -> None:
        """Phát dữ liệu ban đầu rồi bắt đầu sinh dữ liệu giả mỗi giây."""
        for device in self._devices:
            self.device_updated.emit(device)
        self._emit_diagnosis(self._last_verdict)
        if not self._alerts:
            self._raise_random_alert()  # có sẵn một cảnh báo để B thấy ngay khi mở UI
        self._timer.start()

    def stop(self) -> None:
        """Dừng sinh dữ liệu giả (gọi nhiều lần vẫn an toàn)."""
        self._timer.stop()

    # ------------------------------------------------------------------ sinh dữ liệu
    def _on_tick(self) -> None:
        self._tick_count += 1
        self._emit_pings()

        if self._tick_count % 4 == 0:
            self._toggle_random_device()

        if self._tick_count % 7 == 0:
            self._raise_random_alert()

        if self._tick_count % 12 == 0:
            self._rotate_verdict()

    def _emit_pings(self) -> None:
        """Bắn PingResult cho ba mốc, RTT dao động nhẹ quanh mức nền."""
        base_rtt = {"router": 3.0, "isp": 12.0, "external": 28.0}
        for target in TARGETS:
            loss = 0.0 if self._rng.random() > 0.08 else self._rng.choice([10.0, 20.0])
            if loss and loss >= 10.0 and self._rng.random() < 0.5:
                rtt = None  # mất gói hẳn
            else:
                rtt = round(base_rtt[target] + self._rng.uniform(-2.0, 18.0), 2)
            result = PingResult(target=target, rtt_ms=rtt, loss_pct=loss)
            self._pings[target].append(result)
            del self._pings[target][:-60]
            self.ping_result.emit(result)

    def _toggle_random_device(self) -> None:
        """Bật/tắt một thiết bị ngẫu nhiên để UI thấy trạng thái đổi."""
        device = self._rng.choice(self._devices)
        device.online = not device.online
        device.last_seen = now()
        self._presence.setdefault(device.mac, []).append((now(), device.online))
        self.device_updated.emit(device)

    def _raise_random_alert(self) -> None:
        """Thỉnh thoảng sinh một cảnh báo thiết bị lạ."""
        stranger = self._rng.choice([d for d in self._devices if not d.trusted])
        message = f"Thiết bị lạ {stranger.ip} ({stranger.mac}) vừa vào mạng."
        if stranger.randomized_mac:
            message += " Địa chỉ MAC trông ngẫu nhiên, có thể là điện thoại đã đổi MAC."
        alert = Alert(level="warning", message=message, device_mac=stranger.mac)
        self._alerts.insert(0, alert)
        del self._alerts[100:]
        self.alert_raised.emit(alert)

    def _rotate_verdict(self) -> None:
        """Đổi kết luận chẩn đoán theo chu kỳ để B thấy màu sắc/thanh trạng thái đổi."""
        cycle = ["ok", "ok", "home_issue", "isp_issue", "ok", "internet_issue"]
        self._last_verdict = cycle[(self._tick_count // 12) % len(cycle)]
        self._emit_diagnosis(self._last_verdict)

    def _emit_diagnosis(self, verdict: str) -> None:
        texts = {
            "ok": "Mạng bình thường: ba mốc ping đều ổn định.",
            "home_issue": "Lỗi trong mạng nhà (Wi-Fi, tín hiệu hoặc router).",
            "isp_issue": "Lỗi ở đường truyền hoặc phía nhà mạng.",
            "internet_issue": "Lỗi xa hơn: phía Internet hoặc server đích.",
            "unknown": "Chưa đủ dữ liệu để kết luận.",
        }
        self.diagnosis_changed.emit(Diagnosis(verdict=verdict, text=texts.get(verdict, "")))

    # ------------------------------------------------------------------ thiết bị
    def list_devices(self) -> list[Device]:
        """Trả về danh sách thiết bị giả, sắp xếp theo IP."""
        return sorted(self._devices, key=lambda d: tuple(int(x) for x in d.ip.split(".")))

    def set_trusted(self, mac: str, trusted: bool) -> None:
        """Đánh dấu tin cậy cho thiết bị giả rồi phát lại sự kiện."""
        for device in self._devices:
            if device.mac == mac:
                device.trusted = trusted
                self.device_updated.emit(device)
                return

    def rename(self, mac: str, name: str, note: str) -> None:
        """Đổi tên và ghi chú của thiết bị giả rồi phát lại sự kiện."""
        for device in self._devices:
            if device.mac == mac:
                device.name = name
                device.note = note
                self.device_updated.emit(device)
                return

    # ------------------------------------------------------------------ baseline, lịch sử
    def is_first_run(self) -> bool:
        """True khi chưa gọi ``finish_baseline()``."""
        return not self._baseline_done

    def finish_baseline(self) -> None:
        """Chốt đường cơ sở giả và phát một cảnh báo mức info."""
        if self._baseline_done:
            return
        self._baseline_done = True
        alert = Alert(level="info", message="Đã chốt danh sách thiết bị tin cậy ban đầu.")
        self._alerts.insert(0, alert)
        self.alert_raised.emit(alert)

    def get_alerts(self, limit: int = 100) -> list[Alert]:
        """Trả về cảnh báo giả, mới nhất trước."""
        return self._alerts[:limit]

    def get_ping_history(self, target: str, minutes: int) -> list[PingResult]:
        """Trả về các mẫu ping giả của một mốc trong ``minutes`` phút gần nhất."""
        since = now() - timedelta(minutes=minutes)
        return [p for p in self._pings.get(target, []) if p.ts >= since]

    def get_device_history(self, mac: str, hours: int) -> list[tuple[datetime, bool]]:
        """Trả về lịch sử online/offline giả của thiết bị trong ``hours`` giờ gần nhất."""
        since = now() - timedelta(hours=hours)
        points = self._presence.get(mac)
        if not points:
            # Chưa có dữ liệu thật: sinh vài mốc mẫu để biểu đồ của B có gì để vẽ.
            start = now() - timedelta(hours=min(hours, 6))
            points = [(start + timedelta(minutes=30 * i), (i % 3) != 1) for i in range(12)]
            self._presence[mac] = points
        return [(ts, online) for ts, online in points if ts >= since]

    # ------------------------------------------------------------------ traceroute, báo cáo
    def run_traceroute(self, target: str = "1.1.1.1") -> None:
        """Trả về một traceroute giả sau 0,6 giây, có một chặng bị đánh dấu."""
        hops = [
            Hop(ttl=1, ip="192.168.102.1", rtt_ms=2.4),
            Hop(ttl=2, ip="192.168.1.1", rtt_ms=8.1),
            Hop(ttl=3, ip=None, rtt_ms=None),  # chặng không trả lời ICMP
            Hop(ttl=4, ip="100.64.12.1", rtt_ms=14.6),
            Hop(ttl=5, ip="203.113.10.1", rtt_ms=35.9),
            Hop(ttl=6, ip="203.113.40.9", rtt_ms=96.2, flagged=True),
            Hop(ttl=7, ip="172.68.1.1", rtt_ms=101.5, flagged=True),
            Hop(ttl=8, ip=target, rtt_ms=104.0, flagged=True),
        ]
        QTimer.singleShot(600, lambda: self.traceroute_done.emit(hops))

    def export_report(self, start: datetime, end: datetime, path: str) -> None:
        """Chế độ dữ liệu giả chưa hỗ trợ xuất PDF."""
        raise NotImplementedError("Chế độ dữ liệu giả chưa hỗ trợ xuất báo cáo PDF.")
