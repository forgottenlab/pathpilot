param(
    [string]$InstallSource = "",
    [switch]$SkipSelfTest,
    [switch]$CliOnly
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================"
Write-Host " PathPilot Updater"
Write-Host " PathPilot 更新程序"
Write-Host "========================================"

$Installer = Join-Path $PSScriptRoot "install.ps1"

if (-not (Test-Path $Installer)) {
    Write-Host "install.ps1 not found: $Installer" -ForegroundColor Red
    Write-Host "未找到 install.ps1：$Installer"
    exit 1
}

& $Installer -InstallSource $InstallSource -SkipSelfTest:$SkipSelfTest -CliOnly:$CliOnly
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
