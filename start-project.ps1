$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$pythonPath = Join-Path $PSScriptRoot "ai\component4-medicine\.venv\Scripts\python.exe"
$envPath = Join-Path $PSScriptRoot "ai\component4-medicine\.env"

if (-not (Test-Path $pythonPath)) {
    throw "Medicine Python environment was not found: $pythonPath"
}

if (-not (Test-Path $envPath)) {
    throw "Create ai/component4-medicine/.env before starting."
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Check your Node.js installation."
}

$occupiedPorts = @()

foreach ($port in @(3000, 8000)) {
    $listener = Get-NetTCPConnection `
        -LocalPort $port `
        -State Listen `
        -ErrorAction SilentlyContinue

    if ($listener) {
        $occupiedPorts += $port
    }
}

if ($occupiedPorts.Count -gt 0) {
    Write-Host ""
    Write-Host "Already running on port(s): $($occupiedPorts -join ', ')" -ForegroundColor Yellow
    Write-Host "Stop the existing frontend/API terminals with Ctrl+C, then run this script again."
    exit 1
}

$medicineCommand = @"
`$Host.UI.RawUI.WindowTitle = 'Medicine API + Groq'
& '.\ai\component4-medicine\.venv\Scripts\python.exe' -m uvicorn main:app --app-dir ai/component4-medicine/src --host 127.0.0.1 --port 8000 --env-file ai/component4-medicine/.env
"@

$backendCommand = @"
`$Host.UI.RawUI.WindowTitle = 'Project Backend'
npm run dev:backend
"@

$frontendCommand = @"
`$Host.UI.RawUI.WindowTitle = 'Project Frontend'
`$env:PORT = '3000'
npm run dev:web
"@

foreach ($command in @(
    $medicineCommand,
    $backendCommand,
    $frontendCommand
)) {
    Start-Process `
        -FilePath "powershell.exe" `
        -WorkingDirectory $PSScriptRoot `
        -ArgumentList @("-NoExit", "-Command", $command)
}

Write-Host ""
Write-Host "Started three terminal windows." -ForegroundColor Green
Write-Host "Wait for the frontend to compile."
Write-Host "Website: http://localhost:3000"
Write-Host "Keep the three server windows open."