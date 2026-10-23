$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot "ai\component4-medicine\.venv\Scripts\python.exe"
$apiDirectory = Join-Path $projectRoot "ai\component4-medicine\src"
$mobileDirectory = Join-Path $projectRoot "frontend\mobile-rn"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Medicine Python environment was not found."
}

if (-not (Test-Path -LiteralPath (Join-Path $mobileDirectory "node_modules\expo"))) {
    throw "Mobile dependencies are missing. Run npm install inside frontend/mobile-rn."
}

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Install Node.js or reopen the terminal."
}

$occupiedPorts = @(
    foreach ($port in @(8000, 8081)) {
        if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
            $port
        }
    }
)

if ($occupiedPorts.Count -gt 0) {
    Write-Host "Already running on port(s): $($occupiedPorts -join ', ')" -ForegroundColor Yellow
    Write-Host "Stop the existing medicine API / Expo terminals with Ctrl+C, then run this script again."
    exit 1
}

$env:GROQ_MODEL = "openai/gpt-oss-20b"
$env:RX_SHORTHAND_CONVENTION = "tablets-per-dose_x_doses-per-day"

if ([string]::IsNullOrWhiteSpace($env:GROQ_API_KEY)) {
    $secret = Read-Host "Paste Groq API key and press Enter" -AsSecureString
    $env:GROQ_API_KEY = ([System.Net.NetworkCredential]::new("", $secret).Password).Trim()
    Remove-Variable secret
}

if ([string]::IsNullOrWhiteSpace($env:GROQ_API_KEY)) {
    throw "Groq API key is empty. Nothing was started."
}

function Quote-PowerShellPath([string]$value) {
    return "'" + $value.Replace("'", "''") + "'"
}

$apiCommand = @"
Set-Location -LiteralPath $(Quote-PowerShellPath $projectRoot)
& $(Quote-PowerShellPath $pythonPath) -m uvicorn main:app --app-dir $(Quote-PowerShellPath $apiDirectory) --host 0.0.0.0 --port 8000
"@

$mobileCommand = @"
Set-Location -LiteralPath $(Quote-PowerShellPath $mobileDirectory)
& npm.cmd start
"@

foreach ($command in @($apiCommand, $mobileCommand)) {
    $encoded = [Convert]::ToBase64String(
        [System.Text.Encoding]::Unicode.GetBytes($command)
    )

    Start-Process powershell.exe -ArgumentList @(
        "-NoProfile",
        "-NoExit",
        "-EncodedCommand",
        $encoded
    ) | Out-Null
}

Write-Host ""
Write-Host "Started medicine API and Expo in two terminal windows." -ForegroundColor Green
Write-Host "Keep both windows open."
Write-Host "Open the app using Expo Go."
Write-Host "Phone and laptop must be connected to the same Wi-Fi."
Write-Host "App Settings: use the laptop Wi-Fi IPv4 address with port 8000."
