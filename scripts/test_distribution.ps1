param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================"
Write-Host " PathPilot Distribution Test"
Write-Host " PathPilot 分发测试"
Write-Host "========================================"

$Root = Split-Path -Parent $PSScriptRoot
$InstallScript = Join-Path $PSScriptRoot "install.ps1"
$TestScript = Join-Path $PSScriptRoot "test_pathpilot.ps1"

if (-not $SkipInstall) {
    Write-Host ""
    Write-Host "Installing local project with pipx / 使用 pipx 安装本地项目..." -ForegroundColor Cyan
    & $InstallScript -InstallSource $Root -SkipSelfTest
}

$PathPilotCommand = Get-Command "pathpilot" -ErrorAction SilentlyContinue

if ($null -eq $PathPilotCommand) {
    $Candidate = Join-Path $env:USERPROFILE ".local\bin\pathpilot.exe"
    if (Test-Path $Candidate) {
        $PathPilotCommand = $Candidate
    }
}

if ($null -eq $PathPilotCommand) {
    Write-Host "Cannot find pathpilot command after install." -ForegroundColor Red
    Write-Host "安装后仍找不到 pathpilot 命令。请重启 PowerShell 或检查 pipx ensurepath。"
    exit 1
}

Write-Host "Using pathpilot command / 使用命令：" -ForegroundColor Green
Write-Host "  $PathPilotCommand"

& $TestScript -PathPilotCommand "$PathPilotCommand"

Write-Host ""
Write-Host "Distribution test finished / 分发测试结束。" -ForegroundColor Green
