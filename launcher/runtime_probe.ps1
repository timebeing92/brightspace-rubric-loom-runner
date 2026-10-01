# Shared bounded startup probe for Windows PowerShell 5.1 and PowerShell 7.
function ConvertTo-PythonArgument([string]$Value) {
    # ProcessStartInfo.Arguments uses Windows command-line quoting on 5.1;
    # ArgumentList is only available on newer .NET runtimes.
    $escaped = $Value -replace '(\\*)"', '$1$1\"'
    $escaped = $escaped -replace '(\\+)$', '$1$1'
    return '"' + $escaped + '"'
}

function Test-Python([string[]]$Command) {
    $process = New-Object System.Diagnostics.Process
    $started = $false
    try {
        $probeArgs = @()
        if ($Command.Count -gt 1) { $probeArgs = @($Command[1..($Command.Count - 1)]) }
        $probeArgs += @("-I", "-c", "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)")
        $process.StartInfo.FileName = $Command[0]
        $process.StartInfo.Arguments = ($probeArgs | ForEach-Object { ConvertTo-PythonArgument $_ }) -join " "
        $process.StartInfo.UseShellExecute = $false
        $process.StartInfo.CreateNoWindow = $true
        $process.StartInfo.RedirectStandardInput = $true
        $process.StartInfo.RedirectStandardOutput = $true
        $process.StartInfo.RedirectStandardError = $true
        $started = $process.Start()
        if (-not $started) { return $false }
        $process.StandardInput.Close()
        # Drain both pipes concurrently so unexpected startup output cannot
        # fill a pipe and make an otherwise healthy probe block.
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(5000)) { return $false }
        return $process.ExitCode -eq 0
    } catch {
        return $false
    } finally {
        if ($started) {
            try {
                if (-not $process.HasExited) {
                    $process.Kill()
                    $null = $process.WaitForExit(1000)
                }
            } catch { }
        }
        $process.Dispose()
    }
}

function Invoke-LoomPython([string]$Executable, [string[]]$Arguments) {
    # Windows PowerShell 5.1's native argument marshalling can split values
    # such as --label="two words". Use the same explicit quoting as the probe,
    # while inheriting the terminal streams for the interactive Loom session.
    $process = New-Object System.Diagnostics.Process
    try {
        $process.StartInfo.FileName = $Executable
        $process.StartInfo.Arguments = ($Arguments | ForEach-Object { ConvertTo-PythonArgument $_ }) -join " "
        $process.StartInfo.UseShellExecute = $false
        $null = $process.Start()
        $process.WaitForExit()
        return $process.ExitCode
    } finally {
        $process.Dispose()
    }
}
