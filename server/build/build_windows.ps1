$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python -m pip install -e ".[build]"
python -m PyInstaller --noconfirm --clean ".\build\pyinstaller_webagent_bridge.spec" --distpath ".\dist\windows" --workpath ".\build\.pyinstaller-win"

Write-Host "Built Windows app under server\\dist\\windows"
