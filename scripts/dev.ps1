#requires -Version 7.0
<#
.SYNOPSIS
Run the local Windows development environment from any working directory.
.EXAMPLE
.\scripts\dev.ps1 ui -Test 'com.example.responsecontrollab.MetaPromptExpansionUiTest'
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('status', 'backend', 'emulator', 'unit', 'build', 'ui')]
    [string]$Action = 'status',
    [string]$Test,
    [string]$Avd,
    [string]$Serial,
    [ValidateRange(5, 300)]
    [int]$ReadyTimeoutSeconds = 90
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$repoRoot = Split-Path -Parent $PSScriptRoot
$androidRoot = Join-Path $repoRoot 'android-app'
$backendRoot = Join-Path $repoRoot 'backend'
$stateRoot = Join-Path $repoRoot '.local/environment'

function Enter-Operation([string]$Name) {
    New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
    try {
        # The OS releases this handle on exit/crash. Never delete a live lock.
        $handle = [IO.File]::Open((Join-Path $stateRoot "$Name.lock"), 'OpenOrCreate', 'ReadWrite', 'None')
    } catch [IO.IOException] {
        throw "$Name is already running through dev.ps1. Wait for that session; do not start another copy."
    }
    $bytes = [Text.Encoding]::UTF8.GetBytes("PID=$PID Action=$Action Started=$([DateTime]::Now.ToString('s'))")
    $handle.SetLength(0)
    $handle.Write($bytes, 0, $bytes.Length)
    $handle.Flush()
    return $handle
}

function Find-Sdk {
    $candidates = @()
    $properties = Join-Path $androidRoot 'local.properties'
    if (Test-Path -LiteralPath $properties) {
        $line = Get-Content -LiteralPath $properties | Where-Object { $_ -match '^\s*sdk\.dir\s*=' } | Select-Object -First 1
        if ($line) { $candidates += ($line -replace '^\s*sdk\.dir\s*=', '').Replace('\\', '\').Replace('\:', ':') }
    }
    $candidates += $env:ANDROID_HOME, $env:ANDROID_SDK_ROOT
    if ($env:LOCALAPPDATA) { $candidates += Join-Path $env:LOCALAPPDATA 'Android/Sdk' }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath (Join-Path $candidate 'platform-tools/adb.exe'))) {
            return [IO.Path]::GetFullPath($candidate)
        }
    }
    throw 'Android SDK not found. Set android-app/local.properties (sdk.dir) or ANDROID_HOME.'
}

function Find-Jdk {
    $candidates = @($env:JAVA_HOME)
    $javaCommand = Get-Command java.exe -ErrorAction SilentlyContinue
    if ($javaCommand) { $candidates += Split-Path -Parent (Split-Path -Parent $javaCommand.Source) }
    if ($env:ProgramFiles) { $candidates += Join-Path $env:ProgramFiles 'Android/Android Studio/jbr' }
    $gradleHome = if ($env:GRADLE_USER_HOME) { $env:GRADLE_USER_HOME } else { Join-Path $env:USERPROFILE '.gradle' }
    $jdkCache = Join-Path $gradleHome 'jdks'
    if (Test-Path -LiteralPath $jdkCache) {
        $candidates += @(Get-ChildItem -LiteralPath $jdkCache -Directory | ForEach-Object {
            $_.FullName
            Get-ChildItem -LiteralPath $_.FullName -Directory | Select-Object -ExpandProperty FullName
        })
    }
    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        $java = Join-Path $candidate 'bin/java.exe'
        if ((Test-Path -LiteralPath $java) -and (Test-Path -LiteralPath (Join-Path $candidate 'bin/javac.exe'))) {
            $version = @(& $java --version 2>$null)
            if ($LASTEXITCODE -eq 0 -and $version.Count -gt 0 -and $version[0] -match '\b(\d+)[.\s]') {
                if ([int]$Matches[1] -ge 17) { return [IO.Path]::GetFullPath($candidate) }
            }
        }
    }
    throw 'JDK 17+ not found. Set JAVA_HOME to an existing JDK; this script does not install tools.'
}

function Get-BackendHealth {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 3 -NoProxy
        if ($health.status -eq 'ok') {
            Write-Host '[backend] /health OK (FastAPI only; OpenAI has not been checked).'
            return $true
        }
    } catch { }
    Write-Host '[backend] /health unavailable or unexpected response.'
    return $false
}

function Invoke-Adb([string]$Adb, [string[]]$Arguments) {
    # Bound each adb client call as well as the overall boot loop.
    $info = [Diagnostics.ProcessStartInfo]::new($Adb)
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    foreach ($argument in $Arguments) { $info.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $info
    try {
        $null = $process.Start()
        $output = $process.StandardOutput.ReadToEndAsync()
        $errors = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(5000)) {
            $process.Kill()
            throw 'adb client timed out after 5 s. Inspect the device/adb server before retrying.'
        }
        $script:LASTEXITCODE = $process.ExitCode
        if ($process.ExitCode -ne 0) { throw "adb failed: $($errors.GetAwaiter().GetResult().Trim())" }
        $output.GetAwaiter().GetResult() -split '\r?\n' | Where-Object { $_ }
    } finally { $process.Dispose() }
}

