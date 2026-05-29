# 青年驿站 · 上线部署手册（腾讯云轻量服务器 + yuexinys.cn）

> 适用环境：腾讯云轻量服务器 119.91.112.109 / Ubuntu 22.04 / 域名 yuexinys.cn

---

## 一、上线总览

```
本地代码 ──scp──▶  服务器 /opt/youth-station/web
                          │
                          ├── deploy.sh  一键部署 (Python + Gunicorn + Nginx)
                          ├── 备案 (yuexinys.cn 关联此服务器)
                          ├── DNS 解析 (@ / www → 119.91.112.109)
                          └── HTTPS (备案后申请 SSL 证书)
```

整个上线分 4 步：
1. **ICP 备案**（前置 / 7-20 工作日）
2. **域名解析**（5 分钟）
3. **服务器部署**（10 分钟）
4. **HTTPS 证书**（备案完成后再做）

---

## 二、第①步 ICP 备案

> ⚠️ 国内服务器使用 80/443 端口对外提供网站服务，**必须**完成 ICP 备案。备案期间可以用 IP+端口（如 `http://119.91.112.109:5000`）做内部测试。

1. 腾讯云控制台 → **顶部菜单 备案** → 新增网站备案
2. 选择主体（个人 / 公司）→ 选关联**这台轻量服务器** + 域名 `yuexinys.cn`
3. 上传材料、做幕布拍照核验、电话核验，提交管局
4. 进度查询：腾讯云控制台 → 备案 → 我的备案

---

## 三、第②步 域名解析

腾讯云控制台 → **域名 → yuexinys.cn → 解析** → 添加：

| 主机记录 | 记录类型 | 线路类型 | 记录值 |
|---|---|---|---|
| `@`   | A | 默认 | `119.91.112.109` |
| `www` | A | 默认 | `119.91.112.109` |

> 解析记录可在备案前就配置；备案未通过前用 IP+端口先测，备案通过后域名自动可访问。

---

## 四、第③步 服务器部署

### 1. 服务器登录

腾讯云控制台 → 轻量服务器 → CentOS-RFGS → **登录**。  
首次登录用网页 OrcaTerm（控制台已经打开），或用 SSH 密钥/密码登录：

```bash
ssh root@119.91.112.109
```

如忘记密码：控制台 → 重置密码。

### 2. 上传代码到服务器

**方式 A：从你本地（推荐）**

在 **本地 Windows PowerShell** 中（项目根目录）：
```powershell
# 创建服务器目标目录
ssh root@119.91.112.109 "mkdir -p /opt/youth-station"

# 上传整个 web 目录（不含 .venv 和 data，节省时间）
scp -r web root@119.91.112.109:/opt/youth-station/

# 同时上传所有城市 Excel 数据文件
scp *.xlsx root@119.91.112.109:/opt/youth-station/
```

**方式 B：用 Git（如果你有仓库）**
```bash
cd /opt
git clone <你的仓库> youth-station
```

### 3. 一键部署

服务器上执行：
```bash
cd /opt/youth-station/web/deploy
sudo bash deploy.sh
```

脚本会自动完成：
- 安装 Python3、Nginx、ufw 等系统包
- 创建 venv 并安装依赖（含 Gunicorn）
- 自动生成 `.env`（含随机 SECRET_KEY，需手动填高德 Key）
- 首次执行 Excel 种子导入（180 条驿站数据）
- 注册 systemd 服务并开机自启
- 配置 Nginx 反向代理到 `127.0.0.1:5000`
- 开放防火墙 22/80/443

### 4. 填高德 Key

```bash
sudo vim /opt/youth-station/web/.env
```

填入你在 https://console.amap.com 申请的 3 个 Key：
```
AMAP_JS_KEY=你的JS Key
AMAP_JS_SECRET=你的JS安全密钥
AMAP_WEB_KEY=你的Web服务Key
```

> **JS Key 申请时**：应用类型选 "Web端(JS API)"，**安全域名**填 `yuexinys.cn`、`www.yuexinys.cn`、`119.91.112.109`（多个用回车分隔）  
> **Web 服务 Key 申请时**：应用类型选 "Web服务"，IP白名单填 `119.91.112.109`

保存后重启服务：
```bash
sudo systemctl restart youth-station
```

### 5. 验证部署

