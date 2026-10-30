param([switch]$NoBrowser, [switch]$Restart)
$ErrorActionPreference = 'Stop'

# Resolve junctions through the project's own interpreter; no model is imported.
$initialPython = Join-Path $PSScriptRoot 'ComfyUI_windows_portable\python_embeded\python.exe'
if (-not (Test-Path -LiteralPath $initialPython -PathType Leaf)) { throw 'Die MORPH-Python-Laufzeit fehlt im Projektordner.' }
$root = (& $initialPython -B -c 'import sys; from pathlib import Path; print(Path(sys.argv[1]).resolve())' $PSScriptRoot | Select-Object -Last 1)
if ($LASTEXITCODE -ne 0 -or -not $root) { throw 'Der MORPH-Projektpfad konnte nicht aufgelöst werden.' }
$python = Join-Path $root 'ComfyUI_windows_portable\python_embeded\python.exe'
$entry = Join-Path $root 'ui\morph_ui\__main__.py'
$logDir = Join-Path $root 'logs\morph-ui'
$dataDir = Join-Path $root 'user\morph-ui'
$tempDir = Join-Path $root 'temp\morph-ui'
foreach ($directory in @($logDir,$dataDir,$tempDir)) { New-Item -ItemType Directory -Path $directory -Force | Out-Null }
$env:TEMP = $tempDir
$env:TMP = $tempDir
$receiptPath = Join-Path $dataDir 'startup.json'

if (-not ('MorphCommandLine' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class MorphCommandLine {
    [DllImport("shell32.dll", SetLastError=true)] static extern IntPtr CommandLineToArgvW([MarshalAs(UnmanagedType.LPWStr)] string command, out int count);
    [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr memory);
    public static string[] Split(string command) {
        int count; IntPtr memory = CommandLineToArgvW(command, out count);
        if (memory == IntPtr.Zero) throw new InvalidOperationException("Prozessargumente nicht lesbar.");
        try { string[] result = new string[count]; for(int i=0;i<count;i++) result[i]=Marshal.PtrToStringUni(Marshal.ReadIntPtr(memory,i*IntPtr.Size)); return result; }
        finally { LocalFree(memory); }
    }
}
'@
}
Add-Type -AssemblyName System.Net.Http
$handler = New-Object System.Net.Http.HttpClientHandler
$handler.UseProxy = $false
$http = New-Object System.Net.Http.HttpClient($handler)
$http.Timeout = [TimeSpan]::FromSeconds(3)
$http.MaxResponseContentBufferSize = 1048576

function Get-UiProcess([int]$processId) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction Stop
    if (-not $process -or -not $process.ExecutablePath -or -not $process.CommandLine -or -not $process.CreationDate) { throw 'Der Prozess auf dem Oberflächenport lässt sich nicht eindeutig prüfen.' }
    $arguments = [MorphCommandLine]::Split($process.CommandLine)
    if ($process.ExecutablePath -ine $python -or $arguments.Count -ne 3 -or $arguments[0] -ine $python -or $arguments[1] -cne '-B' -or $arguments[2] -ine $entry) {
        throw 'Port 8877 gehört einem anderen Dienst. MORPH beendet diesen Dienst nicht.'
    }
    return $process
}
function Get-UiListener {
    $listeners = @(Get-NetTCPConnection -LocalPort 8877 -State Listen -ErrorAction SilentlyContinue)
    if (-not $listeners.Count) { return $null }
    $owners = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($owners.Count -ne 1 -or @($listeners | Where-Object LocalAddress -ne '127.0.0.1').Count) {
        throw 'Port 8877 ist durch einen fremden oder nicht ausschließlich lokalen Dienst belegt.'
    }
    return Get-UiProcess $owners[0]
}
function Test-UiHealth($process) {
    try {
        $response = $http.GetAsync('http://127.0.0.1:8877/api/health').GetAwaiter().GetResult()
        try {
            if ([int]$response.StatusCode -ne 200) { return $false }
            $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult() | ConvertFrom-Json
        } finally { $response.Dispose() }
        if (-not $body.ok -or $body.data.app -cne 'morph-ui' -or $body.data.version -cne '1.0' -or $body.data.project_root -ine $root -or [int]$body.data.pid -ne [int]$process.ProcessId) { return $false }
        $again = Get-UiListener
        return ($again -and $again.ProcessId -eq $process.ProcessId -and $again.CreationDate -eq $process.CreationDate)
    } catch { return $false }
}

