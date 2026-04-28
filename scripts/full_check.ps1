param(
    [switch]$SkipWatcher
)

$ErrorActionPreference = "Stop"

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$TestPrefix = "pathpilot-smoke-$Stamp"
$BackupDir = Join-Path $env:TEMP "pathpilot-full-check-$Stamp"
$UserHome = Join-Path $env:USERPROFILE ".pathpilot"
$ConfigDir = Join-Path $UserHome "config"
$DataDir = Join-Path $UserHome "data"
$PendingFile = Join-Path $DataDir "pending_installs.json"

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

function Write-Section {
    param([string]$Title)

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor DarkGray
    Write-Host " $Title" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor DarkGray
}

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    Write-Section $Name

    & $Action

    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $Name"
    }

    Write-Host "PASS: $Name" -ForegroundColor Green
}

function Backup-PathPilotUserData {
    Write-Section "Backup user config and data / 备份用户配置与数据"

    if (Test-Path $ConfigDir) {
        Copy-Item $ConfigDir (Join-Path $BackupDir "config") -Recurse -Force
        Write-Host "Backed up config: $ConfigDir"
    }

    if (Test-Path $PendingFile) {
        New-Item -ItemType Directory -Force -Path (Join-Path $BackupDir "data") | Out-Null
        Copy-Item $PendingFile (Join-Path $BackupDir "data\pending_installs.json") -Force
        Write-Host "Backed up queue: $PendingFile"
    }
}

function Restore-PathPilotUserData {
    Write-Section "Restore user config and data / 恢复用户配置与数据"

    $backupConfig = Join-Path $BackupDir "config"
    $backupPending = Join-Path $BackupDir "data\pending_installs.json"

    if (Test-Path $backupConfig) {
        if (Test-Path $ConfigDir) {
            Remove-Item $ConfigDir -Recurse -Force
        }

        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ConfigDir) | Out-Null
        Copy-Item $backupConfig $ConfigDir -Recurse -Force
        Write-Host "Restored config."
    }

    if (Test-Path $backupPending) {
        New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
        Copy-Item $backupPending $PendingFile -Force
        Write-Host "Restored pending_installs.json."
    }
}

function Cleanup-SmokeFiles {
    Write-Section "Cleanup smoke files / 清理测试文件"

    Get-PSDrive -PSProvider FileSystem | ForEach-Object {
        $candidate = Join-Path $_.Root "PathPilot\Downloads"
        if (Test-Path $candidate) {
            Get-ChildItem $candidate -Recurse -File -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -like "$TestPrefix*" } |
                ForEach-Object {
                    try {
                        Remove-Item $_.FullName -Force -ErrorAction Stop
                        Write-Host "Removed: $($_.FullName)"
                    } catch {
                        Write-Host "Skip remove: $($_.FullName)" -ForegroundColor Yellow
                    }
                }
        }
    }
}

function Get-FirstInstallId {
    if (-not (Test-Path $PendingFile)) {
        return $null
    }

    try {
        $items = Get-Content $PendingFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($null -eq $items) {
            return $null
        }

        if ($items -is [array] -and $items.Count -gt 0) {
            return $items[0].id
        }

        if ($items.id) {
            return $items.id
        }
    } catch {
        return $null
    }

    return $null
}

$PathPilot = Get-Command "pathpilot" -ErrorAction SilentlyContinue

if ($null -eq $PathPilot) {
    Write-Host "Cannot find pathpilot command. 请先确认 pathpilot 已安装并在 PATH 中。" -ForegroundColor Red
    exit 1
}

$PathPilotExe = $PathPilot.Source
Write-Host "Using pathpilot: $PathPilotExe" -ForegroundColor Green

$WatcherProcess = $null
$TempSource = Join-Path $env:TEMP "$TestPrefix-source"

