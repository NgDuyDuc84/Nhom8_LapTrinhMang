
"""Tao va xu ly canh bao Zalo cho NetGuard."""

from __future__ import annotations

from typing import Any

from models import now


def format_alert(
    event_type: str,
    message: str,
    severity: str = "warning",
) -> str:
    """Tao noi dung thong bao canh bao."""
    timestamp = now().strftime("%d/%m/%Y %H:%M:%S")

    severity_labels = {
        "info": "THONG TIN",
        "warning": "CANH BAO",
        "critical": "NGUY HIEM",
        "danger": "NGUY HIEM",
    }

    level = severity_labels.get(
        severity.lower(), "CANH BAO"
    )

    return (
        "[NETGUARD]\n"
        f"Muc do: {level}\n"
        f"Su kien: {event_type}\n"
        f"Noi dung: {message}\n"
        f"Thoi gian: {timestamp}"
    )


def send_zalo_alert(
    event_type: str,
    message: str,
    severity: str = "warning",
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Mo phong thong bao; chua tich hop Zalo API."""
    alert = format_alert(event_type, message, severity)

    if dry_run:
        print("=== ZALO ALERT - DEMO ===")
        print("Chi mo phong tren terminal, chua gui tin nhan Zalo.")
        print(alert)

        return {
            "success": True,
            "sent": False,
            "mode": "dry_run",
            "message": alert,
        }

    import os
    from extras.notification_http import post_json
    token, user = os.environ.get("NETGUARD_ZALO_ACCESS_TOKEN"), os.environ.get("NETGUARD_ZALO_USER_ID")
    if not token or not user:
        return {"success": False, "sent": False, "mode": "not_configured",
                "error": "Chua cau hinh Zalo Official Account API", "message": alert}
    result = post_json("https://openapi.zalo.me/v3.0/oa/message/cs",
                       {"recipient": {"user_id": user}, "message": {"text": alert[:2000]}},
                       {"access_token": token})
    success = result.get("error") == 0
    return {"success": success, "sent": success, "mode": "api", "message": alert,
            "error": "" if success else "Zalo từ chối tin; kiểm tra quyền OA, tương tác người nhận và token."}


if __name__ == "__main__":
    send_zalo_alert(
        event_type="IP Conflict",
        message="Phat hien hai thiet bi su dung IP 192.168.1.10",
        severity="critical",
    )
