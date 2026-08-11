# -*- coding: utf-8 -*-
"""
stats.py
训练统计路由：/api/stats /api/training/* /api/score/*。
"""

from flask import Blueprint, request, jsonify

from .. import models
from ..services import stats as stats_service
from ..security import login_required, admin_required

bp = Blueprint('stats', __name__)


@bp.route('/api/stats')
@login_required
def get_stats():
    return jsonify(stats_service.get_stats_payload())


@bp.route('/api/training/start', methods=['POST'])
@login_required
def training_start():
    return jsonify({'success': True, 'manual_active': stats_service.start_manual_session()})


@bp.route('/api/training/stop', methods=['POST'])
@login_required
def training_stop():
    return jsonify({'success': True, 'manual_active': stats_service.stop_manual_session()})


@bp.route('/api/score/record', methods=['POST'])
@login_required
def record_score():
    data = request.get_json() or {}
    score = data.get('score')
    samples = stats_service.record_score(score)
    return jsonify({'success': True, 'samples': samples})


@bp.route('/api/stats/reset', methods=['POST'])
@admin_required
def reset():
    with models.state.stats_lock:
        models.reset_stats()
    return jsonify({'success': True})
