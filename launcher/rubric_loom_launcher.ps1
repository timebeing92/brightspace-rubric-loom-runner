# Stable launcher for a managed Rubric Loom install (Windows).
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

. (Join-Path $Here "launcher\runtime_probe.ps1")

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
    $privatePython = Join-Path $Here "user-data\runtime\.venv\Scripts\python.exe"
    if (Test-Path $privatePython) { $candidates += ,@($privatePython) }
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
    if (Install-Python) { $Python = Find-Python }
    if (-not $Python) {
        Write-Host "Python 3.11-3.13 is still not on PATH in this window." -ForegroundColor Yellow
        Write-Host "Open a NEW terminal and rerun this launcher."
        exit 1
    }
}

$PythonCmd = $Python.Executable
$PythonArgs = @($Python.PrefixArguments)

& $PythonCmd @PythonArgs (Join-Path $Here "launcher\stable_launcher.py") --install-root $Here @args
exit $LASTEXITCODE
