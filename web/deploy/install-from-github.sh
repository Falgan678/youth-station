#!/bin/bash
# ==========================================
# 一键从 GitHub 部署到腾讯云轻量服务器
# 使用：在服务器上 ssh 进去，执行：
#   curl -fsSL https://raw.githubusercontent.com/Falgan678/youth-station/main/web/deploy/install-from-github.sh | bash
# ==========================================
set -e

PROJECT_DIR="/opt/youth-station"
REPO_URL="https://github.com/Falgan678/youth-station.git"

echo "🐬 青年驿站一键部署脚本"
echo "================================"

# 1. 装系统依赖（Python 3.10+ / nginx / git）
if ! command -v python3.10 >/dev/null 2>&1; then
  echo "📦 安装 Python 3.10..."
  apt update -qq
  apt install -y python3 python3-venv python3-pip nginx git
fi

# 2. clone 或 pull
if [ -d "$PROJECT_DIR" ]; then
  echo "🔄 更新代码..."
  cd "$PROJECT_DIR" && git pull
else
  echo "📥 拉取代码..."
  git clone "$REPO_URL" "$PROJECT_DIR"
  cd "$PROJECT_DIR"
fi

# 3. venv + 装依赖
cd "$PROJECT_DIR/web"
[ ! -d ".venv" ] && python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# 4. 配置 .env（如果没有）
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "⚠️  请编辑 $PROJECT_DIR/web/.env 填入：AMAP_JS_KEY、AMAP_WEB_KEY、AI_API_KEY"
  echo "    然后再次执行本脚本完成 systemd / nginx 配置。"
  exit 0
fi

# 5. 启动 systemd 服务
SERVICE_FILE="/etc/systemd/system/youth-station.service"
if [ ! -f "$SERVICE_FILE" ]; then
  cp deploy/youth-station.service "$SERVICE_FILE"
  sed -i "s|/your/project/path|$PROJECT_DIR/web|g" "$SERVICE_FILE"
  systemctl daemon-reload
  systemctl enable youth-station
fi
systemctl restart youth-station

# 6. 配置 nginx
NGINX_CONF="/etc/nginx/conf.d/youth-station.conf"
if [ ! -f "$NGINX_CONF" ]; then
  cp deploy/nginx-youth-station.conf "$NGINX_CONF"
  echo "⚠️  请编辑 $NGINX_CONF 修改 server_name 为你的域名"
fi
nginx -t && nginx -s reload

echo ""
echo "✅ 部署完成！"
echo "   访问：http://$(curl -s ifconfig.me)"
echo "   日志：journalctl -u youth-station -f"
echo "   重启：systemctl restart youth-station"
