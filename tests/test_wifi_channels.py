"""Quét lỗi hoặc thiếu dữ liệu không được tạo đề xuất kênh giả."""

from types import SimpleNamespace

import pytest

from extras.wifi_channels import recommend_channel, scan_wifi


@pytest.mark.parametrize('networks', [[], [{'channel': 36, 'band': '5GHz'}],
                                     [{'channel': 5, 'band': '6GHz'}], [{'channel': 'invalid'}]])
def test_no_recommendation_without_24ghz_measurements(networks):
    assert recommend_channel(networks) is None


def test_recommendation_avoids_strong_interference():
    assert recommend_channel([{'channel': 1, 'rssi': -30, 'band': '2.4GHz'}]) in (6, 11)


def test_scan_failure_returns_no_networks(monkeypatch):
    monkeypatch.setattr('extras.wifi_channels.subprocess.run',
                        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout='error'))
    assert scan_wifi() == []


def test_netsh_multiple_bssids_and_explicit_6ghz_band(monkeypatch):
    output = '''SSID 1 : Home
    BSSID 1 : aa:bb:cc:dd:ee:01
         Signal : 80%
         Band : 2.4 GHz
         Channel : 6
    BSSID 2 : aa:bb:cc:dd:ee:02
         Signal : 60%
         Band : 6 GHz
         Channel : 5
'''
    monkeypatch.setattr('extras.wifi_channels.subprocess.run',
                        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=output))
    networks = scan_wifi()
    assert len(networks) == 2
    assert networks[0]['rssi'] == -60
    assert networks[1]['band'] == '6GHz'
    assert networks[0]['ssid'] == networks[1]['ssid'] == 'Home'