```bash
# 应用进程
systemctl status youth-station
# Nginx
systemctl status nginx
# 端口
ss -tlnp | grep -E ':80|:5000'
# 实时日志
journalctl -u youth-station -f
```

浏览器访问：
- 备案中：`http://119.91.112.109:5000`（直连 Gunicorn，**需要在腾讯云控制台-防火墙打开 5000 端口**）
- 备案后：`http://yuexinys.cn`

---

## 五、第④步 HTTPS 证书（备案后）

### 1. 申请 SSL 证书（免费）

腾讯云控制台 → **SSL 证书** → 申请免费证书 → 域名填 `yuexinys.cn` → 验证方式选 **DNS 自动**（同账号自动加记录） → 提交，几分钟下发。

### 2. 下载并上传到服务器

下载 Nginx 版证书包，解压得到 `xxx.pem` 和 `xxx.key`：

```powershell
# 本地 PowerShell
ssh root@119.91.112.109 "mkdir -p /etc/nginx/ssl"
scp yuexinys.cn_bundle.pem root@119.91.112.109:/etc/nginx/ssl/yuexinys.cn.pem
scp yuexinys.cn.key root@119.91.112.109:/etc/nginx/ssl/yuexinys.cn.key
```

### 3. 启用 HTTPS

```bash
sudo vim /etc/nginx/sites-available/youth-station
```

把文件最底部 **=== 备案完成 ... === 以下注释段** 解除注释；并把上面 80 server 块里的 `# return 301 https://...` 解除注释（强制跳转 HTTPS）。  
然后：
```bash
sudo nginx -t && sudo systemctl reload nginx
```

完成。访问 `https://yuexinys.cn` 应有小绿锁。

---

## 六、日常运维

### 后续上传新城市数据

```powershell
# 本地把新 Excel 上传上去
scp 1_江门青年驿站-XXX.xlsx root@119.91.112.109:/opt/youth-station/

# 服务器执行
ssh root@119.91.112.109 "cd /opt/youth-station/web/deploy && sudo bash update.sh"
```

`update.sh` 会自动：扫描所有 Excel → 合并入库（已有按 名称+地址 更新，不会删除）→ 平滑重启服务。

### 修改代码后部署

```powershell
# 同步 web 目录
scp -r web/* root@119.91.112.109:/opt/youth-station/web/
ssh root@119.91.112.109 "systemctl restart youth-station"
```

### 备份数据库

```bash
# 服务器上
sudo cp /opt/youth-station/web/data/app.db /opt/backup/app-$(date +%F).db
```

建议加 cron：
```bash
sudo crontab -e
# 每天凌晨 3 点备份，保留 14 天
0 3 * * * cp /opt/youth-station/web/data/app.db /opt/backup/app-$(date +\%F).db && find /opt/backup -name 'app-*.db' -mtime +14 -delete
```

### 改默认管理员密码

```bash
cd /opt/youth-station/web && . .venv/bin/activate
python -c "
from app import create_app
from models import Admin, db
app = create_app(); app.app_context().push()
u = Admin.query.filter_by(username='admin').first()
u.set_password('你的新强密码')
db.session.commit()
print('OK')
"
```

---

## 七、常见问题

**Q1：访问 `http://yuexinys.cn` 报错 / 跳到腾讯云提示页？**  
→ 域名未备案，必须先完成备案。可暂时用 `http://119.91.112.109:5000` 测试（需在腾讯云防火墙开放 5000）。

**Q2：备案中能否让团队内部测试？**  
→ 可以。腾讯云控制台 → 轻量服务器 → 防火墙 → 添加规则放行 5000 端口；然后访问 `http://119.91.112.109:5000`。  
**注意：备案完成上线后建议关闭 5000 直连，仅留 80/443。**

**Q3：高德地图加载报错 INVALID_USER_KEY / USER_KEY_PLAT_NOMATCH？**  
→ JS Key 没绑定域名/IP，去高德控制台对应应用的"安全域名"里加入 `yuexinys.cn`、`www.yuexinys.cn`、`119.91.112.109`。

**Q4：内存不够用怎么办？**  
→ `deploy/gunicorn_conf.py` 把 workers 改为 2；或开 swap：
```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab
```

**Q5：3Mbps 带宽够用吗？**  
→ 应届毕业生这种轻量查询场景，3Mbps 足够支撑约 50 并发；图片/Excel 都通过 Nginx 直出，已开 7d/30d 缓存。
