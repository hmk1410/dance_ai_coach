# -*- coding: utf-8 -*-
"""
auth.py
认证路由（仿青就业 routers/auth.py）：/api/auth/*
"""

from flask import Blueprint, request, jsonify, session

from .. import models
from ..security import current_user, _user_public

bp = Blueprint('auth', __name__)


@bp.route('/api/auth/status')
def status():
    u = current_user()
    if not u:
        return jsonify({'logged_in': False})
    return jsonify({'logged_in': True, 'user': _user_public(u)})


@bp.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    nickname = (data.get('nickname') or '').strip()
    password = data.get('password') or ''
    if not username or not password:
        return jsonify({'success': False, 'error': '用户名和密码不能为空'}), 400
    if len(username) < 2 or len(username) > 20:
        return jsonify({'success': False, 'error': '用户名需为 2~20 个字符'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'error': '密码至少 6 位'}), 400
    if models.find_user_by_username(username):
        return jsonify({'success': False, 'error': '用户名已被注册'}), 400
    models.create_user(username, password, nickname)
    return jsonify({'success': True, 'message': '注册成功'})


@bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if not username or not password:
        return jsonify({'success': False, 'error': '用户名和密码不能为空'}), 400
    u = models.find_user_by_username(username)
    from werkzeug.security import check_password_hash
    if u is None or not check_password_hash(u['password_hash'], password):
        return jsonify({'success': False, 'error': '用户名或密码错误'}), 401
    if not u.get('is_active'):
        return jsonify({'success': False, 'error': '账号已被封禁，请联系管理员'}), 403
    session['uid'] = u['id']
    return jsonify({'success': True, 'user': _user_public(u)})


@bp.route('/api/auth/logout', methods=['POST'])
def logout():
    session.pop('uid', None)
    return jsonify({'success': True})
