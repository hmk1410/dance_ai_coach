# -*- coding: utf-8 -*-
"""
state.py
全局运行时状态：为保证 Flask 蓝图间共享摄像头/分析器/统计，
需要统一的单例容器，避免循环导入。
"""

import threading
import time

from pose_analyzer import PoseAnalyzer

# ========== 摄像头 / 姿态分析 ==========
camera = None                 # 摄像头对象
analyzer = PoseAnalyzer()     # 姿态分析器（全局单例）
is_running = False            # 是否正在运行
current_frame = None          # 当前帧（用于视频流）
lock = threading.Lock()       # 线程锁
video_extract_lock = threading.Lock()  # 视频标准提取锁

# 视频标准缓存：filename -> metrics
video_standard_cache = {}

# 分析结果缓存（供前端获取）
latest_analysis = {
    'score': 0,
    'feedback': [],
    'source': '未选择视频标准',
    'timestamp': 0
}

# ========== 训练统计（持久化） ==========
stats_lock = threading.Lock()
_training_stats = None
_manual_active = False        # 手动训练会话是否开启
_manual_start = None          # 手动训练开始时间
_session_score_samples = []   # 手动训练期间累积的分数样本


def default_stats():
    return {
        'total_sessions': 0, 'total_seconds': 0.0,
        'daily_seconds': {}, 'daily_sessions': {}, 'session_scores': []
    }
