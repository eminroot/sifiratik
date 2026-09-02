<#
    GÜS-DEDEKTİV launcher.

    Starts the API and the interface together, waits until both actually
    answer, opens the browser, and streams both logs into this one window.
    Ctrl+C or Q stops both.

    Run it from start.bat, or directly:

        powershell -ExecutionPolicy Bypass -File scripts\start.ps1
#>

[CmdletBinding()]
param(
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173,
    [switch]$NoBrowser,
    [switch]$Install,
    [switch]$Reseed
)

$ErrorActionPreference = 'Stop'

$Root = Split-Path $PSScriptRoot -Parent
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$RunDir = Join-Path $Root '.run'

$ApiUrl = "http://127.0.0.1:$ApiPort"
$WebUrl = "http://localhost:$WebPort"

# ---------------------------------------------------------------- helpers --

function Write-Step($text) { Write-Host "  $text" -ForegroundColor DarkGray }
function Write-Good($text) { Write-Host "  $text" -ForegroundColor Green }
function Write-Warn($text) { Write-Host "  $text" -ForegroundColor Yellow }
function Write-Bad($text) { Write-Host "  $text" -ForegroundColor Red }

function Write-Banner {
    Write-Host ''
    Write-Host '  GUS-DEDEKTIV' -ForegroundColor White
    Write-Host '  Inspection prioritisation for GEKAP declarations' -ForegroundColor DarkGray
    Write-Host ''
}

