"""Kiểm tra launcher và UAC mà không xin quyền hoặc bật dịch vụ mạng thật."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import main
from core import startup


@pytest.fixture
def windows_launch(monkeypatch, tmp_path):
    root = tmp_path / "Nhóm 8 & thư mục có dấu cách"
    scripts = root / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "pythonw.exe").touch()
    (scripts / "python.exe").touch()
    (root / "main.py").touch()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(startup, "APP_ROOT", root)
    monkeypatch.setattr(startup.sys, "platform", "win32")
    monkeypatch.setattr(startup.sys, "executable", str(scripts / "python.exe"))
    monkeypatch.setattr(startup, "is_admin", lambda: False)
    execute = Mock(return_value=64)
    show = Mock(return_value=1)
    libraries = {
        "shell32": SimpleNamespace(ShellExecuteW=execute),
        "user32": SimpleNamespace(MessageBoxW=show),
    }
    monkeypatch.setattr(startup.ctypes, "WinDLL", lambda name, **kwargs: libraries[name])
    monkeypatch.setattr(startup.ctypes, "get_last_error", lambda: 0)
    return root, execute, show


def test_normal_gui_launch_requests_uac_once_and_exits_parent(monkeypatch, windows_launch):
    root, execute, _ = windows_launch
    gui = Mock()
    monkeypatch.setattr(main, "run_gui", gui)

    assert main.main([]) == 0

    execute.assert_called_once()
    owner, verb, executable, arguments, cwd, display = execute.call_args.args
    assert owner is None and verb == "runas"
    assert Path(executable) == root / ".venv" / "Scripts" / "pythonw.exe"
    assert arguments.startswith(f'"{root / "main.py"}" ')
    assert arguments.endswith(startup.RELAUNCH_ARGUMENT)
    assert Path(cwd) == root and Path.cwd() == root
    assert display == 1
    gui.assert_not_called()


def test_cancelled_uac_does_not_retry_or_show_error(monkeypatch, windows_launch):
    _, execute, show = windows_launch
    execute.return_value = 5
    monkeypatch.setattr(startup.ctypes, "get_last_error", lambda: startup.ERROR_CANCELLED)
    gui = Mock()
    monkeypatch.setattr(main, "run_gui", gui)

    assert main.main([]) == 0

    execute.assert_called_once()
    gui.assert_not_called()
    show.assert_not_called()


def test_admin_in_project_environment_opens_gui_without_relaunch(monkeypatch, windows_launch):
    root, execute, _ = windows_launch
    monkeypatch.setattr(startup, "is_admin", lambda: True)
    gui = Mock(return_value=0)
    monkeypatch.setattr(main, "run_gui", gui)

    assert main.main([startup.RELAUNCH_ARGUMENT]) == 0

    assert Path.cwd() == root
    execute.assert_not_called()
    gui.assert_called_once_with()


def test_admin_using_other_python_switches_to_project_venv(monkeypatch, windows_launch, tmp_path):
    root, execute, _ = windows_launch
    monkeypatch.setattr(startup, "is_admin", lambda: True)
    monkeypatch.setattr(startup.sys, "executable", str(tmp_path / "other-python" / "python.exe"))

    assert not startup.prepare_gui_launch()

    assert execute.call_args.args[1] == "open"
    assert Path(execute.call_args.args[2]) == root / ".venv" / "Scripts" / "pythonw.exe"


def test_failed_elevation_does_not_create_relaunch_loop(monkeypatch, windows_launch):
    root, execute, show = windows_launch
    gui = Mock()
    monkeypatch.setattr(main, "run_gui", gui)

    assert main.main([startup.RELAUNCH_ARGUMENT]) == 1

    execute.assert_not_called()
    gui.assert_not_called()
    show.assert_called_once()
    assert "Administrator" in show.call_args.args[1]
    assert "RuntimeError" in (root / "logs" / "startup.log").read_text(encoding="utf-8")


def test_windows_launch_failure_is_visible_and_logged(monkeypatch, windows_launch):
    root, execute, show = windows_launch
    execute.return_value = 2
    monkeypatch.setattr(main, "run_gui", Mock())

    assert main.main([]) == 1

    show.assert_called_once()
    assert "Windows không mở được NetGuard" in show.call_args.args[1]
    assert "OSError" in (root / "logs" / "startup.log").read_text(encoding="utf-8")


def test_missing_qt_is_reported_without_importing_qt(monkeypatch, windows_launch):
    root, execute, show = windows_launch
    monkeypatch.setattr(startup, "is_admin", lambda: True)
    monkeypatch.setattr(main, "run_gui", Mock(side_effect=ModuleNotFoundError(
        "No module named 'PySide6'", name="PySide6",
    )))

    assert main.main([]) == 1

    execute.assert_not_called()
    message = show.call_args.args[1]
    assert "PySide6" in message and "requirements.txt" in message
    assert "ModuleNotFoundError" in (root / "logs" / "startup.log").read_text(encoding="utf-8")


def test_cli_does_not_relaunch_or_change_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    launch = Mock()
    command = Mock(return_value=0)
    monkeypatch.setattr(main, "prepare_gui_launch", launch)
    monkeypatch.setattr(main, "run_cli", command)

    assert main.main(["--cli", "baseline"]) == 0

    launch.assert_not_called()
    command.assert_called_once_with("baseline", None)
    assert Path.cwd() == tmp_path


def test_help_does_not_request_privileges_or_expose_internal_argument(monkeypatch, capsys):
    launch = Mock()
    monkeypatch.setattr(main, "prepare_gui_launch", launch)

    with pytest.raises(SystemExit) as stopped:
        main.main(["--help"])

    assert stopped.value.code == 0
    assert startup.RELAUNCH_ARGUMENT not in capsys.readouterr().out
    launch.assert_not_called()
