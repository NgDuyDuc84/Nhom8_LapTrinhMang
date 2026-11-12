"""Hàng đợi thông báo tùy chọn, hữu hạn và thử lại có giới hạn."""
import os
import queue
import threading

from extras.notification_http import NotificationError


class Notifications:
    def __init__(self, on_status=None, senders=None):
        self._queue = queue.Queue(maxsize=100)
        self._stop = threading.Event()
        self._thread = None
        self._on_status = on_status or (lambda status: None)
        self._senders = senders if senders is not None else self._configured_senders()

    @staticmethod
    def _configured_senders():
        # Cần opt-in rõ ràng, không tự bật chỉ vì máy có token của công cụ khác.
        if os.environ.get("NETGUARD_NOTIFICATIONS_ENABLED") != "1":
            return []
        senders = []
        if os.environ.get("NETGUARD_TELEGRAM_TOKEN") and os.environ.get("NETGUARD_TELEGRAM_CHAT_ID"):
            from extras.telegram_notify import send_alert
            senders.append(send_alert)
        if os.environ.get("NETGUARD_ZALO_ACCESS_TOKEN") and os.environ.get("NETGUARD_ZALO_USER_ID"):
            from extras.zalo_notify import send_zalo_alert
            def zalo(text):
                result = send_zalo_alert("NetGuard", text, dry_run=False)
                if not result["sent"]:
                    raise NotificationError(result["error"])
            senders.append(zalo)
        return senders

    def start(self):
        if not self._senders or self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="netguard-notifications", daemon=True)
        self._thread.start()

    def enqueue(self, alert):
        if not self._senders or self._stop.is_set() or alert.kind == "service:notifications":
            return False
        try:
            self._queue.put_nowait(f"[{alert.level.upper()}] {alert.message}")
            return True
        except queue.Full:
            self._on_status({"service": "notifications", "running": False, "error": "Hàng đợi đầy; cảnh báo vẫn được lưu trong CSDL."})
            return False

    def _run(self):
        while not self._stop.is_set():
            try:
                message = self._queue.get(timeout=.2)
            except queue.Empty:
                continue
            for send in self._senders:
                for attempt in range(3):
                    if self._stop.is_set():
                        return
                    try:
                        send(message)
                        break
                    except Exception as exc:
                        retry = isinstance(exc, NotificationError) and exc.retryable and attempt < 2
                        if not retry:
                            self._on_status({"service": "notifications", "running": False,
                                             "error": "Gửi thông báo chưa thành công; xem cấu hình kênh. Cảnh báo còn trong CSDL."})
                            break
                        if self._stop.wait(2**attempt):
                            return

    def stop(self, timeout=6):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)
            if self._thread.is_alive():
                raise RuntimeError("Worker thông báo chưa dừng.")
            self._thread = None