function Test-Port([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $client.Connect('127.0.0.1', $Port)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Test-Endpoint([string]$Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Resolve-Python {
    foreach ($candidate in @('python', 'python3')) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($null -ne $command) {
            $version = & $candidate --version
            if ($LASTEXITCODE -eq 0) { return @{ Exe = $command.Source; Version = $version } }
        }
    }
    $launcher = Get-Command 'py' -ErrorAction SilentlyContinue
    if ($null -ne $launcher) {
        $version = & py -3 --version
        if ($LASTEXITCODE -eq 0) { return @{ Exe = 'py'; Version = $version; Prefix = @('-3') } }
    }
    return $null
}

# Track what we start so a window closed with the X can still be cleaned up
# on the next run, when the OS has left the processes behind.
function Stop-Tree([int]$ProcessId) {
    if ($ProcessId -le 0) { return }
    $running = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($null -eq $running) { return }
    Start-Process -FilePath 'taskkill.exe' -ArgumentList '/PID', $ProcessId, '/T', '/F' `
        -NoNewWindow -Wait -ErrorAction SilentlyContinue | Out-Null
}

function Stop-Previous {
    if (-not (Test-Path $RunDir)) { return }
    foreach ($file in Get-ChildItem -Path $RunDir -Filter '*.pid' -ErrorAction SilentlyContinue) {
        $recorded = 0
        if ([int]::TryParse((Get-Content $file.FullName -Raw).Trim(), [ref]$recorded)) {
            $process = Get-Process -Id $recorded -ErrorAction SilentlyContinue
            # Only ours: a leftover launcher child is always a cmd wrapper.
            if ($null -ne $process -and $process.ProcessName -eq 'cmd') {
                Write-Step "Clearing a process left behind by an earlier run (pid $recorded)"
                Stop-Tree $recorded
            }
        }
        Remove-Item $file.FullName -Force -ErrorAction SilentlyContinue
    }
}

function Start-Service([string]$Name, [string]$WorkingDirectory, [string]$CommandLine, [string]$LogPath) {
    if (Test-Path $LogPath) { Remove-Item $LogPath -Force -ErrorAction SilentlyContinue }

    # cmd.exe wraps the command so both streams land in one file, which keeps
    # the log readable when a traceback and ordinary output interleave.
    $arguments = '/c "' + $CommandLine + '" > "' + $LogPath + '" 2>&1'
    $process = Start-Process -FilePath $env:ComSpec -ArgumentList $arguments `
        -WorkingDirectory $WorkingDirectory -NoNewWindow -PassThru

    Set-Content -Path (Join-Path $RunDir "$Name.pid") -Value $process.Id -Encoding ascii
    return $process
}

function Get-LogTail([string]$Path, [int]$Lines = 18) {
    if (-not (Test-Path $Path)) { return @() }
    try {
        return Get-Content -Path $Path -Tail $Lines -ErrorAction SilentlyContinue
    } catch {
        return @()
    }
}

function New-Follower([string]$Path, [string]$Tag, [string]$Colour) {
    return [pscustomobject]@{ Path = $Path; Tag = $Tag; Colour = $Colour; Position = 0 }
}

function Show-NewOutput($Follower) {
    if (-not (Test-Path $Follower.Path)) { return }
    $length = (Get-Item $Follower.Path).Length
    if ($length -lt $Follower.Position) { $Follower.Position = 0 }
    if ($length -eq $Follower.Position) { return }

    # Shared read: the child process still has the file open for writing.
    $stream = [System.IO.File]::Open($Follower.Path, 'Open', 'Read', 'ReadWrite')
    try {
        $stream.Seek($Follower.Position, 'Begin') | Out-Null
        $reader = New-Object System.IO.StreamReader($stream)
        $text = $reader.ReadToEnd()
        $Follower.Position = $stream.Position
    } finally {
        $stream.Close()
    }

    foreach ($line in ($text -split "`r?`n")) {
        if ($line.Trim() -ne '') {
            Write-Host ('  ' + $Follower.Tag + ' ') -ForegroundColor $Follower.Colour -NoNewline
            Write-Host $line -ForegroundColor Gray
        }
    }
}

# ------------------------------------------------------------------ checks --

Clear-Host
Write-Banner

$python = Resolve-Python
if ($null -eq $python) {
    Write-Bad 'Python was not found on PATH.'
    Write-Step 'Install Python 3.11 or newer from python.org, then run this again.'
    Read-Host '  Press Enter to close'
    exit 1
}

$npm = Get-Command 'npm' -ErrorAction SilentlyContinue
if ($null -eq $npm) {
    Write-Bad 'npm was not found on PATH.'
    Write-Step 'Install Node.js 20 or newer from nodejs.org, then run this again.'
    Read-Host '  Press Enter to close'
    exit 1
}

$pythonExe = $python.Exe
$pythonPrefix = @()
if ($python.ContainsKey('Prefix')) { $pythonPrefix = $python.Prefix }
$pythonCommand = $pythonExe
if ($pythonPrefix.Count -gt 0) { $pythonCommand = "$pythonExe $($pythonPrefix -join ' ')" }

Write-Step "$($python.Version.Trim())  ·  npm $(& npm --version)"

New-Item -ItemType Directory -Path $RunDir -Force | Out-Null
Stop-Previous

# ---------------------------------------------------------------- installs --

Push-Location $Backend
try {
    $needsInstall = $Install.IsPresent
    if (-not $needsInstall) {
        & $pythonExe @pythonPrefix -c 'import fastapi, sqlalchemy, pydantic, uvicorn' 2>$null
        if ($LASTEXITCODE -ne 0) { $needsInstall = $true }
    }
    if ($needsInstall) {
        Write-Step 'Installing backend dependencies, first run only'
        & $pythonExe @pythonPrefix -m pip install -r requirements.txt --quiet --disable-pip-version-check
        if ($LASTEXITCODE -ne 0) {
            Write-Bad 'Backend dependencies failed to install.'
            Read-Host '  Press Enter to close'
            exit 1
        }
    }

    if ($Reseed.IsPresent) {
        Write-Step 'Rebuilding the dataset'
        & $pythonExe @pythonPrefix -m app.database.seed --reset
    }
} finally {
    Pop-Location
}

if ($Install.IsPresent -or -not (Test-Path (Join-Path $Frontend 'node_modules'))) {
    Write-Step 'Installing frontend dependencies, this takes a minute'
    Push-Location $Frontend
    try {
        & npm install --no-audit --no-fund --silent
        if ($LASTEXITCODE -ne 0) {
            Write-Bad 'Frontend dependencies failed to install.'
            Read-Host '  Press Enter to close'
            exit 1
        }
    } finally {
        Pop-Location
    }
}

# ------------------------------------------------------------------- start --

$apiLog = Join-Path $RunDir 'api.log'
$webLog = Join-Path $RunDir 'web.log'
$apiProcess = $null
$webProcess = $null

$apiAlreadyUp = Test-Endpoint "$ApiUrl/api/health"
if ($apiAlreadyUp) {
    Write-Warn "Port $ApiPort is already serving the API, reusing it"
} elseif (Test-Port $ApiPort) {
    Write-Bad "Port $ApiPort is taken by something else. Free it, or pass -ApiPort."
    Read-Host '  Press Enter to close'
    exit 1
} else {
    Write-Step "Starting the API on port $ApiPort"
    $apiProcess = Start-Service 'api' $Backend `
        "$pythonCommand -m uvicorn app.main:app --host 127.0.0.1 --port $ApiPort --reload" $apiLog
}

$webAlreadyUp = Test-Port $WebPort
if ($webAlreadyUp) {
    Write-Warn "Port $WebPort is already in use, reusing it"
} else {
    Write-Step "Starting the interface on port $WebPort"
    $webProcess = Start-Service 'web' $Frontend "npm run dev -- --port $WebPort" $webLog
}

# ------------------------------------------------------------------- wait --

try {
    if (-not $apiAlreadyUp) {
        Write-Step 'Waiting for the API, it seeds itself on first boot'
        $ready = $false
        for ($i = 0; $i -lt 150; $i++) {
            if ($null -ne $apiProcess -and $apiProcess.HasExited) { break }
            if (Test-Endpoint "$ApiUrl/api/health") { $ready = $true; break }
            Start-Sleep -Milliseconds 400
        }
        if (-not $ready) {
            Write-Bad 'The API did not come up.'
            Get-LogTail $apiLog | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
            Stop-Tree $(if ($null -ne $webProcess) { $webProcess.Id } else { 0 })
            Read-Host '  Press Enter to close'
            exit 1
        }
    }
    Write-Good "API ready          $ApiUrl/docs"

    if (-not $webAlreadyUp) {
        $ready = $false
        for ($i = 0; $i -lt 120; $i++) {
            if ($null -ne $webProcess -and $webProcess.HasExited) { break }
            if (Test-Port $WebPort) { $ready = $true; break }
            Start-Sleep -Milliseconds 400
        }
        if (-not $ready) {
            Write-Bad 'The interface did not come up.'
            Get-LogTail $webLog | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
            Stop-Tree $(if ($null -ne $apiProcess) { $apiProcess.Id } else { 0 })
            Read-Host '  Press Enter to close'
            exit 1
        }
    }
    Write-Good "Interface ready    $WebUrl"

    if (-not $NoBrowser.IsPresent) { Start-Process $WebUrl | Out-Null }

    Write-Host ''
    Write-Host '  Ctrl+C or Q stops both. Logs below.' -ForegroundColor DarkGray
    Write-Host ''

    $followers = @(
        (New-Follower $apiLog 'api' 'DarkCyan'),
        (New-Follower $webLog 'web' 'DarkYellow')
    )
    # Skip the output produced before the banner, it has already been summarised.
    foreach ($follower in $followers) {
        if (Test-Path $follower.Path) { $follower.Position = (Get-Item $follower.Path).Length }
    }

    $interactive = $true
    try { $null = [Console]::KeyAvailable } catch { $interactive = $false }
    if ($interactive) { [Console]::TreatControlCAsInput = $true }

    while ($true) {
        if ($interactive -and [Console]::KeyAvailable) {
            $key = [Console]::ReadKey($true)
            $isCtrlC = (($key.Modifiers -band [ConsoleModifiers]::Control) -ne 0) -and ($key.Key -eq 'C')
            if ($isCtrlC -or $key.Key -eq 'Q') { break }
        }

        foreach ($follower in $followers) { Show-NewOutput $follower }

        if ($null -ne $apiProcess -and $apiProcess.HasExited) {
            Write-Bad 'The API stopped.'
            break
        }
        if ($null -ne $webProcess -and $webProcess.HasExited) {
            Write-Bad 'The interface stopped.'
            break
        }

        Start-Sleep -Milliseconds 250
    }
} finally {
    Write-Host ''
    Write-Step 'Stopping'
    if ($null -ne $apiProcess) { Stop-Tree $apiProcess.Id }
    if ($null -ne $webProcess) { Stop-Tree $webProcess.Id }
    Get-ChildItem -Path $RunDir -Filter '*.pid' -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue
    try { [Console]::TreatControlCAsInput = $false } catch { }
    Write-Host ''
}
