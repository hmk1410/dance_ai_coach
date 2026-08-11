# -*- coding: utf-8 -*-
"""
models.py
数据访问层：
视频库扫描、训练统计、SQLite 用户相关查询。
"""

import os
import json
import time
import sqlite3

from werkzeug.security import generate_password_hash, check_password_hash

from . import config
from . import state


# ========== 视频库 ==========

def load_video_library():
    """自动扫描 vidoe 目录，构建视频库（可配合 videos_meta.json 补充元数据）"""
    meta = {}
    if os.path.exists(config.META_FILE):
        try:
            with open(config.META_FILE, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        except Exception:
            meta = {}

    videos = []
    if os.path.isdir(config.VIDEO_DIR):
        for fn in sorted(os.listdir(config.VIDEO_DIR)):
            if fn.lower().endswith(config.VIDEO_EXTS):
                name = os.path.splitext(fn)[0]
                m = meta.get(fn, {})
                videos.append({
                    'id': name,
                    'title': m.get('title', name),
                    'category': m.get('category', '未分类'),
                    'tags': m.get('tags', []),
                    'filename': fn,
                    'size': os.path.getsize(os.path.join(config.VIDEO_DIR, fn)),
                })
    return videos


def find_video(video_id):
    return next((v for v in load_video_library() if v['id'] == video_id), None)


def save_video_meta(filename, entry):
    """合并写入 videos_meta.json 中某视频的元数据"""
    meta = {}
    if os.path.exists(config.META_FILE):
        try:
            with open(config.META_FILE, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        except Exception:
            meta = {}
    if entry:
        meta[filename] = entry
    try:
        with open(config.META_FILE, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def remove_video_meta(filename):
    meta = {}
    if os.path.exists(config.META_FILE):
        try:
            with open(config.META_FILE, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        except Exception:
            meta = {}
    meta.pop(filename, None)
    try:
        with open(config.META_FILE, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ========== 训练统计 ==========

def load_stats():
    """读取训练统计（内存缓存 + 文件回退）"""
    if state._training_stats is None:
        try:
            with open(config.STATS_FILE, 'r', encoding='utf-8') as f:
                state._training_stats = json.load(f)
        except Exception:
            state._training_stats = {}
        s = state.default_stats()
        for k in s:
            state._training_stats.setdefault(k, s[k])
    return state._training_stats


def save_stats():
    """将训练统计写盘"""
    try:
        with open(config.STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(state._training_stats, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def reset_stats():
    """清零全部训练统计（同时结束手动会话）"""
    state._training_stats = state.default_stats()
    state._manual_active = False
    state._manual_start = None
    state._session_score_samples = []
    save_stats()


# ========== 用户（SQLite） ==========

def _connect_users():
    conn = sqlite3.connect(config.BASE_DIR + os.sep + 'users.db')
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables():
    with _connect_users() as conn:
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
        cols = {r[1] for r in conn.execute('PRAGMA table_info(users)')}
        for col, ddl in [
            ('llm_api_key', 'TEXT DEFAULT \'\''),
            ('llm_base_url', 'TEXT DEFAULT \'\''),
            ('llm_model', 'TEXT DEFAULT \'\''),
        ]:
            if col not in cols:
                conn.execute('ALTER TABLE users ADD COLUMN {0} {1}'.format(col, ddl))
    _seed_admin()


def _seed_admin():
    with _connect_users() as conn:
        count = conn.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']
        if count == 0:
            conn.execute(
                'INSERT INTO users (username, password_hash, is_admin, is_active, created_at) VALUES (?,?,?,?,?)',
                ('admin', generate_password_hash('admin123'), 1, 1, time.time())
            )


def find_user_by_username(username):
    with _connect_users() as conn:
        row = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
    return dict(row) if row else None


def find_user_by_id(uid):
    with _connect_users() as conn:
        row = conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
    return dict(row) if row else None


def create_user(username, password, nickname=''):
    with _connect_users() as conn:
        first = conn.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c'] == 0
        conn.execute(
            'INSERT INTO users (username, password_hash, nickname, is_admin, is_active, created_at) VALUES (?,?,?,?,?,?)',
            (username, generate_password_hash(password), nickname, 1 if first else 0, 1, time.time())
        )
        conn.commit()


def list_users():
    with _connect_users() as conn:
        rows = conn.execute('SELECT * FROM users ORDER BY id').fetchall()
    return [dict(r) for r in rows]


def patch_user(uid, is_active=None, is_admin=None):
    """返回 (ok, error 或 None)。含自我保护逻辑。"""
    me = None
    with _connect_users() as conn:
        row = conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
        if row is None:
            return False, '用户不存在'
        target = dict(row)
        me = target
        if is_active is not None and uid == me['id'] and not is_active:
            return False, '不能封禁自己'
        if is_admin is not None:
            if uid == me['id'] and not is_admin:
                other = conn.execute(
                    'SELECT COUNT(*) FROM users WHERE is_admin=1 AND is_active=1 AND id<>?', (uid,)
                ).fetchone()[0]
                if other == 0:
                    return False, '不能取消自己管理员权限，至少保留一名管理员'
        if is_active is not None:
            conn.execute('UPDATE users SET is_active=? WHERE id=?', (1 if is_active else 0, uid))
        if is_admin is not None:
            conn.execute('UPDATE users SET is_admin=? WHERE id=?', (1 if is_admin else 0, uid))
        conn.commit()
    return True, None


def count_users():
    try:
        with _connect_users() as conn:
            return conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    except Exception:
        return 0


def get_llm_config(uid):
    row = None
    with _connect_users() as conn:
        row = conn.execute(
            'SELECT llm_api_key, llm_base_url, llm_model FROM users WHERE id=?', (uid,)
        ).fetchone()
    if row is None:
        return {'api_key': '', 'base_url': '', 'model': ''}
    from .security import decrypt_secret
    return {
        'api_key': decrypt_secret(row['llm_api_key']),
        'base_url': row['llm_base_url'],
        'model': row['llm_model'],
    }


def save_llm_config(uid, api_key='', base_url='', model=''):
    from .security import encrypt_secret
    with _connect_users() as conn:
        conn.execute(
            'UPDATE users SET llm_api_key=?, llm_base_url=?, llm_model=? WHERE id=?',
            (encrypt_secret((api_key or '').strip()), (base_url or '').strip(),
             (model or '').strip(), uid)
        )
        conn.commit()
