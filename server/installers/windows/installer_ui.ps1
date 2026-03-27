$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

[System.Windows.Forms.Application]::EnableVisualStyles()

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$packagedInstallScript = Join-Path $scriptDir "install_webagent_bridge.ps1"
$packagedUninstallScript = Join-Path $scriptDir "uninstall_webagent_bridge.ps1"
$installedUninstallScript = Join-Path $env:LOCALAPPDATA "WebAgentBridge\\uninstall_webagent_bridge.ps1"
$isInstalled = Test-Path (Join-Path $env:LOCALAPPDATA "WebAgentBridge\\WebAgentBridge.exe")

$form = New-Object System.Windows.Forms.Form
$form.Text = "WebAgent Bridge Setup"
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.ClientSize = New-Object System.Drawing.Size(430, 190)
$form.BackColor = [System.Drawing.Color]::FromArgb(245, 247, 251)

$title = New-Object System.Windows.Forms.Label
$title.Text = "WebAgent Bridge Setup"
$title.Font = New-Object System.Drawing.Font("Segoe UI", 15, [System.Drawing.FontStyle]::Bold)
$title.AutoSize = $true
$title.Location = New-Object System.Drawing.Point(22, 18)
$form.Controls.Add($title)

$subtitle = New-Object System.Windows.Forms.Label
$subtitle.Text = if ($isInstalled) { "WebAgent Bridge is installed on this PC. Choose an action." } else { "Install or remove the local WebAgent Bridge app." }
$subtitle.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$subtitle.AutoSize = $true
$subtitle.ForeColor = [System.Drawing.Color]::FromArgb(76, 89, 109)
$subtitle.Location = New-Object System.Drawing.Point(24, 54)
$form.Controls.Add($subtitle)

$installButton = New-Object System.Windows.Forms.Button
$installButton.Text = if ($isInstalled) { "Reinstall" } else { "Install" }
$installButton.Size = New-Object System.Drawing.Size(160, 42)
$installButton.Location = New-Object System.Drawing.Point(24, 104)
$installButton.BackColor = [System.Drawing.Color]::FromArgb(37, 78, 135)
$installButton.ForeColor = [System.Drawing.Color]::White
$installButton.FlatStyle = "Flat"
$installButton.Add_Click({
  $form.Tag = "install"
  $form.Close()
})
$form.Controls.Add($installButton)

$uninstallButton = New-Object System.Windows.Forms.Button
$uninstallButton.Text = "Uninstall"
$uninstallButton.Size = New-Object System.Drawing.Size(160, 42)
$uninstallButton.Location = New-Object System.Drawing.Point(206, 104)
$uninstallButton.BackColor = [System.Drawing.Color]::FromArgb(234, 238, 245)
$uninstallButton.ForeColor = [System.Drawing.Color]::FromArgb(24, 34, 46)
$uninstallButton.FlatStyle = "Flat"
$uninstallButton.Enabled = $isInstalled
$uninstallButton.Add_Click({
  $form.Tag = "uninstall"
  $form.Close()
})
$form.Controls.Add($uninstallButton)

[void]$form.ShowDialog()

$choice = [string]($form.Tag)
if ($choice -eq "install") {
  if (-not (Test-Path $packagedInstallScript)) {
    throw "Install script not found: $packagedInstallScript"
  }
  powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File $packagedInstallScript
  exit $LASTEXITCODE
}
if ($choice -eq "uninstall") {
  $target = if (Test-Path $installedUninstallScript) { $installedUninstallScript } else { $packagedUninstallScript }
  if (-not (Test-Path $target)) {
    throw "Uninstall script not found."
  }
  powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File $target
  Add-Type -AssemblyName PresentationFramework
  [System.Windows.MessageBox]::Show(
    "WebAgent Bridge was removed from this PC.",
    "WebAgent Bridge Setup",
    [System.Windows.MessageBoxButton]::OK,
    [System.Windows.MessageBoxImage]::Information
  ) | Out-Null
  exit $LASTEXITCODE
}
exit 0
