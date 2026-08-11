# -*- coding: utf-8 -*-
"""
用户认证模块：注册 / 登录 / 登出 + 管理员管理

- 存储：SQLite（标准库 sqlite3，无额外依赖）
- 密码：werkzeug.security 的 PBKDF2 哈希
- 会话：Flask 签名 session cookie
"""

import os
import sqlite3
import time
import base64
import hashlib

from werkzeug.security import generate_password_hash, check_password_hash
from flask import session, request, jsonify
from functools import wraps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'users.db')

# 与 app.secret_key 保持一致，用于派生 LLM Key 加密密钥
# （XOR + base64，非强加密，仅防数据库泄露时 Key 被直接读出）
_APP_SECRET = os.environ.get('DANCE_SECRET', 'dance-coach-secret-2026-verify-works-001')


def _key_stream():
    return hashlib.sha256(_APP_SECRET.encode('utf-8')).digest()


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

# ========== 数据库基础 ==========

def _connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                nickname TEXT DEFAULT '',
                is_admin INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                llm_api_key TEXT DEFAULT '',
                llm_base_url TEXT DEFAULT '',
                llm_model TEXT DEFAULT '',
                created_at REAL NOT NULL
            )
        """)
        # 兼容旧库：补齐缺失的 LLM 配置列
        cols = {r[1] for r in conn.execute('PRAGMA table_info(users)')}
        for col, ddl in [
            ('llm_api_key', 'TEXT DEFAULT \'\''),
            ('llm_base_url', 'TEXT DEFAULT \'\''),
            ('llm_model', 'TEXT DEFAULT \'\''),
        ]:
            if col not in cols:
                conn.execute(f'ALTER TABLE users ADD COLUMN {col} {ddl}')
    _seed_admin()


def _seed_admin():
    """首个注册用户自动成为管理员；若无任何用户则创建默认管理员"""
    with _connect() as conn:
        count = conn.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']
        if count == 0:
            conn.execute(
                'INSERT INTO users (username, password_hash, is_admin, is_active, created_at) VALUES (?,?,?,?,?)',
                ('admin', generate_password_hash('admin123'), 1, 1, time.time())
            )


def init_auth():
    """初始化（启动时调用）"""
    _ensure_tables()


# ========== 鉴权工具 ==========

def current_user():
    """返回当前登录用户（dict）或 None"""
    uid = session.get('uid')
    if not uid:
        return None
    with _connect() as conn:
        row = conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
        if row is None:
            return None
        return dict(row)


def current_is_admin():
    u = current_user()
    return bool(u and u.get('is_admin'))


def login_required(f):
    """需要登录的接口装饰器"""
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
    """需要管理员权限的接口装饰器"""
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


# ========== 业务逻辑 ==========

def register(username, password, nickname=''):
    """注册。返回 (success, message 或 user)"""
    username = (username or '').strip()
    nickname = (nickname or '').strip()
    if not username or not password:
        return False, '用户名和密码不能为空'
    if len(username) < 2 or len(username) > 20:
        return False, '用户名需为 2~20 个字符'
    if len(password) < 6:
        return False, '密码至少 6 位'

    with _connect() as conn:
        exists = conn.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()
        if exists:
            return False, '用户名已被注册'
        # 首个普通注册：若库里只有种子 admin，则第一个真实注册者成为管理员
        first = conn.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c'] == 0
        conn.execute(
            'INSERT INTO users (username, password_hash, nickname, is_admin, is_active, created_at) VALUES (?,?,?,?,?,?)',
            (username, generate_password_hash(password), nickname, 1 if first else 0, 1, time.time())
        )
    return True, '注册成功'


def login(username, password):
    """登录。返回 (success, message 或 user)"""
    username = (username or '').strip()
    if not username or not password:
        return False, '用户名和密码不能为空'
    with _connect() as conn:
        row = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if row is None:
            return False, '用户名或密码错误'
        u = dict(row)
    if not check_password_hash(u['password_hash'], password):
        return False, '用户名或密码错误'
    if not u.get('is_active'):
        return False, '账号已被封禁，请联系管理员'
    return True, u


def logout():
    session.pop('uid', None)


# ========== 用户 LLM 配置 ==========

def get_llm_config(uid):
    """读取用户自己的 LLM 配置。返回 dict(api_key/base_url/model)"""
    with _connect() as conn:
        row = conn.execute(
            'SELECT llm_api_key, llm_base_url, llm_model FROM users WHERE id=?', (uid,)
        ).fetchone()
    if row is None:
        return {'api_key': '', 'base_url': '', 'model': ''}
    return {
        'api_key': decrypt_secret(row['llm_api_key']),
        'base_url': row['llm_base_url'],
        'model': row['llm_model'],
    }


def save_llm_config(uid, api_key='', base_url='', model=''):
    """保存用户 LLM 配置。api_key 加密存储；传空串表示清除用户 Key。"""
    with _connect() as conn:
        conn.execute(
            'UPDATE users SET llm_api_key=?, llm_base_url=?, llm_model=? WHERE id=?',
            (encrypt_secret((api_key or '').strip()), (base_url or '').strip(),
             (model or '').strip(), uid)
        )
        conn.commit()


def _mask_key(key):
    """API Key 脱敏：只显示后 4 位"""
    key = (key or '').strip()
    if len(key) <= 8:
        return '*' * len(key)
    return '*' * (len(key) - 4) + key[-4:]


def llm_config_response(uid):
    """
    仿青就业：返回前端展示的 LLM 配置状态。
    source 标明当前生效来源：user（用户Key）/ global（config.json）/ none（无，走内置引擎）
    """
    cfg = get_llm_config(uid)
    has_user_key = bool(cfg['api_key'])
    if has_user_key:
        source, source_desc = 'user', '用户自己的 Key（当前生效）'
    else:
        try:
            from dance_coach import load_config as _dc_load
            g = _dc_load()
            if g.get('deepseek_api_key'):
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


def _user_public(u):
    """去除敏感字段，返回前端可用数据"""
    return {
        'id': u['id'],
        'username': u['username'],
        'nickname': u['nickname'],
        'is_admin': bool(u['is_admin']),
        'is_active': bool(u['is_active']),
        'created_at': u['created_at'],
    }
