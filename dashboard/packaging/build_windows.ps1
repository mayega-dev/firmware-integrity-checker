# Builds a standalone Windows executable. Run this FROM Windows, in
# PowerShell - PyInstaller cannot cross-compile a .exe from Linux/Docker,
# so there is no way to run this step from the Ubuntu/Docker side of this
# project. See PACKAGING.md for the full explanation and options if you
# don't have Windows access at all.
#
# Prerequisites: Python 3.11+ installed from python.org (check "Add
# python.exe to PATH" during install).
#
# Usage: open PowerShell, cd to the dashboard\ folder, then:
#   .\packaging\build_windows.ps1

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")   # dashboard\ directory

python -m venv .venv-build
.\.venv-build\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install --timeout 180 --retries 15 -r requirements.txt -r packaging\requirements-build.txt

pyinstaller --noconfirm --clean packaging\dashboard.spec

deactivate

Write-Host ""
Write-Host "Built: dist\FirmwareIntegrityMonitor\"
Write-Host "Run it directly: dist\FirmwareIntegrityMonitor\FirmwareIntegrityMonitor.exe"
Write-Host "Or zip the whole dist\FirmwareIntegrityMonitor\ folder to share it -"
Write-Host "everything needed is inside, no Python install required on the target machine."
Write-Host ""
Write-Host "First launch may trigger a Windows SmartScreen warning ('Windows protected"
Write-Host "your PC') - this is expected for any unsigned .exe, not a sign something's"
Write-Host "wrong. Click 'More info' -> 'Run anyway'. See PACKAGING.md for why, and what"
Write-Host "code-signing would involve if you want to remove that warning for others."
