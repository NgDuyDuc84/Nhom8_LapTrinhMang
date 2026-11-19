param(
    [ValidateSet('Native', 'Full', 'Setup', 'All')]
    [string]$Edition = 'Native'
)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        throw 'Chua co .venv. Xem huong dan build trong README.md.'
    }
    $specs = switch ($Edition) {
        'Native' { @('NetGuard.spec') }
        'Full' { @('NetGuardFull.spec') }
        'Setup' { @('NetGuardSetup.spec') }
        'All' { @('NetGuard.spec', 'NetGuardFull.spec', 'NetGuardSetup.spec') }
    }
    foreach ($spec in $specs) {
        & $python -m PyInstaller --noconfirm --clean --distpath output --workpath tmp\pyinstaller $spec
        if ($LASTEXITCODE -ne 0) { throw "Build $spec that bai." }
    }
    Copy-Item -LiteralPath 'packaging\Mo_LichSu.cmd' -Destination 'output\Mo_LichSu.cmd'
    Copy-Item -LiteralPath 'packaging\HUONG_DAN.txt' -Destination 'output\HUONG_DAN.txt'
    Copy-Item -LiteralPath 'packaging\HAI_PHIEN_BAN.txt' -Destination 'output\HAI_PHIEN_BAN.txt'
    Write-Host "Da build $Edition tai: $PSScriptRoot\output"
}
finally {
    Pop-Location
}
