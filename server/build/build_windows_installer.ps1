$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$distDir = Join-Path $root "dist\\windows"
$buildDir = Join-Path $root "build\\.installer-win"
$payloadDir = Join-Path $buildDir "payload"
$sedPath = Join-Path $buildDir "webagent_bridge_installer.sed"
$installerPath = Join-Path $distDir "WebAgentBridgeSetup.exe"
$exePath = Join-Path $distDir "WebAgentBridge.exe"
$installerUiSource = Join-Path $root "installers\\windows\\installer_ui.ps1"
$installScriptSource = Join-Path $root "installers\\windows\\install_webagent_bridge.ps1"
$uninstallScriptSource = Join-Path $root "installers\\windows\\uninstall_webagent_bridge.ps1"

if (-not (Test-Path $exePath)) {
  throw "Built app not found at $exePath. Run .\\build\\build_windows.ps1 first."
}

Remove-Item -LiteralPath $payloadDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $payloadDir | Out-Null
Copy-Item -LiteralPath $exePath -Destination (Join-Path $payloadDir "WebAgentBridge.exe") -Force
Copy-Item -LiteralPath $installerUiSource -Destination (Join-Path $payloadDir "installer_ui.ps1") -Force
Copy-Item -LiteralPath $installScriptSource -Destination (Join-Path $payloadDir "install_webagent_bridge.ps1") -Force
Copy-Item -LiteralPath $uninstallScriptSource -Destination (Join-Path $payloadDir "uninstall_webagent_bridge.ps1") -Force

$escapedPayloadDir = $payloadDir.Replace("\", "\\")
$escapedInstaller = $installerPath.Replace("\", "\\")
$sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=
DisplayLicense=
FinishMessage=
TargetName=$escapedInstaller
FriendlyName=WebAgent Bridge Setup
AppLaunched=powershell.exe -WindowStyle Hidden -ExecutionPolicy Bypass -File installer_ui.ps1
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
SourceFiles=SourceFiles
[Strings]
FILE0=WebAgentBridge.exe
FILE1=installer_ui.ps1
FILE2=install_webagent_bridge.ps1
FILE3=uninstall_webagent_bridge.ps1
[SourceFiles]
SourceFiles0=$escapedPayloadDir
[SourceFiles0]
%FILE0%=
%FILE1%=
%FILE2%=
%FILE3%=
"@

New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
Set-Content -LiteralPath $sedPath -Value $sed -Encoding ASCII

& "$env:SystemRoot\\System32\\iexpress.exe" /N $sedPath | Out-Null

if (-not (Test-Path $installerPath)) {
  throw "Installer build failed: $installerPath was not created."
}

Write-Host "Built Windows installer at $installerPath"
