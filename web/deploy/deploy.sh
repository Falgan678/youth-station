#!/bin/bash
# ==========================================================
#  青年驿站 一键部署脚本 (Ubuntu 22.04)
# ==========================================================
#  用法（首次部署 root 或 sudo 执行）:
#    sudo bash deploy.sh
# ==========================================================
set -e

APP_DIR=/opt/youth-station
WEB_DIR=$APP_DIR/web
DOMAIN=${DOMAIN:-yuexinys.cn}
APP_USER=www-data

echo "========================================"
echo "  青年驿站 部署脚本"
echo "  目标目录: $WEB_DIR"
echo "  域名    : $DOMAIN"
echo "========================================"

# 1) 系统依赖
echo "[1/7] 安装系统依赖..."
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 python3-venv python3-pip \
    nginx git curl ufw

# 2) 拷贝代码（假设你已经把 web/ 目录上传到 $APP_DIR/web）
if [ ! -d "$WEB_DIR" ]; then
    echo "[ERROR] 未发现 $WEB_DIR，请先把 web/ 目录上传到 $APP_DIR/"
    echo "  推荐用 scp 或 rsync："
    echo "  scp -r web/ root@SERVER_IP:$APP_DIR/"
    exit 1
fi

# 3) 创建虚拟环境 + 安装依赖
echo "[2/7] 创建 Python 虚拟环境..."
cd "$WEB_DIR"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
. .venv/bin/activate
pip install --upgrade pip -q -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install gunicorn==22.0.0 -q -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4) 创建 .env（如不存在）
echo "[3/7] 配置环境变量..."
if [ ! -f "$WEB_DIR/.env" ]; then
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    cat > "$WEB_DIR/.env" <<EOF
# === 自动生成 - 请尽快补全高德 Key ===
SECRET_KEY=$SECRET_KEY
AMAP_JS_KEY=请填写高德前端JS Key
AMAP_JS_SECRET=请填写高德前端JS安全密钥
AMAP_WEB_KEY=请填写高德Web服务Key
EOF
    chmod 600 "$WEB_DIR/.env"
    echo "  -> 已生成 $WEB_DIR/.env，请用 vim 编辑填入高德 Key"
fi

# 5) 数据目录权限
echo "[4/7] 准备数据目录..."
mkdir -p "$WEB_DIR/data" "$WEB_DIR/uploads" /var/log/youth-station
chown -R $APP_USER:$APP_USER "$WEB_DIR/data" "$WEB_DIR/uploads" /var/log/youth-station "$APP_DIR"

# 首次种子导入
if [ ! -f "$WEB_DIR/data/app.db" ]; then
    echo "  -> 首次启动，执行 Excel 种子导入..."
    sudo -u $APP_USER bash -c "cd $WEB_DIR && . .venv/bin/activate && python seed_from_excel.py" || true
fi

# 6) Systemd 服务
echo "[5/7] 注册 Systemd 服务..."
cp "$WEB_DIR/deploy/youth-station.service" /etc/systemd/system/youth-station.service
systemctl daemon-reload
systemctl enable youth-station
systemctl restart youth-station
sleep 2
systemctl --no-pager -l status youth-station | head -15

# 7) Nginx
echo "[6/7] 配置 Nginx..."
NGINX_CONF=/etc/nginx/sites-available/youth-station
cp "$WEB_DIR/deploy/nginx-youth-station.conf" "$NGINX_CONF"
# 替换域名
sed -i "s/yuexinys.cn/$DOMAIN/g" "$NGINX_CONF"
ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/youth-station
# 移除默认站点
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx
systemctl enable nginx

# 8) 防火墙
echo "[7/7] 配置防火墙..."
ufw allow 22/tcp || true
ufw allow 80/tcp || true
ufw allow 443/tcp || true
ufw --force enable || true

# 完成
echo ""
echo "========================================"
echo "  部署完成！"
echo "========================================"
echo "  网站访问: http://$DOMAIN  (备案完成后)"
echo "  IP 直连 : http://119.91.112.109  (临时使用)"
echo "  管理后台: http://$DOMAIN/admin"
echo "  默认账号: admin / admin123"
echo ""
echo "  日志:"
echo "    journalctl -u youth-station -f          # 应用日志"
echo "    tail -f /var/log/nginx/access.log        # Nginx 访问日志"
echo "    tail -f /var/log/youth-station/error.log # Gunicorn 错误日志"
echo ""
echo "  下一步:"
echo "    1. 编辑 $WEB_DIR/.env 填入高德 Key"
echo "    2. 重启服务: systemctl restart youth-station"
echo "    3. 备案完成后申请 SSL 证书并启用 HTTPS"
echo "========================================"
