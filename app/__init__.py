# -*- coding: utf-8 -*-
"""
app 包：Flask 应用工厂（仿青就业 backend/app 结构）
"""

import os

from flask import Flask

from . import config
from . import models
from .routers import auth as auth_router
from .routers import admin as admin_router
from .routers import live as live_router
from .routers import videos as videos_router
from .routers import coach as coach_router
from .routers import stats as stats_router


def create_app():
    app = Flask(__name__, template_folder=os.path.join(config.BASE_DIR, 'templates'))
    app.secret_key = config.get_secret_key()
    app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

    models.ensure_tables()

    app.register_blueprint(auth_router.bp)
    app.register_blueprint(admin_router.bp)
    app.register_blueprint(live_router.bp)
    app.register_blueprint(videos_router.bp)
    app.register_blueprint(coach_router.bp)
    app.register_blueprint(stats_router.bp)

    return app


def init():
    """启动初始化（建表 + 种子管理员）"""
    models.ensure_tables()
