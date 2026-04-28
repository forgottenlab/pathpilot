param(
    [string]$PathPilotCommand = "pathpilot"
)

$ErrorActionPreference = "Stop"

function Invoke-Check {
    param(
        [string]$Title,
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host "----------------------------------------" -ForegroundColor DarkGray
    Write-Host " $Title" -ForegroundColor Cyan
    Write-Host "----------------------------------------" -ForegroundColor DarkGray

    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "Check failed: $Title"
    }
}

Write-Host ""
Write-Host "========================================"
Write-Host " PathPilot Smoke Test"
Write-Host " PathPilot 冒烟测试"
Write-Host "========================================"

Invoke-Check "Version / 版本" {
    & $PathPilotCommand -v
}

Invoke-Check "Guide / 指引" {
    & $PathPilotCommand guide
}

Invoke-Check "Status / 状态" {
    & $PathPilotCommand status
}

Invoke-Check "Install Suggestions / 安装建议" {
    & $PathPilotCommand installs list --all
}

Invoke-Check "Sources / 监听目录" {
    & $PathPilotCommand sources list
}

Write-Host ""
Write-Host "PathPilot smoke test passed / PathPilot 冒烟测试通过。" -ForegroundColor Green