function Get-Emulators([string]$Adb) {
    $lines = @(Invoke-Adb $Adb @('devices'))
    if ($LASTEXITCODE -ne 0) { throw 'adb devices failed.' }
    foreach ($line in $lines) {
        if ($line -match '^(emulator-\d+)\s+(\S+)') {
            [PSCustomObject]@{ Serial = $Matches[1]; State = $Matches[2] }
        }
    }
}

function Wait-Emulator([string]$Adb, [string]$Device, [Diagnostics.Stopwatch]$Watch) {
    Write-Host "[emulator] Waiting for $Device..."
    while ($Watch.Elapsed.TotalSeconds -lt $ReadyTimeoutSeconds) {
        $devices = @(Get-Emulators $Adb)
        $ready = @($devices | Where-Object { $_.Serial -eq $Device -and $_.State -eq 'device' })
        if ($ready.Count -eq 1) {
            $boot = Invoke-Adb $Adb @('-s', $Device, 'shell', 'getprop', 'sys.boot_completed')
            if ($LASTEXITCODE -eq 0 -and "$boot".Trim() -eq '1') {
                Write-Host "[emulator] $Device ready in $([Math]::Round($Watch.Elapsed.TotalSeconds, 1)) s."
                return $Device
            }
        }
        Start-Sleep -Seconds 2
    }
    throw "Emulator readiness timed out. Check $stateRoot/emulator*.log and the existing process before retrying."
}

function Ensure-Emulator([string]$Sdk) {
    $lock = Enter-Operation 'emulator'
    $watch = [Diagnostics.Stopwatch]::StartNew()
    try {
        $adb = Join-Path $Sdk 'platform-tools/adb.exe'
        $emulator = Join-Path $Sdk 'emulator/emulator.exe'
        $devices = @(Get-Emulators $adb)
        if ($Serial) {
            if ($Serial -notmatch '^emulator-\d+$') { throw '-Serial must identify an Android emulator.' }
            return Wait-Emulator $adb $Serial $watch
        }
        if ($Avd) {
            foreach ($device in $devices) {
                if ($device.State -eq 'device') {
                    $name = @(Invoke-Adb $adb @('-s', $device.Serial, 'emu', 'avd', 'name'))
                    if ($LASTEXITCODE -eq 0 -and $name -contains $Avd) {
                        return Wait-Emulator $adb $device.Serial $watch
                    }
                }
            }
            if ($devices.Count -gt 0) { throw 'Another emulator is connected. Select -Serial or close it before selecting a different AVD.' }
        } elseif ($devices.Count -eq 1) {
            return Wait-Emulator $adb $devices[0].Serial $watch
        } elseif ($devices.Count -gt 1) { throw 'Multiple emulators are connected. Specify -Serial.' }
        $processes = @(Get-Process -Name emulator, 'qemu-system-*' -ErrorAction SilentlyContinue)
        if ($processes.Count -gt 0) {
            throw 'An emulator process already exists but no matching adb device is ready. Check status; no second emulator was started.'
        }
        $avds = @(& $emulator -list-avds)
        if ($LASTEXITCODE -ne 0) { throw 'Cannot list AVDs.' }
        $avds = @($avds | Where-Object { $_.Trim() })
        $selected = $Avd
        if (-not $selected) {
            if ($avds.Count -ne 1) { throw 'Specify -Avd from the installed AVDs (emulator -list-avds).' }
            $selected = $avds[0]
        }
        if ($selected -notin $avds -or $selected -notmatch '^[\w.-]+$') { throw 'Unknown or unsupported AVD name.' }
        Write-Host "[emulator] Starting $selected with Quick Boot enabled; readiness limit $ReadyTimeoutSeconds s."
        $startOptions = @{
            FilePath = $emulator
            ArgumentList = @('-avd', $selected, '-no-audio')
            WindowStyle = 'Hidden'
            PassThru = $true
            RedirectStandardOutput = Join-Path $stateRoot 'emulator.stdout.log'
            RedirectStandardError = Join-Path $stateRoot 'emulator.stderr.log'
        }
        $child = Start-Process @startOptions
        Write-Host "[emulator] Launcher PID: $($child.Id)"
        while ($watch.Elapsed.TotalSeconds -lt $ReadyTimeoutSeconds) {
            $devices = @(Get-Emulators $adb)
            if ($devices.Count -eq 1) { return Wait-Emulator $adb $devices[0].Serial $watch }
            if ($devices.Count -gt 1) { throw 'Multiple emulators appeared. Select -Serial explicitly.' }
            if ($child.HasExited) { throw "Emulator exited before connecting. Check $stateRoot/emulator.stderr.log." }
            Start-Sleep -Seconds 2
        }
        throw "Emulator did not connect in $ReadyTimeoutSeconds s. Check existing processes and emulator logs before retrying."
    } finally { $lock.Dispose() }
}

