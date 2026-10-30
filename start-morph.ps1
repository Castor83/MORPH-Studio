$ErrorActionPreference = 'Stop'

function Invoke-MorphGuardProcess([string]$PythonPath, [string]$GuardPath, [string]$Mode) {
    if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) { throw 'Die MORPH-Python-Laufzeit fehlt.' }
    if (-not (Test-Path -LiteralPath $GuardPath -PathType Leaf)) { throw 'Die MORPH-Dienstverwaltung fehlt.' }
    & $PythonPath -B -X utf8 $GuardPath $Mode
    if ($LASTEXITCODE -ne 0) { throw 'MORPH konnte den Rechendienst nicht bereitstellen. Die genaue Ursache steht oben.' }
}

function Invoke-MorphStart([string]$ProjectRoot = $PSScriptRoot) {
    Invoke-MorphGuardProcess -PythonPath (Join-Path $ProjectRoot 'ComfyUI_windows_portable\python_embeded\python.exe') -GuardPath (Join-Path $ProjectRoot 'tools\lmstudio-wan-chat\start_mcp.py') -Mode '--start-only'
}

if ($MyInvocation.InvocationName -ne '.') {
    try { Invoke-MorphStart -ProjectRoot $PSScriptRoot; exit 0 }
    catch { Write-Error $_ -ErrorAction Continue; exit 1 }
}
