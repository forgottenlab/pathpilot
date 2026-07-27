param(
    [string]$PathPilotCommand = "pathpilot",
    [string]$PathPilotHome = ""
)

$ErrorActionPreference = "Stop"
$originalPathPilotHome = $env:PATHPILOT_HOME
$ownsTemporaryHome = [string]::IsNullOrWhiteSpace($PathPilotHome)
if ($ownsTemporaryHome) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss-fff"
    $PathPilotHome = Join-Path ([System.IO.Path]::GetTempPath()) "pathpilot-smoke-$stamp"
}

function Invoke-Check {
    param([string]$Title, [scriptblock]$Action)
    Write-Host ""
    Write-Host "----------------------------------------" -ForegroundColor DarkGray
    Write-Host " $Title" -ForegroundColor Cyan
    Write-Host "----------------------------------------" -ForegroundColor DarkGray
    $global:LASTEXITCODE = 0
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "Check failed: $Title"
    }
}

try {
    $env:PATHPILOT_HOME = $PathPilotHome
    Write-Host "Using isolated PATHPILOT_HOME / 使用隔离目录: $PathPilotHome"
    Invoke-Check "Version / 版本" { & $PathPilotCommand -v }
    Invoke-Check "Guide / 指引" { & $PathPilotCommand guide }
    Invoke-Check "Status / 状态" { & $PathPilotCommand status }
    Invoke-Check "Doctor / 只读诊断" { & $PathPilotCommand doctor }
    Invoke-Check "Test / 隔离测试" { & $PathPilotCommand test }
    Invoke-Check "Install Suggestions / 安装建议" { & $PathPilotCommand installs list --all }
    Invoke-Check "Sources / 监听目录" { & $PathPilotCommand sources list }
    Write-Host "PathPilot smoke test passed / PathPilot 冒烟测试通过。" -ForegroundColor Green
}
finally {
    if ($null -eq $originalPathPilotHome) {
        Remove-Item Env:PATHPILOT_HOME -ErrorAction SilentlyContinue
    } else {
        $env:PATHPILOT_HOME = $originalPathPilotHome
    }
    if ($ownsTemporaryHome) {
        $tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
        $resolved = [System.IO.Path]::GetFullPath($PathPilotHome)
        if ($resolved.StartsWith($tempBase, [System.StringComparison]::OrdinalIgnoreCase) -and
            (Split-Path -Leaf $resolved).StartsWith("pathpilot-smoke-")) {
            Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
            $runtimeSibling = "$resolved-runtime"
            Remove-Item -LiteralPath $runtimeSibling -Recurse -Force -ErrorAction SilentlyContinue
        } else {
            Write-Warning "Refused cleanup outside validated temporary root: $resolved"
        }
    }
}
