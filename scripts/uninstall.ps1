param(
    [switch]$Yes,
    [switch]$RemoveUserShim
)

$ErrorActionPreference = "Stop"

function Test-Command {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Resolve-PythonCommand {
    if (Test-Command "py") {
        return "py"
    }

    if (Test-Command "python") {
        return "python"
    }

    return $null
}

function Invoke-External {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [switch]$AllowFailure
    )

    & $FilePath @Arguments
    $code = $LASTEXITCODE

    if ($code -ne 0 -and -not $AllowFailure) {
        throw "Command failed with exit code ${code}: $FilePath $($Arguments -join ' ')"
    }
}

function Test-PythonModule {
    param(
        [string]$PythonCommand,
        [string]$ModuleName
    )

    & $PythonCommand -m $ModuleName --version *> $null
    return $LASTEXITCODE -eq 0
}

Write-Host ""
Write-Host "========================================"
Write-Host " PathPilot Uninstaller"
Write-Host " PathPilot 卸载程序"
Write-Host "========================================"

Write-Host "This script will uninstall PathPilot installed by pipx."
Write-Host "此脚本将卸载通过 pipx 安装的 PathPilot。"
Write-Host ""
Write-Host "It will not delete your PathPilot managed files, Downloads, Apps, or installer queue."
Write-Host "它不会删除你的 PathPilot 管理目录、Downloads、Apps 或安装建议队列。"
Write-Host ""

$PythonCommand = Resolve-PythonCommand

if ($null -eq $PythonCommand) {
    Write-Host "Python was not found. Cannot run pipx uninstall." -ForegroundColor Yellow
    Write-Host "未找到 Python，无法执行 pipx 卸载。"
    exit 0
}

Write-Host "Python command / Python 命令: $PythonCommand" -ForegroundColor Green

$PipxAvailable = Test-PythonModule $PythonCommand "pipx"

if (-not $PipxAvailable) {
    Write-Host "pipx is not installed. Nothing to uninstall through pipx." -ForegroundColor Yellow
    Write-Host "未检测到 pipx，因此没有可通过 pipx 卸载的 PathPilot。"
}
else {
    if (-not $Yes) {
        $answer = Read-Host "Continue? / 是否继续？(y/N)"
        if ($answer -notin @("y", "Y", "yes", "YES")) {
            Write-Host "Cancelled / 已取消。"
            exit 0
        }
    }

    $originalLocation = Get-Location
    try {
        Set-Location $env:TEMP
        Invoke-External $PythonCommand @("-m", "pipx", "uninstall", "pathpilot") -AllowFailure
    }
    finally {
        Set-Location $originalLocation
    }

    Write-Host ""
    Write-Host "Checking pipx list / 正在检查 pipx 列表..."

    $List = & $PythonCommand -m pipx list

    if ($List -match "pathpilot") {
        Write-Host "PathPilot still appears in pipx list. Please check manually." -ForegroundColor Yellow
        Write-Host "PathPilot 仍然出现在 pipx 列表中，请手动检查。"
    }
    else {
        Write-Host "PathPilot has been removed from pipx list." -ForegroundColor Green
        Write-Host "PathPilot 已从 pipx 列表中移除。"
    }
}

if ($RemoveUserShim) {
    $Shim = Join-Path $env:USERPROFILE ".pathpilot\bin\pathpilot.cmd"
    if (Test-Path $Shim) {
        Remove-Item $Shim -Force
        Write-Host "Removed user shim / 已移除用户 shim: $Shim" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Uninstall finished / 卸载流程结束。" -ForegroundColor Green
