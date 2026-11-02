"""Gửi cảnh báo qua Telegram (phần của C – đây chỉ là file khung)."""

from __future__ import annotations


def send_alert(text: str) -> None:
    """Gửi một tin nhắn cảnh báo qua Telegram bot.

    Đầu vào: ``text`` là nội dung tin nhắn tiếng Việt.
    Đầu ra: không trả về gì; ném ngoại lệ có thông báo tiếng Việt nếu chưa cấu hình
    token/chat id hoặc gửi thất bại.
    """
    raise NotImplementedError("extras.telegram_notify.send_alert chưa được cài đặt (phần của C).")
