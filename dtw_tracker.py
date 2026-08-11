# -*- coding: utf-8 -*-
"""
dtw_tracker.py
时序姿态对齐：从标准视频提取"标准姿态序列"，实时把用户的动作序列与标准序列
做动态时间规整（DTW）对齐，输出跟练进度与相似度评分。

适用场景：广播体操等连贯动作。无需人工定义角度标准——标准视频本身就是标准，
系统自动学习其中的姿态变化节奏，允许用户动作稍快或稍慢。
"""

import cv2
import numpy as np

import mediapipe as mp

# ========== 关键点归一化 ==========

def normalize_pose(landmarks):
    """33 个关键点 -> 66 维向量（x,y 归一化）。

    以髋中点为原点、肩宽为尺度，消除人物大小与画面位置的影响。
    landmarks: MediaPipe NormalizedLandmarkList 的 .landmark 列表
    """
    pts = np.array([[lm.x, lm.y] for lm in landmarks], dtype=np.float64)
    hip_mid = (pts[23] + pts[24]) / 2.0
    shoulder_w = float(np.linalg.norm(pts[11] - pts[12]))
    if shoulder_w < 1e-6:
        shoulder_w = 1.0
    return ((pts - hip_mid) / shoulder_w).flatten()


JOINT_NAMES = {
    0: '头部', 7: '左耳', 8: '右耳',
    11: '左肩', 12: '右肩',
    13: '左肘', 14: '右肘',
    15: '左腕', 16: '右腕',
    23: '左髋', 24: '右髋',
    25: '左膝', 26: '右膝',
    27: '左踝', 28: '右踝',
}


# ========== 从标准视频提取标准姿态序列 ==========

def extract_standard_sequence(video_path, target_len=60):
    """从视频提取标准姿态序列（归一化向量列表）。

    返回 list[np.ndarray]（每项 66 维），失败返回 None。
    采样策略：逐帧检测取到目标数量的 4 倍，再均匀下采样到 target_len，
    覆盖完整动作节奏。
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None

    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(static_image_mode=True, model_complexity=1,
                        min_detection_confidence=0.3)

    vectors = []
    frame_count = 0
    while len(vectors) < target_len * 4:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_count % 3 != 0:
            frame_count += 1
            continue
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)
        if results.pose_landmarks:
            try:
                vectors.append(normalize_pose(results.pose_landmarks.landmark))
            except Exception:
                pass
        frame_count += 1

    cap.release()
    pose.close()

    if len(vectors) < 3:
        return None

    if len(vectors) > target_len:
        idx = np.linspace(0, len(vectors) - 1, target_len).astype(int)
        vectors = [vectors[i] for i in idx]
    return vectors


# ========== 在线 DTW 对齐器 ==========

class OnlineDtwMatcher:
    """在线 DTW：维护用户滑动缓冲，与标准序列对齐，输出进度与评分。"""

    def __init__(self, standard_seq, window=None):
        self.S = np.asarray(standard_seq, dtype=np.float64)  # (L, D)
        self.L = len(self.S)
        self.window = window or max(20, self.L)
        self.buffer = []
        self.current_score = 0
        self.current_index = 0
        self.last_feedback = []

    def reset(self):
        self.buffer = []
        self.current_score = 0
        self.current_index = 0
        self.last_feedback = []

    def update(self, vec):
        """送入用户最新一帧的归一化向量，执行对齐并更新评分/进度。"""
        self.buffer.append(np.asarray(vec, dtype=np.float64))
        if len(self.buffer) > self.window:
            self.buffer.pop(0)
        self._align()
        return self.current_score

    def _align(self):
        B = self.buffer
        if len(B) < 3:
            self.current_score = 0
            self.current_index = 0
            return

        Bm = np.asarray(B)                                   # (n, D)
        diff = Bm[:, None, :] - self.S[None, :, :]
        d = np.sqrt((diff ** 2).sum(axis=2))                 # (n, L) 距离矩阵

        n, m = d.shape
        cost = np.full((n, m), np.inf)
        cost[0, 0] = d[0, 0]
        for i in range(1, n):
            cost[i, 0] = cost[i - 1, 0] + d[i, 0]
        for j in range(1, m):
            cost[0, j] = cost[0, j - 1] + d[0, j]
        for i in range(1, n):
            ci = cost[i]
            cp = cost[i - 1]
            di = d[i]
            for j in range(1, m):
                ci[j] = di[j] + min(cp[j], ci[j - 1], cp[j - 1])

        # 平均对齐距离 -> 0~100 分
        avg = cost[n - 1, m - 1] / (n + m - 1)
        score = max(0.0, min(100.0, (2.0 - avg) / 2.0 * 100.0))
        self.current_score = round(score, 1)

        # 进度：用户最新一帧在标准序列中的最佳位置
        self.current_index = int(np.argmin(cost[n - 1]))

        self._build_feedback()

    def _build_feedback(self):
        i = len(self.buffer) - 1
        j = self.current_index
        u = self.buffer[i]
        s = self.S[j]
        dev = np.abs(u - s).reshape(-1, 2).max(axis=1)       # 每个关键点偏差
        order = np.argsort(dev)[::-1][:4]
        items = []
        for k in order:
            name = JOINT_NAMES.get(k, '关键点{0}'.format(k))
            level = 'good' if dev[k] < 0.3 else 'warning' if dev[k] < 0.6 else 'error'
            items.append({
                'name': name,
                'actual': round(float(dev[k]), 2),
                'standard': 0.0,
                'deviation': round(float(dev[k]), 2),
                'level': level,
                'unit': '偏差'
            })
        self.last_feedback = items
