# -*- coding: utf-8 -*-
"""
admin.py
后台管理路由：/admin 页面 + /api/admin/*
"""

from flask import Blueprint, render_template, request, jsonify

from .. import models
from ..services import stats as stats_service
from ..security import admin_required, current_user

bp = Blueprint('pages', __name__)


@bp.route('/')
def index():
    """主页面"""
    return render_template('index.html')


@bp.route('/admin')
def admin_page():
    return render_template('admin.html')


@bp.route('/api/admin/users')
@admin_required
def list_users():
    users = []
    try:
        for u in models.list_users():
            users.append({
                'id': u['id'],
                'username': u['username'],
                'nickname': u['nickname'],
                'is_admin': bool(u['is_admin']),
                'is_active': bool(u['is_active']),
                'created_at': u['created_at'],
            })
    except Exception:
        pass
    return jsonify({'success': True, 'users': users})


@bp.route('/api/admin/users/<int:uid>', methods=['PATCH'])
@admin_required
def patch_user(uid):
    data = request.get_json() or {}
    is_active = data.get('is_active') if 'is_active' in data else None
    is_admin = data.get('is_admin') if 'is_admin' in data else None
    ok, err = models.patch_user(uid, is_active=is_active, is_admin=is_admin)
    if not ok:
        return jsonify({'success': False, 'error': err}), 400
    return jsonify({'success': True})


@bp.route('/api/admin/stats')
@admin_required
def admin_stats():
    return jsonify({'success': True, 'stats': stats_service.admin_dashboard()})
