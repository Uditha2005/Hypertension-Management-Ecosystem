param(
    [ValidateSet("web", "mobile")]
    [string]$Mode = "web"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot "ai\component4-medicine\.venv\Scripts\python.exe"
$runtime = Join-Path $PSScriptRoot "ai\component4-medicine\.env.runtime"

foreach ($required in @($python, $runtime)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required file missing: $required"
    }
}

function Get-PortOwners([int]$Port) {
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
}

# Restart only this project's medicine API so saved Groq settings are loaded.
$owners = @(Get-PortOwners 8000)
foreach ($ownerId in $owners) {
    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $ownerId"
    if (
        $processInfo.Name -ne "python.exe" -or
        $processInfo.CommandLine -notlike "*Hypertension-Management-Ecosystem*" -or
        $processInfo.CommandLine -notlike "*uvicorn main:app*" -or
        $processInfo.CommandLine -notlike "*component4-medicine*"
    ) {
        throw "Port 8000 belongs to another application. Nothing was stopped."
    }
}

foreach ($ownerId in $owners) {
    Stop-Process -Id $ownerId -ErrorAction Stop
    Wait-Process -Id $ownerId -ErrorAction SilentlyContinue
}

if ($Mode -eq "mobile") {
    $frontendFolder = Join-Path $PSScriptRoot "frontend\mobile-rn"
    if (-not (Test-Path "$frontendFolder\node_modules\expo")) {
        throw "Mobile dependencies missing. Run npm install in frontend/mobile-rn."
    }
} else {
    $frontendFolder = Join-Path $PSScriptRoot "frontend\web"
    if (-not (Test-Path "$frontendFolder\node_modules\react-scripts")) {
        throw "Web dependencies missing. Run npm install in frontend/web."
    }
}

# Prevent an old environment value from overriding the saved configuration.
Remove-Item Env:GROQ_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:GROQ_MODEL -ErrorAction SilentlyContinue
Remove-Item Env:RX_SHORTHAND_CONVENTION -ErrorAction SilentlyContinue

Start-Process powershell.exe -WorkingDirectory $PSScriptRoot -ArgumentList @(
    "-NoExit",
    "-Command",
    "& '.\ai\component4-medicine\.venv\Scripts\python.exe' -m uvicorn main:app --app-dir ai/component4-medicine/src --env-file ai/component4-medicine/.env.runtime --host 0.0.0.0 --port 8000"
)

if (-not @(Get-PortOwners 5000).Count) {
    Start-Process powershell.exe -WorkingDirectory $PSScriptRoot -ArgumentList @(
        "-NoExit", "-Command", "npm --prefix backend start"
    )
} else {
    Write-Host "Account backend port 5000 is already in use; kept running."
}

if ($Mode -eq "web") {
    if (-not @(Get-PortOwners 3000).Count) {
        Start-Process powershell.exe -WorkingDirectory $frontendFolder -ArgumentList @(
            "-NoExit", "-Command", "npm start"
        )
    } else {
        Write-Host "Web port 3000 is already in use; kept running."
    }
    Write-Host ""
    Write-Host "After compilation, open http://localhost:3000"
} else {
    # Prefer the active Wi-Fi address for Expo LAN connections.
    $wifiAddress = Get-NetIPConfiguration |
        Where-Object {
            $_.IPv4DefaultGateway -and
            $_.NetAdapter.Status -eq "Up" -and
            $_.InterfaceAlias -like "*Wi-Fi*"
        } |
        ForEach-Object { $_.IPv4Address.IPAddress } |
        Select-Object -First 1

    if ($wifiAddress) {
        $env:REACT_NATIVE_PACKAGER_HOSTNAME = $wifiAddress
        Write-Host "Medicine API: http://${wifiAddress}:8000"
        Write-Host "Account API:  http://${wifiAddress}:5000"
    }

    if (-not @(Get-PortOwners 8081).Count) {
        Start-Process powershell.exe -WorkingDirectory $frontendFolder -ArgumentList @(
            "-NoExit", "-Command", "npx expo start --clear --lan --port 8081"
        )
    } else {
        Write-Host "Expo port 8081 is already in use. Use its existing QR code."
    }

    Write-Host ""
    Write-Host "Scan the QR code using Expo Go."
    Write-Host "Phone and laptop must use the same Wi-Fi."
}

Write-Host "Keep the server windows open."
Write-Host "Medicine records use SQLite; Groq loads from .env.runtime."
Write-Host "Check the server windows for any startup errors."