try {
    Backup-PathPilotUserData

    Invoke-Step "Version / 版本" {
        & $PathPilotExe -v
    }

    Invoke-Step "Commands / 命令表" {
        & $PathPilotExe commands
    }

    Invoke-Step "Guide zh / 中文指引" {
        & $PathPilotExe guide
    }

    Invoke-Step "Guide en / 英文指引" {
        & $PathPilotExe --lang en guide
    }

    Invoke-Step "Doctor / 诊断" {
        & $PathPilotExe doctor
    }

    Invoke-Step "Self Test / 基础自检" {
        & $PathPilotExe test
    }

    Invoke-Step "Status / 状态" {
        & $PathPilotExe status
    }

    Invoke-Step "Config show / 配置显示" {
        & $PathPilotExe config show
    }

    Invoke-Step "Sources list / 监听目录列表" {
        & $PathPilotExe sources list
    }

    Invoke-Step "Installs list all / 安装建议列表" {
        & $PathPilotExe installs list --all
    }

    $firstId = Get-FirstInstallId
    if ($null -ne $firstId) {
        Invoke-Step "Installs detail / 安装建议详情" {
            & $PathPilotExe installs detail $firstId
        }
    } else {
        Write-Host "No install suggestion found, skip detail test." -ForegroundColor Yellow
    }

    Invoke-Step "Sources add/remove / 来源目录增删" {
        New-Item -ItemType Directory -Force -Path $TempSource | Out-Null
        & $PathPilotExe sources add $TempSource
        & $PathPilotExe sources list
        & $PathPilotExe sources remove $TempSource
    }

    if (-not $SkipWatcher) {
        Invoke-Step "Watcher smoke / 监听器冒烟测试" {
            New-Item -ItemType Directory -Force -Path $TempSource | Out-Null

            # 先添加临时监听目录
            & $PathPilotExe sources add $TempSource

            $watchOut = Join-Path $BackupDir "watcher.stdout.txt"
            $watchErr = Join-Path $BackupDir "watcher.stderr.txt"

            $WatcherProcess = Start-Process `
                -FilePath $PathPilotExe `
                -ArgumentList @("watch") `
                -PassThru `
                -RedirectStandardOutput $watchOut `
                -RedirectStandardError $watchErr `
                -WindowStyle Hidden

            Start-Sleep -Seconds 4

            Set-Content -Path (Join-Path $TempSource "$TestPrefix-demo.py") -Value 'print("hello pathpilot")' -Encoding UTF8
            Set-Content -Path (Join-Path $TempSource "$TestPrefix-notes.txt") -Value 'PathPilot smoke test note' -Encoding UTF8
            Set-Content -Path (Join-Path $TempSource "$TestPrefix-setup.exe") -Value 'MZ dummy Inno Setup smoke installer' -Encoding ASCII

            Start-Sleep -Seconds 12

            if ($WatcherProcess -and -not $WatcherProcess.HasExited) {
                Stop-Process -Id $WatcherProcess.Id -Force
                Start-Sleep -Seconds 1
            }

            Write-Host ""
            Write-Host "Watcher stdout:" -ForegroundColor Cyan
            if (Test-Path $watchOut) {
                Get-Content $watchOut -Encoding UTF8 | Select-Object -Last 80
            }

            Write-Host ""
            Write-Host "Watcher stderr:" -ForegroundColor Cyan
            if (Test-Path $watchErr) {
                Get-Content $watchErr -Encoding UTF8 | Select-Object -Last 80
            }

            & $PathPilotExe installs list --all
        }
    } else {
        Write-Host "Skip watcher smoke test." -ForegroundColor Yellow
    }

    Write-Section "Manual GUI check / 手动 GUI 检查"
    Write-Host "请手动运行下面命令确认窗口能正常打开：" -ForegroundColor Yellow
    Write-Host "  pathpilot ui"
    Write-Host ""
    Write-Host "如果 GUI 能打开、待安装建议页能显示、设置页能打开，则 GUI 基础通过。"

    Write-Section "Full check passed / 完整测试通过"
    Write-Host "PathPilot CLI / config / doctor / test / sources / installs / watcher smoke checks passed." -ForegroundColor Green
    Write-Host "如果 GUI 手动检查也正常，就可以开始创建 GitHub 仓库。" -ForegroundColor Green
}
finally {
    if ($WatcherProcess -and -not $WatcherProcess.HasExited) {
        Stop-Process -Id $WatcherProcess.Id -Force
    }

    if (Test-Path $TempSource) {
        Remove-Item $TempSource -Recurse -Force -ErrorAction SilentlyContinue
    }

    Restore-PathPilotUserData
    Cleanup-SmokeFiles

    Write-Host ""
    Write-Host "Test backup dir: $BackupDir" -ForegroundColor DarkGray
}
