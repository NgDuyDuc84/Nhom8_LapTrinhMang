from pathlib import Path
from unittest.mock import Mock

import pytest

from installer import setup_core as setup


@pytest.fixture
def files(tmp_path):
    payload = tmp_path / "payload" / "NetGuardFull.exe"
    payload.parent.mkdir()
    payload.write_bytes(b"MZ-test-program")
    return payload, tmp_path / "Cài đặt & phòng khách", setup.digest(payload)


def invoke(files, **kwargs):
    return setup.install(*files, shortcuts=Mock(), **kwargs)


def test_existing_driver_skips_download_and_preserves_history(files):
    payload, target, checksum = files
    (target / "data").mkdir(parents=True)
    history = target / "data" / "netguard.db"
    history.write_bytes(b"keep-user-history")
    download = Mock(side_effect=AssertionError("Không tải khi đã có Npcap"))
    result = invoke(files, check_npcap=lambda: True, downloader=download)
    assert result.executable.read_bytes() == payload.read_bytes()
    assert history.read_bytes() == b"keep-user-history"
    assert not result.reboot_required
    download.assert_not_called()
    assert not list(target.glob(".netguard-*.tmp"))


def test_missing_driver_is_downloaded_verified_and_installed_before_app(files):
    events = []
    check = Mock(side_effect=[False, True])
    def download(path, progress):
        events.append("download")
        path.write_bytes(b"signed-npcap")
    def verify(path):
        assert path.read_bytes() == b"signed-npcap"
        events.append("verify")
    def run(path):
        assert not files[1].exists()
        events.append("wizard")
        return 0
    result = invoke(files, check_npcap=check, downloader=download, verifier=verify, runner=run)
    assert events == ["download", "verify", "wizard"]
    assert result.executable.is_file()


@pytest.mark.parametrize("code", [1, 2, 350, 1618, 1633])
def test_cancelled_or_failed_driver_does_not_install_app(files, code):
    with pytest.raises(RuntimeError):
        invoke(files, check_npcap=lambda: False, downloader=Mock(), verifier=Mock(), runner=lambda path: code)
    assert not files[1].exists()


def test_reboot_required_does_not_claim_driver_is_ready(files):
    check = Mock(return_value=False)
    result = invoke(files, check_npcap=check, downloader=Mock(), verifier=Mock(), runner=lambda path: 3010)
    assert result.reboot_required and result.executable.exists()
    check.assert_called_once()


def test_bad_signature_prevents_execution_and_copy(files):
    run = Mock()
    with pytest.raises(RuntimeError, match="invalid signature"):
        invoke(files, check_npcap=lambda: False, downloader=Mock(),
               verifier=Mock(side_effect=RuntimeError("invalid signature")), runner=run)
    run.assert_not_called()
    assert not files[1].exists()


def test_payload_corruption_stops_before_download(files):
    payload, target, checksum = files
    payload.write_bytes(b"tampered")
    check = Mock()
    with pytest.raises(RuntimeError, match="hỏng"):
        invoke(files, check_npcap=check)
    check.assert_not_called()
    assert not target.exists()


def test_download_failure_preserves_existing_program(files):
    payload, target, checksum = files
    target.mkdir()
    existing = target / "NetGuardFull.exe"
    existing.write_bytes(b"old-version")
    with pytest.raises(OSError):
        invoke(files, check_npcap=lambda: False, downloader=Mock(side_effect=OSError("offline")))
    assert existing.read_bytes() == b"old-version"


def test_shortcut_failure_reports_installed_executable(files):
    result = setup.install(*files, check_npcap=lambda: True,
                           shortcuts=Mock(side_effect=OSError("COM unavailable")))
    assert result.executable.exists() and result.shortcut_error == "COM unavailable"


def test_npcap_bad_hash_is_not_sent_to_signature_verifier(tmp_path, monkeypatch):
    path = tmp_path / "npcap.exe"
    path.write_bytes(b"modified")
    verify = Mock()
    monkeypatch.setattr(setup, "powershell", verify)
    with pytest.raises(RuntimeError, match="SHA256"):
        setup.verify_npcap(path)
    verify.assert_not_called()


def test_npcap_command_is_interactive_and_does_not_replace_winpcap(monkeypatch):
    shell = Mock(return_value="0")
    monkeypatch.setattr(setup, "powershell", shell)
    assert setup.run_npcap(Path("npcap.exe")) == 0
    script = shell.call_args.args[0]
    assert "/S" not in script and "/winpcap_mode=no" in script and "/no_kill=yes" in script
    assert "-Verb RunAs" in script and "-Wait" in script
    assert shell.call_args.kwargs["timeout"] is None


def test_setup_window_does_nothing_until_install_is_clicked(monkeypatch):
    import setup_main
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    install = Mock()
    monkeypatch.setattr(setup_main, "install", install)
    window = setup_main.SetupWindow()
    assert window.worker is None and window.result is None
    assert window.install_btn.isEnabled() and window.open_after.isChecked()
    install.assert_not_called()
    window.close()
    window.deleteLater()
    app.processEvents()
