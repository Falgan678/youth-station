@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv" (
  echo [INIT] 创建虚拟环境...
  python -m venv .venv
)
call .venv\Scripts\activate.bat

echo [INIT] 安装依赖...
pip install -r requirements.txt -q -i https://pypi.tuna.tsinghua.edu.cn/simple

echo [INIT] 导入 Excel 种子数据...
python seed_from_excel.py

echo.
echo ===========================================
echo  启动服务器:  http://127.0.0.1:5000
echo  后台地址  :  http://127.0.0.1:5000/admin
echo  默认账号  :  admin / admin123
echo ===========================================
echo.
python app.py
pause
