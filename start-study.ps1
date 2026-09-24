$ErrorActionPreference = 'Stop'
$studyRoot = $PSScriptRoot
$studyUrl = 'http://127.0.0.1:8765'
$studyPython = 'E:\miniconda\python.exe'
if (-not (Test-Path -LiteralPath $studyPython)) {
    $studyPython = (Get-Command python -ErrorAction Stop).Source
}
try {
    $studyResponse = Invoke-WebRequest -Uri "$studyUrl/api/bootstrap" -UseBasicParsing -TimeoutSec 2
    $studyRunning = $studyResponse.StatusCode -eq 200
} catch {
    $studyRunning = $false
}
if (-not $studyRunning) {
    New-Item -ItemType Directory -Path (Join-Path $studyRoot 'data') -Force | Out-Null
    Start-Process -FilePath $studyPython -ArgumentList 'app.py' -WorkingDirectory $studyRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $studyRoot 'data/server.log') -RedirectStandardError (Join-Path $studyRoot 'data/server-error.log') | Out-Null
    for ($studyAttempt = 0; $studyAttempt -lt 20; $studyAttempt++) {
        Start-Sleep -Milliseconds 400
        try {
            Invoke-WebRequest -Uri "$studyUrl/api/bootstrap" -UseBasicParsing -TimeoutSec 1 | Out-Null
            $studyRunning = $true
            break
        } catch {}
    }
}
if (-not $studyRunning) { throw 'The study server did not start. Check data/server-error.log.' }
Start-Process $studyUrl
