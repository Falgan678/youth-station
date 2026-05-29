# Gunicorn 生产配置
import multiprocessing
import os

bind = "127.0.0.1:5000"
# 2核机器，公式 (2*CPU)+1，但 2GB 内存稍紧，限制为 3 个 worker
workers = int(os.environ.get("GUNICORN_WORKERS", 3))
worker_class = "sync"
threads = 2
timeout = 60
keepalive = 5
graceful_timeout = 30

# 日志
accesslog = "/var/log/youth-station/access.log"
errorlog = "/var/log/youth-station/error.log"
loglevel = "info"

# 进程命名
proc_name = "youth-station"

# 启动前确保日志目录
def on_starting(server):
    os.makedirs("/var/log/youth-station", exist_ok=True)
