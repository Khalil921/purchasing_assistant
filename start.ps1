$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed. Stop processes using .venv before retrying.' }
}
& .venv/Scripts/python -c "import fastapi, uvicorn, multipart, docx, pypdf, httpx, dotenv, pydantic"
if ($LASTEXITCODE -ne 0) {
    & .venv/Scripts/python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
}
$runningApp = $null
try {
    $runningApp = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 3
} catch {
    # No responding service; continue with normal startup.
}
if ($null -ne $runningApp) {
    if ($runningApp.service -eq 'caihe-assistant') {
        $liveSchema = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/openapi.json' -TimeoutSec 3
        if ($null -eq $liveSchema.paths.'/api/tasks/{tid}'.delete) {
            throw 'An older backend is running without task deletion support. Press Ctrl+C in its terminal, then run .\start.ps1 again. Refresh the browser after restarting.'
        }
        Write-Host 'Caihe Assistant is already running: http://127.0.0.1:8000'
        return
    }
    throw 'Port 8000 is occupied by another web service. Stop that service before starting Caihe Assistant.'
}
if (-not (Test-Path 'frontend/dist/index.html')) {
    Push-Location frontend
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
}
Write-Host 'Caihe Assistant http://127.0.0.1:8000  Press Ctrl+C to stop.'
& .venv/Scripts/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
