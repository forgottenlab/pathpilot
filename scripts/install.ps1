param(
    [string]$InstallSource = "",
    [switch]$SkipSelfTest
)

$ErrorActionPreference = "Stop"

$InstallerVersion = "0.2.0"
$ProjectName = "PathPilot"
$PackageName = "pathpilot"

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor DarkGray
    Write-Host " $Title" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor DarkGray
}

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

function Get-PathPilotCommand {
    $pipxCandidate = Join-Path $env:USERPROFILE ".local\bin\pathpilot.exe"
    if (Test-Path $pipxCandidate) {
        return $pipxCandidate
    }

    $cmd = Get-Command "pathpilot" -ErrorAction SilentlyContinue
    if ($null -ne $cmd) {
        return $cmd.Source
    }

    return $null
}

function Resolve-DefaultInstallSource {
    $scriptDir = $PSScriptRoot
    $projectRoot = Split-Path -Parent $scriptDir

    if (Test-Path (Join-Path $projectRoot "pyproject.toml")) {
        return $projectRoot
    }

    return "git+https://github.com/forgottenlab/pathpilot.git"
}

if ([string]::IsNullOrWhiteSpace($InstallSource)) {
    $InstallSource = Resolve-DefaultInstallSource
}

Write-Section "PathPilot Installer / PathPilot 安装程序"

Write-Host "Installer Version / 安装器版本: $InstallerVersion"
Write-Host "Install Source / 安装来源: $InstallSource"
Write-Host ""
Write-Host "Privacy / 隐私说明:" -ForegroundColor Yellow
Write-Host "- PathPilot does not upload your personal files, installer files, or paths."
Write-Host "- PathPilot 不会上传你的个人文件、安装包或本地路径。"
Write-Host ""
Write-Host "This script will / 此脚本将会："
Write-Host "1. Check Python / 检查 Python"
Write-Host "2. Install pipx if missing / 如果缺少 pipx 则安装"
Write-Host "3. Install or update PathPilot with pipx / 使用 pipx 安装或更新 PathPilot"
Write-Host "4. Verify the pathpilot command / 验证 pathpilot 命令"

Write-Section "Checking Python / 检查 Python"

$PythonCommand = Resolve-PythonCommand

if ($null -eq $PythonCommand) {
    Write-Host "Python was not found." -ForegroundColor Red
    Write-Host "未找到 Python。请先安装 Python 3.12+，或确认 conda/python 已加入 PATH。"
    Write-Host "Download / 下载地址: https://www.python.org/downloads/"
    exit 1
}

Write-Host "Python command / Python 命令: $PythonCommand" -ForegroundColor Green
Invoke-External $PythonCommand @("--version")

Write-Section "Checking pipx / 检查 pipx"

$PipxAvailable = Test-PythonModule $PythonCommand "pipx"

if (-not $PipxAvailable) {
    Write-Host "pipx not found. Installing pipx..." -ForegroundColor Yellow
    Write-Host "未检测到 pipx，正在安装 pipx..." -ForegroundColor Yellow

    Invoke-External $PythonCommand @("-m", "pip", "install", "--user", "pipx")
    Invoke-External $PythonCommand @("-m", "pipx", "ensurepath")
}
else {
    $PipxVersion = & $PythonCommand -m pipx --version
    Write-Host "pipx is available / pipx 已可用: $PipxVersion" -ForegroundColor Green
}

Write-Section "Installing or Updating PathPilot / 安装或更新 PathPilot"

Write-Host "Running / 正在执行:"
Write-Host "$PythonCommand -m pipx install --force $InstallSource"
Write-Host ""

Invoke-External $PythonCommand @("-m", "pipx", "install", "--force", $InstallSource)

Write-Section "Verifying Installation / 验证安装"

$PathPilotCommand = Get-PathPilotCommand

if ($null -eq $PathPilotCommand) {
    Write-Host "PathPilot was installed, but 'pathpilot' is not available in this PowerShell session." -ForegroundColor Yellow
    Write-Host "PathPilot 可能已经安装成功，但当前 PowerShell 会话暂时找不到 pathpilot 命令。"
    Write-Host ""
    Write-Host "Please restart PowerShell, then run / 请重启 PowerShell 后运行："
    Write-Host "  pathpilot -v"
    Write-Host "  pathpilot guide"
    Write-Host "  pathpilot status"
}
else {
    Write-Host "pathpilot command found / 已找到 pathpilot 命令：" -ForegroundColor Green
    Write-Host "  $PathPilotCommand"
    Write-Host ""
    & $PathPilotCommand -v

    if (-not $SkipSelfTest) {
        Write-Host ""
        Write-Host "Running self-test / 正在运行基础自检..." -ForegroundColor Cyan
        & $PathPilotCommand status
        if ($LASTEXITCODE -ne 0) {
            throw "PathPilot status check failed."
        }

        & $PathPilotCommand installs list --all
        if ($LASTEXITCODE -ne 0) {
            throw "PathPilot installs list check failed."
        }
    }
}

Write-Section "Next Steps / 下一步"

Write-Host "Run quick guide / 查看基础指引："
Write-Host "  pathpilot guide"
Write-Host ""
Write-Host "Check status / 查看状态："
Write-Host "  pathpilot status"
Write-Host ""
Write-Host "Start watcher / 启动监听："
Write-Host "  pathpilot watch"
Write-Host ""
Write-Host "Open GUI / 打开图形界面："
Write-Host "  pathpilot ui"
Write-Host ""
Write-Host "Update PathPilot / 更新 PathPilot："
Write-Host "  .\scripts\update.ps1"
Write-Host ""
Write-Host "Uninstall PathPilot / 卸载 PathPilot："
Write-Host "  $PythonCommand -m pipx uninstall pathpilot"
Write-Host "  或运行 scripts/uninstall.ps1"

Write-Host ""
Write-Host "PathPilot installation finished / PathPilot 安装流程结束" -ForegroundColor Green

