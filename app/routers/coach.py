# -*- coding: utf-8 -*-
"""
coach.py
AI 教练路由：/api/chat /api/coach/status /api/llm/config。
"""

from flask import Blueprint, request, jsonify

from .. import state
from .. import models
from ..services import coach as coach_service
from ..security import login_required, current_user, llm_config_response

bp = Blueprint('coach', __name__)


@bp.route('/api/chat', methods=['POST'])
@login_required
def chat():
    data = request.get_json() or {}
    message = (data.get('message') or '').strip()
    history = data.get('history') or []
    if not message:
        return jsonify({'success': False, 'error': '请输入问题'}), 400

    with state.lock:
        context = state.latest_analysis.get('source', '') or ''

    user_llm = None
    me = current_user()
    if me:
        try:
            from dance_coach import _is_placeholder_key
            ucfg = models.get_llm_config(me['id'])
            if ucfg and not _is_placeholder_key(ucfg.get('api_key')):
                user_llm = ucfg
        except Exception:
            user_llm = None

    answer, err = coach_service.ask(message, history, context=context, user_llm=user_llm)
    if err:
        return jsonify({'success': False, 'error': err})
    return jsonify({'success': True, 'reply': answer})


@bp.route('/api/coach/status')
@login_required
def coach_status():
    cfg = coach_service.load_global_config()
    me = current_user()
    llm = llm_config_response(me['id']) if me else {}
    return jsonify({
        'configured': coach_service.is_configured(),
        'model': cfg.get('deepseek_model', 'deepseek-chat'),
        'base_url': cfg.get('deepseek_base_url', 'https://api.deepseek.com'),
        'source': llm.get('source', 'none'),
        'source_desc': llm.get('source_desc', ''),
        'has_user_key': llm.get('has_user_key', False),
    })


@bp.route('/api/llm/config', methods=['GET', 'POST'])
@login_required
def llm_config():
    me = current_user()
    if request.method == 'GET':
        return jsonify({'success': True, **llm_config_response(me['id'])})
    data = request.get_json() or {}
    models.save_llm_config(me['id'],
                           api_key=data.get('api_key') or '',
                           base_url=data.get('base_url') or '',
                           model=data.get('model') or '')
    return jsonify({'success': True, **llm_config_response(me['id'])})
