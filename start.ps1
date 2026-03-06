#!/usr/bin/env pwsh
# PowerShell start script for AgentCore Public Stack (Windows)

$ErrorActionPreference = "Stop"

Write-Host "Starting AgentCore Public Stack..." -ForegroundColor Cyan

# --- Path Setup ---
$projectRoot = $PSScriptRoot
$backendDir = Join-Path $projectRoot "backend"
$venvDir = Join-Path $backendDir "venv"
$venvScripts = Join-Path $venvDir "Scripts"
$venvPython = Join-Path $venvScripts "python.exe"
$frontendBase = Join-Path $projectRoot "frontend"
$frontendDir = Join-Path $frontendBase "ai.client"
$nodeModules = Join-Path $frontendDir "node_modules"
$envBase = Join-Path $backendDir "src"
$masterEnvFile = Join-Path $envBase ".env"

# --- Cleanup Function ---
$script:appApiJob = $null
$script:inferenceApiJob = $null
$script:frontendJob = $null

function Cleanup {
    Write-Host ""
    Write-Host "Shutting down services..." -ForegroundColor Yellow

    if ($script:appApiJob) {
        Write-Host "  Stopping App API..." -ForegroundColor Gray
        Stop-Job $script:appApiJob -ErrorAction SilentlyContinue
        Remove-Job $script:appApiJob -ErrorAction SilentlyContinue
    }

    if ($script:inferenceApiJob) {
        Write-Host "  Stopping Inference API..." -ForegroundColor Gray
        Stop-Job $script:inferenceApiJob -ErrorAction SilentlyContinue
        Remove-Job $script:inferenceApiJob -ErrorAction SilentlyContinue
    }

    if ($script:frontendJob) {
        Write-Host "  Stopping Frontend..." -ForegroundColor Gray
        Stop-Job $script:frontendJob -ErrorAction SilentlyContinue
        Remove-Job $script:frontendJob -ErrorAction SilentlyContinue
    }

    # Kill processes on ports
    Write-Host "  Cleaning up ports..." -ForegroundColor Gray
    foreach ($p in @(8000, 8001, 4200)) {
        Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | ForEach-Object {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }

    # Clean up log files
    Remove-Item (Join-Path $projectRoot "app_api.log") -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $projectRoot "inference_api.log") -ErrorAction SilentlyContinue

    Write-Host "Cleanup complete" -ForegroundColor Green
    exit 0
}

# Register cleanup on Ctrl+C
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Cleanup } | Out-Null

# --- Prerequisites Check ---
if (-not (Test-Path $nodeModules)) {
    Write-Host "Frontend dependencies not found. Please run setup first:" -ForegroundColor Red
    Write-Host "  .\setup.ps1" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $venvDir)) {
    Write-Host "Backend virtual environment not found. Please run setup first:" -ForegroundColor Red
    Write-Host "  .\setup.ps1" -ForegroundColor Yellow
    exit 1
}

# --- Clean Up Existing Processes ---
Write-Host "Checking for existing processes on ports 8000, 8001, and 4200..." -ForegroundColor Yellow

