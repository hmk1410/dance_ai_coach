# -*- coding: utf-8 -*-
"""
run.py
启动脚本（仿青就业 run.py）：初始化并启动 Flask 应用。
"""

import threading

from app import create_app, init
from app import state
from app.services import pose_runner

if __name__ == '__main__':
    init()
    app = create_app()

    # 启动时自动开始处理
    state.is_running = True
    thread = threading.Thread(target=pose_runner.processing_loop)
    thread.daemon = True
    thread.start()

    print("=" * 50)
    print("舞镜·智芯 - AI舞蹈教练 Demo")
    print("=" * 50)
    print("访问地址：")
    print("  本机：http://127.0.0.1:5000")
    print("  局域网：http://<本机IP>:5000")
    print("=" * 50)

    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
