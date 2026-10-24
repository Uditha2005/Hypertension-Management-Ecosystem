$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot "ai\component4-medicine\.venv\Scripts\python.exe"
$mobile = Join-Path $PSScriptRoot "frontend\mobile-rn"

if (-not (Test-Path $python)) {
    throw "Medicine Python environment was not found."
}
if (-not (Test-Path "$mobile\node_modules\expo")) {
    throw "Mobile dependencies are missing. Run npm install inside frontend/mobile-rn."
}

function Test-Listening($port) {
    return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

# Ask for the key only when starting a new medicine API.
if (-not (Test-Listening 8000)) {
    if ([string]::IsNullOrWhiteSpace($env:GROQ_API_KEY)) {
        $secret = Read-Host -Prompt "Paste Groq API key and press Enter" -AsSecureString
        $env:GROQ_API_KEY = ([System.Net.NetworkCredential]::new("", $secret).Password).Trim()
        Remove-Variable secret
    }

    if ([string]::IsNullOrWhiteSpace($env:GROQ_API_KEY)) {
        throw "Key is empty. Nothing was started."
    }
}

$env:GROQ_MODEL = "openai/gpt-oss-20b"
$env:RX_SHORTHAND_CONVENTION = "tablets-per-dose_x_doses-per-day"

if (-not (Test-Listening 5000)) {
    Start-Process powershell.exe -WorkingDirectory $PSScriptRoot -ArgumentList @(
        "-NoExit", "-Command", "npm --prefix backend start"
    )
} else {
    Write-Host "Port 5000 is already running; skipped."
}

if (-not (Test-Listening 8000)) {
    Start-Process powershell.exe -WorkingDirectory $PSScriptRoot -ArgumentList @(
        "-NoExit", "-Command",
        "& '.\ai\component4-medicine\.venv\Scripts\python.exe' -m uvicorn main:app --app-dir ai/component4-medicine/src --host 0.0.0.0 --port 8000"
    )
} else {
    Write-Host "Port 8000 is already running; skipped."
}

if (-not (Test-Listening 8081)) {
    Start-Process powershell.exe -WorkingDirectory $mobile -ArgumentList @(
        "-NoExit", "-Command", "npx expo start --clear --port 8081"
    )
} else {
    Write-Host "Expo port 8081 is already running; skipped."
}

Write-Host ""
Write-Host "Scan the Expo QR code using Expo Go."
Write-Host "Keep the server windows open."
Write-Host "Phone and laptop must use the same Wi-Fi."