$watch = [Diagnostics.Stopwatch]::StartNew()
$operationLock = $null
$oldJavaHome = $env:JAVA_HOME
$oldAndroidSerial = $env:ANDROID_SERIAL
$exitCode = 0
try {
    if ($Test -and $Action -notin @('unit', 'ui')) { throw '-Test is supported only for unit or ui.' }
    if (($Avd -or $Serial) -and $Action -notin @('emulator', 'ui')) { throw '-Avd/-Serial is supported only for emulator or ui.' }
    if ($Avd -and $Serial) { throw 'Use either -Avd or -Serial.' }
    switch ($Action) {
        'status' {
            foreach ($tool in @('JDK', 'SDK')) {
                try {
                    $path = if ($tool -eq 'JDK') { Find-Jdk } else { Find-Sdk }
                    Write-Host "[$tool] $path"
                } catch { Write-Host "[$tool] $($_.Exception.Message)"; $exitCode = 1 }
            }
            $hasPython = Test-Path -LiteralPath (Join-Path $backendRoot '.venv/Scripts/python.exe')
            Write-Host "[backend] Python present: $hasPython"
            if (-not $hasPython) { $exitCode = 1 }
            if (-not (Get-BackendHealth)) { $exitCode = 1 }
            Get-Process -Name java, emulator, 'qemu-system-*', python -ErrorAction SilentlyContinue |
                Select-Object ProcessName, Id | Format-Table -AutoSize | Out-Host
            Write-Host '[status] Java processes can be idle daemons; a running process alone is not a hung build.'
        }
        'backend' {
            $operationLock = Enter-Operation 'backend'
            $python = Join-Path $backendRoot '.venv/Scripts/python.exe'
            if (-not (Test-Path -LiteralPath $python)) { throw 'Create backend/.venv and install backend/requirements.txt first.' }
            $listeners = @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
            if ($listeners.Count -gt 0) {
                $null = Get-BackendHealth
                throw "Port 8000 is already in use (PID: $($listeners.OwningProcess -join ', ')). Use that session or inspect its owner; no process was stopped."
            }
            $arguments = @('-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000')
            if (Test-Path -LiteralPath (Join-Path $backendRoot '.env')) { $arguments += @('--env-file', '.env') }
            Write-Host '[backend] Starting in this terminal; logs stay here. Use another terminal for status/tests. Ctrl+C stops this server.'
            Push-Location -LiteralPath $backendRoot
            try { & $python @arguments; $exitCode = $LASTEXITCODE } finally { Pop-Location }
        }
        'emulator' { $null = Ensure-Emulator (Find-Sdk) }
        default {
            $operationLock = Enter-Operation 'gradle'
            $env:JAVA_HOME = Find-Jdk
            Write-Host "[gradle] JAVA_HOME=$env:JAVA_HOME"
            $tasks = switch ($Action) {
                'unit' { @('testDebugUnitTest') }
                'build' { @('assembleDebug') }
                'ui' { @('connectedDebugAndroidTest') }
            }
            $arguments = @($tasks) + @('--console=plain', '--daemon', '--configuration-cache')
            if ($Action -eq 'ui') {
                if ($Test -and $Test -notmatch '^[\w.$]+(#[\w$]+)?$') { throw 'UI -Test must be a fully qualified class, optionally followed by #method.' }
                $env:ANDROID_SERIAL = Ensure-Emulator (Find-Sdk)
                if ($Test) { $arguments += "-Pandroid.testInstrumentationRunnerArguments.class=$Test" }
                Write-Host "[ui] Device=$env:ANDROID_SERIAL; backend and OpenAI are not needed for the current UI tests."
            } elseif ($Test) { $arguments += @('--tests', $Test) }
            Write-Host "[gradle] Tasks: $($tasks -join ', '). Keep other CLI/Android Studio builds idle in this checkout."
            $buildWatch = [Diagnostics.Stopwatch]::StartNew()
            Push-Location -LiteralPath $androidRoot
            try { & '.\gradlew.bat' @arguments; $exitCode = $LASTEXITCODE } finally { Pop-Location }
            Write-Host "[gradle] Finished in $([Math]::Round($buildWatch.Elapsed.TotalSeconds, 1)) s; exit=$exitCode."
        }
    }
} catch {
    Write-Host "[error] $($_.Exception.Message)" -ForegroundColor Red
    $exitCode = 1
} finally {
    if ($operationLock) { $operationLock.Dispose() }
    $env:JAVA_HOME = $oldJavaHome
    $env:ANDROID_SERIAL = $oldAndroidSerial
    Write-Host "[$Action] Total $([Math]::Round($watch.Elapsed.TotalSeconds, 1)) s."
}
exit $exitCode
