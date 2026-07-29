# One-terminal launcher for Rubric Loom (Windows).
# Windows (PowerShell 5.1+ or PowerShell 7):
#     powershell -NoProfile -ExecutionPolicy Bypass -File rubric_loom.ps1
# or double-click "Rubric Loom.bat".
# NOTE: no Set-Location — the Loom resolves its own files absolutely, and
# staying in the caller's directory lets relative --export paths work.
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

$MinVersion = [Version]"3.11"
$MaxVersion = [Version]"3.14"
$AssumeYes = ($args -contains "--yes") -or ($args -contains "-y")

function Read-YesNo([string]$Prompt, [bool]$Default = $false) {
    if ($AssumeYes) { return $true }
    $suffix = if ($Default) { "[Y/n]" } else { "[y/N]" }
    $reply = Read-Host "$Prompt $suffix"
    if ([string]::IsNullOrWhiteSpace($reply)) { return $Default }
    return $reply -match "^(y|yes)$"
}

function Test-Python([string[]]$Command) {
    # Probe the interpreter's version; also filters out the Microsoft Store
    # "python" alias, which fails this probe instead of running it.
    try {
        $probeArgs = @()
        if ($Command.Count -gt 1) { $probeArgs = @($Command[1..($Command.Count - 1)]) }
        $probeArgs += @("-c", "import sys; print('.'.join(map(str, sys.version_info[:2])))")
        $probe = & $Command[0] @probeArgs 2>$null
        if ($LASTEXITCODE -eq 0 -and $probe) {
            $version = [Version]("$probe".Trim())
            return ($version -ge $MinVersion -and $version -lt $MaxVersion)
        }
    } catch { }
    return $false
}

function New-PythonSelection([string[]]$Command) {
    $prefixArguments = @()
    if ($Command.Count -gt 1) {
        $prefixArguments = @($Command[1..($Command.Count - 1)])
    }
    return [PSCustomObject]@{
        Executable = [string]$Command[0]
        PrefixArguments = [string[]]$prefixArguments
    }
}

function Find-Python {
    $candidates = @()
    if ($env:PYTHON) { $candidates += ,@($env:PYTHON) }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($ver in "-3.13", "-3.12", "-3.11", "-3") {
            $candidates += ,@("py", $ver)
        }
    }
    foreach ($cmd in "python3", "python") {
        if (Get-Command $cmd -ErrorAction SilentlyContinue) { $candidates += ,@($cmd) }
    }
    foreach ($candidate in $candidates) {
        if (Test-Python $candidate) {
            # A one-element PowerShell array is normally unwrapped to a
            # string on return. Preserve the executable and any py-launcher
            # prefix arguments as named fields so "python3" never becomes
            # only its first character ("p") at invocation time.
            return (New-PythonSelection $candidate)
        }
    }
    return $null
}

function Install-Python {
    Write-Host "A supported Python 3.11-3.13 installation was not found."
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "winget was not found. Install Python 3.11-3.13 from https://www.python.org/downloads/ (check 'Add python.exe to PATH'), then rerun this launcher."
        return $false
    }
    if (-not (Read-YesNo "Install Python with winget now?" $true)) { return $false }
    winget install --id Python.Python.3.12 -e --source winget
    return ($LASTEXITCODE -eq 0)
}

$Python = Find-Python
if (-not $Python) {
    if (Install-Python) {
        # A fresh install updates PATH for new shells, not this one; the py
        # launcher usually appears immediately, so try once more.
        $Python = Find-Python
    }
    if (-not $Python) {
        Write-Host "Python 3.11-3.13 is still not on PATH in this window." -ForegroundColor Yellow
        Write-Host "Open a NEW terminal (so PATH refreshes) and rerun this launcher."
        exit 1
    }
}

$PythonCmd = $Python.Executable
$PythonArgs = @($Python.PrefixArguments)

$PackageRoot = Split-Path -Parent $Here
$BundleDir = if ($env:RUBRIC_LOOM_BUNDLE_DIR) {
    $env:RUBRIC_LOOM_BUNDLE_DIR
} else {
    Join-Path $PackageRoot "brightspace-rubric-bundle"
}
$ReleaseManifest = Join-Path $PackageRoot "RELEASE_MANIFEST.json"
$DefaultUserData = if (Test-Path $ReleaseManifest) {
    Join-Path $PackageRoot "user-data"
} else {
    Join-Path $Here "user-data"
}
if (-not $env:RUBRIC_LOOM_USER_DATA) {
    $env:RUBRIC_LOOM_USER_DATA = $DefaultUserData
}
if (-not $env:RUBRIC_LOOM_VENV) {
    $env:RUBRIC_LOOM_VENV = Join-Path $env:RUBRIC_LOOM_USER_DATA "runtime\.venv"
}
if (-not $env:RUBRIC_LOOM_RELEASE_REPOSITORY) {
    $env:RUBRIC_LOOM_RELEASE_REPOSITORY = "timebeing92/brightspace-rubric-loom-runner"
}
if (-not $env:RUBRIC_LOOM_INSTALLED_VERSION) {
    $VersionPath = Join-Path $Here "VERSION"
    if (Test-Path $VersionPath) {
        $env:RUBRIC_LOOM_INSTALLED_VERSION = (Get-Content $VersionPath -Raw).Trim()
    }
}
$LoomEntry = Join-Path $BundleDir "scripts\rubric_loom_wizard.py"
if (-not (Test-Path $LoomEntry)) {
    Write-Host "Rubric Loom engine not found: $BundleDir" -ForegroundColor Red
    Write-Host "Download a Rubric Loom release ZIP rather than GitHub's source-code ZIP."
    exit 1
}

& $PythonCmd @PythonArgs $LoomEntry @args
exit $LASTEXITCODE
