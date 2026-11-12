"""Telegram Bot API, chỉ gửi khi người vận hành cấu hình và bật kênh."""

from __future__ import annotations


def send_alert(text: str) -> None:
    """Gửi một tin nhắn cảnh báo qua Telegram bot.

    Đầu vào: ``text`` là nội dung tin nhắn tiếng Việt.
    Đầu ra: không trả về gì; ném ngoại lệ có thông báo tiếng Việt nếu chưa cấu hình
    token/chat id hoặc gửi thất bại.
    """
    import os
    from extras.notification_http import post_json, NotificationError
    token, chat = os.environ.get("NETGUARD_TELEGRAM_TOKEN"), os.environ.get("NETGUARD_TELEGRAM_CHAT_ID")
    if not token or not chat:
        raise NotificationError("Chưa cấu hình Telegram token/chat ID.")
    result = post_json(f"https://api.telegram.org/bot{token}/sendMessage", {"chat_id": chat, "text": text[:4000]})
    if not result.get("ok"):
        raise NotificationError("Telegram từ chối thông báo; kiểm tra quyền bot/chat và token.")
