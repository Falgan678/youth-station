# ============================================================
#  本地 → 服务器 一键上传脚本
#  用法：powershell -ExecutionPolicy Bypass -File deploy\upload-to-server.ps1
# ============================================================
param(
    [string]$ServerIP = "119.91.112.109",
    [string]$ServerUser = "root",
    [string]$RemoteDir = "/opt/youth-station"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  青年驿站 -> 腾讯云轻量服务器" -ForegroundColor Cyan
Write-Host "  目标: $ServerUser@$ServerIP : $RemoteDir" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# 1) 创建目录
Write-Host "`n[1/4] 准备远程目录..." -ForegroundColor Yellow
ssh "$ServerUser@$ServerIP" "mkdir -p $RemoteDir/web"

# 2) 上传 web/ 目录（排除虚拟环境/数据库/缓存）
Write-Host "`n[2/4] 上传 web 代码..." -ForegroundColor Yellow
$WebDir = Join-Path $ProjectRoot "web"
# 用 tar+ssh 方式做"忽略式"上传
Push-Location $ProjectRoot
tar --exclude='web/.venv' --exclude='web/data' --exclude='web/uploads' `
    --exclude='web/__pycache__' --exclude='web/**/__pycache__' --exclude='web/.gitignore' `
    -czf - web | ssh "$ServerUser@$ServerIP" "tar -xzf - -C $RemoteDir"
Pop-Location

# 3) 上传所有 Excel 数据
Write-Host "`n[3/4] 上传 Excel 数据..." -ForegroundColor Yellow
$xlsx = Get-ChildItem -Path $ProjectRoot -Filter "*.xlsx" -File
if ($xlsx.Count -gt 0) {
    foreach ($f in $xlsx) {
        Write-Host "   - $($f.Name)"
        scp $f.FullName "${ServerUser}@${ServerIP}:${RemoteDir}/"
    }
} else {
    Write-Host "   (无 xlsx 文件)" -ForegroundColor Gray
}

# 4) 提示
Write-Host "`n[4/4] 上传完成！" -ForegroundColor Green
Write-Host ""
Write-Host "下一步：登录服务器执行部署" -ForegroundColor Cyan
Write-Host "  ssh $ServerUser@$ServerIP"
Write-Host "  cd $RemoteDir/web/deploy && sudo bash deploy.sh"
Write-Host ""
Write-Host "如果是日常更新（仅改了代码或数据）："
Write-Host "  cd $RemoteDir/web/deploy && sudo bash update.sh"