$lock = $null
try {
    $lockPath = Join-Path $dataDir 'startup.lock'
    $deadline = [DateTime]::UtcNow.AddSeconds(25)
    while (-not $lock) {
        try { $lock = [IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None) }
        catch [IO.IOException] { if ([DateTime]::UtcNow -ge $deadline) { throw 'Ein anderer MORPH-Start ist noch beschäftigt. Bitte kurz warten.' }; Start-Sleep -Milliseconds 250 }
    }
    $listener = Get-UiListener
    if ($Restart -and $listener) {
        if (-not (Test-UiHealth $listener)) { throw 'Die laufende Oberfläche ist nicht eindeutig bestätigt; kein Neustart ausgeführt.' }
        $restartRequest = New-Object System.Net.Http.HttpRequestMessage([System.Net.Http.HttpMethod]::Post, 'http://127.0.0.1:8877/api/service/prepare-restart')
        $restartRequest.Headers.Add('X-MORPH-Request','1')
        $restartRequest.Headers.Add('Origin','http://127.0.0.1:8877')
        $restartRequest.Content = New-Object System.Net.Http.StringContent('{}',[Text.Encoding]::UTF8,'application/json')
        $response = $http.SendAsync($restartRequest).GetAwaiter().GetResult()
        try {
            if ([int]$response.StatusCode -ne 200) { throw 'Neustart nicht freigegeben: laufende/ungeklärte Aufträge oder ältere Oberfläche ohne sichere Neustartsperre.' }
            $restartState = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult() | ConvertFrom-Json
        } finally { $response.Dispose(); $restartRequest.Dispose() }
        if (-not $restartState.ok -or -not $restartState.data.ready -or [int]$restartState.data.pid -ne [int]$listener.ProcessId -or $restartState.data.project_root -ine $root) {
            throw 'Die Oberfläche hat den sicheren Neustart nicht eindeutig bestätigt.'
        }
        $again = Get-UiListener
        if (-not $again -or $again.ProcessId -ne $listener.ProcessId -or $again.CreationDate -ne $listener.CreationDate) { throw 'Der Oberflächenprozess hat sich verändert; kein Neustart ausgeführt.' }
        Stop-Process -Id $listener.ProcessId -ErrorAction Stop
        Wait-Process -Id $listener.ProcessId -Timeout 10 -ErrorAction SilentlyContinue
        $listener = Get-UiListener
        if ($listener) { throw 'Der Oberflächenport ist nach dem Beenden erneut belegt; kein weiterer Prozess wird beendet.' }
    }
    $startingProcess = $null
    if (-not $listener -and (Test-Path -LiteralPath $receiptPath)) {
        $saved = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
        $candidate = Get-CimInstance Win32_Process -Filter "ProcessId = $([int]$saved.pid)" -ErrorAction Stop
        if ($candidate -and $candidate.CreationDate.ToUniversalTime().ToString('o') -ceq $saved.created_at) { $startingProcess = Get-UiProcess $candidate.ProcessId }
    }
    if (-not $listener -and -not $startingProcess) {
        $child = Start-Process -FilePath $python -ArgumentList @('-B',('"'+$entry+'"')) -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'startup-out.log') -RedirectStandardError (Join-Path $logDir 'startup-error.log')
        $startingProcess = Get-UiProcess $child.Id
        @{pid=$startingProcess.ProcessId;created_at=$startingProcess.CreationDate.ToUniversalTime().ToString('o');project_root=$root} | ConvertTo-Json | Set-Content -LiteralPath $receiptPath -Encoding UTF8
    }
    $ready = $false
    $deadline = [DateTime]::UtcNow.AddSeconds(25)
    do {
        $listener = Get-UiListener
        if ($listener -and (Test-UiHealth $listener)) { $ready = $true; break }
        if ([DateTime]::UtcNow -ge $deadline) { break }
        Start-Sleep -Milliseconds 350
    } while ($true)
    if (-not $ready) { throw "Die Oberfläche hat ihren Start nicht bestätigt. Protokoll: $logDir\startup-error.log" }
    Write-Output "MORPH-Oberfläche bereit: http://127.0.0.1:8877 (Projekt: $root)"
} finally {
    if ($lock) { $lock.Dispose() }
    $http.Dispose()
    $handler.Dispose()
}
if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:8877' }
