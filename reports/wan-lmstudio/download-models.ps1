$ErrorActionPreference = 'Stop'
$reportDir = 'D:\MORPH-Studio\reports\wan-lmstudio'
$env:TEMP='D:\MORPH-Studio\temp'
$env:TMP=$env:TEMP
Set-Location -LiteralPath 'D:\MORPH-Studio'
& curl.exe --parallel --parallel-max 3 --config "$reportDir\models-download.curl"
if ($LASTEXITCODE -ne 0) { throw "Download exit: $LASTEXITCODE" }
$results = foreach ($item in (Get-Content -LiteralPath "$reportDir\models-manifest.json" -Raw | ConvertFrom-Json)) {
    $final = Join-Path ('D:\MORPH-Studio\ComfyUI_windows_portable\ComfyUI\models\' + $item.folder) $item.name
    $part = $final + '.part'
    $size = (Get-Item -LiteralPath $part).Length
    if ($size -ne $item.bytes) { throw "Size mismatch: $($item.name) $size" }
    $actualHash = (Get-FileHash -LiteralPath $part -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $item.sha256) { throw "SHA mismatch: $($item.name)" }
    Move-Item -LiteralPath $part -Destination $final
    [pscustomobject]@{name=$item.name;path=$final;bytes=$size;sha256=$actualHash;verified=$true;time=(Get-Date -Format o)}
    Write-Host "VERIFIED $($item.name)"
}
$results | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath "$reportDir\models-installed.json" -Encoding UTF8
