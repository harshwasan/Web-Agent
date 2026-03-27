$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceExe = Join-Path $scriptDir "WebAgentBridge.exe"
if (-not (Test-Path $sourceExe)) {
  throw "WebAgentBridge.exe not found next to installer script."
}

$appName = "WebAgent Bridge"
$installRoot = Join-Path $env:LOCALAPPDATA "WebAgentBridge"
$targetExe = Join-Path $installRoot "WebAgentBridge.exe"
$uninstallScript = Join-Path $installRoot "uninstall_webagent_bridge.ps1"
$startMenuDir = Join-Path $env:APPDATA "Microsoft\\Windows\\Start Menu\\Programs\\WebAgent Bridge"
$startMenuShortcut = Join-Path $startMenuDir "WebAgent Bridge.lnk"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "WebAgent Bridge.lnk"
$uninstallRegPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\WebAgentBridge"

New-Item -ItemType Directory -Force -Path $installRoot | Out-Null
Copy-Item -LiteralPath $sourceExe -Destination $targetExe -Force

$embeddedUninstall = @'
$ErrorActionPreference = "SilentlyContinue"
$installRoot = Join-Path $env:LOCALAPPDATA "WebAgentBridge"
$targetExe = Join-Path $installRoot "WebAgentBridge.exe"
$uninstallScript = Join-Path $installRoot "uninstall_webagent_bridge.ps1"
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\WebAgent Bridge"
$startMenuShortcut = Join-Path $startMenuDir "WebAgent Bridge.lnk"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "WebAgent Bridge.lnk"
$uninstallRegPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\WebAgentBridge"
Remove-Item -LiteralPath "HKCU:\Software\Classes\webagent" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $uninstallRegPath -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $startMenuShortcut -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $desktopShortcut -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $startMenuDir -Recurse -Force -ErrorAction SilentlyContinue
Get-Process WebAgentBridge -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $installRoot -Recurse -Force -ErrorAction SilentlyContinue
'@
Set-Content -LiteralPath $uninstallScript -Value $embeddedUninstall -Encoding UTF8

New-Item -Path "HKCU:\Software\Classes\webagent" -Force | Out-Null
Set-ItemProperty -Path "HKCU:\Software\Classes\webagent" -Name "(default)" -Value "URL:WebAgent Protocol" -Force
New-ItemProperty -Path "HKCU:\Software\Classes\webagent" -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
New-Item -Path "HKCU:\Software\Classes\webagent\DefaultIcon" -Force | Out-Null
Set-ItemProperty -Path "HKCU:\Software\Classes\webagent\DefaultIcon" -Name "(default)" -Value $targetExe -Force
New-Item -Path "HKCU:\Software\Classes\webagent\shell\open\command" -Force | Out-Null
$command = '"' + $targetExe + '" "%1"'
Set-ItemProperty -Path "HKCU:\Software\Classes\webagent\shell\open\command" -Name "(default)" -Value $command -Force

New-Item -ItemType Directory -Force -Path $startMenuDir | Out-Null
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($startMenuShortcut)
$shortcut.TargetPath = $targetExe
$shortcut.WorkingDirectory = $installRoot
$shortcut.IconLocation = $targetExe
$shortcut.Save()

$uninstallCmd = 'powershell.exe -ExecutionPolicy Bypass -File "' + $uninstallScript + '"'
$desktop = $wsh.CreateShortcut($desktopShortcut)
$desktop.TargetPath = $targetExe
$desktop.WorkingDirectory = $installRoot
$desktop.IconLocation = $targetExe
$desktop.Save()

New-Item -Path $uninstallRegPath -Force | Out-Null
Set-ItemProperty -Path $uninstallRegPath -Name "DisplayName" -Value $appName -Force
Set-ItemProperty -Path $uninstallRegPath -Name "DisplayVersion" -Value "0.1.0" -Force
Set-ItemProperty -Path $uninstallRegPath -Name "Publisher" -Value "WebAgent" -Force
Set-ItemProperty -Path $uninstallRegPath -Name "InstallLocation" -Value $installRoot -Force
Set-ItemProperty -Path $uninstallRegPath -Name "DisplayIcon" -Value $targetExe -Force
Set-ItemProperty -Path $uninstallRegPath -Name "UninstallString" -Value $uninstallCmd -Force
Set-ItemProperty -Path $uninstallRegPath -Name "QuietUninstallString" -Value $uninstallCmd -Force
New-ItemProperty -Path $uninstallRegPath -Name "NoModify" -Value 1 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path $uninstallRegPath -Name "NoRepair" -Value 1 -PropertyType DWord -Force | Out-Null

Start-Process -FilePath $targetExe -ArgumentList "--tray"

Add-Type -AssemblyName PresentationFramework
[System.Windows.MessageBox]::Show(
  "WebAgent Bridge was installed successfully.`n`nInstalled to: $installRoot",
  $appName,
  [System.Windows.MessageBoxButton]::OK,
  [System.Windows.MessageBoxImage]::Information
) | Out-Null
