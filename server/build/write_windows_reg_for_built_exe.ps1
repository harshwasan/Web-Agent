$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$exePath = Join-Path $root "dist\\windows\\WebAgentBridge.exe"
$outPath = Join-Path $root "dist\\windows\\webagent_protocol_built_exe.reg"

if (-not (Test-Path $exePath)) {
  throw "Built executable not found at $exePath"
}

$escapedExe = $exePath.Replace('\', '\\')
$content = @"
Windows Registry Editor Version 5.00

[HKEY_CURRENT_USER\Software\Classes\webagent]
@="URL:WebAgent Protocol"
"URL Protocol"=""

[HKEY_CURRENT_USER\Software\Classes\webagent\DefaultIcon]
@="$escapedExe"

[HKEY_CURRENT_USER\Software\Classes\webagent\shell]

[HKEY_CURRENT_USER\Software\Classes\webagent\shell\open]

[HKEY_CURRENT_USER\Software\Classes\webagent\shell\open\command]
@="\"$escapedExe\" \"%1\""
"@

Set-Content -LiteralPath $outPath -Value $content -Encoding Unicode
Write-Host "Wrote $outPath"
