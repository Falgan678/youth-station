#!/bin/bash
# ==========================================================
#  日常更新脚本：当本地代码或 Excel 数据有变动时使用
# ==========================================================
#  用法：sudo bash update.sh
# ==========================================================
set -e

APP_DIR=/opt/youth-station
WEB_DIR=$APP_DIR/web
APP_USER=www-data

cd "$WEB_DIR"
. .venv/bin/activate

# 如果 requirements 有变更，重装
pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple

# 重新导入 Excel 数据（已存在按 名称+地址 更新，不存在则新增；不会删除已有数据）
echo "[INFO] 重新扫描 $APP_DIR 下的 Excel 文件并合并入库..."
sudo -u $APP_USER bash -c "cd $WEB_DIR && . .venv/bin/activate && python seed_from_excel.py"

# 重启服务（平滑）
systemctl reload youth-station || systemctl restart youth-station
echo "[DONE] 已更新并重启"
