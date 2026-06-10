# Upload + optional remote deploy
#   powershell -ExecutionPolicy Bypass -File web\deploy\deploy-tencent.ps1 -RunDeploy

param(
    [string]$ServerIP = "119.91.112.109",
    [string]$ServerUser = "root",
    [string]$RemoteDir = "/opt/youth-station",
    [string]$Domain = "yuexinys.cn",
    [switch]$RunDeploy,
    [switch]$SkipUpload
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $SkipUpload) {
    & (Join-Path $ScriptDir "upload-to-server.ps1") -ServerIP $ServerIP -ServerUser $ServerUser -RemoteDir $RemoteDir -Domain $Domain
}

if ($RunDeploy) {
    $remoteCmd = "cd " + $RemoteDir + "/web/deploy; sudo DOMAIN=" + $Domain + " bash deploy.sh"
    Write-Host ""
    Write-Host "Running deploy on server..." -ForegroundColor Yellow
    ssh ($ServerUser + "@" + $ServerIP) $remoteCmd
}

Write-Host ""
Write-Host "Site: http://" + $ServerIP
Write-Host "Admin: http://" + $ServerIP + "/admin"
