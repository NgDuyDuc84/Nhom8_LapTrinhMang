@echo off
setlocal
set "NETGUARD_APP_ROOT=%~dp0"
if not exist "%NETGUARD_APP_ROOT%.venv\Scripts\pythonw.exe" (
    echo Khong tim thay Python trong .venv. Hay cai moi truong theo README.md.
    pause
    exit /b 1
)
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; try { Start-Process -FilePath (Join-Path $env:NETGUARD_APP_ROOT '.venv\Scripts\pythonw.exe') -ArgumentList @('main.py') -WorkingDirectory $env:NETGUARD_APP_ROOT -Verb RunAs } catch { Write-Host $_.Exception.Message; exit 1 }"
if errorlevel 1 pause
