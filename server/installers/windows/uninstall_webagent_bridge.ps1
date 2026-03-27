$ErrorActionPreference = "SilentlyContinue"

$installRoot = Join-Path $env:LOCALAPPDATA "WebAgentBridge"
$startMenuDir = Join-Path $env:APPDATA "Microsoft\\Windows\\Start Menu\\Programs\\WebAgent Bridge"
$uninstallShortcut = Join-Path $startMenuDir "Uninstall WebAgent Bridge.lnk"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "WebAgent Bridge.lnk"
$uninstallRegPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\WebAgentBridge"

Remove-Item -LiteralPath "HKCU:\Software\Classes\webagent" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $uninstallRegPath -Recurse -Force -ErrorAction SilentlyContinue
Get-Process WebAgentBridge -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $uninstallShortcut -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $desktopShortcut -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $startMenuDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $installRoot -Recurse -Force -ErrorAction SilentlyContinue
