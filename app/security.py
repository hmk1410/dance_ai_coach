# -*- coding: utf-8 -*-
"""
security.py
认证与安全（仿青就业 security.py）：
登录装饰器、密码哈希、LLM Key 加解密。
"""

import base64
import hashlib
from functools import wraps

from flask import session, jsonify

from . import config
from . import models


def _key_stream():
    return hashlib.sha256(config.get_secret_key().encode('utf-8')).digest()


def encrypt_secret(plaintext):
    """加密用户 LLM API Key（XOR + base64）"""
    if not plaintext:
        return ''
    ks = _key_stream()
    data = plaintext.encode('utf-8')
    out = bytes(b ^ ks[i % len(ks)] for i, b in enumerate(data))
    return base64.b64encode(out).decode('utf-8')


def decrypt_secret(ciphertext):
    """解密用户 LLM API Key。解析失败或空串返回 ''"""
    if not ciphertext:
        return ''
    try:
        ks = _key_stream()
        data = base64.b64decode(ciphertext.encode('utf-8'))
        out = bytes(b ^ ks[i % len(ks)] for i, b in enumerate(data))
        return out.decode('utf-8')
    except Exception:
        return ''


def current_user():
    """返回当前登录用户（dict）或 None"""
    uid = session.get('uid')
    if not uid:
        return None
    return models.find_user_by_id(uid)


def current_is_admin():
    u = current_user()
    return bool(u and u.get('is_admin'))


def _user_public(u):
    return {
        'id': u['id'],
        'username': u['username'],
        'nickname': u['nickname'],
        'is_admin': bool(u['is_admin']),
        'is_active': bool(u['is_active']),
        'created_at': u['created_at'],
    }


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        u = current_user()
        if not u:
            return jsonify({'success': False, 'error': '未登录'}), 401
        if not u.get('is_active'):
            return jsonify({'success': False, 'error': '账号已被封禁'}), 403
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        u = current_user()
        if not u:
            return jsonify({'success': False, 'error': '未登录'}), 401
        if not u.get('is_active'):
            return jsonify({'success': False, 'error': '账号已被封禁'}), 403
        if not u.get('is_admin'):
            return jsonify({'success': False, 'error': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return wrapper


def llm_config_response(uid):
    """仿青就业：返回前端展示的 LLM 配置状态（source: user/global/none）"""
    cfg = models.get_llm_config(uid)
    has_user_key = bool(cfg['api_key'])
    if has_user_key:
        source, source_desc = 'user', '用户自己的 Key（当前生效）'
    else:
        try:
            from .services.coach import load_global_config
            if load_global_config().get('deepseek_api_key'):
                source, source_desc = 'global', 'config.json 全局配置（当前生效）'
            else:
                source, source_desc = 'none', '未配置 API Key，使用内置免费答疑引擎'
        except Exception:
            source, source_desc = 'none', '未配置 API Key，使用内置免费答疑引擎'
    return {
        'has_user_key': has_user_key,
        'api_key_masked': _mask_key(cfg['api_key']),
        'base_url': cfg['base_url'],
        'model': cfg['model'],
        'source': source,
        'source_desc': source_desc,
    }


def _mask_key(key):
    key = (key or '').strip()
    if len(key) <= 8:
        return '*' * len(key)
    return '*' * (len(key) - 4) + key[-4:]
