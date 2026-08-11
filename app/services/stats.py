# -*- coding: utf-8 -*-
"""
stats.py
训练统计服务：会话时长、得分样本、今日/累计统计。
"""

import time

from .. import models
from .. import state


def get_stats_payload():
    """当前统计快照（供 /api/stats）"""
    with state.stats_lock:
        stats = models.load_stats()
        today = time.strftime('%Y-%m-%d')
        return {
            'total_sessions': stats['total_sessions'],
            'total_seconds': round(stats['total_seconds'], 1),
            'today_seconds': round(stats['daily_seconds'].get(today, 0.0), 1),
            'today_sessions': stats['daily_sessions'].get(today, 0),
            'today': today,
            'session_scores': stats.get('session_scores', []),
            'manual_active': state._manual_active,
            'manual_paused': state._manual_paused,
            'manual_elapsed': _elapsed_seconds()
        }


def _elapsed_seconds():
    """当前会话已计时秒数（暂停时冻结）"""
    if not state._manual_active or state._manual_start is None:
        return 0.0
    if state._manual_paused:
        if state._paused_at is not None:
            return round(state._paused_at - state._manual_start, 1)
        return 0.0
    return round(time.time() - state._manual_start, 1)


def start_manual_session():
    """手动开始一次训练：计一次会话并开始计时"""
    with state.stats_lock:
        if not state._manual_active:
            state._manual_active = True
            state._manual_start = time.time()
            state._manual_paused = False
            state._paused_at = None
            state._session_score_samples = []
            stats = models.load_stats()
            today = time.strftime('%Y-%m-%d')
            stats['total_sessions'] += 1
            stats['daily_sessions'][today] = stats['daily_sessions'].get(today, 0) + 1
            models.save_stats()
    return state._manual_active


def pause_manual_session():
    """暂停训练：冻结计时，等待继续"""
    with state.stats_lock:
        if state._manual_active and not state._manual_paused:
            state._paused_at = time.time()
            state._manual_paused = True
    return state._manual_active


def resume_manual_session():
    """继续训练：把暂停时间从计时中排除"""
    with state.stats_lock:
        if state._manual_active and state._manual_paused:
            if state._paused_at is not None:
                state._manual_start += time.time() - state._paused_at
            state._paused_at = None
            state._manual_paused = False
    return state._manual_active


def stop_manual_session():
    """手动结束训练：把时长计入累计并记录平均得分"""
    with state.stats_lock:
        if state._manual_active and state._manual_start is not None:
            elapsed = _elapsed_seconds()
            stats = models.load_stats()
            today = time.strftime('%Y-%m-%d')
            stats['total_seconds'] += elapsed
            stats['daily_seconds'][today] = stats['daily_seconds'].get(today, 0.0) + elapsed

            if state._session_score_samples:
                avg_score = round(sum(state._session_score_samples) / len(state._session_score_samples), 1)
            else:
                avg_score = 0
            stats['session_scores'].append({
                'date': today,
                'avg_score': avg_score,
                'duration': round(elapsed, 1)
            })
            if len(stats['session_scores']) > 60:
                stats['session_scores'] = stats['session_scores'][-60:]

            state._manual_active = False
            state._manual_start = None
            state._manual_paused = False
            state._paused_at = None
            state._session_score_samples = []
            models.save_stats()
    return state._manual_active


def record_score(score):
    """手动训练期间记录分数样本，返回当前样本数（暂停时不记录）"""
    if score is None:
        return len(state._session_score_samples)
    if state._manual_active and not state._manual_paused:
        with state.stats_lock:
            state._session_score_samples.append(float(score))
    return len(state._session_score_samples)


def admin_dashboard():
    """管理员数据看板统计"""
    stats = models.load_stats()
    session_scores = stats.get('session_scores', [])
    daily = {}
    for s in session_scores:
        d = s.get('date', '')
        daily[d] = daily.get(d, 0) + 1
    return {
        'users': models.count_users(),
        'videos': len(models.load_video_library()),
        'total_sessions': stats.get('total_sessions', 0),
        'total_seconds': round(stats.get('total_seconds', 0.0), 1),
        'avg_score': round(sum(s.get('avg_score', 0) for s in session_scores) / len(session_scores), 1) if session_scores else 0,
        'daily_trend': daily,
    }
