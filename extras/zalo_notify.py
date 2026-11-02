
"""Tao va xu ly canh bao Zalo cho NetGuard."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def format_alert(
    event_type: str,
    message: str,
    severity: str = "warning",
) -> str:
    """Tao noi dung thong bao canh bao."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    severity_labels = {
        "info": "THONG TIN",
        "warning": "CANH BAO",
        "critical": "NGUY HIEM",
    }

    level = severity_labels.get(
        severity.lower(), "CANH BAO"
    )

    return (
        "[NETGUARD]\n"
        f"Muc do: {level}\n"
        f"Su kien: {event_type}\n"
        f"Noi dung: {message}\n"
        f"Thoi gian: {now}"
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
        print(alert)

        return {
            "success": True,
            "sent": False,
            "mode": "dry_run",
            "message": alert,
        }

    return {
        "success": False,
        "sent": False,
        "mode": "not_configured",
        "error": "Chua cau hinh Zalo Official Account API",
        "message": alert,
    }


if __name__ == "__main__":
    send_zalo_alert(
        event_type="IP Conflict",
        message="Phat hien hai thiet bi su dung IP 192.168.1.10",
        severity="critical",
    )
