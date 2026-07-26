param(
    [switch]$SkipWatcher,
    [string]$PathPilotCommand = "",
    [string]$PythonExecutable = ""
)

$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss-fff"
$tempBase = [System.IO.Path]::GetTempPath()
$testRoot = Join-Path $tempBase "pathpilot-full-check-$stamp"
$isolatedHome = Join-Path $testRoot "home"
$managedRoot = Join-Path $testRoot "managed"
$sourceRoot = Join-Path $testRoot "source"
$pendingFile = Join-Path $isolatedHome "data\pending_installs.json"
$originalPathPilotHome = $env:PATHPILOT_HOME
$watcherProcess = $null

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor DarkGray
    Write-Host " $Title" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor DarkGray
}

function Invoke-Step {
    param([string]$Name, [scriptblock]$Action)
    Write-Section $Name
    $global:LASTEXITCODE = 0
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $Name (exit $LASTEXITCODE)"
    }
    Write-Host "PASS: $Name" -ForegroundColor Green
}

function Wait-ForPath {
    param([string]$Path, [int]$TimeoutSeconds = 35)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            return $true
        }
        Start-Sleep -Milliseconds 250
    }
    return $false
}

if (-not $PathPilotCommand) {
    $pathPilot = Get-Command "pathpilot" -ErrorAction SilentlyContinue
    if ($null -eq $pathPilot) {
        throw "Cannot find pathpilot command."
    }
    $PathPilotCommand = $pathPilot.Source
}
if (-not $PythonExecutable) {
    $python = Get-Command "python" -ErrorAction SilentlyContinue
    if ($null -eq $python) {
        throw "Cannot find python command."
    }
    $PythonExecutable = $python.Source
}

try {
    New-Item -ItemType Directory -Path $testRoot, $sourceRoot -Force | Out-Null
    $env:PATHPILOT_HOME = $isolatedHome
    Write-Host "Using isolated PATHPILOT_HOME: $isolatedHome" -ForegroundColor Green
    Write-Host "Using isolated managed root: $managedRoot" -ForegroundColor Green

    Invoke-Step "Initialize isolated state" {
        & $PythonExecutable -c "from app.core.paths import ensure_user_config_files; ensure_user_config_files()"
    }
    Invoke-Step "Configure isolated roots" {
        & $PathPilotCommand sources remove "{user_downloads}"
        & $PathPilotCommand config set-root $managedRoot
        & $PathPilotCommand sources add $sourceRoot
        & $PathPilotCommand status
    }
    Invoke-Step "CLI help" { & $PathPilotCommand --help }
    Invoke-Step "Doctor read-only" { & $PathPilotCommand doctor }
    Invoke-Step "Isolated self test" { & $PathPilotCommand test }
    Invoke-Step "Install commands" { & $PathPilotCommand installs --help }

    if (-not $SkipWatcher) {
        Invoke-Step "Watcher isolated behavior" {
            $watchOut = Join-Path $testRoot "watcher.stdout.txt"
            $watchErr = Join-Path $testRoot "watcher.stderr.txt"
            $script:watcherProcess = Start-Process `
                -FilePath $PathPilotCommand `
                -ArgumentList @("watch") `
                -PassThru `
                -RedirectStandardOutput $watchOut `
                -RedirectStandardError $watchErr `
                -WindowStyle Hidden

            Start-Sleep -Seconds 2
            Set-Content -LiteralPath (Join-Path $sourceRoot "full-check.py") -Value "print('fixture')" -Encoding UTF8
            Set-Content -LiteralPath (Join-Path $sourceRoot "full-check.txt") -Value "fixture" -Encoding UTF8
            Set-Content -LiteralPath (Join-Path $sourceRoot "full-check.exe") -Value "MZ inert Inno Setup fixture" -Encoding ASCII

            $pythonTarget = Join-Path $managedRoot "Downloads\06-Code\Python\full-check.py"
            $textTarget = Join-Path $managedRoot "Downloads\05-Documents\Mixed\full-check.txt"
            $installerTarget = Join-Path $managedRoot "Downloads\01-Software\_IncomingInstallers\full-check.exe"
            foreach ($target in @($pythonTarget, $textTarget, $installerTarget)) {
                if (-not (Wait-ForPath -Path $target)) {
                    throw "Watcher did not produce expected final path: $target"
                }
            }
            if (-not (Wait-ForPath -Path $pendingFile)) {
                throw "Watcher did not create isolated pending queue."
            }

            $records = @(Get-Content -LiteralPath $pendingFile -Raw -Encoding UTF8 | ConvertFrom-Json)
            $record = $records | Where-Object { $_.installer_path -eq $installerTarget } | Select-Object -First 1
            if ($null -eq $record) {
                throw "Missing installer suggestion for isolated fixture."
            }
            foreach ($field in @("executable", "args", "preview", "installer_path", "target_dir", "installer_family")) {
                if ($null -eq $record.$field) {
                    throw "Installer suggestion missing field: $field"
                }
            }
            if ($record.mode -ne "suggest" -or $record.status -ne "pending") {
                throw "Installer suggestion has unsafe mode/status."
            }
        }
    }

    Write-Section "Full check passed"
    Write-Host "All state and watcher checks used isolated temporary directories." -ForegroundColor Green
}
finally {
    if ($watcherProcess -and -not $watcherProcess.HasExited) {
        Stop-Process -Id $watcherProcess.Id -Force -ErrorAction SilentlyContinue
        $watcherProcess.WaitForExit(5000) | Out-Null
    }
    if ($null -eq $originalPathPilotHome) {
        Remove-Item Env:PATHPILOT_HOME -ErrorAction SilentlyContinue
    } else {
        $env:PATHPILOT_HOME = $originalPathPilotHome
    }

    $resolvedTestRoot = [System.IO.Path]::GetFullPath($testRoot)
    $resolvedTempBase = [System.IO.Path]::GetFullPath($tempBase)
    if ($resolvedTestRoot.StartsWith($resolvedTempBase, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $resolvedTestRoot).StartsWith("pathpilot-full-check-")) {
        Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force -ErrorAction SilentlyContinue
    } else {
        Write-Warning "Refused cleanup outside validated temporary root: $resolvedTestRoot"
    }
}
