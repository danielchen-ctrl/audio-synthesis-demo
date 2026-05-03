#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server_platform.py
==================
语料生成平台入口。

用法：
    python server_platform.py

与原 server.py 的区别：
  - 在现有 demo 路由基础上追加 /api/platform/* 路由
  - 启动 SQLite 数据库（platform.db）
  - 启动异步任务 worker
  - 原有 /api/generate_text、/api/synthesize_audio 等全部保留

原 demo 依然可通过 python server.py 独立运行（互不影响）。
"""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from demo_app.embedded_server_main import (
    _ensure_manifest_cache,
    local_urls,
    make_app,
)

from src.webapp.db import init_db
from src.webapp.routes import register_platform_routes
from src.webapp.task_runner import start_worker

import os
import tornado.ioloop


def main() -> None:
    host = os.environ.get("DEMO_APP_HOST", "0.0.0.0")
    port = int(os.environ.get("DEMO_APP_PORT") or os.environ.get("AUTOGATE_PORT") or "8899")

    # 1. 初始化数据库
    init_db()
    logging.getLogger(__name__).info("[platform] Database initialized → %s", ROOT / "runtime" / "platform.db")

    # 2. 构建 Tornado app（含所有原有路由）
    app = make_app()

    # 3. 注册平台路由
    register_platform_routes(app)
    logging.getLogger(__name__).info("[platform] Platform routes registered")

    # 4. 启动服务
    app.listen(port, address=host)

    # 5. 预热 manifest 缓存（后台线程）
    threading.Thread(target=_ensure_manifest_cache, daemon=True, name="manifest-cache-warmer").start()

    # 6. 启动异步任务 worker（在 IOLoop 内）
    tornado.ioloop.IOLoop.current().call_later(0.1, start_worker)

    print(f"\n{'='*55}")
    print(f"  语料生成平台  |  http://{host}:{port}/")
    print(f"{'='*55}")
    for url in local_urls(port):
        print(f"  访问地址: {url}")
    print(f"  数据库:   {ROOT / 'runtime' / 'platform.db'}")
    print(f"  存储目录: {ROOT / 'storage'}")
    print(f"{'='*55}\n")

    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
