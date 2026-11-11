@echo off
setlocal
set "NETGUARD_APP_ROOT=%~dp0"
if not exist "%NETGUARD_APP_ROOT%.venv\Scripts\pythonw.exe" (
    echo Khong tim thay Python trong .venv. Hay cai moi truong theo README.md.
    pause
    exit /b 1
)
start "" /d "%NETGUARD_APP_ROOT%" "%NETGUARD_APP_ROOT%.venv\Scripts\pythonw.exe" "%NETGUARD_APP_ROOT%main.py"
if errorlevel 1 (
    echo Khong mo duoc NetGuard. Hay kiem tra moi truong .venv theo README.md.
    pause
    exit /b 1
)
