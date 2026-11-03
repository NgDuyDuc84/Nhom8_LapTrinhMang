
"""Kiểm thử chức năng chẩn đoán mạng NetGuard."""

from core.diagnosis import TargetStats, diagnose, is_bad


def make_stats(loss=0, rtt=10, baseline=10, samples=30, available=True):
    """Tạo dữ liệu Ping mẫu."""
    return TargetStats(
        loss_pct=loss,
        rtt_median=rtt,
        rtt_baseline=baseline,
        samples=samples,
        available=available,
    )


def test_network_ok():
    """Mạng hoạt động bình thường."""
    result = diagnose(make_stats(), make_stats(), make_stats())
    assert result.verdict == "ok"


def test_home_issue():
    """Router mất gói nhiều."""
    result = diagnose(
        make_stats(loss=20), make_stats(), make_stats()
    )
    assert result.verdict == "home_issue"


def test_isp_issue():
    """Đường truyền nhà mạng có vấn đề."""
    result = diagnose(
        make_stats(), make_stats(loss=15), make_stats()
    )
    assert result.verdict == "isp_issue"


def test_internet_issue():
    """Máy chủ bên ngoài có vấn đề."""
    result = diagnose(
        make_stats(), make_stats(), make_stats(loss=30)
    )
    assert result.verdict == "internet_issue"


def test_router_not_enough_samples():
    """Router chưa đủ 10 mẫu Ping."""
    result = diagnose(
        make_stats(samples=5), make_stats(), make_stats()
    )
    assert result.verdict == "unknown"


def test_external_not_available():
    """Không có dữ liệu máy chủ bên ngoài."""
    result = diagnose(
        make_stats(), make_stats(), make_stats(available=False)
    )
    assert result.verdict == "unknown"


def test_no_isp_external_bad():
    """Không có mốc ISP và Internet bị lỗi."""
    result = diagnose(
        make_stats(), None, make_stats(loss=25)
    )
    assert result.verdict == "internet_issue"


def test_no_isp_external_ok():
    """Không có mốc ISP, Internet vẫn ổn định."""
    result = diagnose(
        make_stats(), None, make_stats()
    )
    assert result.verdict == "unknown"


def test_loss_threshold():
    """Mất gói trên 5% mới được xem là xấu."""
    assert is_bad(make_stats(loss=5)) is False
    assert is_bad(make_stats(loss=6)) is True


def test_high_rtt():
    """RTT vượt ngưỡng cho phép."""
    assert is_bad(make_stats(rtt=50, baseline=10)) is True


def test_rtt_at_threshold():
    """RTT đúng ngưỡng chưa được xem là xấu."""
    assert is_bad(make_stats(rtt=30, baseline=10)) is False


def test_insufficient_samples():
    """Dưới 10 mẫu thì chưa kết luận xấu."""
    assert is_bad(make_stats(loss=100, samples=9)) is False
