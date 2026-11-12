import threading
from urllib.error import HTTPError
from unittest.mock import Mock

import pytest
from extras import telegram_notify, zalo_notify, notification_http
from models import Alert
from services.notifications import Notifications


def test_notifications_are_opt_in_and_do_not_start_by_default():
    worker = Notifications()
    worker.start()
    assert worker._thread is None
    assert not worker.enqueue(Alert("warning", "event"))


def test_telegram_request_uses_expected_payload_without_real_delivery(monkeypatch):
    monkeypatch.setenv("NETGUARD_TELEGRAM_TOKEN", "fake-token")
    monkeypatch.setenv("NETGUARD_TELEGRAM_CHAT_ID", "fake-chat")
    post = Mock(return_value={"ok": True})
    monkeypatch.setattr(notification_http, "post_json", post)
    telegram_notify.send_alert("Cảnh báo thử")
    assert post.call_args.args[1] == {"chat_id": "fake-chat", "text": "Cảnh báo thử"}


def test_zalo_request_preserves_demo_and_supports_configured_api(monkeypatch):
    monkeypatch.setenv("NETGUARD_ZALO_ACCESS_TOKEN", "fake-token")
    monkeypatch.setenv("NETGUARD_ZALO_USER_ID", "fake-user")
    post = Mock(return_value={"error": 0})
    monkeypatch.setattr(notification_http, "post_json", post)
    assert not zalo_notify.send_zalo_alert("event", "text")["sent"]
    post.assert_not_called()
    assert zalo_notify.send_zalo_alert("event", "text", dry_run=False)["sent"]
    assert post.call_args.args[1]["recipient"] == {"user_id": "fake-user"}


def test_http_errors_are_sanitized_and_marked_retryable(monkeypatch):
    url = "https://api.telegram.org/botTOP_SECRET/sendMessage"
    monkeypatch.setattr(notification_http, "urlopen", Mock(side_effect=HTTPError(url, 500, "failed", {}, None)))
    with pytest.raises(notification_http.NotificationError) as caught:
        notification_http.post_json(url, {})
    assert caught.value.retryable
    assert "TOP_SECRET" not in str(caught.value)


def test_notification_queue_has_bound_and_worker_delivers_only_via_fake_sender():
    delivered = threading.Event()
    sender = Mock(side_effect=lambda text: delivered.set())
    worker = Notifications(senders=[sender])
    worker.start()
    try:
        assert worker.enqueue(Alert("warning", "event"))
        assert delivered.wait(2)
        sender.assert_called_once_with("[WARNING] event")
    finally:
        worker.stop()
    blocked = Notifications(senders=[sender])
    for _ in range(100):
        assert blocked.enqueue(Alert("warning", "event"))
    assert not blocked.enqueue(Alert("warning", "overflow"))