foreach ($port in @(8000, 8001, 4200)) {
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connections) {
        Write-Host "  Killing process on port $port..." -ForegroundColor Gray
        $connections | ForEach-Object {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

Start-Sleep -Seconds 1
Write-Host "Ports cleared successfully" -ForegroundColor Green
Write-Host ""

# --- Load Environment Variables ---
if (Test-Path $masterEnvFile) {
    Write-Host "Loading environment variables from: $masterEnvFile" -ForegroundColor Yellow
    Get-Content $masterEnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $eqIndex = $line.IndexOf("=")
            $key = $line.Substring(0, $eqIndex).Trim()
            $value = $line.Substring($eqIndex + 1).Trim()
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
    Write-Host "Environment variables loaded" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "Master .env file not found at $masterEnvFile, using defaults" -ForegroundColor Yellow
    Write-Host ""
}

# --- Configure AWS Credentials ---
Write-Host "Configuring AWS credentials..." -ForegroundColor Yellow

if (Get-Command aws -ErrorAction SilentlyContinue) {
    $awsProfile = $env:AWS_PROFILE
    if (-not $awsProfile) { $awsProfile = "default" }

    if ($awsProfile -ne "default") {
        Write-Host "  Using AWS profile: $awsProfile" -ForegroundColor Gray
        $env:AWS_PROFILE = $awsProfile

        $prevErrorPref = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $testResult = & aws sts get-caller-identity 2>&1
        $awsWorking = $LASTEXITCODE -eq 0
        $ErrorActionPreference = $prevErrorPref

        if ($awsWorking) {
            Write-Host "  AWS profile is valid and credentials are working" -ForegroundColor Green
        } else {
            Write-Host "  AWS profile credentials are not working" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "  To fix this, run one of:" -ForegroundColor Cyan
            Write-Host "    For SSO: aws configure sso --profile $awsProfile" -ForegroundColor White
            Write-Host "    To refresh SSO: aws sso login --profile $awsProfile" -ForegroundColor White
            Write-Host "    For standard credentials: aws configure --profile $awsProfile" -ForegroundColor White
            Write-Host ""
            Write-Host "  Falling back to default AWS credentials" -ForegroundColor Yellow
            Remove-Item Env:\AWS_PROFILE -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "  Using default AWS credentials" -ForegroundColor Gray
        Remove-Item Env:\AWS_PROFILE -ErrorAction SilentlyContinue
    }

    # Verify credentials
    $prevErrorPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $account = & aws sts get-caller-identity --query "Account" --output text 2>&1
    $awsValid = $LASTEXITCODE -eq 0
    $ErrorActionPreference = $prevErrorPref

    if ($awsValid) {
        Write-Host "  AWS credentials valid (Account: $account)" -ForegroundColor Green
    } else {
        Write-Host "  Could not verify AWS credentials" -ForegroundColor Yellow
        Write-Host "  Some features may not work. Run 'aws configure' to set up." -ForegroundColor Gray
    }
} else {
    Write-Host "  AWS CLI not installed - using credentials from environment" -ForegroundColor Yellow
}

Write-Host ""

# --- Start App API ---
Write-Host "Starting App API on port 8000..." -ForegroundColor Yellow
$appApiBase = Join-Path $backendDir "src"
$appApiApis = Join-Path $appApiBase "apis"
$appApiDir = Join-Path $appApiApis "app_api"
$appApiMain = Join-Path $appApiDir "main.py"
$appApiLog = Join-Path $projectRoot "app_api.log"

$script:appApiJob = Start-Job -ScriptBlock {
    param($python, $main, $log)
    & $python $main *>&1 | Tee-Object -FilePath $log
} -ArgumentList $venvPython, $appApiMain, $appApiLog

Write-Host "  App API started (Job ID: $($script:appApiJob.Id))" -ForegroundColor Green

Start-Sleep -Seconds 2

# --- Start Inference API ---
Write-Host "Starting Inference API on port 8001..." -ForegroundColor Yellow
$inferenceApiDir = Join-Path $appApiApis "inference_api"
$inferenceApiMain = Join-Path $inferenceApiDir "main.py"
$inferenceApiLog = Join-Path $projectRoot "inference_api.log"

$script:inferenceApiJob = Start-Job -ScriptBlock {
    param($python, $main, $log)
    & $python $main *>&1 | Tee-Object -FilePath $log
} -ArgumentList $venvPython, $inferenceApiMain, $inferenceApiLog

Write-Host "  Inference API started (Job ID: $($script:inferenceApiJob.Id))" -ForegroundColor Green

# --- Wait for APIs to Initialize ---
Write-Host ""
Write-Host "Waiting for APIs to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Verify APIs are running
$appApiRunning = (Get-Job -Id $script:appApiJob.Id).State -eq "Running"
$inferenceApiRunning = (Get-Job -Id $script:inferenceApiJob.Id).State -eq "Running"

if ($appApiRunning) {
    Write-Host "  App API process is running" -ForegroundColor Green
} else {
    Write-Host "  App API failed to start - check app_api.log for errors" -ForegroundColor Red
}

if ($inferenceApiRunning) {
    Write-Host "  Inference API process is running" -ForegroundColor Green
} else {
    Write-Host "  Inference API failed to start - check inference_api.log for errors" -ForegroundColor Red
}

# Check if ports are listening
Write-Host ""
Write-Host "Checking if ports are listening..." -ForegroundColor Yellow
Start-Sleep -Seconds 2

$port8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
$port8001 = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue

if ($port8000) {
    Write-Host "  Port 8000 is listening" -ForegroundColor Green
} else {
    Write-Host "  Port 8000 not yet listening (App API may still be starting)" -ForegroundColor Yellow
}

if ($port8001) {
    Write-Host "  Port 8001 is listening" -ForegroundColor Green
} else {
    Write-Host "  Port 8001 not yet listening (Inference API may still be starting)" -ForegroundColor Yellow
}

# --- Start Frontend ---
Write-Host ""
Write-Host "Starting frontend server (local mode)..." -ForegroundColor Yellow

# Disable Angular analytics
Push-Location $frontendDir
try {
    npx ng analytics off --skip-nx-cache 2>&1 | Out-Null
} catch {
    # Ignore errors
}

$env:NODE_NO_WARNINGS = "1"
Remove-Item Env:\PORT -ErrorAction SilentlyContinue

$script:frontendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    npm run start
} -ArgumentList $frontendDir

Write-Host "  Frontend started (Job ID: $($script:frontendJob.Id))" -ForegroundColor Green

Pop-Location

# --- Display Summary ---
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "All services started successfully!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Frontend:       http://localhost:4200" -ForegroundColor White
Write-Host "App API:        http://localhost:8000" -ForegroundColor White
Write-Host "  - API Docs:   http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "Inference API:  http://localhost:8001" -ForegroundColor White
Write-Host "  - API Docs:   http://localhost:8001/docs" -ForegroundColor Gray
Write-Host ""
Write-Host "Logs:" -ForegroundColor Yellow
Write-Host "  App API:       Get-Content app_api.log -Wait" -ForegroundColor White
Write-Host "  Inference API: Get-Content inference_api.log -Wait" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop all services" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# --- Wait for Jobs ---
try {
    while ($true) {
        Start-Sleep -Seconds 1

        $jobs = @($script:appApiJob, $script:inferenceApiJob, $script:frontendJob)
        foreach ($job in $jobs) {
            if ($job -and (Get-Job -Id $job.Id).State -eq "Failed") {
                Write-Host ""
                Write-Host "A service has failed. Check logs for details." -ForegroundColor Red
                Cleanup
            }
        }
    }
} finally {
    Cleanup
}
