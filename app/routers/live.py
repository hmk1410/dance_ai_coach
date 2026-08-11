# -*- coding: utf-8 -*-
"""
live.py
实时训练路由：视频流 / 分析结果 / 启停处理。
"""

import threading

from flask import Blueprint, Response, jsonify

from .. import state
from ..services import pose_runner
from ..security import login_required

bp = Blueprint('live', __name__)


@bp.route('/video_feed')
def video_feed():
    return Response(pose_runner.generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@bp.route('/api/analysis')
@login_required
def get_analysis():
    return jsonify(state.latest_analysis)


@bp.route('/api/start', methods=['POST'])
@login_required
def start():
    if not state.is_running:
        state.is_running = True
        thread = threading.Thread(target=pose_runner.processing_loop)
        thread.daemon = True
        thread.start()
        return jsonify({'status': 'started'})
    return jsonify({'status': 'already_running'})


@bp.route('/api/stop', methods=['POST'])
@login_required
def stop():
    state.is_running = False
    from ..services import stats_service
    stats_service.save_all()
    return jsonify({'status': 'stopped'})
