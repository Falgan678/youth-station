# Upload project to Tencent Cloud (Windows PowerShell 5.1+)
# Run from project root:
#   powershell -ExecutionPolicy Bypass -File web\deploy\upload-to-server.ps1

param(
    [string]$ServerIP = "119.91.112.109",
    [string]$ServerUser = "root",
    [string]$RemoteDir = "/opt/youth-station",
    [string]$Domain = "yuexinys.cn"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$WebDir = Join-Path $ProjectRoot "web"

if (-not (Test-Path $WebDir)) {
    throw "web folder not found: $WebDir"
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Upload to: ${ServerUser}@${ServerIP}" -ForegroundColor Cyan
Write-Host "  Local web: $WebDir" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "[1/4] Create remote folder..." -ForegroundColor Yellow
ssh -o StrictHostKeyChecking=accept-new ($ServerUser + "@" + $ServerIP) ("mkdir -p " + $RemoteDir + "/web")

Write-Host ""
Write-Host "[2/4] Upload web code (1-3 min)..." -ForegroundColor Yellow
$StageRoot = Join-Path $env:TEMP ("yst-upload-" + (Get-Date -Format "yyyyMMddHHmmss"))
$StageWeb = Join-Path $StageRoot "web"
New-Item -ItemType Directory -Path $StageWeb -Force | Out-Null

robocopy $WebDir $StageWeb /E /XD .venv data uploads __pycache__ /XF *.pyc /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
if ($LASTEXITCODE -ge 8) {
    Remove-Item $StageRoot -Recurse -Force -ErrorAction SilentlyContinue
    throw ("robocopy failed, code " + $LASTEXITCODE)
}

$remoteTarget = $ServerUser + "@" + $ServerIP + ":" + $RemoteDir + "/"
scp -r $StageWeb $remoteTarget
Remove-Item $StageRoot -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "[3/4] Upload Excel files..." -ForegroundColor Yellow
$xlsx = Get-ChildItem -Path $ProjectRoot -Filter "*.xlsx" -File -ErrorAction SilentlyContinue
if ($xlsx) {
    foreach ($f in $xlsx) {
        Write-Host ("   - " + $f.Name)
        scp $f.FullName ($ServerUser + "@" + $ServerIP + ":" + $RemoteDir + "/")
    }
} else {
    Write-Host "   (no xlsx, skip)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "[4/4] Upload OK!" -ForegroundColor Green
Write-Host ""
Write-Host "Next step 1 - login:" -ForegroundColor Cyan
Write-Host ("  ssh " + $ServerUser + "@" + $ServerIP)
Write-Host ""
Write-Host "Next step 2 - on server run:" -ForegroundColor Cyan
Write-Host ("  cd " + $RemoteDir + "/web/deploy")
Write-Host ("  sudo DOMAIN=" + $Domain + " bash deploy.sh")
