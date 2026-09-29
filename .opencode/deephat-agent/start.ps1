param([Parameter(ValueFromRemainingArguments=$true)][string[]]$OpenCodeArgs)
$ErrorActionPreference = 'Stop'
$ownedBridge = $null
$savedConfig = $env:OPENCODE_CONFIG
$adapterDir = $PSScriptRoot
$pythonPath = 'C:\Python313\python.exe'

try {
    & $pythonPath -c 'import jsonschema' 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw 'Missing jsonschema. Install it with: python -m pip install -r requirements.txt'
    }
    $ollamaVersion = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 3
    $health = $null
    try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:11435/health' -TimeoutSec 2 } catch {}
    if ($health -and ($health.service -ne 'deephat-agent' -or $health.version -ne 1)) {
        throw 'Port 11435 is occupied by another service.'
    }
    if (-not $health) {
        $bridgePath = Join-Path $adapterDir 'bridge.py'
        $ownedBridge = Start-Process -FilePath $pythonPath -ArgumentList @('-u', ('"' + $bridgePath + '"'), '--port', '11435') -WindowStyle Hidden -PassThru
        for ($attempt = 0; $attempt -lt 50; $attempt++) {
            if ($ownedBridge.HasExited) { throw 'The DeepHat adapter could not start. Port 11435 may already be in use.' }
            try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:11435/health' -TimeoutSec 1 } catch {}
            if ($health.service -eq 'deephat-agent' -and $health.version -eq 1) { break }
            Start-Sleep -Milliseconds 100
        }
        if (-not $health) { throw 'The DeepHat adapter did not become ready.' }
    }
    $env:OPENCODE_CONFIG = Join-Path $adapterDir 'opencode.json'
    & opencode @OpenCodeArgs --model deephat-agent/deephat --agent deephat
    $resultCode = $LASTEXITCODE
} finally {
    $env:OPENCODE_CONFIG = $savedConfig
    if ($ownedBridge -and -not $ownedBridge.HasExited) {
        Stop-Process -InputObject $ownedBridge
    }
}
exit $resultCode
