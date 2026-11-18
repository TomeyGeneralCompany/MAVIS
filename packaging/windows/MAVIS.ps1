# MAVIS Windows launcher + guided WSL setup. No user-typed shell commands.
[CmdletBinding()]
param([ValidateSet('Setup', 'Launch')][string]$Action = 'Launch')

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$Distro = 'Ubuntu'
$LinuxUser = 'mavis'
$WebUrl = 'http://127.0.0.1:8765'
$InstallDeb = Join-Path $PSScriptRoot 'mavis.deb'
$InstallScript = Join-Path $PSScriptRoot 'install-wsl.sh'
$LogFolder = Join-Path $env:LOCALAPPDATA 'MAVIS'
New-Item -ItemType Directory -Force $LogFolder | Out-Null
$LogFile = Join-Path $LogFolder 'windows-launch.log'

function Notice([string]$message, [string]$title = 'MAVIS Setup') {
    [System.Windows.Forms.MessageBox]::Show($message, $title, 'OK', 'Information') | Out-Null
}
function Log([string]$message) {
    Add-Content -Path $LogFile -Value ('{0:o} {1}' -f (Get-Date), $message)
    if ($Action -eq 'Setup') { Write-Host $message }
}
function DistroInstalled {
    # wsl.exe --list --quiet emits NULs on some Windows builds.
    $found = (& "$env:WINDIR\System32\wsl.exe" --list --quiet 2>$null | Out-String) -replace [char]0, ''
    return (($found -split '[\r\n]+' | ForEach-Object { $_.Trim() }) -contains $Distro)
}
function LinuxPath([string]$path) {
    $mapped = & "$env:WINDIR\System32\wsl.exe" -d $Distro -u root -- wslpath -u -a $path
    if ($LASTEXITCODE -ne 0 -or !$mapped) { throw "Cannot map Windows installer path into Ubuntu." }
    return ($mapped | Select-Object -First 1).Trim()
}
function InstalledEngine {
    & "$env:WINDIR\System32\wsl.exe" -d $Distro -u root -- bash -c 'test -x /usr/bin/mavis && test -x /var/lib/mavis/voice/source/build/qwen-tts' 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}
function SetupEngine {
    if (!(Test-Path $InstallDeb) -or !(Test-Path $InstallScript)) {
        throw 'The MAVIS installer is missing its embedded Linux components. Reinstall MAVIS for Windows.'
    }
    if (!(DistroInstalled)) {
        Notice "MAVIS needs Ubuntu inside Windows Subsystem for Linux (WSL). Windows may ask for administrator approval and may require a restart. No Linux commands need to be entered."
        Log 'Installing WSL and Ubuntu with Microsoft tools.'
        & "$env:WINDIR\System32\wsl.exe" --install --distribution $Distro --web-download --no-launch
        if ($LASTEXITCODE -ne 0) {
            throw 'Windows could not finish WSL setup. Check virtualization support, restart Windows, and launch MAVIS again.'
        }
        if (!(DistroInstalled)) {
            Notice "Windows has staged WSL. Restart your computer, then click the MAVIS desktop icon to finish setup."
            return $false
        }
    }
    $linuxDeb = LinuxPath $InstallDeb
    $linuxScript = LinuxPath $InstallScript
    for ($attempt = 0; $attempt -lt 2; $attempt++) {
        Log 'Installing MAVIS runtime, models, and video dependencies. This downloads several GB.'
        & "$env:WINDIR\System32\wsl.exe" -d $Distro -u root -- bash $linuxScript $linuxDeb
        $code = $LASTEXITCODE
        if ($code -eq 75 -and $attempt -eq 0) {
            Log 'Enabling systemd in Ubuntu WSL and restarting the environment.'
            & "$env:WINDIR\System32\wsl.exe" --terminate $Distro | Out-Null
            Start-Sleep -Seconds 3
            continue
        }
        if ($code -ne 0) {
            throw "Ubuntu installation failed (exit $code). See the MAVIS setup output and $LogFile."
        }
        if (InstalledEngine) {
            Log 'MAVIS Ubuntu production runtime installed.'
            return $true
        }
        throw 'Ubuntu completed setup without the MAVIS voice engine.'
    }
    throw 'WSL could not be restarted with systemd enabled. Restart Windows and open MAVIS again.'
}
function LaunchEngine {
    if (!(DistroInstalled) -or !(InstalledEngine)) {
        # First launch completes installation; it is not a command the user types.
        Notice "MAVIS needs to finish its one-time setup. Approve the Windows setup prompt. A restart may be required."
        $args = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'), '-Action', 'Setup')
        $setup = Start-Process -FilePath 'powershell.exe' -ArgumentList $args -Verb RunAs -Wait -PassThru
        if ($setup.ExitCode -ne 0 -or !(InstalledEngine)) { return }
    }
    try {
        $response = Invoke-WebRequest $WebUrl -UseBasicParsing -TimeoutSec 2
        if ($response.StatusCode -eq 200) { Start-Process $WebUrl; return }
    } catch { }
    Log 'Starting MAVIS Linux application inside WSL.'
    Start-Process -FilePath "$env:WINDIR\System32\wsl.exe" -ArgumentList @(
        '-d', $Distro, '-u', $LinuxUser, '--', '/usr/bin/mavis', '--no-browser', '--port', '8765'
    ) -WindowStyle Hidden | Out-Null
    for ($i = 0; $i -lt 300; $i++) {
        Start-Sleep -Seconds 2
        try {
            $response = Invoke-WebRequest $WebUrl -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                Start-Process $WebUrl
                return
            }
        } catch { }
    }
    throw "MAVIS didn't start within ten minutes. Check the Ubuntu runtime and $LogFile."
}
try {
    if ($Action -eq 'Setup') {
        if (SetupEngine) { Notice 'MAVIS setup completed. Click the MAVIS desktop icon to open your browser dashboard.' }
    } else {
        LaunchEngine
    }
} catch {
    Log ('ERROR: ' + $_.Exception.Message)
    [System.Windows.Forms.MessageBox]::Show(
        $_.Exception.Message, 'MAVIS Setup Problem', 'OK', 'Error'
    ) | Out-Null
    exit 1
}
