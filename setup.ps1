#!/usr/bin/env pwsh
# PowerShell setup script for AgentCore Public Stack (Windows)

$ErrorActionPreference = "Stop"

Write-Host "Setting up AgentCore Public Stack..." -ForegroundColor Cyan

# --- Prerequisites Check ---
Write-Host "`nChecking prerequisites..." -ForegroundColor Yellow

# Check Python
try {
    $pythonVersion = & python --version 2>&1
    Write-Host "$pythonVersion" -ForegroundColor Green
} catch {
    try {
        $pythonVersion = & python3 --version 2>&1
        Write-Host "$pythonVersion" -ForegroundColor Green
    } catch {
        Write-Host "Python 3 is not installed. Please install Python 3.8 or higher." -ForegroundColor Red
        exit 1
    }
}

# Determine python command
$pythonCmd = if (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } else { "python" }

# Check Node.js
try {
    $nodeVersion = & node --version 2>&1
    Write-Host "Node.js $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "Node.js is not installed. Please install Node.js 18 or higher." -ForegroundColor Red
    exit 1
}

# Check npm
try {
    $npmVersion = & npm --version 2>&1
    Write-Host "npm $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "npm is not installed. Please install npm." -ForegroundColor Red
    exit 1
}

Write-Host "Prerequisites check passed`n" -ForegroundColor Green

# --- Backend Setup ---
Write-Host "Installing backend dependencies...`n" -ForegroundColor Yellow

$backendDir = Join-Path $PSScriptRoot "backend"
$venvDir = Join-Path $backendDir "venv"
$venvScripts = Join-Path $venvDir "Scripts"
$venvPython = Join-Path $venvScripts "python.exe"

# Create virtual environment if it doesn't exist
if (-not (Test-Path $venvDir)) {
    Write-Host "  Creating virtual environment..."
    & $pythonCmd -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
}

# Upgrade pip
Write-Host "  Upgrading pip..."
& $venvPython -m pip install --upgrade pip 2>&1 | Out-Null

# Install dependencies
Write-Host "  Installing agentcore-stack package with all dependencies..."
& $venvPython -m pip install -e "$backendDir[agentcore,dev]"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Backend dependencies installed successfully`n" -ForegroundColor Green
} else {
    Write-Host "Failed to install backend dependencies" -ForegroundColor Red
    exit 1
}

# --- Frontend Setup ---
Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow

$frontendBase = Join-Path $PSScriptRoot "frontend"
$frontendDir = Join-Path $frontendBase "ai.client"

if (-not (Test-Path $frontendDir)) {
    Write-Host "Frontend directory not found at: $frontendDir" -ForegroundColor Red
    exit 1
}

Push-Location $frontendDir
try {
    & npm install
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Frontend dependencies installed successfully`n" -ForegroundColor Green
    } else {
        Write-Host "Failed to install frontend dependencies" -ForegroundColor Red
        exit 1
    }
} finally {
    Pop-Location
}

# --- Done ---
Write-Host "Setup completed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "To start the application:" -ForegroundColor Cyan
Write-Host "  .\start.ps1" -ForegroundColor White
Write-Host ""
Write-Host "Or start components separately:" -ForegroundColor Cyan
Write-Host "  App API:       cd backend; venv\Scripts\Activate.ps1; cd src\apis\app_api; python main.py" -ForegroundColor White
Write-Host "  Inference API: cd backend; venv\Scripts\Activate.ps1; cd src\apis\inference_api; python main.py" -ForegroundColor White
Write-Host "  Frontend:      cd frontend\ai.client; npm run start" -ForegroundColor White
