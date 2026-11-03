
"""Kiem thu chuc nang canh bao Zalo cua NetGuard."""

from extras.zalo_notify import format_alert, send_zalo_alert


def test_format_alert():
    result = format_alert(
        "IP Conflict",
        "Phat hien trung dia chi IP",
        "critical",
    )

    assert "[NETGUARD]" in result
    assert "IP Conflict" in result
    assert "NGUY HIEM" in result
    assert "Phat hien trung dia chi IP" in result


def test_warning_alert():
    result = format_alert(
        "Packet Loss",
        "Mat goi 20%",
        "warning",
    )

    assert "CANH BAO" in result
    assert "Packet Loss" in result


def test_dry_run():
    result = send_zalo_alert(
        "Device Offline",
        "Thiet bi mat ket noi",
        dry_run=True,
    )

    assert result["success"] is True
    assert result["sent"] is False
    assert result["mode"] == "dry_run"


def test_not_configured():
    result = send_zalo_alert(
        "IP Conflict",
        "Trung dia chi IP",
        dry_run=False,
    )

    assert result["success"] is False
    assert result["sent"] is False
    assert result["mode"] == "not_configured"
